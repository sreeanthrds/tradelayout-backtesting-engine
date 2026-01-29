"""
Shared Data Cache for Multi-Strategy Execution

Provides centralized caching of:
- Candles (per symbol:timeframe)
- Indicators (per symbol:timeframe:indicator)
- LTP (latest traded price per symbol)

Benefits:
- Eliminates duplicate data loading across strategies
- Shares indicator computation results
- Reduces memory footprint
- Faster strategy initialization

Architecture:
- Strategy-agnostic: Serves all strategies from single cache
- Lazy loading: Data loaded only when first requested
- Incremental updates: Tick-by-tick updates for live trading
"""

import logging
from typing import Dict, Any, Optional, Callable, Tuple
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class SharedDataCache:
    """
    Centralized data cache for multi-strategy execution.
    
    Manages three types of data:
    1. Candles: Raw OHLCV data per symbol:timeframe
    2. Indicators: Computed indicator values per symbol:timeframe:indicator
    3. LTP: Current price per symbol
    
    Thread-safe for single-threaded sequential execution (backtesting).
    For multi-threaded live trading, add locks if needed.
    """
    
    def __init__(self):
        """Initialize empty cache structures."""
        
        # Candle cache: {symbol: {timeframe: DataFrame}}
        # DataFrame has columns: timestamp, open, high, low, close, volume
        self._candle_cache: Dict[str, Dict[str, pd.DataFrame]] = {}
        
        # Indicator cache: {symbol: {timeframe: {indicator_key: Series/DataFrame}}}
        # indicator_key format: "ema(21,close)" or "rsi(14,close)"
        self._indicator_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        
        # LTP store: {symbol: (price, timestamp)}
        # Stores latest traded price with timestamp
        self._ltp_store: Dict[str, Tuple[float, datetime]] = {}
        
        # Statistics for monitoring
        self._stats = {
            'candle_loads': 0,  # Total candle load operations
            'candle_hits': 0,   # Cache hits for candles
            'indicator_computes': 0,  # Total indicator computations
            'indicator_hits': 0,  # Cache hits for indicators
            'ltp_updates': 0,   # Total LTP updates
            'symbols_cached': set(),  # Unique symbols in cache
            'timeframes_cached': set(),  # Unique timeframes in cache
        }
        
        logger.info("📦 SharedDataCache initialized")
    
    # ========================================================================
    # CANDLE CACHE METHODS
    # ========================================================================
    
    def get_or_load_candles(
        self,
        symbol: str,
        timeframe: str,
        loader_func: Callable[[str, str], pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Get candles from cache or load if not present.
        
        Args:
            symbol: Trading symbol (e.g., "NIFTY")
            timeframe: Timeframe (e.g., "1m", "5m")
            loader_func: Function to load candles if not cached
                         Signature: (symbol, timeframe) -> DataFrame
        
        Returns:
            DataFrame with candles (may be cached or freshly loaded)
        """
        # Check cache
        if symbol in self._candle_cache:
            if timeframe in self._candle_cache[symbol]:
                self._stats['candle_hits'] += 1
                logger.debug(f"✅ Cache HIT: {symbol}:{timeframe} candles")
                return self._candle_cache[symbol][timeframe]
        
        # Cache miss - load data
        logger.info(f"📥 Loading {symbol}:{timeframe} candles (not in cache)")
        candles = loader_func(symbol, timeframe)
        
        # Store in cache
        if symbol not in self._candle_cache:
            self._candle_cache[symbol] = {}
        self._candle_cache[symbol][timeframe] = candles
        
        # Update stats
        self._stats['candle_loads'] += 1
        self._stats['symbols_cached'].add(symbol)
        self._stats['timeframes_cached'].add(timeframe)
        
        logger.info(f"✅ Cached {len(candles)} candles for {symbol}:{timeframe}")
        return candles
    
    def get_candles(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get candles from cache (without loading if missing).
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            DataFrame if cached, None otherwise
        """
        if symbol in self._candle_cache:
            return self._candle_cache[symbol].get(timeframe)
        return None
    
    def append_candle(self, symbol: str, timeframe: str, candle: Dict[str, Any]) -> None:
        """
        Append a new candle to existing cached data.
        Used during live trading when new candles close.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            candle: Dict with keys: timestamp, open, high, low, close, volume
        """
        if symbol not in self._candle_cache:
            logger.warning(f"Cannot append candle - {symbol} not in cache")
            return
        
        if timeframe not in self._candle_cache[symbol]:
            logger.warning(f"Cannot append candle - {symbol}:{timeframe} not in cache")
            return
        
        # Convert candle dict to DataFrame row
        candle_df = pd.DataFrame([candle])
        
        # Append to existing data
        self._candle_cache[symbol][timeframe] = pd.concat(
            [self._candle_cache[symbol][timeframe], candle_df],
            ignore_index=True
        )
        
        logger.debug(f"➕ Appended candle to {symbol}:{timeframe}")
    
    def update_last_candle(
        self,
        symbol: str,
        timeframe: str,
        candle_updates: Dict[str, Any]
    ) -> None:
        """
        Update the last (current forming) candle in cache.
        Used during live trading for tick-by-tick updates.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            candle_updates: Dict with fields to update (e.g., {'high': 25900, 'close': 25890})
        """
        if symbol not in self._candle_cache:
            return
        
        if timeframe not in self._candle_cache[symbol]:
            return
        
        df = self._candle_cache[symbol][timeframe]
        if len(df) == 0:
            return
        
        # Update last row
        for key, value in candle_updates.items():
            if key in df.columns:
                df.iloc[-1, df.columns.get_loc(key)] = value
        
        logger.debug(f"🔄 Updated last candle for {symbol}:{timeframe}")
    
    # ========================================================================
    # INDICATOR CACHE METHODS
    # ========================================================================
    
    def get_or_compute_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator_key: str,
        compute_func: Callable[[pd.DataFrame], Any]
    ) -> Any:
        """
        Get indicator from cache or compute if not present.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_key: Unique indicator key (e.g., "ema(21,close)")
            compute_func: Function to compute indicator if not cached
                         Signature: (candles_df) -> Series/DataFrame
        
        Returns:
            Indicator values (Series or DataFrame)
        """
        # Check cache
        if symbol in self._indicator_cache:
            if timeframe in self._indicator_cache[symbol]:
                if indicator_key in self._indicator_cache[symbol][timeframe]:
                    self._stats['indicator_hits'] += 1
                    logger.debug(f"✅ Cache HIT: {symbol}:{timeframe} {indicator_key}")
                    return self._indicator_cache[symbol][timeframe][indicator_key]
        
        # Cache miss - compute indicator
        logger.info(f"🔢 Computing {indicator_key} for {symbol}:{timeframe}")
        
        # Get candles (should already be cached)
        candles = self.get_candles(symbol, timeframe)
        if candles is None:
            raise ValueError(f"Cannot compute indicator - no candles for {symbol}:{timeframe}")
        
        # Compute indicator
        indicator_values = compute_func(candles)
        
        # Store in cache
        if symbol not in self._indicator_cache:
            self._indicator_cache[symbol] = {}
        if timeframe not in self._indicator_cache[symbol]:
            self._indicator_cache[symbol][timeframe] = {}
        self._indicator_cache[symbol][timeframe][indicator_key] = indicator_values
        
        # Update stats
        self._stats['indicator_computes'] += 1
        
        logger.info(f"✅ Cached {indicator_key} for {symbol}:{timeframe}")
        return indicator_values
    
    def get_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator_key: str
    ) -> Optional[Any]:
        """
        Get indicator from cache (without computing if missing).
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_key: Unique indicator key
        
        Returns:
            Indicator values if cached, None otherwise
        """
        if symbol in self._indicator_cache:
            if timeframe in self._indicator_cache[symbol]:
                return self._indicator_cache[symbol][timeframe].get(indicator_key)
        return None
    
    def update_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator_key: str,
        new_value: Any
    ) -> None:
        """
        Update indicator with new computed value.
        Used for incremental indicator updates.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_key: Unique indicator key
            new_value: New indicator value to append/update
        """
        if symbol not in self._indicator_cache:
            self._indicator_cache[symbol] = {}
        if timeframe not in self._indicator_cache[symbol]:
            self._indicator_cache[symbol][timeframe] = {}
        
        # If indicator exists, append/update
        if indicator_key in self._indicator_cache[symbol][timeframe]:
            existing = self._indicator_cache[symbol][timeframe][indicator_key]
            
            # If Series, append new value
            if isinstance(existing, pd.Series) and isinstance(new_value, (int, float)):
                self._indicator_cache[symbol][timeframe][indicator_key] = pd.concat(
                    [existing, pd.Series([new_value])],
                    ignore_index=True
                )
            # If DataFrame, append new row
            elif isinstance(existing, pd.DataFrame) and isinstance(new_value, dict):
                new_row = pd.DataFrame([new_value])
                self._indicator_cache[symbol][timeframe][indicator_key] = pd.concat(
                    [existing, new_row],
                    ignore_index=True
                )
        else:
            # First value for this indicator
            self._indicator_cache[symbol][timeframe][indicator_key] = new_value
        
        logger.debug(f"🔄 Updated {indicator_key} for {symbol}:{timeframe}")
    
    # ========================================================================
    # LTP STORE METHODS
    # ========================================================================
    
    def update_ltp(self, symbol: str, price: float, timestamp: datetime = None) -> None:
        """
        Update latest traded price for a symbol.
        
        Args:
            symbol: Trading symbol
            price: Latest price
            timestamp: Timestamp of price (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self._ltp_store[symbol] = (price, timestamp)
        self._stats['ltp_updates'] += 1
        
        logger.debug(f"💰 LTP updated: {symbol} = {price}")
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get latest traded price for a symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Latest price if available, None otherwise
        """
        if symbol in self._ltp_store:
            return self._ltp_store[symbol][0]  # Return price only
        return None
    
    def get_ltp_with_timestamp(self, symbol: str) -> Optional[Tuple[float, datetime]]:
        """
        Get latest traded price with timestamp.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Tuple of (price, timestamp) if available, None otherwise
        """
        return self._ltp_store.get(symbol)
    
    def get_all_ltp(self) -> Dict[str, float]:
        """
        Get all LTPs as a dictionary.
        
        Returns:
            Dict mapping symbol to price
        """
        return {symbol: price for symbol, (price, ts) in self._ltp_store.items()}
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def clear_cache(self) -> None:
        """Clear all cached data. Use with caution."""
        self._candle_cache.clear()
        self._indicator_cache.clear()
        self._ltp_store.clear()
        logger.info("🗑️ Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache performance metrics
        """
        stats = self._stats.copy()
        
        # Convert sets to counts
        stats['symbols_cached'] = len(stats['symbols_cached'])
        stats['timeframes_cached'] = len(stats['timeframes_cached'])
        
        # Calculate hit rates
        total_candle_requests = stats['candle_loads'] + stats['candle_hits']
        stats['candle_hit_rate'] = (
            stats['candle_hits'] / total_candle_requests * 100
            if total_candle_requests > 0 else 0
        )
        
        total_indicator_requests = stats['indicator_computes'] + stats['indicator_hits']
        stats['indicator_hit_rate'] = (
            stats['indicator_hits'] / total_indicator_requests * 100
            if total_indicator_requests > 0 else 0
        )
        
        # Memory estimates (rough)
        stats['candle_entries'] = sum(
            len(tfs) for tfs in self._candle_cache.values()
        )
        stats['indicator_entries'] = sum(
            sum(len(inds) for inds in tfs.values())
            for tfs in self._indicator_cache.values()
        )
        stats['ltp_entries'] = len(self._ltp_store)
        
        return stats
    
    def print_stats(self) -> None:
        """Print cache statistics to console."""
        stats = self.get_stats()
        
        print("\n" + "="*80)
        print("📊 SHARED DATA CACHE STATISTICS")
        print("="*80)
        
        print("\n🗂️  Cache Contents:")
        print(f"   Symbols cached      : {stats['symbols_cached']}")
        print(f"   Timeframes cached   : {stats['timeframes_cached']}")
        print(f"   Candle entries      : {stats['candle_entries']}")
        print(f"   Indicator entries   : {stats['indicator_entries']}")
        print(f"   LTP entries         : {stats['ltp_entries']}")
        
        print("\n📈 Performance Metrics:")
        print(f"   Candle loads        : {stats['candle_loads']}")
        print(f"   Candle hits         : {stats['candle_hits']}")
        print(f"   Candle hit rate     : {stats['candle_hit_rate']:.1f}%")
        print(f"   Indicator computes  : {stats['indicator_computes']}")
        print(f"   Indicator hits      : {stats['indicator_hits']}")
        print(f"   Indicator hit rate  : {stats['indicator_hit_rate']:.1f}%")
        print(f"   LTP updates         : {stats['ltp_updates']}")
        
        print("="*80 + "\n")
    
    def __repr__(self) -> str:
        """String representation of cache state."""
        stats = self.get_stats()
        return (
            f"SharedDataCache("
            f"symbols={stats['symbols_cached']}, "
            f"candles={stats['candle_entries']}, "
            f"indicators={stats['indicator_entries']}, "
            f"ltp={stats['ltp_entries']})"
        )
