"""
Redis + ClickHouse DataReader Implementation

Reads from Redis cache first, falls back to ClickHouse.
ZERO dependency on old context!
"""

import json
import pandas as pd
import redis.asyncio as redis
import clickhouse_connect
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from interfaces.data_reader import DataReaderInterface


logger = logging.getLogger(__name__)


class RedisClickHouseDataReader(DataReaderInterface):
    """
    DataReader implementation using Redis (cache) and ClickHouse (DB).
    
    Cache Strategy:
    - LTP: Redis only (real-time, no fallback)
    - Candles: Redis → ClickHouse fallback
    - Indicators: Redis → ClickHouse fallback
    - Positions: Redis → ClickHouse fallback
    - Node variables: Redis → ClickHouse fallback
    - Node states: Redis → ClickHouse fallback
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
        self.clickhouse_client = clickhouse_connect.get_client(
            host=self.clickhouse_host,
            port=self.clickhouse_port,
            database=self.clickhouse_database,
            username=self.clickhouse_user,
            password=self.clickhouse_password,
            secure=self.clickhouse_secure
        )
        
        logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
        logger.info(f"Connected to ClickHouse at {self.clickhouse_host}:{self.clickhouse_port}")
    
    async def disconnect(self):
        """Close connections."""
        if self.redis_client:
            await self.redis_client.close()
        if self.clickhouse_client:
            self.clickhouse_client.disconnect()
    
    # ========================================================================
    # CANDLES
    # ========================================================================
    
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        n: int = 100
    ) -> pd.DataFrame:
        """Get candles from Redis cache or ClickHouse."""
        # Try Redis cache first
        cache_key = f"candles:{symbol}:{timeframe}"
        
        try:
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                candles = json.loads(cached)
                df = pd.DataFrame(candles)
                
                if len(df) >= n:
                    # Cache hit - return last N candles
                    df['ts'] = pd.to_datetime(df['ts'])
                    df.set_index('ts', inplace=True)
                    return df.tail(n)
        except Exception as e:
            logger.warning(f"Redis cache miss for {cache_key}: {e}")
        
        # Cache miss - query ClickHouse
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
            LIMIT %(n)s
            """
            
            result = self.clickhouse_client.execute(
                query,
                {'symbol': symbol, 'timeframe': timeframe, 'n': n}
            )
            
            if not result:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(
                result,
                columns=['ts', 'open', 'high', 'low', 'close', 'volume']
            )
            df['ts'] = pd.to_datetime(df['ts'])
            df.set_index('ts', inplace=True)
            df = df.sort_index()  # Reverse to chronological order
            
            # Cache for next time (1 hour TTL)
            cache_data = df.reset_index().to_dict('records')
            await self.redis_client.setex(
                cache_key,
                3600,  # 1 hour
                json.dumps(cache_data, default=str)
            )
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching candles from ClickHouse: {e}")
            return pd.DataFrame()
    
    # ========================================================================
    # INDICATORS
    # ========================================================================
    
    async def get_indicators(
        self,
        symbol: str,
        timeframe: str
    ) -> Dict[str, float]:
        """Get latest indicators from Redis or ClickHouse."""
        cache_key = f"indicators:{symbol}:{timeframe}"
        
        try:
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache miss for {cache_key}: {e}")
        
        # Fallback to ClickHouse
        try:
            query = """
            SELECT
                indicator_name,
                value
            FROM mv_latest_indicators
            WHERE symbol = %(symbol)s
              AND timeframe = %(timeframe)s
            """
            
            result = self.clickhouse_client.execute(
                query,
                {'symbol': symbol, 'timeframe': timeframe}
            )
            
            indicators = {row[0]: float(row[1]) for row in result}
            
            # Cache for next time (60 seconds TTL)
            await self.redis_client.setex(
                cache_key,
                60,
                json.dumps(indicators)
            )
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error fetching indicators from ClickHouse: {e}")
            return {}
    
    # ========================================================================
    # LTP (Live Tick Price)
    # ========================================================================
    
    async def get_ltp(self, symbol: str) -> Dict[str, Any]:
        """Get latest LTP from Redis (no fallback - must be real-time)."""
        cache_key = f"ltp:{symbol}"
        
        try:
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Error fetching LTP from Redis: {e}")
        
        # No fallback for LTP - must be in Redis
        return {
            'ltp': 0,
            'timestamp': None,
            'volume': 0,
            'oi': 0,
            'bid': 0,
            'ask': 0,
            'bid_qty': 0,
            'ask_qty': 0
        }
    
    # ========================================================================
    # POSITIONS
    # ========================================================================
    
    async def get_positions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get open positions for user."""
        cache_key = f"positions:{user_id}"
        
        try:
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache miss for {cache_key}: {e}")
        
        # Fallback to ClickHouse
        try:
            query = """
            SELECT
                position_id,
                symbol,
                exchange,
                transaction_type,
                quantity,
                entry_price,
                current_price,
                pnl,
                entry_time,
                status
            FROM positions
            WHERE user_id = %(user_id)s
              AND status = 'OPEN'
            ORDER BY entry_time DESC
            """
            
            result = self.clickhouse_client.execute(
                query,
                {'user_id': user_id}
            )
            
            positions = []
            for row in result:
                positions.append({
                    'position_id': row[0],
                    'symbol': row[1],
                    'exchange': row[2],
                    'transaction_type': row[3],
                    'quantity': row[4],
                    'entry_price': float(row[5]),
                    'current_price': float(row[6]),
                    'pnl': float(row[7]),
                    'entry_time': row[8],
                    'status': row[9]
                })
            
            # Cache for next time (10 seconds TTL)
            await self.redis_client.setex(
                cache_key,
                10,
                json.dumps(positions, default=str)
            )
            
            return positions
            
        except Exception as e:
            logger.error(f"Error fetching positions from ClickHouse: {e}")
            return []
    
    async def get_position_by_id(
        self,
        user_id: str,
        position_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get specific position by ID."""
        positions = await self.get_positions(user_id)
        
        for pos in positions:
            if pos['position_id'] == position_id:
                return pos
        
        return None
    
    # ========================================================================
    # NODE VARIABLES
    # ========================================================================
    
    async def get_node_variable(
        self,
        user_id: str,
        strategy_id: str,
        node_id: str,
        variable_name: str
    ) -> Optional[float]:
        """Get node variable value."""
        cache_key = f"node_var:{user_id}:{strategy_id}:{node_id}:{variable_name}"
        
        try:
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                return float(cached)
        except Exception as e:
            logger.warning(f"Redis cache miss for {cache_key}: {e}")
        
        # Fallback to ClickHouse
        try:
            query = """
            SELECT value
            FROM node_variables
            WHERE user_id = %(user_id)s
              AND strategy_id = %(strategy_id)s
              AND node_id = %(node_id)s
              AND variable_name = %(variable_name)s
            ORDER BY updated_at DESC
            LIMIT 1
            """
            
            result = self.clickhouse_client.execute(
                query,
                {
                    'user_id': user_id,
                    'strategy_id': strategy_id,
                    'node_id': node_id,
                    'variable_name': variable_name
                }
            )
            
            if result:
                value = float(result[0][0])
                
                # Cache for next time
                await self.redis_client.setex(cache_key, 60, str(value))
                
                return value
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching node variable from ClickHouse: {e}")
            return None
    
    # ========================================================================
    # NODE STATES
    # ========================================================================
    
    async def get_node_state(
        self,
        user_id: str,
        strategy_id: str,
        node_id: str
    ) -> Dict[str, Any]:
        """Get node state."""
        cache_key = f"node_state:{user_id}:{strategy_id}:{node_id}"
        
        try:
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache miss for {cache_key}: {e}")
        
        # Fallback to ClickHouse
        try:
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
                {
                    'user_id': user_id,
                    'strategy_id': strategy_id,
                    'node_id': node_id
                }
            )
            
            if result:
                state = {
                    'status': result[0][0],
                    'visited': bool(result[0][1]),
                    're_entry_num': int(result[0][2])
                }
                
                # Cache for next time
                await self.redis_client.setex(
                    cache_key,
                    60,
                    json.dumps(state)
                )
                
                return state
            
            # Default state if not found
            return {
                'status': 'Inactive',
                'visited': False,
                're_entry_num': 0
            }
            
        except Exception as e:
            logger.error(f"Error fetching node state from ClickHouse: {e}")
            return {
                'status': 'Inactive',
                'visited': False,
                're_entry_num': 0
            }
    
    async def get_all_node_states(
        self,
        user_id: str,
        strategy_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """Get all node states for a strategy."""
        cache_key = f"node_states:{user_id}:{strategy_id}"
        
        try:
            cached = await self.redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache miss for {cache_key}: {e}")
        
        # Fallback to ClickHouse
        try:
            query = """
            SELECT node_id, status, visited, re_entry_num
            FROM node_states
            WHERE user_id = %(user_id)s
              AND strategy_id = %(strategy_id)s
            """
            
            result = self.clickhouse_client.execute(
                query,
                {'user_id': user_id, 'strategy_id': strategy_id}
            )
            
            states = {}
            for row in result:
                states[row[0]] = {
                    'status': row[1],
                    'visited': bool(row[2]),
                    're_entry_num': int(row[3])
                }
            
            # Cache for next time
            await self.redis_client.setex(
                cache_key,
                60,
                json.dumps(states)
            )
            
            return states
            
        except Exception as e:
            logger.error(f"Error fetching node states from ClickHouse: {e}")
            return {}
