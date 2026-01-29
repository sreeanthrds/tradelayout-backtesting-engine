"""
LTP Updater - WebSocket Integration

Connects InstrumentLTPStore with broker WebSocket to receive real-time LTP updates.
"""

from typing import Dict, List, Any, Optional
from src.data.instrument_ltp_store import InstrumentLTPStore
from src.utils.logger import log_info, log_error, log_debug


class LTPUpdater:
    """
    Updates InstrumentLTPStore with real-time data from WebSocket.
    
    Usage:
        store = InstrumentLTPStore()
        updater = LTPUpdater(store, broker_adapter)
        updater.subscribe_all_options('NIFTY')
        updater.start()
    """
    
    def __init__(self, store: InstrumentLTPStore, broker_adapter):
        """
        Initialize LTP updater.
        
        Args:
            store: InstrumentLTPStore instance
            broker_adapter: Broker adapter with WebSocket support
        """
        self.store = store
        self.broker = broker_adapter
        self.subscribed_tokens = set()
        
    def subscribe_instruments(self, symbols: List[str]) -> int:
        """
        Subscribe to LTP updates for specific symbols.
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            Number of instruments subscribed
        """
        tokens_to_subscribe = []
        
        for symbol in symbols:
            inst = self.store.get_instrument(symbol)
            if inst:
                token = inst['token']
                exchange = inst['exchange']
                
                if token not in self.subscribed_tokens:
                    tokens_to_subscribe.append({
                        'exchange': exchange,
                        'token': token
                    })
                    self.subscribed_tokens.add(token)
        
        if tokens_to_subscribe:
            # Subscribe via WebSocket
            if hasattr(self.broker, 'websocket') and self.broker.websocket:
                success = self.broker.websocket.subscribe(tokens_to_subscribe)
                if success:
                    log_info(f"✅ Subscribed to {len(tokens_to_subscribe)} instruments for LTP updates")
                    return len(tokens_to_subscribe)
        
        return 0
    
    def subscribe_options_chain(self, 
                                underlying: str,
                                expiry_date: str,
                                exchange: str = 'NFO',
                                spot_price: float = None,
                                strike_range: int = 10) -> int:
        """
        Subscribe to entire options chain.
        
        Args:
            underlying: Underlying name (e.g., 'NIFTY')
            expiry_date: Expiry date (ISO format)
            exchange: Exchange
            spot_price: Current spot price (for filtering)
            strike_range: Number of strikes above/below spot
            
        Returns:
            Number of instruments subscribed
        """
        # Get options chain
        chain = self.store.get_options_chain(
            underlying=underlying,
            expiry_date=expiry_date,
            exchange=exchange,
            spot_price=spot_price,
            strike_range=strike_range
        )
        
        # Collect all symbols
        symbols = []
        symbols.extend([opt['symbol'] for opt in chain['CE']])
        symbols.extend([opt['symbol'] for opt in chain['PE']])
        
        log_info(f"📊 Subscribing to options chain: {underlying} {expiry_date}")
        log_info(f"   Strikes: {len(chain['CE'])} CE + {len(chain['PE'])} PE = {len(symbols)} total")
        
        return self.subscribe_instruments(symbols)
    
    def subscribe_all_options(self, 
                             underlying: str,
                             exchange: str = 'NFO',
                             max_instruments: int = 1000) -> int:
        """
        Subscribe to all options for an underlying (all expiries).
        
        Args:
            underlying: Underlying name
            exchange: Exchange
            max_instruments: Maximum instruments to subscribe
            
        Returns:
            Number of instruments subscribed
        """
        # Search all options
        options = self.store.search_instruments(
            name=underlying,
            exchange=exchange,
            instrument_type='OPTIDX'
        )
        
        # Limit to max_instruments
        if len(options) > max_instruments:
            log_info(f"⚠️ Found {len(options)} options, limiting to {max_instruments}")
            options = options[:max_instruments]
        
        symbols = [opt['symbol'] for opt in options]
        
        log_info(f"📊 Subscribing to all {underlying} options: {len(symbols)} instruments")
        
        return self.subscribe_instruments(symbols)
    
    def on_tick(self, tick_data: Dict):
        """
        WebSocket tick callback - updates store with LTP.
        
        Args:
            tick_data: Tick data from WebSocket
        """
        token = tick_data.get('token')
        if token:
            self.store.update_ltp(str(token), tick_data)
    
    def start(self):
        """
        Start receiving LTP updates.
        
        Note: Assumes WebSocket is already connected.
        """
        log_info("✅ LTP Updater started - receiving real-time updates")
    
    def stop(self):
        """Stop receiving updates."""
        log_info("🛑 LTP Updater stopped")
    
    def get_subscription_count(self) -> int:
        """Get number of subscribed instruments."""
        return len(self.subscribed_tokens)
