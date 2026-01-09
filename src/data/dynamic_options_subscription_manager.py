"""
Dynamic Options Subscription Manager

Automatically manages option contract subscriptions based on spot price movement.
Subscribes/unsubscribes options as spot crosses strike intervals.

Features:
- Auto-subscribe options when spot moves into new strike range
- Auto-unsubscribe far OTM options to save subscription slots
- Support for multiple expiries
- Configurable ATM range (e.g., ±10 strikes)
- Strike interval detection (50, 100, etc.)
- Priority-based subscription
- Thread-safe

Example:
    manager = DynamicOptionsSubscriptionManager(
        ltp_store=ltp_store,
        broker_adapter=broker,
        subscription_manager=smart_sub_manager
    )
    
    # Configure NIFTY options
    manager.add_underlying(
        underlying='NIFTY',
        spot_symbol='NIFTY 50',
        expiries=['2024-11-14', '2024-11-21'],
        atm_range=10,  # ±10 strikes
        priority=SmartSubscriptionManager.PRIORITY_HIGH
    )
    
    # Auto-updates on spot tick
    manager.on_spot_tick('NIFTY 50', 25000.0)
"""

from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime, date
import threading
import math

from src.utils.logger import log_info, log_debug, log_warning, log_error
from src.data.smart_subscription_manager import SmartSubscriptionManager


