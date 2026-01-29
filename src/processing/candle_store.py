"""
Candle Store - Hybrid Redis + ClickHouse Storage
=================================================

Strategy:
- Redis: Last 10 closed candles per symbol-timeframe (fast access)
- ClickHouse: Full history (1 year retention)
- Fallback: Query ClickHouse if expression needs > 10 candles

Author: TradeLayout Engine
Date: 2025-11-05
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import redis
from clickhouse_driver import Client as ClickHouseClient


class CandleStore:
    """
    Hybrid candle storage using Redis (cache) and ClickHouse (persistent).
    
    Features:
    - Last 10 candles in Redis for fast access
    - Full history in ClickHouse
    - Automatic fallback to ClickHouse for historical queries
    - Batch inserts for performance
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        clickhouse_client: ClickHouseClient,
        max_cached_candles: int = 10,
        cache_ttl: int = 3600,
        batch_size: int = 100
    ):
        """
        Initialize CandleStore.
        
        Args:
            redis_client: Redis client instance
            clickhouse_client: ClickHouse client instance
            max_cached_candles: Number of candles to keep in Redis (default: 10)
            cache_ttl: Redis cache TTL in seconds (default: 3600 = 1 hour)
            batch_size: ClickHouse batch insert size (default: 100)
        """
        self.redis = redis_client
        self.clickhouse = clickhouse_client
        self.max_cached_candles = max_cached_candles
        self.cache_ttl = cache_ttl
        self.batch_size = batch_size
        
        # Batch buffer for ClickHouse inserts
        self.batch_buffer: List[Dict[str, Any]] = []
    
    def add_candle(
        self,
        symbol: str,
        timeframe: str,
        candle: Dict[str, Any],
        exchange: str = 'NSE'
    ) -> None:
        """
        Add a closed candle to both Redis and ClickHouse.
        
        Args:
            symbol: Trading symbol (e.g., 'NIFTY', 'BANKNIFTY')
            timeframe: Candle timeframe (e.g., '1m', '5m', '15m')
            candle: Candle data dict with keys: ts, open, high, low, close, volume
            exchange: Exchange name (default: 'NSE')
        
        Example:
            store.add_candle('NIFTY', '5m', {
                'ts': datetime(2025, 11, 5, 9, 25),
                'open': 25900.00,
                'high': 25920.00,
                'low': 25890.00,
                'close': 25910.00,
                'volume': 1000000,
                'tick_count': 150
            })
        """
        # 1. Add to Redis cache
        self._add_to_redis_cache(symbol, timeframe, candle)
        
        # 2. Add to ClickHouse batch buffer
        self._add_to_clickhouse_batch(symbol, timeframe, candle, exchange)
    
    def _add_to_redis_cache(
        self,
        symbol: str,
        timeframe: str,
        candle: Dict[str, Any]
    ) -> None:
        """Add candle to Redis cache (last 10 candles)."""
        key = f"candles:{symbol}:{timeframe}"
        
        try:
            # Get existing candles
            data = self.redis.get(key)
            candles = json.loads(data) if data else []
            
            # Add new candle
            candles.append({
                'ts': candle['ts'].isoformat() if isinstance(candle['ts'], datetime) else candle['ts'],
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),
                'volume': int(candle['volume'])
            })
            
            # Keep only last N candles
            if len(candles) > self.max_cached_candles:
                candles = candles[-self.max_cached_candles:]
            
            # Save to Redis with TTL
            self.redis.setex(
                key,
                self.cache_ttl,
                json.dumps(candles)
            )
            
        except Exception as e:
            print(f"❌ Error adding candle to Redis: {e}")
            # Don't fail if Redis is down, ClickHouse is the source of truth
    
    def _add_to_clickhouse_batch(
        self,
        symbol: str,
        timeframe: str,
        candle: Dict[str, Any],
        exchange: str
    ) -> None:
        """Add candle to ClickHouse batch buffer."""
        self.batch_buffer.append({
            'ts': candle['ts'],
            'symbol': symbol,
            'timeframe': timeframe,
            'exchange': exchange,
            'open': Decimal(str(candle['open'])),
            'high': Decimal(str(candle['high'])),
            'low': Decimal(str(candle['low'])),
            'close': Decimal(str(candle['close'])),
            'volume': int(candle['volume']),
            'is_closed': 1,
            'tick_count': candle.get('tick_count', 0)
        })
        
        # Flush if batch is full
        if len(self.batch_buffer) >= self.batch_size:
            self.flush_to_clickhouse()
    
    def flush_to_clickhouse(self) -> None:
        """Flush batch buffer to ClickHouse."""
        if not self.batch_buffer:
            return
        
        try:
            self.clickhouse.execute(
                """
                INSERT INTO ohlcv_candles 
                (ts, symbol, timeframe, exchange, open, high, low, close, volume, is_closed, tick_count)
                VALUES
                """,
                self.batch_buffer
            )
            
            print(f"✅ Flushed {len(self.batch_buffer)} candles to ClickHouse")
            self.batch_buffer = []
            
        except Exception as e:
            print(f"❌ Error flushing to ClickHouse: {e}")
            # Keep buffer for retry
    
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        n: int = 10,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get last N candles for a symbol-timeframe.
        
        Strategy:
        1. Try Redis cache first (if n <= 10 and use_cache=True)
        2. Fallback to ClickHouse if cache miss or n > 10
        3. Update cache with fetched data
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            n: Number of candles to fetch (default: 10)
            use_cache: Whether to use Redis cache (default: True)
        
        Returns:
            List of candle dicts in chronological order (oldest first)
        
        Example:
            candles = store.get_candles('NIFTY', '5m', n=20)
            # Returns last 20 candles from ClickHouse
        """
        # Try Redis cache first (if applicable)
        if use_cache and n <= self.max_cached_candles:
            cached_candles = self._get_from_redis_cache(symbol, timeframe)
            if cached_candles and len(cached_candles) >= n:
                return cached_candles[-n:]
        
        # Fallback to ClickHouse
        return self._fetch_from_clickhouse(symbol, timeframe, n)
    
    def _get_from_redis_cache(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get candles from Redis cache."""
        key = f"candles:{symbol}:{timeframe}"
        
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"⚠️ Redis cache miss: {e}")
        
        return None
    
    def _fetch_from_clickhouse(
        self,
        symbol: str,
        timeframe: str,
        n: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch candles from ClickHouse.
        
        Returns candles in chronological order (oldest first).
        """
        try:
            query = """
            SELECT
                ts,
                open,
                high,
                low,
                close,
                volume
            FROM ohlcv_candles
            WHERE symbol = %(symbol)s
              AND timeframe = %(timeframe)s
              AND is_closed = 1
            ORDER BY ts DESC
            LIMIT %(limit)s
            """
            
            result = self.clickhouse.execute(
                query,
                {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'limit': n
                }
            )
            
            # Convert to list of dicts (reverse for chronological order)
            candles = [
                {
                    'ts': row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
                    'open': float(row[1]),
                    'high': float(row[2]),
                    'low': float(row[3]),
                    'close': float(row[4]),
                    'volume': int(row[5])
                }
                for row in reversed(result)  # Reverse to get chronological order
            ]
            
            # Update Redis cache with latest candles
            if candles:
                self._update_redis_cache(symbol, timeframe, candles[-self.max_cached_candles:])
            
            return candles
            
        except Exception as e:
            print(f"❌ Error fetching from ClickHouse: {e}")
            return []
    
    def _update_redis_cache(
        self,
        symbol: str,
        timeframe: str,
        candles: List[Dict[str, Any]]
    ) -> None:
        """Update Redis cache with candles."""
        key = f"candles:{symbol}:{timeframe}"
        
        try:
            self.redis.setex(
                key,
                self.cache_ttl,
                json.dumps(candles)
            )
        except Exception as e:
            print(f"⚠️ Error updating Redis cache: {e}")
    
    def get_candles_in_range(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get candles in a specific time range.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
            start_time: Start timestamp (inclusive)
            end_time: End timestamp (inclusive)
        
        Returns:
            List of candle dicts in chronological order
        
        Example:
            candles = store.get_candles_in_range(
                'NIFTY',
                '5m',
                datetime(2025, 11, 5, 9, 15),
                datetime(2025, 11, 5, 15, 30)
            )
        """
        try:
            query = """
            SELECT
                ts,
                open,
                high,
                low,
                close,
                volume
            FROM ohlcv_candles
            WHERE symbol = %(symbol)s
              AND timeframe = %(timeframe)s
              AND ts >= %(start_time)s
              AND ts <= %(end_time)s
              AND is_closed = 1
            ORDER BY ts ASC
            """
            
            result = self.clickhouse.execute(
                query,
                {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'start_time': start_time,
                    'end_time': end_time
                }
            )
            
            return [
                {
                    'ts': row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
                    'open': float(row[1]),
                    'high': float(row[2]),
                    'low': float(row[3]),
                    'close': float(row[4]),
                    'volume': int(row[5])
                }
                for row in result
            ]
            
        except Exception as e:
            print(f"❌ Error fetching range from ClickHouse: {e}")
            return []
    
    def get_latest_candle(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest closed candle for a symbol-timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Candle timeframe
        
        Returns:
            Latest candle dict or None
        """
        candles = self.get_candles(symbol, timeframe, n=1)
        return candles[0] if candles else None
    
    def clear_cache(self, symbol: str = None, timeframe: str = None) -> None:
        """
        Clear Redis cache.
        
        Args:
            symbol: If provided, clear only this symbol (default: clear all)
            timeframe: If provided, clear only this timeframe (default: clear all)
        """
        try:
            if symbol and timeframe:
                # Clear specific key
                key = f"candles:{symbol}:{timeframe}"
                self.redis.delete(key)
            elif symbol:
                # Clear all timeframes for symbol
                pattern = f"candles:{symbol}:*"
                keys = self.redis.keys(pattern)
                if keys:
                    self.redis.delete(*keys)
            else:
                # Clear all candle keys
                pattern = "candles:*"
                keys = self.redis.keys(pattern)
                if keys:
                    self.redis.delete(*keys)
            
            print(f"✅ Cleared Redis cache")
            
        except Exception as e:
            print(f"❌ Error clearing cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with cache stats (total keys, memory usage, etc.)
        """
        try:
            pattern = "candles:*"
            keys = self.redis.keys(pattern)
            
            total_candles = 0
            for key in keys:
                data = self.redis.get(key)
                if data:
                    candles = json.loads(data)
                    total_candles += len(candles)
            
            return {
                'total_keys': len(keys),
                'total_candles': total_candles,
                'avg_candles_per_key': total_candles / len(keys) if keys else 0,
                'max_cached_candles': self.max_cached_candles,
                'cache_ttl': self.cache_ttl
            }
            
        except Exception as e:
            print(f"❌ Error getting cache stats: {e}")
            return {}


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Initialize clients
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    clickhouse_client = ClickHouseClient(host='localhost')
    
    # Create candle store
    store = CandleStore(
        redis_client=redis_client,
        clickhouse_client=clickhouse_client,
        max_cached_candles=10,
        cache_ttl=3600
    )
    
    # Add candles
    for i in range(15):
        store.add_candle(
            symbol='NIFTY',
            timeframe='5m',
            candle={
                'ts': datetime(2025, 11, 5, 9, 15) + timedelta(minutes=5*i),
                'open': 25900 + i,
                'high': 25920 + i,
                'low': 25890 + i,
                'close': 25910 + i,
                'volume': 1000000 + i*10000,
                'tick_count': 150
            }
        )
    
    # Flush to ClickHouse
    store.flush_to_clickhouse()
    
    # Get last 5 candles (from Redis cache)
    candles = store.get_candles('NIFTY', '5m', n=5)
    print(f"Last 5 candles (from cache): {len(candles)}")
    
    # Get last 20 candles (from ClickHouse)
    candles = store.get_candles('NIFTY', '5m', n=20)
    print(f"Last 20 candles (from ClickHouse): {len(candles)}")
    
    # Get cache stats
    stats = store.get_cache_stats()
    print(f"Cache stats: {stats}")
