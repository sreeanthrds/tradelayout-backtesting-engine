"""
Dynamic Option Subscriber for Backtesting

Dynamically subscribes to option strikes based on spot price:
- Calculates ATM from first NIFTY tick
- Subscribes to ITM1-ITM16 and OTM1-OTM16
- Re-subscribes when spot moves and ATM changes
- Only loads needed strikes, not all contracts
"""

from typing import List, Dict, Set, Optional
from datetime import datetime
import clickhouse_connect

from src.utils.logger import log_info, log_debug, log_warning
from src.config.clickhouse_config import ClickHouseConfig


class DynamicOptionSubscriber:
    """
    Manages dynamic option subscription based on spot price.
    
    Features:
    - ATM calculation from spot price
    - ITM1-ITM16 and OTM1-OTM16 strike selection
    - Dynamic re-subscription on spot movement
    - Efficient loading (only needed strikes)
    """
    
    def __init__(
        self,
        underlying: str = "NIFTY",
        expiries: List[str] = None,
        itm_depth: int = 16,
        otm_depth: int = 16,
        clickhouse_config: ClickHouseConfig = None
    ):
        """
        Initialize dynamic option subscriber.
        
        Args:
            underlying: Underlying symbol (NIFTY, BANKNIFTY)
            expiries: List of expiries to subscribe (YYYY-MM-DD format)
            itm_depth: Number of ITM strikes to subscribe
            otm_depth: Number of OTM strikes to subscribe
            clickhouse_config: ClickHouse configuration
        """
        self.underlying = underlying
        self.expiries = expiries or []
        self.itm_depth = itm_depth
        self.otm_depth = otm_depth
        self.config = clickhouse_config or ClickHouseConfig()
        
        # Current state
        self.current_spot = None
        self.current_atm = None
        self.subscribed_strikes: Set[int] = set()
        
        # Strike interval (50 for NIFTY, 100 for BANKNIFTY)
        self.strike_interval = 50 if underlying == "NIFTY" else 100
        
        # ClickHouse client
        self.client = None
        
        log_info(f"📊 Dynamic Option Subscriber initialized")
        log_info(f"   Underlying: {underlying}")
        log_info(f"   ITM Depth: {itm_depth}, OTM Depth: {otm_depth}")
        log_info(f"   Strike Interval: {self.strike_interval}")
    
    def calculate_atm(self, spot_price: float) -> int:
        """
        Calculate ATM strike from spot price.
        
        Args:
            spot_price: Current spot price
            
        Returns:
            ATM strike price
        """
        # Round to nearest strike interval
        atm = round(spot_price / self.strike_interval) * self.strike_interval
        return int(atm)
    
    def get_required_strikes(self, atm_strike: int) -> List[int]:
        """
        Get list of required strikes based on ATM.
        
        Args:
            atm_strike: ATM strike price
            
        Returns:
            List of strike prices (ITM1-ITM16, ATM, OTM1-OTM16)
        """
        strikes = []
        
        # ITM strikes (below ATM for CE, above ATM for PE)
        for i in range(1, self.itm_depth + 1):
            itm_strike = atm_strike - (i * self.strike_interval)
            if itm_strike > 0:
                strikes.append(itm_strike)
        
        # ATM strike
        strikes.append(atm_strike)
        
        # OTM strikes (above ATM for CE, below ATM for PE)
        for i in range(1, self.otm_depth + 1):
            otm_strike = atm_strike + (i * self.strike_interval)
            strikes.append(otm_strike)
        
        return sorted(strikes)
    
    def update_subscription(self, spot_price: float) -> Dict[str, any]:
        """
        Update option subscription based on current spot price.
        
        Args:
            spot_price: Current spot price
            
        Returns:
            Dict with subscription update info
        """
        # Calculate new ATM
        new_atm = self.calculate_atm(spot_price)
        
        # Check if ATM changed
        if new_atm == self.current_atm:
            return {
                'changed': False,
                'atm': new_atm,
                'spot': spot_price,
                'strikes': list(self.subscribed_strikes)
            }
        
        # ATM changed - update subscription
        old_atm = self.current_atm
        self.current_spot = spot_price
        self.current_atm = new_atm
        
        # Get new required strikes
        new_strikes = set(self.get_required_strikes(new_atm))
        
        # Calculate changes
        added_strikes = new_strikes - self.subscribed_strikes
        removed_strikes = self.subscribed_strikes - new_strikes
        
        # Update subscribed strikes
        self.subscribed_strikes = new_strikes
        
        log_info(f"🔄 ATM changed: {old_atm} → {new_atm} (Spot: {spot_price:.2f})")
        log_info(f"   Added {len(added_strikes)} strikes, Removed {len(removed_strikes)} strikes")
        log_info(f"   Total subscribed: {len(self.subscribed_strikes)} strikes × {len(self.expiries)} expiries")
        
        return {
            'changed': True,
            'old_atm': old_atm,
            'new_atm': new_atm,
            'spot': spot_price,
            'added_strikes': list(added_strikes),
            'removed_strikes': list(removed_strikes),
            'total_strikes': list(self.subscribed_strikes)
        }
    
    def get_option_symbols(self, expiry_date: str) -> List[str]:
        """
        Get option symbols for subscribed strikes and expiry.
        
        Args:
            expiry_date: Expiry date (YYYY-MM-DD)
            
        Returns:
            List of option symbols in ClickHouse format
        """
        if not self.subscribed_strikes:
            return []
        
        symbols = []
        
        # Format expiry for symbol (e.g., 2024-10-03 → 03OCT24)
        dt = datetime.strptime(expiry_date, '%Y-%m-%d')
        expiry_str = dt.strftime('%d%b%y').upper()
        
        for strike in self.subscribed_strikes:
            # Call option
            ce_symbol = f"{self.underlying}{expiry_str}{strike}CE.NFO"
            symbols.append(ce_symbol)
            
            # Put option
            pe_symbol = f"{self.underlying}{expiry_str}{strike}PE.NFO"
            symbols.append(pe_symbol)
        
        return symbols
    
    def get_all_option_symbols(self) -> List[str]:
        """
        Get all option symbols for all expiries.
        
        Returns:
            List of all option symbols
        """
        all_symbols = []
        
        for expiry in self.expiries:
            symbols = self.get_option_symbols(expiry)
            all_symbols.extend(symbols)
        
        return all_symbols
    
    def load_option_ticks(
        self,
        backtest_date: str,
        client: clickhouse_connect.driver.Client
    ) -> List[Dict]:
        """
        Load option ticks for subscribed strikes from ClickHouse.
        
        Args:
            backtest_date: Date to load ticks for (YYYY-MM-DD)
            client: ClickHouse client
            
        Returns:
            List of tick dictionaries
        """
        if not self.subscribed_strikes:
            log_warning("⚠️  No strikes subscribed, skipping option tick load")
            return []
        
        # Get all option symbols
        symbols = self.get_all_option_symbols()
        
        if not symbols:
            return []
        
        log_info(f"📥 Loading option ticks for {len(symbols)} symbols...")
        log_info(f"   Strikes: {len(self.subscribed_strikes)} × {len(self.expiries)} expiries × 2 (CE/PE)")
        
        # Build query with symbol filter
        symbols_str = "', '".join(symbols)
        query = f"""
            SELECT 
                ticker,
                timestamp,
                ltp,
                volume,
                oi
            FROM nse_ticks_options
            WHERE trading_day = '{backtest_date}'
              AND ticker IN ('{symbols_str}')
            ORDER BY timestamp ASC
        """
        
        result = client.query(query)
        
        ticks = []
        for row in result.result_rows:
            tick = {
                'symbol': row[0],
                'timestamp': row[1],
                'ltp': row[2],
                'volume': row[3],
                'oi': row[4]
            }
            ticks.append(tick)
        
        log_info(f"✅ Loaded {len(ticks):,} option ticks")
        
        return ticks
    
    def get_subscription_summary(self) -> Dict:
        """
        Get summary of current subscription.
        
        Returns:
            Summary dictionary
        """
        return {
            'underlying': self.underlying,
            'spot': self.current_spot,
            'atm': self.current_atm,
            'strike_interval': self.strike_interval,
            'itm_depth': self.itm_depth,
            'otm_depth': self.otm_depth,
            'subscribed_strikes': sorted(list(self.subscribed_strikes)),
            'total_strikes': len(self.subscribed_strikes),
            'expiries': self.expiries,
            'total_symbols': len(self.get_all_option_symbols())
        }
