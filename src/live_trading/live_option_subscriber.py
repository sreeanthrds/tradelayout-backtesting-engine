"""
Live Trading Option Subscriber

Manages dynamic option subscription for live trading based on spot price.
Uses first NIFTY tick at 09:15 to calculate ATM and subscribe to ITM/OTM strikes.

Features:
- Waits for first NIFTY tick at market open (09:15)
- Calculates ATM strike from spot price
- Subscribes to ITM1-16, ATM, OTM1-16 for all available expiries
- Dynamic re-subscription when ATM changes
- Integrates with SmartSubscriptionManager for WebSocket
"""

from typing import List, Dict, Optional, Set
from datetime import datetime, date
from src.utils.logger import log_info, log_warning, log_error


class LiveOptionSubscriber:
    """
    Manages dynamic option subscription for live trading.
    
    Workflow:
    1. Wait for first NIFTY tick at 09:15
    2. Calculate ATM from spot price
    3. Subscribe to ITM1-16, ATM, OTM1-16 strikes
    4. For all available expiries
    5. Re-subscribe when ATM changes
    """
    
    def __init__(
        self,
        underlying: str,
        subscription_manager,
        ltp_store,
        strike_interval: int = 50,
        itm_depth: int = 16,
        otm_depth: int = 16
    ):
        """
        Initialize live option subscriber.
        
        Args:
            underlying: Underlying symbol (e.g., 'NIFTY')
            subscription_manager: SmartSubscriptionManager instance
            ltp_store: InstrumentLTPStore instance
            strike_interval: Strike interval (50 for NIFTY, 100 for BANKNIFTY)
            itm_depth: Number of ITM strikes to subscribe (default: 16)
            otm_depth: Number of OTM strikes to subscribe (default: 16)
        """
        self.underlying = underlying
        self.subscription_manager = subscription_manager
        self.ltp_store = ltp_store
        self.strike_interval = strike_interval
        self.itm_depth = itm_depth
        self.otm_depth = otm_depth
        
        # State
        self.first_tick_received = False
        self.current_spot = None
        self.current_atm = None
        self.subscribed_strikes: Set[int] = set()
        self.available_expiries: List[date] = []
        
        log_info(f"📡 Live Option Subscriber initialized for {underlying}")
        log_info(f"   Strike Interval: {strike_interval}")
        log_info(f"   ITM Depth: {itm_depth}, OTM Depth: {otm_depth}")
    
    def set_available_expiries(self, expiries: List[date]):
        """
        Set available expiries for the trading day.
        
        Args:
            expiries: List of expiry dates
        """
        self.available_expiries = expiries
        log_info(f"📅 Set {len(expiries)} available expiries for {self.underlying}")
    
    def on_tick(self, symbol: str, ltp: float, timestamp: datetime = None) -> Dict:
        """
        Process tick and manage option subscriptions.
        
        Call this for every NIFTY tick received from WebSocket.
        
        Args:
            symbol: Symbol name (should be NIFTY)
            ltp: Last traded price
            timestamp: Tick timestamp (optional)
            
        Returns:
            Dict with subscription update info
        """
        if symbol != self.underlying:
            return {'changed': False}
        
        # Check if market hours (09:15 onwards)
        if timestamp:
            hour = timestamp.hour
            minute = timestamp.minute
            
            # Before 09:15 - ignore
            if hour < 9 or (hour == 9 and minute < 15):
                return {'changed': False}
            
            # After 15:30 - ignore
            if hour > 15 or (hour == 15 and minute >= 30):
                return {'changed': False}
        
        # First tick at 09:15 - calculate ATM and subscribe
        if not self.first_tick_received:
            self.first_tick_received = True
            self.current_spot = ltp
            
            log_info(f"\n🎯 First {self.underlying} tick at market open: {ltp:.2f}")
            
            return self._subscribe_options(ltp, is_first=True)
        
        # Subsequent ticks - check if ATM changed
        self.current_spot = ltp
        new_atm = self._calculate_atm(ltp)
        
        if new_atm != self.current_atm:
            log_info(f"\n🔄 ATM changed: {self.current_atm} → {new_atm} (Spot: {ltp:.2f})")
            return self._subscribe_options(ltp, is_first=False)
        
        return {'changed': False}
    
    def _calculate_atm(self, spot_price: float) -> int:
        """
        Calculate ATM strike from spot price.
        
        Args:
            spot_price: Current spot price
            
        Returns:
            ATM strike (rounded to nearest strike interval)
        """
        return round(spot_price / self.strike_interval) * self.strike_interval
    
    def _subscribe_options(self, spot_price: float, is_first: bool = False) -> Dict:
        """
        Subscribe to option strikes based on spot price.
        
        Args:
            spot_price: Current spot price
            is_first: Whether this is the first subscription
            
        Returns:
            Dict with subscription info
        """
        # Calculate ATM
        atm_strike = self._calculate_atm(spot_price)
        old_atm = self.current_atm
        self.current_atm = atm_strike
        
        # Calculate strike range
        strikes = self._calculate_strikes(atm_strike)
        
        # Find new strikes to subscribe
        new_strikes = set(strikes) - self.subscribed_strikes
        
        # Find old strikes to unsubscribe
        old_strikes = self.subscribed_strikes - set(strikes)
        
        # Generate option symbols
        symbols_to_subscribe = []
        symbols_to_unsubscribe = []
        
        for expiry in self.available_expiries:
            expiry_str = expiry.strftime('%Y-%m-%d')
            
            # New strikes
            for strike in new_strikes:
                ce_symbol = f"{self.underlying}:{expiry_str}:OPT:{strike}:CE"
                pe_symbol = f"{self.underlying}:{expiry_str}:OPT:{strike}:PE"
                symbols_to_subscribe.append(ce_symbol)
                symbols_to_subscribe.append(pe_symbol)
            
            # Old strikes
            for strike in old_strikes:
                ce_symbol = f"{self.underlying}:{expiry_str}:OPT:{strike}:CE"
                pe_symbol = f"{self.underlying}:{expiry_str}:OPT:{strike}:PE"
                symbols_to_unsubscribe.append(ce_symbol)
                symbols_to_unsubscribe.append(pe_symbol)
        
        # Unsubscribe old strikes
        if symbols_to_unsubscribe:
            count = self.subscription_manager.unsubscribe_by_symbols(symbols_to_unsubscribe)
            log_info(f"📉 Unsubscribed {count} option symbols (old strikes)")
        
        # Subscribe new strikes
        if symbols_to_subscribe:
            count = self.subscription_manager.subscribe_by_symbols(
                symbols_to_subscribe,
                priority=self.subscription_manager.PRIORITY_HIGH,
                metadata=f"{self.underlying}_options"
            )
            log_info(f"📈 Subscribed {count} option symbols (new strikes)")
        
        # Update subscribed strikes
        self.subscribed_strikes = set(strikes)
        
        # Log summary
        if is_first:
            log_info(f"   Spot Price: {spot_price:.2f}")
            log_info(f"   ATM Strike: {atm_strike}")
            log_info(f"   Subscribed Strikes: {len(strikes)} ({min(strikes)} to {max(strikes)})")
            log_info(f"   Total Symbols: {len(strikes) * 2} (CE + PE)")
            log_info(f"   Expiries: {len(self.available_expiries)}")
            log_info(f"   Total Option Symbols: {len(strikes) * 2 * len(self.available_expiries)}")
        
        return {
            'changed': True,
            'old_atm': old_atm,
            'new_atm': atm_strike,
            'spot_price': spot_price,
            'total_strikes': strikes,
            'new_strikes': list(new_strikes),
            'removed_strikes': list(old_strikes),
            'symbols_subscribed': len(symbols_to_subscribe),
            'symbols_unsubscribed': len(symbols_to_unsubscribe)
        }
    
    def _calculate_strikes(self, atm_strike: int) -> List[int]:
        """
        Calculate all strikes to subscribe (ITM1-16, ATM, OTM1-16).
        
        Args:
            atm_strike: ATM strike price
            
        Returns:
            List of strike prices
        """
        strikes = []
        
        # ITM strikes (below ATM for CE, above ATM for PE)
        for i in range(1, self.itm_depth + 1):
            itm_strike = atm_strike - (i * self.strike_interval)
            strikes.append(itm_strike)
        
        # ATM strike
        strikes.append(atm_strike)
        
        # OTM strikes (above ATM for CE, below ATM for PE)
        for i in range(1, self.otm_depth + 1):
            otm_strike = atm_strike + (i * self.strike_interval)
            strikes.append(otm_strike)
        
        return sorted(strikes)
    
    def get_subscribed_symbols(self) -> List[str]:
        """
        Get list of currently subscribed option symbols.
        
        Returns:
            List of option symbols
        """
        symbols = []
        
        for expiry in self.available_expiries:
            expiry_str = expiry.strftime('%Y-%m-%d')
            
            for strike in self.subscribed_strikes:
                ce_symbol = f"{self.underlying}:{expiry_str}:OPT:{strike}:CE"
                pe_symbol = f"{self.underlying}:{expiry_str}:OPT:{strike}:PE"
                symbols.append(ce_symbol)
                symbols.append(pe_symbol)
        
        return symbols
    
    def get_status(self) -> Dict:
        """
        Get current subscription status.
        
        Returns:
            Dict with status info
        """
        return {
            'underlying': self.underlying,
            'first_tick_received': self.first_tick_received,
            'current_spot': self.current_spot,
            'current_atm': self.current_atm,
            'subscribed_strikes': sorted(list(self.subscribed_strikes)),
            'num_strikes': len(self.subscribed_strikes),
            'num_expiries': len(self.available_expiries),
            'total_symbols': len(self.subscribed_strikes) * 2 * len(self.available_expiries)
        }
