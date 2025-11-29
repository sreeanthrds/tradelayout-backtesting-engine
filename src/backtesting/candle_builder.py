"""
Simple Candle Builder for DataManager
======================================

Lightweight candle builder that builds OHLCV candles from ticks.
Used by DataManager for incremental candle building.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class CandleBuilder:
    """
    Simple candle builder for tick-by-tick processing.
    
    Builds OHLCV candles and calls callback when candle completes.
    """
    
    def __init__(self, timeframe: str, on_candle_complete: Optional[Callable] = None, exchange: str = 'NSE'):
        """
        Initialize candle builder.
        
        Args:
            timeframe: Timeframe string (e.g., '1m', '5m', '15m')
            on_candle_complete: Callback function(symbol, candle_dict)
            exchange: Exchange name ('NSE', 'BSE', 'MCX') - determines market opening time
        """
        self.timeframe = timeframe
        self.on_candle_complete = on_candle_complete
        self.exchange = exchange.upper()
        
        # Parse timeframe to minutes
        self.interval_minutes = self._parse_timeframe(timeframe)
        
        # Market opening time based on exchange
        self.market_open_hour, self.market_open_minute = self._get_market_open_time()
        
        # Current candles being built {symbol: candle_dict}
        self.current_candles: Dict[str, dict] = {}
        
        logger.debug(f"CandleBuilder initialized: {timeframe} ({self.interval_minutes}m), Exchange: {self.exchange}, Market Open: {self.market_open_hour:02d}:{self.market_open_minute:02d}")
    
    def _get_market_open_time(self) -> tuple:
        """
        Get market opening time based on exchange.
        
        Returns:
            Tuple of (hour, minute) for market opening
        """
        # Market opening times for different exchanges
        market_times = {
            'NSE': (9, 15),   # 09:15 AM
            'BSE': (9, 15),   # 09:15 AM
            'MCX': (9, 0),    # 09:00 AM
            'NCDEX': (9, 0),  # 09:00 AM
        }
        
        return market_times.get(self.exchange, (9, 15))  # Default to NSE/BSE timing
    
    def _parse_timeframe(self, timeframe: str) -> int:
        """
        Parse timeframe string to minutes.
        
        Args:
            timeframe: Timeframe string (e.g., '1m', '5m', '15m', '1h')
        
        Returns:
            Interval in minutes
        """
        timeframe = timeframe.lower().strip()
        
        if timeframe.endswith('m'):
            return int(timeframe[:-1])
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 1440
        else:
            raise ValueError(f"Invalid timeframe format: {timeframe}")
    
    def _get_candle_start_time(self, timestamp: datetime) -> datetime:
        """
        Get candle start time for given timestamp based on market opening time.
        
        Args:
            timestamp: Current timestamp
        
        Returns:
            Candle start timestamp aligned to market opening time
        
        Example:
            Market opens at 09:15, timeframe is 5m
            - 09:16 -> 09:15 (first candle)
            - 09:20 -> 09:20 (second candle)
            - 09:24 -> 09:20 (second candle)
            - 09:25 -> 09:25 (third candle)
        """
        # Calculate minutes since market open
        market_open_minutes = self.market_open_hour * 60 + self.market_open_minute
        current_minutes = timestamp.hour * 60 + timestamp.minute
        
        # Minutes elapsed since market open
        minutes_since_open = current_minutes - market_open_minutes
        
        # If before market open, use market open time
        if minutes_since_open < 0:
            return timestamp.replace(
                hour=self.market_open_hour,
                minute=self.market_open_minute,
                second=0,
                microsecond=0
            )
        
        # Calculate candle index (0-based from market open)
        candle_index = minutes_since_open // self.interval_minutes
        
        # Calculate candle start time in minutes from market open
        candle_start_minutes_from_open = candle_index * self.interval_minutes
        
        # Convert back to absolute time
        candle_start_total_minutes = market_open_minutes + candle_start_minutes_from_open
        
        return timestamp.replace(
            hour=candle_start_total_minutes // 60,
            minute=candle_start_total_minutes % 60,
            second=0,
            microsecond=0
        )
    
    def process_tick(self, tick: dict) -> Optional[dict]:
        """
        Process a tick and update/complete candles.
        
        Args:
            tick: Tick data with symbol, timestamp, ltp
        
        Returns:
            Completed candle dict if candle completed, None otherwise
        """
        symbol = tick.get('symbol')
        timestamp = tick.get('timestamp')
        ltp = tick.get('ltp', 0.0)
        volume = tick.get('volume', 0)
        
        if not symbol or not timestamp:
            return None
        
        # Get candle start time
        candle_start = self._get_candle_start_time(timestamp)
        
        # Check if we have a current candle for this symbol
        if symbol not in self.current_candles:
            # Start new candle
            self.current_candles[symbol] = {
                'symbol': symbol,
                'timeframe': self.timeframe,
                'timestamp': candle_start,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': volume
            }
            return None
        
        current_candle = self.current_candles[symbol]
        
        # Check if tick belongs to current candle
        if candle_start == current_candle['timestamp']:
            # Update current candle
            current_candle['high'] = max(current_candle['high'], ltp)
            current_candle['low'] = min(current_candle['low'], ltp)
            current_candle['close'] = ltp
            current_candle['volume'] += volume
            return None
        else:
            # Candle completed - start new one
            completed_candle = current_candle.copy()
            
            # Start new candle
            self.current_candles[symbol] = {
                'symbol': symbol,
                'timeframe': self.timeframe,
                'timestamp': candle_start,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': volume
            }
            
            # Call callback if provided
            if self.on_candle_complete:
                self.on_candle_complete(symbol, completed_candle)
            
            return completed_candle
    
    def get_current_candle(self, symbol: str) -> Optional[dict]:
        """
        Get current incomplete candle for symbol.
        
        Args:
            symbol: Symbol name
        
        Returns:
            Current candle dict or None
        """
        return self.current_candles.get(symbol)
    
    def force_complete(self, symbol: str) -> Optional[dict]:
        """
        Force complete current candle for symbol.
        
        Args:
            symbol: Symbol name
        
        Returns:
            Completed candle dict or None
        """
        if symbol in self.current_candles:
            completed_candle = self.current_candles[symbol].copy()
            del self.current_candles[symbol]
            
            if self.on_candle_complete:
                self.on_candle_complete(symbol, completed_candle)
            
            return completed_candle
        return None
    
    def force_complete_all(self) -> Dict[str, dict]:
        """
        Force complete all current candles.
        
        Returns:
            Dict of {symbol: completed_candle}
        """
        completed = {}
        for symbol in list(self.current_candles.keys()):
            candle = self.force_complete(symbol)
            if candle:
                completed[symbol] = candle
        return completed
