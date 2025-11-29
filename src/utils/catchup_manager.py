"""
Catchup Manager
Handles data gap detection and filling during WebSocket disconnections.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import pandas as pd
import threading
import time


class CatchupManager:
    """
    Manages catchup of missed data during WebSocket disconnections.
    Detects gaps and fills them with historical data.
    """

    def __init__(self, broker_adapter, on_catchup_data: Optional[Callable] = None):
        """
        Initialize catchup manager.
        
        Args:
            broker_adapter: Broker adapter instance with historical data capability
            on_catchup_data: Optional callback for catchup data
        """
        self.broker_adapter = broker_adapter
        self.on_catchup_data = on_catchup_data
        
        # Track last tick time for each symbol
        self.last_tick_time = {}  # {symbol: datetime}
        
        # Track connection status
        self.is_connected = False
        self.disconnect_time = None
        self.reconnect_time = None
        
        # Catchup settings
        self.max_gap_seconds = 5  # Max gap before triggering catchup
        self.catchup_interval = '1'  # 1-minute candles for catchup
        
        # Monitoring thread
        self.monitor_thread = None
        self.is_monitoring = False
        
        # Subscribed symbols
        self.subscribed_symbols = {}  # {symbol: {'exchange': 'NSE', 'token': '123'}}

    def start_monitoring(self):
        """Start monitoring for gaps and disconnections."""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("✅ Catchup monitoring started")

    def stop_monitoring(self):
        """Stop monitoring."""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print("✅ Catchup monitoring stopped")

    def on_tick_received(self, symbol: str, tick_data: Dict):
        """
        Called when a tick is received.
        Updates last tick time for the symbol.
        
        Args:
            symbol: Trading symbol
            tick_data: Tick data dictionary
        """
        self.last_tick_time[symbol] = datetime.now()

    def on_websocket_connected(self):
        """Called when WebSocket connects."""
        self.is_connected = True
        self.reconnect_time = datetime.now()
        
        # If we had a disconnection, trigger catchup
        if self.disconnect_time:
            print(f"\n🔄 WebSocket reconnected after {(self.reconnect_time - self.disconnect_time).total_seconds():.1f}s")
            self._trigger_catchup_for_all()

    def on_websocket_disconnected(self):
        """Called when WebSocket disconnects."""
        self.is_connected = False
        self.disconnect_time = datetime.now()
        print(f"\n⚠️ WebSocket disconnected at {self.disconnect_time.strftime('%H:%M:%S')}")

    def add_symbol(self, symbol: str, exchange: str, token: str):
        """
        Add a symbol to track for catchup.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            token: Instrument token
        """
        self.subscribed_symbols[symbol] = {
            'exchange': exchange,
            'token': token
        }
        self.last_tick_time[symbol] = datetime.now()
        print(f"📊 Tracking {symbol} for catchup")

    def remove_symbol(self, symbol: str):
        """Remove a symbol from tracking."""
        self.subscribed_symbols.pop(symbol, None)
        self.last_tick_time.pop(symbol, None)

    def _monitor_loop(self):
        """Background monitoring loop to detect gaps."""
        while self.is_monitoring:
            try:
                # Check for gaps every 5 seconds
                time.sleep(5)
                
                if not self.is_connected:
                    continue
                
                # Check each symbol for gaps
                now = datetime.now()
                for symbol in list(self.subscribed_symbols.keys()):
                    if symbol not in self.last_tick_time:
                        continue
                    
                    last_tick = self.last_tick_time[symbol]
                    gap_seconds = (now - last_tick).total_seconds()
                    
                    # If gap is too large, trigger catchup
                    if gap_seconds > self.max_gap_seconds:
                        print(f"\n⚠️ Gap detected for {symbol}: {gap_seconds:.1f}s since last tick")
                        self._trigger_catchup(symbol, last_tick, now)
                        
            except Exception as e:
                print(f"❌ Error in monitor loop: {e}")

    def _trigger_catchup_for_all(self):
        """Trigger catchup for all subscribed symbols after reconnection."""
        if not self.disconnect_time or not self.reconnect_time:
            return
        
        print(f"\n🔄 Starting catchup for all symbols...")
        print(f"   Gap period: {self.disconnect_time.strftime('%H:%M:%S')} to {self.reconnect_time.strftime('%H:%M:%S')}")
        
        for symbol in self.subscribed_symbols.keys():
            self._trigger_catchup(symbol, self.disconnect_time, self.reconnect_time)

    def _trigger_catchup(self, symbol: str, from_time: datetime, to_time: datetime):
        """
        Trigger catchup for a specific symbol.
        
        Args:
            symbol: Trading symbol
            from_time: Start time of gap
            to_time: End time of gap
        """
        try:
            symbol_info = self.subscribed_symbols.get(symbol)
            if not symbol_info:
                return
            
            exchange = symbol_info['exchange']
            
            print(f"\n🔄 Fetching catchup data for {symbol}...")
            print(f"   Period: {from_time.strftime('%H:%M:%S')} to {to_time.strftime('%H:%M:%S')}")
            
            # Fetch historical data for the gap period
            df = self.broker_adapter.fetch_historical_data(
                symbol=symbol,
                from_date=from_time,
                to_date=to_time,
                interval=self.catchup_interval,
                exchange=exchange
            )
            
            if df is not None and not df.empty:
                print(f"✅ Catchup: Retrieved {len(df)} candles for {symbol}")
                
                # Convert to tick-like format and call callback
                if self.on_catchup_data:
                    for _, row in df.iterrows():
                        catchup_tick = {
                            'symbol': symbol,
                            'exchange': exchange,
                            'timestamp': row['timestamp'],
                            'open': row['open'],
                            'high': row['high'],
                            'low': row['low'],
                            'close': row['close'],
                            'volume': row['volume'],
                            'ltp': row['close'],  # Use close as LTP
                            'is_catchup': True  # Flag to identify catchup data
                        }
                        self.on_catchup_data(catchup_tick)
                
                # Update last tick time
                self.last_tick_time[symbol] = to_time
                
            else:
                print(f"⚠️ No catchup data available for {symbol}")
                
        except Exception as e:
            print(f"❌ Catchup error for {symbol}: {e}")
            import traceback
            traceback.print_exc()

    def get_status(self) -> Dict:
        """
        Get current catchup manager status.
        
        Returns:
            Status dictionary
        """
        return {
            'is_connected': self.is_connected,
            'is_monitoring': self.is_monitoring,
            'disconnect_time': self.disconnect_time,
            'reconnect_time': self.reconnect_time,
            'tracked_symbols': list(self.subscribed_symbols.keys()),
            'last_tick_times': {
                symbol: time.strftime('%H:%M:%S')
                for symbol, time in self.last_tick_time.items()
            }
        }


class CatchupBuffer:
    """
    Buffer to merge live ticks and catchup data in chronological order.
    """

    def __init__(self, max_buffer_size: int = 1000):
        """
        Initialize catchup buffer.
        
        Args:
            max_buffer_size: Maximum number of ticks to buffer
        """
        self.buffer = []  # List of (timestamp, tick_data) tuples
        self.max_buffer_size = max_buffer_size
        self.lock = threading.Lock()

    def add_tick(self, tick_data: Dict):
        """
        Add a tick to the buffer.
        
        Args:
            tick_data: Tick data dictionary (must have 'timestamp' field)
        """
        with self.lock:
            timestamp = tick_data.get('timestamp')
            if timestamp:
                self.buffer.append((timestamp, tick_data))
                
                # Sort by timestamp
                self.buffer.sort(key=lambda x: x[0])
                
                # Trim if too large
                if len(self.buffer) > self.max_buffer_size:
                    self.buffer = self.buffer[-self.max_buffer_size:]

    def get_ticks_after(self, after_time: datetime) -> List[Dict]:
        """
        Get all ticks after a specific time.
        
        Args:
            after_time: Get ticks after this time
        
        Returns:
            List of tick data dictionaries
        """
        with self.lock:
            return [
                tick_data
                for timestamp, tick_data in self.buffer
                if timestamp > after_time
            ]

    def get_latest_ticks(self, count: int = 10) -> List[Dict]:
        """
        Get the latest N ticks.
        
        Args:
            count: Number of ticks to retrieve
        
        Returns:
            List of tick data dictionaries
        """
        with self.lock:
            return [tick_data for _, tick_data in self.buffer[-count:]]

    def clear(self):
        """Clear the buffer."""
        with self.lock:
            self.buffer.clear()