class DynamicOptionsSubscriptionManager:
    """
    Manages dynamic option subscriptions based on spot movement.
    
    Key Features:
    1. Auto-subscribe ATM options when spot moves
    2. Auto-unsubscribe far OTM options
    3. Support multiple expiries
    4. Strike interval detection
    5. Efficient subscription management
    """
    
    def __init__(self, 
                 ltp_store,
                 broker_adapter,
                 subscription_manager: SmartSubscriptionManager):
        """
        Initialize dynamic options manager.
        
        Args:
            ltp_store: InstrumentLTPStore instance
            broker_adapter: Broker adapter
            subscription_manager: SmartSubscriptionManager instance
        """
        self.store = ltp_store
        self.broker = broker_adapter
        self.sub_manager = subscription_manager
        
        # Configuration for each underlying
        self.underlyings: Dict[str, Dict] = {}
        
        # Current state
        self.current_spot_prices: Dict[str, float] = {}
        self.current_atm_strikes: Dict[str, float] = {}
        self.subscribed_options: Dict[str, Set[str]] = {}  # underlying -> set of symbols
        
        # Thread safety
        self.lock = threading.RLock()
        
        log_info("🎯 Dynamic Options Subscription Manager initialized")
    
    def add_underlying(self,
                      underlying: str,
                      spot_symbol: str,
                      expiries: List[str],
                      atm_range: int = 10,
                      strike_interval: int = None,
                      priority: int = SmartSubscriptionManager.PRIORITY_HIGH,
                      auto_detect_interval: bool = True) -> None:
        """
        Add an underlying for dynamic options subscription.
        
        Args:
            underlying: Underlying name (e.g., 'NIFTY', 'BANKNIFTY')
            spot_symbol: Spot instrument symbol (e.g., 'NIFTY 50')
            expiries: List of expiry dates (ISO format: 'YYYY-MM-DD')
            atm_range: Number of strikes above/below ATM (default: 10)
            strike_interval: Strike interval (e.g., 50, 100). Auto-detected if None
            priority: Subscription priority
            auto_detect_interval: Auto-detect strike interval from available options
        """
        with self.lock:
            # Auto-detect strike interval if needed
            if strike_interval is None and auto_detect_interval:
                strike_interval = self._detect_strike_interval(underlying, expiries[0] if expiries else None)
            
            config = {
                'spot_symbol': spot_symbol,
                'expiries': expiries,
                'atm_range': atm_range,
                'strike_interval': strike_interval or 50,  # Default to 50
                'priority': priority,
                'enabled': True
            }
            
            self.underlyings[underlying] = config
            self.subscribed_options[underlying] = set()
            
            log_info(f"✅ Added {underlying} for dynamic options subscription")
            log_info(f"   Spot: {spot_symbol}, Expiries: {len(expiries)}, ATM Range: ±{atm_range}")
            log_info(f"   Strike Interval: {config['strike_interval']}")
    
    def remove_underlying(self, underlying: str) -> None:
        """Remove an underlying from dynamic management."""
        with self.lock:
            if underlying in self.underlyings:
                # Unsubscribe all options
                if underlying in self.subscribed_options:
                    symbols = list(self.subscribed_options[underlying])
                    if symbols:
                        self.sub_manager.unsubscribe_by_symbols(symbols)
                    self.subscribed_options[underlying].clear()
                
                del self.underlyings[underlying]
                log_info(f"❌ Removed {underlying} from dynamic options subscription")
    
    def on_spot_tick(self, spot_symbol: str, spot_price: float) -> Dict[str, int]:
        """
        Handle spot price tick and update option subscriptions.
        
        Args:
            spot_symbol: Spot instrument symbol
            spot_price: Current spot price
            
        Returns:
            Dict with 'subscribed' and 'unsubscribed' counts
        """
        with self.lock:
            # Find underlying for this spot symbol
            underlying = None
            for name, config in self.underlyings.items():
                if config['spot_symbol'] == spot_symbol:
                    underlying = name
                    break
            
            if not underlying or not self.underlyings[underlying]['enabled']:
                return {'subscribed': 0, 'unsubscribed': 0}
            
            config = self.underlyings[underlying]
            
            # Update current spot price
            old_spot = self.current_spot_prices.get(underlying)
            self.current_spot_prices[underlying] = spot_price
            
            # Calculate ATM strike
            strike_interval = config['strike_interval']
            atm_strike = self._round_to_strike(spot_price, strike_interval)
            
            # Check if ATM changed
            old_atm = self.current_atm_strikes.get(underlying)
            self.current_atm_strikes[underlying] = atm_strike
            
            if old_atm is None or atm_strike != old_atm:
                # ATM changed - update subscriptions
                log_info(f"📊 {underlying} ATM changed: {old_atm} → {atm_strike} (Spot: {spot_price:.2f})")
                return self._update_subscriptions(underlying, atm_strike, config)
            
            return {'subscribed': 0, 'unsubscribed': 0}
    
    def _update_subscriptions(self, 
                             underlying: str, 
                             atm_strike: float,
                             config: Dict) -> Dict[str, int]:
        """
        Update option subscriptions based on new ATM strike.
        
        Args:
            underlying: Underlying name
            atm_strike: Current ATM strike
            config: Underlying configuration
            
        Returns:
            Dict with subscription counts
        """
        atm_range = config['atm_range']
        strike_interval = config['strike_interval']
        expiries = config['expiries']
        priority = config['priority']
        
        # Calculate required strikes
        required_strikes = self._calculate_required_strikes(
            atm_strike, 
            atm_range, 
            strike_interval
        )
        
        # Get required option symbols
        required_symbols = set()
        for expiry in expiries:
            for strike in required_strikes:
                # Get CE and PE symbols
                ce_symbol = self._get_option_symbol(underlying, expiry, strike, 'CE')
                pe_symbol = self._get_option_symbol(underlying, expiry, strike, 'PE')
                
                if ce_symbol:
                    required_symbols.add(ce_symbol)
                if pe_symbol:
                    required_symbols.add(pe_symbol)
        
        # Current subscriptions
        current_symbols = self.subscribed_options.get(underlying, set())
        
        # Calculate changes
        to_subscribe = required_symbols - current_symbols
        to_unsubscribe = current_symbols - required_symbols
        
        # Unsubscribe far OTM options
        unsubscribed = 0
        if to_unsubscribe:
            log_debug(f"📉 Unsubscribing {len(to_unsubscribe)} far OTM options for {underlying}")
            unsubscribed = self.sub_manager.unsubscribe_by_symbols(list(to_unsubscribe))
            current_symbols -= to_unsubscribe
        
        # Subscribe new ATM options
        subscribed = 0
        if to_subscribe:
            log_debug(f"📈 Subscribing {len(to_subscribe)} new ATM options for {underlying}")
            subscribed = self.sub_manager.subscribe_by_symbols(
                symbols=list(to_subscribe),
                priority=priority,
                metadata=f"dynamic_options_{underlying}"
            )
            current_symbols.update(to_subscribe)
        
        # Update tracking
        self.subscribed_options[underlying] = current_symbols
        
        if subscribed > 0 or unsubscribed > 0:
            log_info(f"✅ {underlying} options updated: +{subscribed} subscribed, -{unsubscribed} unsubscribed")
            log_info(f"   Total active: {len(current_symbols)} options")
        
        return {
            'subscribed': subscribed,
            'unsubscribed': unsubscribed,
            'total_active': len(current_symbols)
        }
    
    def _calculate_required_strikes(self,
                                   atm_strike: float,
                                   atm_range: int,
                                   strike_interval: int) -> List[float]:
        """
        Calculate list of required strikes around ATM.
        
        Args:
            atm_strike: ATM strike price
            atm_range: Number of strikes above/below
            strike_interval: Strike interval
            
        Returns:
            List of strike prices
        """
        strikes = []
        
        # ATM strike
        strikes.append(atm_strike)
        
        # Strikes above ATM
        for i in range(1, atm_range + 1):
            strikes.append(atm_strike + (i * strike_interval))
        
        # Strikes below ATM
        for i in range(1, atm_range + 1):
            strikes.append(atm_strike - (i * strike_interval))
        
        return sorted(strikes)
    
    def _round_to_strike(self, price: float, strike_interval: int) -> float:
        """
        Round price to nearest strike.
        
        Args:
            price: Current price
            strike_interval: Strike interval
            
        Returns:
            Nearest strike price
        """
        return round(price / strike_interval) * strike_interval
    
    def _detect_strike_interval(self, underlying: str, expiry: str = None) -> int:
        """
        Auto-detect strike interval from available options.
        
        Args:
            underlying: Underlying name
            expiry: Expiry date (optional)
            
        Returns:
            Strike interval (e.g., 50, 100)
        """
        try:
            # Get some options for this underlying
            options = self.store.search_instruments(
                underlying=underlying,
                instrument_type='CE',
                expiry_date=expiry
            )
            
            if len(options) >= 2:
                # Sort by strike
                options.sort(key=lambda x: x.get('strike', 0))
                
                # Calculate interval from first two strikes
                strike1 = options[0].get('strike', 0)
                strike2 = options[1].get('strike', 0)
                interval = abs(strike2 - strike1)
                
                log_debug(f"🔍 Detected strike interval for {underlying}: {interval}")
                return int(interval)
        except Exception as e:
            log_warning(f"⚠️  Could not detect strike interval for {underlying}: {e}")
        
        # Default intervals by underlying
        defaults = {
            'NIFTY': 50,
            'BANKNIFTY': 100,
            'FINNIFTY': 50,
            'MIDCPNIFTY': 25,
            'SENSEX': 100,
            'BANKEX': 100
        }
        
        return defaults.get(underlying, 50)
    
    def _get_option_symbol(self,
                          underlying: str,
                          expiry: str,
                          strike: float,
                          option_type: str) -> Optional[str]:
        """
        Get option symbol for given parameters.
        
        Args:
            underlying: Underlying name
            expiry: Expiry date (ISO format)
            strike: Strike price
            option_type: 'CE' or 'PE'
            
        Returns:
            Option symbol or None
        """
        try:
            # Search for exact match
            options = self.store.search_instruments(
                underlying=underlying,
                instrument_type=option_type,
                strike=strike,
                expiry_date=expiry
            )
            
            if options:
                return options[0]['symbol']
        except Exception as e:
            log_debug(f"Could not find option: {underlying} {strike} {option_type} {expiry}: {e}")
        
        return None
    
    def force_refresh(self, underlying: str = None) -> Dict[str, int]:
        """
        Force refresh subscriptions for an underlying.
        
        Args:
            underlying: Underlying name (None for all)
            
        Returns:
            Dict with subscription counts
        """
        with self.lock:
            if underlying:
                underlyings = [underlying]
            else:
                underlyings = list(self.underlyings.keys())
            
            total_subscribed = 0
            total_unsubscribed = 0
            
            for name in underlyings:
                if name not in self.underlyings:
                    continue
                
                config = self.underlyings[name]
                atm_strike = self.current_atm_strikes.get(name)
                
                if atm_strike:
                    result = self._update_subscriptions(name, atm_strike, config)
                    total_subscribed += result['subscribed']
                    total_unsubscribed += result['unsubscribed']
            
            return {
                'subscribed': total_subscribed,
                'unsubscribed': total_unsubscribed
            }
    
    def get_stats(self) -> Dict:
        """
        Get statistics for all underlyings.
        
        Returns:
            Statistics dict
        """
        with self.lock:
            stats = {}
            
            for underlying, config in self.underlyings.items():
                spot_price = self.current_spot_prices.get(underlying)
                atm_strike = self.current_atm_strikes.get(underlying)
                subscribed_count = len(self.subscribed_options.get(underlying, set()))
                
                stats[underlying] = {
                    'spot_price': spot_price,
                    'atm_strike': atm_strike,
                    'subscribed_options': subscribed_count,
                    'expiries': len(config['expiries']),
                    'atm_range': config['atm_range'],
                    'strike_interval': config['strike_interval'],
                    'enabled': config['enabled']
                }
            
            return stats
    
    def enable_underlying(self, underlying: str) -> None:
        """Enable dynamic subscription for an underlying."""
        with self.lock:
            if underlying in self.underlyings:
                self.underlyings[underlying]['enabled'] = True
                log_info(f"✅ Enabled dynamic subscription for {underlying}")
    
    def disable_underlying(self, underlying: str) -> None:
        """Disable dynamic subscription for an underlying."""
        with self.lock:
            if underlying in self.underlyings:
                self.underlyings[underlying]['enabled'] = False
                log_info(f"⏸️  Disabled dynamic subscription for {underlying}")
    
    def get_subscribed_options(self, underlying: str) -> List[str]:
        """Get list of currently subscribed options for an underlying."""
        with self.lock:
            return list(self.subscribed_options.get(underlying, set()))
    
    def __repr__(self):
        stats = self.get_stats()
        total_options = sum(s['subscribed_options'] for s in stats.values())
        return f"<DynamicOptionsSubscriptionManager: {len(stats)} underlyings, {total_options} options>"


# Example usage
if __name__ == '__main__':
    print("Dynamic Options Subscription Manager")
    print("=" * 50)
    print()
    print("This manager automatically subscribes/unsubscribes")
    print("option contracts as spot price moves through strikes.")
    print()
    print("Features:")
    print("  ✅ Auto-subscribe ATM options")
    print("  ✅ Auto-unsubscribe far OTM options")
    print("  ✅ Multiple expiries support")
    print("  ✅ Strike interval detection")
    print("  ✅ Priority-based subscription")
    print()
    print("Example:")
    print("  manager.add_underlying(")
    print("      underlying='NIFTY',")
    print("      spot_symbol='NIFTY 50',")
    print("      expiries=['2024-11-14', '2024-11-21'],")
    print("      atm_range=10")
    print("  )")
    print()
    print("  manager.on_spot_tick('NIFTY 50', 25000.0)")
