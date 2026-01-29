"""
Smart Catchup Manager with Candle Alignment
Catches up with 1-minute candles and stops when aligned with live data.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import pandas as pd
import threading
import time


class SmartCatchupManager:
    """
    Intelligent catchup manager that:
    1. Detects gaps in live data
    2. Fetches 1-minute candles to fill gaps
    3. Stops catchup when aligned with current time
    4. Switches back to live tick processing
    """

    def __init__(self, broker_adapter, on_catchup_candle: Optional[Callable] = None):
        """
        Initialize smart catchup manager.
        
        Args:
            broker_adapter: Broker adapter with historical data capability
            on_catchup_candle: Callback for catchup candles
        """
        self.broker_adapter = broker_adapter
        self.on_catchup_candle = on_catchup_candle
        
        # Track last candle time for each symbol
        self.last_candle_time = {}  # {symbol: datetime}
        
        # Connection status
        self.is_connected = False
        self.disconnect_time = None
        self.reconnect_time = None
        
        # Catchup state
        self.is_catching_up = {}  # {symbol: bool}
        self.catchup_progress = {}  # {symbol: {'current': datetime, 'target': datetime}}
        
        # Settings
        self.catchup_interval = '1'  # 1-minute candles
        self.alignment_tolerance_seconds = 60  # Consider aligned if within 60 seconds
        
        # Monitoring
        self.monitor_thread = None
        self.is_monitoring = False
        
        # Subscribed symbols
        self.subscribed_symbols = {}  # {symbol: {'exchange': 'NSE', 'token': '123'}}
        
        # Lock for thread safety
        self.lock = threading.Lock()

    def start_monitoring(self):
        """Start monitoring for gaps."""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("✅ Smart catchup monitoring started")

    def stop_monitoring(self):
        """Stop monitoring."""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print("✅ Smart catchup monitoring stopped")

    def on_candle_completed(self, symbol: str, candle_time: datetime):
        """
        Called when a candle is completed (from live ticks).
        
        Args:
            symbol: Trading symbol
            candle_time: Timestamp of completed candle
        """
        with self.lock:
            self.last_candle_time[symbol] = candle_time
            
            # Check if we're catching up and if we've reached alignment
            if self.is_catching_up.get(symbol, False):
                self._check_alignment(symbol, candle_time)

    def on_websocket_connected(self):
        """Called when WebSocket connects."""
        self.is_connected = True
        self.reconnect_time = datetime.now()
        
        # If we had a disconnection, trigger catchup
        if self.disconnect_time:
            gap_seconds = (self.reconnect_time - self.disconnect_time).total_seconds()
            print(f"\n🔄 WebSocket reconnected after {gap_seconds:.1f}s")
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
        with self.lock:
            self.subscribed_symbols[symbol] = {
                'exchange': exchange,
                'token': token
            }
            self.last_candle_time[symbol] = datetime.now()
            self.is_catching_up[symbol] = False
        
        print(f"📊 Tracking {symbol} for smart catchup")

    def remove_symbol(self, symbol: str):
        """Remove a symbol from tracking."""
        with self.lock:
            self.subscribed_symbols.pop(symbol, None)
            self.last_candle_time.pop(symbol, None)
            self.is_catching_up.pop(symbol, None)
            self.catchup_progress.pop(symbol, None)

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.is_monitoring:
            try:
                time.sleep(10)  # Check every 10 seconds
                
                if not self.is_connected:
                    continue
                
                # Check each symbol for gaps
                now = datetime.now()
                for symbol in list(self.subscribed_symbols.keys()):
                    if symbol not in self.last_candle_time:
                        continue
                    
                    # Skip if already catching up
                    if self.is_catching_up.get(symbol, False):
                        continue
                    
                    last_candle = self.last_candle_time[symbol]
                    gap_seconds = (now - last_candle).total_seconds()
                    
                    # If gap is more than 2 minutes, trigger catchup
                    if gap_seconds > 120:
                        print(f"\n⚠️ Gap detected for {symbol}: {gap_seconds:.1f}s since last candle")
                        self._start_catchup(symbol, last_candle, now)
                        
            except Exception as e:
                print(f"❌ Error in monitor loop: {e}")

    def _trigger_catchup_for_all(self):
        """Trigger catchup for all subscribed symbols after reconnection."""
        if not self.disconnect_time or not self.reconnect_time:
            return
        
        print(f"\n🔄 Starting catchup for all symbols...")
        print(f"   Gap period: {self.disconnect_time.strftime('%H:%M:%S')} to {self.reconnect_time.strftime('%H:%M:%S')}")
        
        for symbol in self.subscribed_symbols.keys():
            self._start_catchup(symbol, self.disconnect_time, self.reconnect_time)

    def _start_catchup(self, symbol: str, from_time: datetime, to_time: datetime):
        """
        Start catchup process for a symbol.
        
        Args:
            symbol: Trading symbol
            from_time: Start time of gap
            to_time: End time of gap (target alignment time)
        """
        with self.lock:
            if self.is_catching_up.get(symbol, False):
                print(f"⚠️ {symbol} is already catching up")
                return
            
            self.is_catching_up[symbol] = True
            self.catchup_progress[symbol] = {
                'start': from_time,
                'current': from_time,
                'target': to_time,
                'candles_fetched': 0
            }
        
        # Start catchup in background thread
        thread = threading.Thread(
            target=self._catchup_worker,
            args=(symbol, from_time, to_time),
            daemon=True
        )
        thread.start()

    def _catchup_worker(self, symbol: str, from_time: datetime, to_time: datetime):
        """
        Worker thread to fetch and process catchup candles.
        
        Args:
            symbol: Trading symbol
            from_time: Start time
            to_time: Target time
        """
        try:
            symbol_info = self.subscribed_symbols.get(symbol)
            if not symbol_info:
                return
            
            exchange = symbol_info['exchange']
            
            print(f"\n🔄 [{symbol}] Starting catchup...")
            print(f"   From: {from_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   To:   {to_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Gap:  {(to_time - from_time).total_seconds() / 60:.1f} minutes")
            
            # Fetch 1-minute candles
            df = self.broker_adapter.fetch_historical_data(
                symbol=symbol,
                from_date=from_time,
                to_date=to_time,
                interval=self.catchup_interval,
                exchange=exchange
            )
            
            if df is None or df.empty:
                print(f"⚠️ [{symbol}] No catchup data available")
                with self.lock:
                    self.is_catching_up[symbol] = False
                return
            
            # Sort by timestamp
            df = df.sort_values('timestamp')
            
            print(f"✅ [{symbol}] Fetched {len(df)} catchup candles")
            
            # Process each candle
            for idx, row in df.iterrows():
                candle_time = row['timestamp']
                
                # Create candle data
                candle = {
                    'symbol': symbol,
                    'exchange': exchange,
                    'timestamp': candle_time,
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume'],
                    'is_catchup': True
                }
                
                # Update progress
                with self.lock:
                    if symbol in self.catchup_progress:
                        self.catchup_progress[symbol]['current'] = candle_time
                        self.catchup_progress[symbol]['candles_fetched'] += 1
                
                # Call callback
                if self.on_catchup_candle:
                    self.on_catchup_candle(candle)
                
                # Check if we've reached alignment
                if self._is_aligned(candle_time, to_time):
                    print(f"\n✅ [{symbol}] Catchup complete - Aligned with current time!")
                    print(f"   Last catchup candle: {candle_time.strftime('%H:%M:%S')}")
                    print(f"   Current time: {to_time.strftime('%H:%M:%S')}")
                    print(f"   Total candles: {self.catchup_progress[symbol]['candles_fetched']}")
                    break
            
            # Mark catchup as complete
            with self.lock:
                self.is_catching_up[symbol] = False
                self.last_candle_time[symbol] = to_time
            
            print(f"🎯 [{symbol}] Switching to live candle building from ticks")
            
        except Exception as e:
            print(f"❌ [{symbol}] Catchup error: {e}")
            import traceback
            traceback.print_exc()
            
            with self.lock:
                self.is_catching_up[symbol] = False

    def _is_aligned(self, candle_time: datetime, target_time: datetime) -> bool:
        """
        Check if candle time is aligned with target time.
        
        Args:
            candle_time: Time of the candle
            target_time: Target alignment time
        
        Returns:
            True if aligned within tolerance
        """
        diff_seconds = abs((target_time - candle_time).total_seconds())
        return diff_seconds <= self.alignment_tolerance_seconds

    def _check_alignment(self, symbol: str, candle_time: datetime):
        """
        Check if catchup has reached alignment.
        
        Args:
            symbol: Trading symbol
            candle_time: Latest candle time
        """
        if symbol not in self.catchup_progress:
            return
        
        target_time = self.catchup_progress[symbol]['target']
        
        if self._is_aligned(candle_time, target_time):
            print(f"\n✅ [{symbol}] Alignment reached!")
            print(f"   Candle time: {candle_time.strftime('%H:%M:%S')}")
            print(f"   Target time: {target_time.strftime('%H:%M:%S')}")
            
            with self.lock:
                self.is_catching_up[symbol] = False

    def get_status(self, symbol: Optional[str] = None) -> Dict:
        """
        Get catchup status.
        
        Args:
            symbol: Optional symbol to get status for
        
        Returns:
            Status dictionary
        """
        with self.lock:
            if symbol:
                return {
                    'symbol': symbol,
                    'is_catching_up': self.is_catching_up.get(symbol, False),
                    'last_candle_time': self.last_candle_time.get(symbol),
                    'progress': self.catchup_progress.get(symbol, {})
                }
            else:
                return {
                    'is_connected': self.is_connected,
                    'is_monitoring': self.is_monitoring,
                    'tracked_symbols': list(self.subscribed_symbols.keys()),
                    'catching_up': {
                        sym: self.is_catching_up.get(sym, False)
                        for sym in self.subscribed_symbols.keys()
                    },
                    'progress': self.catchup_progress
                }
