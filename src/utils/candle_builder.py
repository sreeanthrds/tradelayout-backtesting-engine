"""
Candle Builder
Builds OHLCV candles from live ticks with catchup integration.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import threading


class CandleBuilder:
    """
    Builds OHLCV candles from live ticks.
    Integrates with SmartCatchupManager for seamless gap filling.
    """

    def __init__(
        self,
        interval_minutes: int = 1,
        on_candle_complete: Optional[Callable[[Dict], None]] = None
    ):
        """
        Initialize candle builder.
        
        Args:
            interval_minutes: Candle interval in minutes (default: 1)
            on_candle_complete: Callback when candle is completed
        """
        self.interval_minutes = interval_minutes
        self.on_candle_complete = on_candle_complete
        
        # Current candles being built
        self.current_candles = {}  # {symbol: candle_dict}
        
        # Candle start times
        self.candle_start_times = {}  # {symbol: datetime}
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        print(f"🕯️ Candle Builder initialized ({interval_minutes}-minute candles)")

    def on_tick(self, tick_data: Dict):
        """
        Process a live tick and update candle.
        
        Args:
            tick_data: Tick data dictionary with:
                - symbol: str
                - ltp: float
                - volume: int
                - timestamp: datetime or int (milliseconds)
        """
        symbol = tick_data.get('symbol') or tick_data.get('token', 'UNKNOWN')
        ltp = tick_data.get('ltp', 0)
        volume = tick_data.get('volume', 0)
        
        # Get timestamp
        timestamp = tick_data.get('timestamp')
        if isinstance(timestamp, int):
            # Convert milliseconds to datetime
            tick_time = datetime.fromtimestamp(timestamp / 1000)
        elif isinstance(timestamp, datetime):
            tick_time = timestamp
        else:
            tick_time = datetime.now()
        
        with self.lock:
            # Get candle start time for this tick
            candle_start = self._get_candle_start_time(tick_time)
            
            # Check if we need to complete previous candle
            if symbol in self.candle_start_times:
                prev_start = self.candle_start_times[symbol]
                if candle_start > prev_start:
                    # Complete previous candle
                    self._complete_candle(symbol)
            
            # Initialize or update current candle
            if symbol not in self.current_candles or candle_start != self.candle_start_times.get(symbol):
                # Start new candle
                self.current_candles[symbol] = {
                    'symbol': symbol,
                    'timestamp': candle_start,
                    'open': ltp,
                    'high': ltp,
                    'low': ltp,
                    'close': ltp,
                    'volume': volume,
                    'tick_count': 1,
                    'is_catchup': False
                }
                self.candle_start_times[symbol] = candle_start
            else:
                # Update existing candle
                candle = self.current_candles[symbol]
                candle['high'] = max(candle['high'], ltp)
                candle['low'] = min(candle['low'], ltp)
                candle['close'] = ltp
                candle['volume'] = volume  # Use latest volume (cumulative for the day)
                candle['tick_count'] += 1

    def on_catchup_candle(self, catchup_candle: Dict):
        """
        Process a catchup candle (already formed 1-minute candle).
        
        Args:
            catchup_candle: Candle data from catchup with:
                - symbol: str
                - timestamp: datetime
                - open, high, low, close, volume: float
                - is_catchup: True
        """
        symbol = catchup_candle['symbol']
        
        print(f"🔄 [{symbol}] Processing catchup candle: {catchup_candle['timestamp'].strftime('%H:%M')}")
        
        # Catchup candles are already complete, just forward them
        if self.on_candle_complete:
            self.on_candle_complete(catchup_candle)

    def _get_candle_start_time(self, tick_time: datetime) -> datetime:
        """
        Get the start time of the candle for a given tick time.
        
        Args:
            tick_time: Time of the tick
        
        Returns:
            Start time of the candle (floored to interval)
        """
        # Floor to the nearest interval
        minutes = (tick_time.minute // self.interval_minutes) * self.interval_minutes
        
        return tick_time.replace(
            minute=minutes,
            second=0,
            microsecond=0
        )

    def _complete_candle(self, symbol: str):
        """
        Complete and emit the current candle for a symbol.
        
        Args:
            symbol: Trading symbol
        """
        if symbol not in self.current_candles:
            return
        
        candle = self.current_candles[symbol]
        
        print(f"✅ [{symbol}] Candle complete: {candle['timestamp'].strftime('%H:%M')} "
              f"O:{candle['open']:.2f} H:{candle['high']:.2f} "
              f"L:{candle['low']:.2f} C:{candle['close']:.2f} "
              f"V:{candle['volume']} ({candle['tick_count']} ticks)")
        
        # Call callback
        if self.on_candle_complete:
            self.on_candle_complete(candle)
        
        # Remove completed candle
        del self.current_candles[symbol]

    def force_complete_all(self):
        """Force complete all current candles (e.g., on shutdown)."""
        with self.lock:
            for symbol in list(self.current_candles.keys()):
                self._complete_candle(symbol)

    def get_current_candle(self, symbol: str) -> Optional[Dict]:
        """
        Get the current (incomplete) candle for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Current candle dict or None
        """
        with self.lock:
            return self.current_candles.get(symbol)

    def get_status(self) -> Dict:
        """
        Get candle builder status.
        
        Returns:
            Status dictionary
        """
        with self.lock:
            return {
                'interval_minutes': self.interval_minutes,
                'active_candles': list(self.current_candles.keys()),
                'candle_details': {
                    symbol: {
                        'start_time': candle['timestamp'].strftime('%H:%M:%S'),
                        'tick_count': candle['tick_count'],
                        'price_range': f"{candle['low']:.2f} - {candle['high']:.2f}"
                    }
                    for symbol, candle in self.current_candles.items()
                }
            }
