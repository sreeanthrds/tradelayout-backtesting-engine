"""
Option Subscription Manager - Smart option contract subscription based on entry nodes.

This module manages option contract subscriptions:
1. Entry-node-based subscription (only subscribe what's needed)
2. Strike change monitoring (auto-resubscribe when ATM changes)
3. Deduplication (multiple strategies can use same strikes)
4. No unsubscribe (keep all subscribed contracts)

Key Principle: Subscribe only the option contracts that strategies actually need,
not all ITM1-16, ATM, OTM1-16 strikes.

Author: UniTrader Team
Created: 2024-11-12
"""

from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime, date
from src.utils.logger import log_info, log_warning, log_debug, log_error
from src.data.fo_dynamic_resolver import FODynamicResolver


class OptionSubscriptionManager:
    """
    Manage option contract subscriptions based on entry node requirements.
    
    Key Features:
    1. Entry-node-based subscription (ATM, OTM5, ITM3, etc.)
    2. Strike change monitoring (resubscribe when ATM changes)
    3. Deduplication (multiple strategies can use same strikes)
    4. No unsubscribe (keep all subscribed contracts)
    """
    
    def __init__(self, cache_manager, ltp_store, subscription_manager=None):
        """
        Initialize option subscription manager.
        
        Args:
            cache_manager: CacheManager instance
            ltp_store: InstrumentLTPStore instance
            subscription_manager: SmartSubscriptionManager instance (for live trading)
        """
        self.cache = cache_manager
        self.ltp_store = ltp_store
        self.subscription_manager = subscription_manager
        
        # Strike intervals
        self.strike_intervals = {
            'NIFTY': 50,
            'BANKNIFTY': 100,
            'FINNIFTY': 50,
            'MIDCPNIFTY': 25
        }
        
        log_info("📡 Initializing Option Subscription Manager")
    
    def subscribe_from_requirements(
        self, 
        option_requirements: List[Dict[str, str]], 
        strategy_instance_id: str
    ) -> Dict[str, int]:
        """
        Subscribe option contracts based on requirements from entry nodes.
        
        Args:
            option_requirements: List of option requirements
                [
                    {'underlying': 'NIFTY', 'strike_type': 'ATM', 'option_type': 'CE', 'expiry_code': 'W0'},
                    {'underlying': 'NIFTY', 'strike_type': 'OTM5', 'option_type': 'PE', 'expiry_code': 'W0'}
                ]
            strategy_instance_id: Strategy instance ID
        
        Returns:
            Dictionary with counts: {'new': X, 'reused': Y}
        """
        if not option_requirements:
            return {'new': 0, 'reused': 0}

        new_count = 0
        reused_count = 0

        for req in option_requirements:
            pattern = req.get('pattern')
            if not pattern:
                # Backward-compat: build pattern from legacy fields if present
                underlying_alias = req.get('underlying_alias', 'TI')
                expiry_code = req.get('expiry_code') or req.get('expiry')
                strike_type = req.get('strike_type')
                option_type = req.get('option_type')
                if not (expiry_code and strike_type and option_type):
                    log_warning(f"⚠️ Invalid option requirement, skipping: {req}")
                    continue
                pattern = f"{underlying_alias}:{expiry_code}:{strike_type}:{option_type}"

            existing = self.cache.get_option_pattern(pattern)

            if existing:
                used_by = set(existing.get('used_by_strategies', []))
                if strategy_instance_id not in used_by:
                    used_by.add(strategy_instance_id)
                    existing['used_by_strategies'] = list(used_by)

                # Merge entry/vpi metadata
                entry_ids = set(existing.get('entry_node_ids', []))
                vpis = set(existing.get('vpis', []))

                if req.get('entry_node_id'):
                    entry_ids.add(req['entry_node_id'])
                if req.get('vpi'):
                    vpis.add(req['vpi'])

                existing['entry_node_ids'] = list(entry_ids)
                existing['vpis'] = list(vpis)

                # Update underlying symbol if provided
                underlying_symbol = req.get('underlying_symbol')
                if underlying_symbol:
                    existing['underlying_symbol'] = underlying_symbol

                self.cache.set_option_pattern(pattern, existing)
                log_debug(f"♻️ Reusing option pattern: {pattern} (used by {strategy_instance_id})")
                reused_count += 1
            else:
                data = {
                    'pattern': pattern,
                    'underlying_alias': req.get('underlying_alias', 'TI'),
                    'underlying_symbol': req.get('underlying_symbol'),
                    'entry_node_ids': [req['entry_node_id']] if req.get('entry_node_id') else [],
                    'vpis': [req['vpi']] if req.get('vpi') else [],
                    'used_by_strategies': [strategy_instance_id],
                    'subscribed_at': datetime.now().isoformat()
                }
                self.cache.set_option_pattern(pattern, data)
                log_info(f"✅ Registered option pattern: {pattern} (used by {strategy_instance_id})")
                new_count += 1

        log_info(f"📡 Option pattern registration for {strategy_instance_id}: {new_count} new, {reused_count} reused")

        return {'new': new_count, 'reused': reused_count}

    def get_all_option_patterns(self) -> List[str]:
        """Get list of all option patterns currently registered across strategies."""
        return self.cache.get_all_option_patterns()
    
    def subscribe_full_universe(
        self,
        underlying: str,
        ltp: float,
        expiry_codes: Optional[List[str]] = None,
        max_otm: int = 10,
        max_itm: int = 10
    ):
        """Subscribe a full ATM/ITM/OTM option universe for an underlying.

        This is primarily intended for backtesting "full mode" where we want a
        reasonably dense ladder of strikes around ATM for a small set of
        expiries. It uses the legacy strike-based option_subscriptions cache so
        that existing resubscribe logic continues to work unchanged.

        Args:
            underlying: Spot symbol (e.g., 'NIFTY').
            ltp: Current spot price from the first tick.
            expiry_codes: List of expiry codes (e.g., ['W0', 'W1', 'M0']). If
                None, a sensible default is used.
            max_otm: Maximum OTM levels to subscribe (OTM1..OTM<N>). ATM is
                always included separately.
            max_itm: Maximum ITM levels to subscribe (ITM1..ITM<N>).
        """
        if underlying not in self.strike_intervals:
            return

        if expiry_codes is None:
            expiry_codes = ['W0', 'W1', 'M0']

        # Calculate ATM from current LTP and store it
        atm_strike = self._calculate_atm(ltp, underlying)
        self.cache.set_current_atm(underlying, atm_strike)

        # Prepare strike types: ATM + ITM/OTM ladders
        strike_types: List[str] = ['ATM']
        strike_types.extend([f"OTM{i}" for i in range(1, max_otm + 1)])
        strike_types.extend([f"ITM{i}" for i in range(1, max_itm + 1)])

        # For each expiry and option type, generate strikes and subscribe
        option_types = ['CE', 'PE']

        for expiry_code in expiry_codes:
            expiry_date = self._resolve_expiry(expiry_code, underlying)
            if not expiry_date:
                continue

            for option_type in option_types:
                for strike_type in strike_types:
                    strike = self._calculate_strike_from_type(atm_strike, strike_type, underlying)
                    strike_key = (strike_type, option_type, expiry_code)

                    # Build unified option symbol
                    symbol = f"{underlying}:{expiry_date}:OPT:{strike}:{option_type}"

                    # Store in legacy option_subscriptions so resubscribe logic works
                    existing = self.cache.get_option_subscription(underlying, strike_key)
                    if existing:
                        data = existing
                        data['strike'] = strike
                        data['symbol'] = symbol
                    else:
                        data = {
                            'strike': strike,
                            'symbol': symbol,
                            'used_by_strategies': []
                        }

                    self.cache.set_option_subscription(underlying, strike_key, data)

                    # Subscribe via live subscription manager if available
                    if self.subscription_manager:
                        try:
                            self.subscription_manager.subscribe_by_symbols([symbol])
                        except Exception as e:
                            import traceback
                            log_error(f"❌ CRITICAL: Failed to subscribe option {symbol}: {e}")
                            log_error(f"   Full traceback:\n{traceback.format_exc()}")
                            # Re-raise - option subscription failures are critical
                            raise RuntimeError(f"Option subscription failed for {symbol}") from e

                    log_info(f"✅ Subscribed full-universe option: {symbol}")

    def on_tick(self, symbol: str, ltp: float, timestamp: datetime = None):
        """
        Handle each tick for option management.
        
        Args:
            symbol: Underlying symbol (e.g., 'NIFTY')
            ltp: Last traded price of the underlying
            timestamp: Tick timestamp (optional)
        """
        # Check if this is an underlying we're tracking
        if symbol not in self.strike_intervals:
            # This indicates an integration bug: we received ticks for an
            # underlying without having configured its strike interval.
            log_error(
                f"❌ OptionSubscriptionManager.on_tick called for unknown underlying '{symbol}'. "
                f"No strike interval configured. Ensure cold subscription and setup are complete."
            )
            raise ValueError(
                f"OptionSubscriptionManager: strike interval not configured for underlying '{symbol}'."
            )
        
        # Get current ATM from cache
        old_atm = self.cache.get_current_atm(symbol)
        
        # If we have not yet initialized the option universe for this underlying,
        # do a one-time full-universe subscription using the current LTP.
        if old_atm is None:
            log_info(f"🆕 Initializing full option universe for {symbol} (Spot: {ltp:.2f})")
            self.subscribe_full_universe(symbol, ltp)
            return

        # Calculate new ATM
        new_atm = self._calculate_atm(ltp, symbol)
        
        # Check if ATM changed
        if new_atm != old_atm:
            log_info(f"🔄 {symbol} ATM changed: {old_atm} → {new_atm} (Spot: {ltp:.2f})")
            
            # Update cache
            self.cache.set_current_atm(symbol, new_atm)
            
            # Resubscribe all option requirements for this underlying
            self._resubscribe_for_underlying(symbol, new_atm)
    
    def _resubscribe_for_underlying(self, underlying: str, new_atm: float):
        """
        Resubscribe all option contracts for an underlying when ATM changes.
        
        Args:
            underlying: Underlying symbol
            new_atm: New ATM strike
        """
        # Get all subscriptions for this underlying
        subscriptions = self.cache.get_option_subscriptions(underlying)
        
        if not subscriptions or 'subscribed_strikes' not in subscriptions:
            return
        
        subscribed_strikes = subscriptions['subscribed_strikes']
        
        # Resubscribe each strike
        for strike_key, data in subscribed_strikes.items():
            strike_type, option_type, expiry_code = strike_key
            
            # Calculate new strike
            new_strike = self._calculate_strike_from_type(new_atm, strike_type, underlying)
            
            # Resolve expiry
            expiry_date = self._resolve_expiry(expiry_code, underlying)
            
            if not expiry_date:
                continue
            
            # Create new symbol
            new_symbol = f"{underlying}:{expiry_date}:OPT:{new_strike}:{option_type}"
            
            # Update cache
            data['strike'] = new_strike
            data['symbol'] = new_symbol
            self.cache.set_option_subscription(underlying, strike_key, data)
            
            # Subscribe via subscription manager (if available)
            # Note: We don't unsubscribe old strikes (as per requirement)
            if self.subscription_manager:
                self.subscription_manager.subscribe_by_symbols([new_symbol])
            
            log_info(f"✅ Resubscribed option: {new_symbol}")
    
    def _calculate_atm(self, spot_price: float, underlying: str) -> int:
        """
        Calculate ATM strike from spot price.
        
        Args:
            spot_price: Current spot price
            underlying: Underlying symbol
        
        Returns:
            ATM strike (rounded to nearest strike interval)
        """
        strike_interval = self.strike_intervals.get(underlying, 50)
        return round(spot_price / strike_interval) * strike_interval
    
    def _calculate_strike_from_type(self, atm_strike: float, strike_type: str, underlying: str) -> int:
        """
        Calculate actual strike from strike type.
        
        Args:
            atm_strike: ATM strike
            strike_type: Strike type (ATM, OTM5, ITM3, etc.)
            underlying: Underlying symbol
        
        Returns:
            Actual strike price
        
        Examples:
            ATM → atm_strike
            OTM5 → atm_strike + 5 * strike_interval
            ITM3 → atm_strike - 3 * strike_interval
        """
        strike_interval = self.strike_intervals.get(underlying, 50)
        
        if strike_type == 'ATM':
            return int(atm_strike)
        elif strike_type.startswith('OTM'):
            # Extract number (e.g., OTM5 → 5)
            offset = int(strike_type[3:])
            return int(atm_strike + offset * strike_interval)
        elif strike_type.startswith('ITM'):
            # Extract number (e.g., ITM3 → 3)
            offset = int(strike_type[3:])
            return int(atm_strike - offset * strike_interval)
        else:
            log_warning(f"⚠️ Unknown strike type: {strike_type}, using ATM")
            return int(atm_strike)
    
    def _resolve_expiry(self, expiry_code: str, underlying: str) -> Optional[str]:
        """
        Resolve expiry code to actual expiry date.
        
        Args:
            expiry_code: Expiry code (W0, W1, M0, etc.)
            underlying: Underlying symbol
        
        Returns:
            Expiry date string (YYYY-MM-DD) or None
        
        Examples:
            W0 → Next weekly expiry
            W1 → Weekly expiry after next
            M0 → Next monthly expiry
        """
        # This is a placeholder - in production, you'd use FODynamicResolver
        # or query from instrument store
        
        # For now, return a dummy date
        # In production, integrate with FODynamicResolver
        try:
            from datetime import timedelta
            today = datetime.now().date()
            
            if expiry_code.startswith('W'):
                # Weekly expiry (Thursday)
                weeks_ahead = int(expiry_code[1:])
                days_until_thursday = (3 - today.weekday()) % 7
                if days_until_thursday == 0:
                    days_until_thursday = 7
                expiry_date = today + timedelta(days=days_until_thursday + weeks_ahead * 7)
            elif expiry_code.startswith('M'):
                # Monthly expiry (last Thursday of month)
                months_ahead = int(expiry_code[1:])
                # Simplified - just add 30 days per month
                expiry_date = today + timedelta(days=30 * (months_ahead + 1))
            else:
                log_warning(f"⚠️ Unknown expiry code: {expiry_code}")
                return None
            
            return expiry_date.strftime('%Y-%m-%d')
        
        except Exception as e:
            log_error(f"❌ Failed to resolve expiry {expiry_code}: {e}")
            return None
    
    def get_subscribed_options_for_underlying(self, underlying: str) -> List[str]:
        """
        Get all subscribed option symbols for an underlying.
        
        Args:
            underlying: Underlying symbol
        
        Returns:
            List of option symbols
        """
        subscriptions = self.cache.get_option_subscriptions(underlying)
        
        if not subscriptions or 'subscribed_strikes' not in subscriptions:
            return []
        
        symbols = []
        for strike_key, data in subscriptions['subscribed_strikes'].items():
            symbols.append(data['symbol'])
        
        return symbols
    
    def print_subscription_summary(self):
        """Print summary of option subscriptions."""
        all_subscriptions = self.cache.get_option_subscriptions()
        
        log_info("📡 Option Subscription Summary:")
        for underlying, data in all_subscriptions.items():
            current_atm = data.get('current_atm', 'N/A')
            subscribed_strikes = data.get('subscribed_strikes', {})
            
            log_info(f"   {underlying} (ATM: {current_atm}):")
            for strike_key, strike_data in subscribed_strikes.items():
                strike_type, option_type, expiry_code = strike_key
                symbol = strike_data['symbol']
                users = len(strike_data.get('used_by_strategies', []))
                log_info(f"      - {strike_type} {option_type} {expiry_code}: {symbol} (used by {users} strategies)")
