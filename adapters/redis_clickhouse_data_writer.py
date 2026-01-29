"""
Redis + ClickHouse DataWriter Implementation

Writes data to Redis (cache) and ClickHouse (DB).
ZERO dependency on old context!
"""

import json
import redis.asyncio as redis
from clickhouse_driver import Client
from typing import List, Dict, Any
from datetime import datetime
import logging

from interfaces.data_writer import DataWriterInterface


logger = logging.getLogger(__name__)


class RedisClickHouseDataWriter(DataWriterInterface):
    """
    DataWriter implementation using Redis (cache) and ClickHouse (DB).
    
    Write Strategy:
    - Write to ClickHouse first (persistence)
    - Then update Redis cache (speed)
    - If ClickHouse fails, log error but don't fail
    - If Redis fails, log warning but continue
    """
    
    def __init__(
        self,
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        redis_db: int = 0,
        clickhouse_host: str = 'localhost',
        clickhouse_port: int = 9000,
        clickhouse_database: str = 'tradelayout',
        clickhouse_user: str = 'default',
        clickhouse_password: str = '',
        clickhouse_secure: bool = False
    ):
        """Initialize Redis and ClickHouse connections."""
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.clickhouse_host = clickhouse_host
        self.clickhouse_port = clickhouse_port
        self.clickhouse_database = clickhouse_database
        self.clickhouse_user = clickhouse_user
        self.clickhouse_password = clickhouse_password
        self.clickhouse_secure = clickhouse_secure
        
        # Will be initialized in connect()
        self.redis_client = None
        self.clickhouse_client = None
    
    async def connect(self):
        """Establish connections to Redis and ClickHouse."""
        # Redis connection (async)
        self.redis_client = await redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            decode_responses=True
        )
        
        # ClickHouse connection (sync)
        self.clickhouse_client = Client(
            host=self.clickhouse_host,
            port=self.clickhouse_port,
            database=self.clickhouse_database,
            user=self.clickhouse_user,
            password=self.clickhouse_password,
            secure=self.clickhouse_secure
        )
        
        logger.info(f"DataWriter connected to Redis and ClickHouse")
    
    async def disconnect(self):
        """Close connections."""
        if self.redis_client:
            await self.redis_client.close()
        if self.clickhouse_client:
            self.clickhouse_client.disconnect()
    
    # ========================================================================
    # CANDLES
    # ========================================================================
    
    async def store_candle(
        self,
        symbol: str,
        timeframe: str,
        candle: Dict[str, Any]
    ) -> None:
        """Store a single candle."""
        try:
            # Write to ClickHouse
            data = [(
                candle['ts'],
                symbol,
                timeframe,
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                candle['volume'],
                candle.get('is_closed', 1),
                datetime.now(),
                datetime.now()
            )]
            
            self.clickhouse_client.execute(
                'INSERT INTO ohlcv_candles VALUES',
                data
            )
            
            logger.debug(f"Stored candle: {symbol} {timeframe} {candle['ts']}")
            
        except Exception as e:
            logger.error(f"Error storing candle to ClickHouse: {e}")
            raise
        
        # Update Redis cache
        try:
            cache_key = f"candles:{symbol}:{timeframe}"
            
            # Get existing candles
            cached = await self.redis_client.get(cache_key)
            if cached:
                candles = json.loads(cached)
            else:
                candles = []
            
            # Add new candle
            candles.append({
                'ts': candle['ts'].isoformat() if isinstance(candle['ts'], datetime) else str(candle['ts']),
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),
                'volume': int(candle['volume'])
            })
            
            # Keep only last 500 candles in cache
            if len(candles) > 500:
                candles = candles[-500:]
            
            # Update cache
            await self.redis_client.setex(
                cache_key,
                3600,  # 1 hour TTL
                json.dumps(candles)
            )
            
        except Exception as e:
            logger.warning(f"Error updating Redis cache for candle: {e}")
    
    async def store_candles_batch(
        self,
        symbol: str,
        timeframe: str,
        candles: List[Dict[str, Any]]
    ) -> None:
        """Store multiple candles in batch."""
        if not candles:
            return
        
        try:
            # Prepare batch data
            data = []
            for candle in candles:
                data.append((
                    candle['ts'],
                    symbol,
                    timeframe,
                    candle['open'],
                    candle['high'],
                    candle['low'],
                    candle['close'],
                    candle['volume'],
                    candle.get('is_closed', 1),
                    datetime.now(),
                    datetime.now()
                ))
            
            # Batch insert to ClickHouse
            self.clickhouse_client.execute(
                'INSERT INTO ohlcv_candles VALUES',
                data
            )
            
            logger.info(f"Stored {len(candles)} candles: {symbol} {timeframe}")
            
        except Exception as e:
            logger.error(f"Error storing candles batch to ClickHouse: {e}")
            raise
        
        # Update Redis cache
        try:
            cache_key = f"candles:{symbol}:{timeframe}"
            
            # Convert candles to cache format
            cache_candles = []
            for candle in candles:
                cache_candles.append({
                    'ts': candle['ts'].isoformat() if isinstance(candle['ts'], datetime) else str(candle['ts']),
                    'open': float(candle['open']),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'close': float(candle['close']),
                    'volume': int(candle['volume'])
                })
            
            # Keep only last 500
            if len(cache_candles) > 500:
                cache_candles = cache_candles[-500:]
            
            # Update cache
            await self.redis_client.setex(
                cache_key,
                3600,
                json.dumps(cache_candles)
            )
            
        except Exception as e:
            logger.warning(f"Error updating Redis cache for candles batch: {e}")
    
    # ========================================================================
    # INDICATORS
    # ========================================================================
    
    async def store_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator_name: str,
        value: float,
        timestamp: datetime
    ) -> None:
        """Store a single indicator value."""
        try:
            # Write to ClickHouse
            data = [(timestamp, symbol, timeframe, indicator_name, value, datetime.now())]
            
            self.clickhouse_client.execute(
                'INSERT INTO indicator_values VALUES',
                data
            )
            
            logger.debug(f"Stored indicator: {symbol} {timeframe} {indicator_name} = {value}")
            
        except Exception as e:
            logger.error(f"Error storing indicator to ClickHouse: {e}")
            raise
        
        # Update Redis cache
        try:
            cache_key = f"indicators:{symbol}:{timeframe}"
            
            # Get existing indicators
            cached = await self.redis_client.get(cache_key)
            if cached:
                indicators = json.loads(cached)
            else:
                indicators = {}
            
            # Update indicator
            indicators[indicator_name] = float(value)
            
            # Update cache
            await self.redis_client.setex(
                cache_key,
                60,  # 1 minute TTL
                json.dumps(indicators)
            )
            
        except Exception as e:
            logger.warning(f"Error updating Redis cache for indicator: {e}")
    
    async def store_indicators_batch(
        self,
        symbol: str,
        timeframe: str,
        indicators: Dict[str, float],
        timestamp: datetime
    ) -> None:
        """Store multiple indicators in batch."""
        if not indicators:
            return
        
        try:
            # Prepare batch data
            data = []
            for indicator_name, value in indicators.items():
                data.append((timestamp, symbol, timeframe, indicator_name, value, datetime.now()))
            
            # Batch insert to ClickHouse
            self.clickhouse_client.execute(
                'INSERT INTO indicator_values VALUES',
                data
            )
            
            logger.info(f"Stored {len(indicators)} indicators: {symbol} {timeframe}")
            
        except Exception as e:
            logger.error(f"Error storing indicators batch to ClickHouse: {e}")
            raise
        
        # Update Redis cache
        try:
            cache_key = f"indicators:{symbol}:{timeframe}"
            
            # Convert to cache format
            cache_indicators = {k: float(v) for k, v in indicators.items()}
            
            # Update cache
            await self.redis_client.setex(
                cache_key,
                60,
                json.dumps(cache_indicators)
            )
            
        except Exception as e:
            logger.warning(f"Error updating Redis cache for indicators batch: {e}")
    
    # ========================================================================
    # TICKS
    # ========================================================================
    
    async def store_tick(
        self,
        symbol: str,
        exchange: str,
        tick: Dict[str, Any]
    ) -> None:
        """Store a single tick."""
        try:
            # Write to ClickHouse
            data = [(
                tick['timestamp'],
                symbol,
                exchange,
                tick.get('ltp', 0),
                tick.get('volume', 0),
                tick.get('oi', 0),
                tick.get('bid', 0),
                tick.get('ask', 0),
                tick.get('bid_qty', 0),
                tick.get('ask_qty', 0),
                datetime.now()
            )]
            
            self.clickhouse_client.execute(
                'INSERT INTO raw_ticks VALUES',
                data
            )
            
        except Exception as e:
            logger.error(f"Error storing tick to ClickHouse: {e}")
            # Don't raise - ticks are high volume, don't want to stop on error
        
        # Update Redis with latest LTP
        try:
            cache_key = f"ltp:{symbol}"
            
            ltp_data = {
                'ltp': float(tick.get('ltp', 0)),
                'timestamp': tick['timestamp'].isoformat() if isinstance(tick['timestamp'], datetime) else str(tick['timestamp']),
                'volume': int(tick.get('volume', 0)),
                'oi': int(tick.get('oi', 0)),
                'bid': float(tick.get('bid', 0)),
                'ask': float(tick.get('ask', 0)),
                'bid_qty': int(tick.get('bid_qty', 0)),
                'ask_qty': int(tick.get('ask_qty', 0))
            }
            
            await self.redis_client.setex(
                cache_key,
                10,  # 10 seconds TTL
                json.dumps(ltp_data)
            )
            
        except Exception as e:
            logger.warning(f"Error updating Redis cache for tick: {e}")
    
    # ========================================================================
    # NODE VARIABLES
    # ========================================================================
    
    async def update_node_variable(
        self,
        user_id: str,
        strategy_id: str,
        node_id: str,
        variable_name: str,
        value: float
    ) -> None:
        """Update node variable value."""
        try:
            # Write to ClickHouse
            data = [(user_id, strategy_id, node_id, variable_name, value, datetime.now())]
            
            self.clickhouse_client.execute(
                'INSERT INTO node_variables VALUES',
                data
            )
            
        except Exception as e:
            logger.error(f"Error storing node variable to ClickHouse: {e}")
            raise
        
        # Update Redis cache
        try:
            cache_key = f"node_var:{user_id}:{strategy_id}:{node_id}:{variable_name}"
            await self.redis_client.setex(cache_key, 60, str(value))
            
        except Exception as e:
            logger.warning(f"Error updating Redis cache for node variable: {e}")
    
    # ========================================================================
    # NODE STATES
    # ========================================================================
    
    async def update_node_state(
        self,
        user_id: str,
        strategy_id: str,
        node_id: str,
        status: str,
        visited: bool = None,
        re_entry_num: int = None
    ) -> None:
        """Update node state."""
        try:
            # Get current state first
            query = """
            SELECT status, visited, re_entry_num
            FROM node_states
            WHERE user_id = %(user_id)s
              AND strategy_id = %(strategy_id)s
              AND node_id = %(node_id)s
            ORDER BY updated_at DESC
            LIMIT 1
            """
            
            result = self.clickhouse_client.execute(
                query,
                {'user_id': user_id, 'strategy_id': strategy_id, 'node_id': node_id}
            )
            
            # Use current values if not provided
            if result:
                current_status, current_visited, current_re_entry = result[0]
                if visited is None:
                    visited = bool(current_visited)
                if re_entry_num is None:
                    re_entry_num = int(current_re_entry)
            else:
                if visited is None:
                    visited = False
                if re_entry_num is None:
                    re_entry_num = 0
            
            # Write to ClickHouse
            data = [(user_id, strategy_id, node_id, status, int(visited), re_entry_num, datetime.now())]
            
            self.clickhouse_client.execute(
                'INSERT INTO node_states VALUES',
                data
            )
            
        except Exception as e:
            logger.error(f"Error storing node state to ClickHouse: {e}")
            raise
        
        # Update Redis cache
        try:
            cache_key = f"node_state:{user_id}:{strategy_id}:{node_id}"
            
            state = {
                'status': status,
                'visited': visited,
                're_entry_num': re_entry_num
            }
            
            await self.redis_client.setex(
                cache_key,
                60,
                json.dumps(state)
            )
            
        except Exception as e:
            logger.warning(f"Error updating Redis cache for node state: {e}")
    
    # ========================================================================
    # POSITIONS
    # ========================================================================
    
    async def store_position(
        self,
        position: Dict[str, Any]
    ) -> None:
        """Store/update position."""
        try:
            # Write to ClickHouse
            data = [(
                position['position_id'],
                position['user_id'],
                position['strategy_id'],
                position['symbol'],
                position['exchange'],
                position['transaction_type'],
                position['quantity'],
                position['entry_price'],
                position.get('current_price', position['entry_price']),
                position.get('pnl', 0),
                position['status'],
                position['entry_time'],
                position.get('exit_time'),
                position.get('exit_price'),
                datetime.now(),
                datetime.now()
            )]
            
            self.clickhouse_client.execute(
                'INSERT INTO positions VALUES',
                data
            )
            
        except Exception as e:
            logger.error(f"Error storing position to ClickHouse: {e}")
            raise
        
        # Update Redis cache
        try:
            cache_key = f"positions:{position['user_id']}"
            
            # Invalidate cache - will be refreshed on next read
            await self.redis_client.delete(cache_key)
            
        except Exception as e:
            logger.warning(f"Error updating Redis cache for position: {e}")
    
    # ========================================================================
    # ORDERS
    # ========================================================================
    
    async def store_order(
        self,
        order: Dict[str, Any]
    ) -> None:
        """Store/update order."""
        try:
            # Write to ClickHouse
            data = [(
                order['order_id'],
                order['user_id'],
                order['strategy_id'],
                order.get('position_id'),
                order['symbol'],
                order['exchange'],
                order['transaction_type'],
                order['order_type'],
                order['quantity'],
                order.get('price'),
                order.get('trigger_price'),
                order.get('filled_quantity', 0),
                order.get('average_price'),
                order['status'],
                order['order_time'],
                order.get('fill_time'),
                order.get('broker_order_id'),
                order.get('error_message'),
                datetime.now(),
                datetime.now()
            )]
            
            self.clickhouse_client.execute(
                'INSERT INTO orders VALUES',
                data
            )
            
        except Exception as e:
            logger.error(f"Error storing order to ClickHouse: {e}")
            raise
