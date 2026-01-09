"""
Smart Subscription Manager

Intelligently manages WebSocket subscriptions with limits and priorities.

Features:
- Respects broker subscription limits (3000 per connection)
- Priority-based subscription
- Auto-subscribe to active instruments
- Batch subscription/unsubscription
- Multiple connection management (if needed)
"""

from typing import Dict, List, Set, Optional
from src.utils.logger import log_info, log_warning, log_error
import threading


class SmartSubscriptionManager:
    """
    Manages WebSocket subscriptions intelligently.
    
    Features:
    - Subscription limits enforcement
    - Priority-based subscription
    - Auto-cleanup of inactive subscriptions
    - Multiple connection support
    """
    
    # Subscription limits
    MAX_SUBSCRIPTIONS_PER_CONNECTION = 3000
    
    # Priority levels
    PRIORITY_CRITICAL = 1   # Active positions
    PRIORITY_HIGH = 2       # Strategy instruments
    PRIORITY_MEDIUM = 3     # Watchlist
    PRIORITY_LOW = 4        # General monitoring
    
    def __init__(self, ltp_store, broker_adapter):
        """
        Initialize subscription manager.
        
        Args:
            ltp_store: InstrumentLTPStore instance
            broker_adapter: Broker adapter with WebSocket
        """
        self.store = ltp_store
        self.broker = broker_adapter
        
        # Subscription tracking
        self.subscribed_tokens = set()  # Currently subscribed tokens
        self.subscription_priorities = {}  # token -> priority
        self.subscription_metadata = {}  # token -> metadata (why subscribed)
        
        # Limits
        self.max_subscriptions = self.MAX_SUBSCRIPTIONS_PER_CONNECTION
        
        # Thread safety
        self.lock = threading.RLock()
        
        log_info(f"📡 Smart Subscription Manager initialized (limit: {self.max_subscriptions})")
    
    def subscribe_by_symbols(self, 
                            symbols: List[str], 
                            priority: int = PRIORITY_MEDIUM,
                            metadata: str = None) -> int:
        """
        Subscribe to instruments by symbols.
        
        Args:
            symbols: List of trading symbols
            priority: Subscription priority (1=highest, 4=lowest)
            metadata: Optional metadata (e.g., "strategy_123", "position_456")
            
        Returns:
            Number of instruments subscribed
        """
        with self.lock:
            tokens_to_subscribe = []
            
            for symbol in symbols:
                inst = self.store.get_instrument(symbol)
                if not inst:
                    log_warning(f"⚠️  Symbol not found: {symbol}")
                    continue
                
                token = inst['token']
                exchange = inst['exchange']
                
                # Check if already subscribed
                if token in self.subscribed_tokens:
                    # Update priority if higher
                    if priority < self.subscription_priorities.get(token, 999):
                        self.subscription_priorities[token] = priority
                        log_info(f"📈 Updated priority for {symbol}: {priority}")
                    continue
                
                # Check subscription limit
                if len(self.subscribed_tokens) >= self.max_subscriptions:
                    # Try to free up space by removing low priority subscriptions
                    if not self._free_subscription_slot(priority):
                        log_warning(f"⚠️  Subscription limit reached ({self.max_subscriptions})")
                        log_warning(f"   Cannot subscribe to {symbol}")
                        break
                
                tokens_to_subscribe.append({
                    'exchange': exchange,
                    'token': token
                })
                
                # Track subscription
                self.subscribed_tokens.add(token)
                self.subscription_priorities[token] = priority
                self.subscription_metadata[token] = {
                    'symbol': symbol,
                    'reason': metadata or 'manual',
                    'exchange': exchange
                }
            
            # Subscribe via WebSocket
            if tokens_to_subscribe:
                if hasattr(self.broker, 'websocket') and self.broker.websocket:
                    success = self.broker.websocket.subscribe(tokens_to_subscribe)
                    if success:
                        log_info(f"✅ Subscribed to {len(tokens_to_subscribe)} instruments (priority: {priority})")
                        return len(tokens_to_subscribe)
                    else:
                        log_error(f"❌ Failed to subscribe to instruments")
                        # Rollback tracking
                        for token_info in tokens_to_subscribe:
                            token = token_info['token']
                            self.subscribed_tokens.discard(token)
                            self.subscription_priorities.pop(token, None)
                            self.subscription_metadata.pop(token, None)
                        return 0
            
            return 0
    
    def unsubscribe_by_symbols(self, symbols: List[str]) -> int:
        """
        Unsubscribe from instruments by symbols.
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            Number of instruments unsubscribed
        """
        with self.lock:
            tokens_to_unsubscribe = []
            
            for symbol in symbols:
                inst = self.store.get_instrument(symbol)
                if not inst:
                    continue
                
                token = inst['token']
                exchange = inst['exchange']
                
                if token in self.subscribed_tokens:
                    tokens_to_unsubscribe.append({
                        'exchange': exchange,
                        'token': token
                    })
                    
                    # Remove tracking
                    self.subscribed_tokens.discard(token)
                    self.subscription_priorities.pop(token, None)
                    self.subscription_metadata.pop(token, None)
            
            # Unsubscribe via WebSocket
            if tokens_to_unsubscribe:
                if hasattr(self.broker, 'websocket') and self.broker.websocket:
                    success = self.broker.websocket.unsubscribe(tokens_to_unsubscribe)
                    if success:
                        log_info(f"✅ Unsubscribed from {len(tokens_to_unsubscribe)} instruments")
                        return len(tokens_to_unsubscribe)
            
            return 0
    
    def subscribe_top_liquid(self, limit: int = 500, exchange: str = 'NSE') -> int:
        """
        Subscribe to top liquid stocks (by lot size as proxy).
        
        Args:
            limit: Number of stocks to subscribe
            exchange: Exchange to filter
            
        Returns:
            Number of instruments subscribed
        """
        # Get all stocks from exchange
        stocks = self.store.search_instruments(
            exchange=exchange,
            instrument_type=''  # Empty for equities
        )
        
        # Sort by lot size (higher lot size = more liquid typically)
        stocks.sort(key=lambda x: x.get('lot_size', 0), reverse=True)
        
        # Take top N
        top_stocks = stocks[:limit]
        symbols = [s['symbol'] for s in top_stocks]
        
        log_info(f"📊 Subscribing to top {len(symbols)} liquid stocks on {exchange}")
        
        return self.subscribe_by_symbols(
            symbols=symbols,
            priority=self.PRIORITY_LOW,
            metadata=f"top_liquid_{exchange}"
        )
    
    def subscribe_options_chain(self,
                               underlying: str,
                               expiry_date: str,
                               spot_price: float = None,
                               strike_range: int = 10,
                               priority: int = PRIORITY_HIGH) -> int:
        """
        Subscribe to options chain.
        
        Args:
            underlying: Underlying name
            expiry_date: Expiry date (ISO format)
            spot_price: Current spot price (for filtering)
            strike_range: Number of strikes above/below
            priority: Subscription priority
            
        Returns:
            Number of instruments subscribed
        """
        chain = self.store.get_options_chain(
            underlying=underlying,
            expiry_date=expiry_date,
            spot_price=spot_price,
            strike_range=strike_range
        )
        
        symbols = []
        symbols.extend([opt['symbol'] for opt in chain['CE']])
        symbols.extend([opt['symbol'] for opt in chain['PE']])
        
        log_info(f"📊 Subscribing to {underlying} options chain: {len(symbols)} contracts")
        
        return self.subscribe_by_symbols(
            symbols=symbols,
            priority=priority,
            metadata=f"options_chain_{underlying}_{expiry_date}"
        )
    
    def _free_subscription_slot(self, required_priority: int) -> bool:
        """
        Free up a subscription slot by removing low priority subscription.
        
        Args:
            required_priority: Priority of new subscription
            
        Returns:
            True if slot freed
        """
        # Find lowest priority subscription
        lowest_priority = required_priority
        lowest_token = None
        
        for token, priority in self.subscription_priorities.items():
            if priority > lowest_priority:
                lowest_priority = priority
                lowest_token = token
        
        if lowest_token:
            # Unsubscribe lowest priority
            metadata = self.subscription_metadata.get(lowest_token, {})
            symbol = metadata.get('symbol', 'unknown')
            
            log_info(f"📉 Removing low priority subscription: {symbol} (priority: {lowest_priority})")
            
            self.unsubscribe_by_symbols([symbol])
            return True
        
        return False
    
    def get_subscription_stats(self) -> Dict:
        """
        Get subscription statistics.
        
        Returns:
            Statistics dict
        """
        with self.lock:
            # Count by priority
            priority_counts = {}
            for priority in self.subscription_priorities.values():
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            return {
                'total_subscriptions': len(self.subscribed_tokens),
                'max_subscriptions': self.max_subscriptions,
                'available_slots': self.max_subscriptions - len(self.subscribed_tokens),
                'utilization': f"{(len(self.subscribed_tokens) / self.max_subscriptions * 100):.1f}%",
                'by_priority': {
                    'critical': priority_counts.get(self.PRIORITY_CRITICAL, 0),
                    'high': priority_counts.get(self.PRIORITY_HIGH, 0),
                    'medium': priority_counts.get(self.PRIORITY_MEDIUM, 0),
                    'low': priority_counts.get(self.PRIORITY_LOW, 0)
                }
            }
    
    def list_subscriptions(self, priority: int = None) -> List[Dict]:
        """
        List current subscriptions.
        
        Args:
            priority: Filter by priority (optional)
            
        Returns:
            List of subscription info
        """
        with self.lock:
            subscriptions = []
            
            for token in self.subscribed_tokens:
                sub_priority = self.subscription_priorities.get(token)
                
                if priority is not None and sub_priority != priority:
                    continue
                
                metadata = self.subscription_metadata.get(token, {})
                
                subscriptions.append({
                    'token': token,
                    'symbol': metadata.get('symbol'),
                    'exchange': metadata.get('exchange'),
                    'priority': sub_priority,
                    'reason': metadata.get('reason')
                })
            
            return subscriptions
    
    def clear_all_subscriptions(self) -> int:
        """
        Unsubscribe from all instruments.
        
        Returns:
            Number of instruments unsubscribed
        """
        with self.lock:
            all_symbols = [
                meta.get('symbol') 
                for meta in self.subscription_metadata.values()
                if meta.get('symbol')
            ]
            
            if all_symbols:
                log_info(f"🧹 Clearing all {len(all_symbols)} subscriptions")
                return self.unsubscribe_by_symbols(all_symbols)
            
            return 0
    
    def __repr__(self):
        stats = self.get_subscription_stats()
        return f"<SmartSubscriptionManager: {stats['total_subscriptions']}/{stats['max_subscriptions']} subscribed ({stats['utilization']})>"
