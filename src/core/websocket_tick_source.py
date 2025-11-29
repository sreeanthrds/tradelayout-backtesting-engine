"""
WebSocket Tick Source
=====================

Tick data source for live trading - receives real-time ticks from broker WebSocket.

This source:
1. Connects to broker WebSocket
2. Subscribes to symbols
3. Receives ticks asynchronously
4. Runs forever until stopped

Author: UniTrader Team
Created: 2024-11-12
"""

import logging
import time
import threading
from typing import Callable, Dict, Any, List, Optional

from src.core.tick_data_source import TickDataSource

logger = logging.getLogger(__name__)


class WebSocketTickSource(TickDataSource):
    """
    Tick source for live trading - receives from WebSocket.
    
    Characteristics:
    - Asynchronous processing (event-driven)
    - Real-time ticks
    - Runs forever until stopped
    - Slower (10-100 ticks/second)
    
    Usage:
        source = WebSocketTickSource(
            broker_adapter=angelone_adapter,
            symbols=['NIFTY', 'BANKNIFTY']
        )
        
        source.start(callback=on_tick)
        source.run_forever()  # Blocks forever
    """
    
    def __init__(
        self,
        broker_adapter: Any,
        symbols: Optional[List[str]] = None
    ):
        """
        Initialize WebSocket tick source.
        
        Args:
            broker_adapter: Broker adapter with WebSocket support
            symbols: List of symbols to subscribe (optional, can subscribe later)
        """
        self.broker_adapter = broker_adapter
        self.symbols = symbols or []
        
        self.callback: Optional[Callable] = None
        self.running = False
        self._stop_event = threading.Event()
        
        # Statistics
        self.ticks_received = 0
        self.errors = 0
        self.connected = False
        
        logger.info(f"📡 WebSocketTickSource initialized")
    
    def start(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Start receiving ticks from WebSocket.
        
        Args:
            callback: Function to call for each tick
        """
        if self.running:
            logger.warning("⚠️ WebSocketTickSource already running")
            return
        
        self.running = True
        self.callback = callback
        self._stop_event.clear()
        
        logger.info(f"🚀 Starting WebSocketTickSource...")
        
        try:
            # Connect to broker WebSocket
            self._connect()
            
            # Subscribe to symbols
            if self.symbols:
                self._subscribe_symbols(self.symbols)
            
            logger.info(f"✅ WebSocketTickSource started")
            
        except Exception as e:
            logger.error(f"❌ Failed to start WebSocketTickSource: {e}")
            self.running = False
            self.errors += 1
    
    def _connect(self):
        """Connect to broker WebSocket."""
        logger.info("🔌 Connecting to broker WebSocket...")
        
        # Register callback with broker adapter
        self.broker_adapter.on_tick = self._on_websocket_tick
        
        # Connect
        self.broker_adapter.connect()
        
        self.connected = True
        logger.info("✅ Connected to broker WebSocket")
    
    def _subscribe_symbols(self, symbols: List[str]):
        """Subscribe to symbols."""
        logger.info(f"📡 Subscribing to {len(symbols)} symbols...")
        
        # Subscribe via broker adapter
        self.broker_adapter.subscribe_instruments(symbols)
        
        logger.info(f"✅ Subscribed to symbols")
    
    def _on_websocket_tick(self, tick_data: Dict[str, Any]):
        """
        Called by broker adapter when tick arrives.
        
        Args:
            tick_data: Tick data from WebSocket
        """
        if not self.running or not self.callback:
            return
        
        try:
            # Call user callback
            self.callback(tick_data)
            self.ticks_received += 1
            
        except Exception as e:
            if self.errors < 10:  # Log first 10 errors only
                logger.error(f"❌ Error processing tick: {e}")
            self.errors += 1
    
    def stop(self):
        """Stop receiving ticks."""
        if not self.running:
            return
        
        logger.info("⏹️ Stopping WebSocketTickSource...")
        
        self.running = False
        self._stop_event.set()
        
        try:
            # Disconnect from broker
            if self.connected:
                self.broker_adapter.disconnect()
                self.connected = False
            
            logger.info("✅ WebSocketTickSource stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping WebSocketTickSource: {e}")
    
    def is_running(self) -> bool:
        """Check if tick source is running."""
        return self.running
    
    def run_forever(self):
        """
        Run forever until stopped.
        
        This keeps the process alive to receive WebSocket ticks.
        Call stop() from another thread to exit.
        """
        logger.info("♾️ WebSocketTickSource running forever (Ctrl+C to stop)...")
        
        try:
            # Wait for stop event
            while not self._stop_event.is_set():
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            logger.info("⌨️ Keyboard interrupt received")
            self.stop()
    
    def subscribe(self, symbols: List[str]):
        """
        Subscribe to additional symbols.
        
        Args:
            symbols: List of symbols to subscribe
        """
        if not self.running:
            logger.warning("⚠️ WebSocketTickSource not running, cannot subscribe")
            return
        
        self._subscribe_symbols(symbols)
        self.symbols.extend(symbols)
    
    def unsubscribe(self, symbols: List[str]):
        """
        Unsubscribe from symbols.
        
        Args:
            symbols: List of symbols to unsubscribe
        """
        if not self.running:
            logger.warning("⚠️ WebSocketTickSource not running, cannot unsubscribe")
            return
        
        logger.info(f"📡 Unsubscribing from {len(symbols)} symbols...")
        
        # Unsubscribe via broker adapter
        self.broker_adapter.unsubscribe_instruments(symbols)
        
        # Remove from symbols list
        for symbol in symbols:
            if symbol in self.symbols:
                self.symbols.remove(symbol)
        
        logger.info(f"✅ Unsubscribed from symbols")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return {
            'ticks_received': self.ticks_received,
            'errors': self.errors,
            'status': 'running' if self.running else 'stopped',
            'connected': self.connected,
            'symbols': self.symbols,
            'symbols_count': len(self.symbols)
        }
