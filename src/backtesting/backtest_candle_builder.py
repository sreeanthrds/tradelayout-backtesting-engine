"""
Backtest Candle Builder

Builds OHLCV candles from ticks during backtesting.
Writes to DataFrameWriter and updates DictCache.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BacktestCandleBuilder:
    """
    Builds candles from ticks for backtesting.
    
    Integrates with:
    - DataFrameWriter: Stores completed candles
    - DictCache: Updates last 10 candles cache
    """
    
    def __init__(
        self,
        data_writer,
        cache,
        interval_minutes: int = 1,
        timeframe: str = '1m',
        on_candle_complete=None
    ):
        """
        Initialize backtest candle builder.
        
        Args:
            data_writer: DataFrameWriter instance
            cache: DictCache instance
            interval_minutes: Candle interval in minutes
            timeframe: Timeframe string (e.g., '1m', '5m')
            on_candle_complete: Callback when candle completes
        """
        self.data_writer = data_writer
        self.cache = cache
        self.interval_minutes = interval_minutes
        self.timeframe = timeframe
        self.on_candle_complete = on_candle_complete
        
        # Current candles being built
        self.current_candles = {}  # {symbol: candle_dict}
        
        # Candle start times
        self.candle_start_times = {}  # {symbol: datetime}
        
        logger.info(f"🕯️ Backtest Candle Builder initialized ({timeframe})")
    
    def process_tick(self, tick_data: Dict):
        """
        Process a tick and update candle.
        
        Args:
            tick_data: Tick data with keys:
                - symbol: str
                - ltp: float
                - ltq: int (last traded quantity)
                - timestamp: datetime
        """
        symbol = tick_data.get('symbol')
        ltp = tick_data.get('ltp')
        ltq = tick_data.get('ltq', 0)
        timestamp = tick_data.get('timestamp')
        
        if not symbol or not ltp or not timestamp:
            return
        
        # Convert timestamp if needed
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        # Get candle start time
        candle_start = self._get_candle_start_time(timestamp)
        
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
                'timeframe': self.timeframe,
                'timestamp': candle_start,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': ltq,
                'tick_count': 1
            }
            self.candle_start_times[symbol] = candle_start
        else:
            # Update existing candle
            candle = self.current_candles[symbol]
            candle['high'] = max(candle['high'], ltp)
            candle['low'] = min(candle['low'], ltp)
            candle['close'] = ltp
            candle['volume'] += ltq
            candle['tick_count'] += 1
    
    def _get_candle_start_time(self, tick_time: datetime) -> datetime:
        """
        Get candle start time for a tick.
        
        Args:
            tick_time: Tick timestamp
        
        Returns:
            Candle start time (floored to interval)
        """
        # Floor to nearest interval
        minutes = (tick_time.minute // self.interval_minutes) * self.interval_minutes
        
        return tick_time.replace(
            minute=minutes,
            second=0,
            microsecond=0
        )
    
    def _complete_candle(self, symbol: str):
        """
        Complete and store a candle.
        
        Args:
            symbol: Trading symbol
        """
        if symbol not in self.current_candles:
            return
        
        candle = self.current_candles[symbol]
        
        # Write to DataFrame
        self.data_writer.write_candle(candle)
        
        # Update cache (add to last 10 candles)
        self.cache.add_candle(symbol, self.timeframe, candle)
        
        # Call callback (for indicator calculation)
        if self.on_candle_complete:
            self.on_candle_complete(candle)
        
        # Log completion (only every 100th candle to avoid spam)
        if candle['tick_count'] % 100 == 0 or candle['tick_count'] == 1:
            logger.debug(
                f"✅ [{symbol}] {self.timeframe} candle: "
                f"{candle['timestamp'].strftime('%H:%M')} "
                f"O:{candle['open']:.2f} H:{candle['high']:.2f} "
                f"L:{candle['low']:.2f} C:{candle['close']:.2f} "
                f"V:{candle['volume']} ({candle['tick_count']} ticks)"
            )
        
        # Remove completed candle
        del self.current_candles[symbol]
    
    def force_complete_all(self):
        """Force complete all current candles (end of day)."""
        for symbol in list(self.current_candles.keys()):
            self._complete_candle(symbol)
        
        logger.info(f"🏁 All {self.timeframe} candles completed")
    
    def get_current_candle(self, symbol: str) -> Optional[Dict]:
        """
        Get current (incomplete) candle.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Current candle or None
        """
        return self.current_candles.get(symbol)
    
    def get_stats(self) -> Dict:
        """
        Get builder statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            'timeframe': self.timeframe,
            'interval_minutes': self.interval_minutes,
            'active_candles': len(self.current_candles),
            'symbols': list(self.current_candles.keys())
        }
