"""
Comprehensive Tests for DataWriter Implementation

Tests all write operations, edge cases, and error handling.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
import clickhouse_connect
import redis.asyncio as redis
import json

import sys
sys.path.append('..')

from adapters.redis_clickhouse_data_writer import RedisClickHouseDataWriter


class TestDataWriterConnection:
    """Test DataWriter connection and initialization."""
    
    @pytest.mark.asyncio
    async def test_connection(self):
        """Test DataWriter can connect to Redis and ClickHouse."""
        writer = RedisClickHouseDataWriter()
        
        try:
            await writer.connect()
            assert writer.redis_client is not None
            assert writer.clickhouse_client is not None
            print("✅ DataWriter connected successfully")
        except Exception as e:
            pytest.fail(f"❌ Connection failed: {e}")
        finally:
            await writer.disconnect()
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test DataWriter can disconnect cleanly."""
        writer = RedisClickHouseDataWriter()
        
        try:
            await writer.connect()
            await writer.disconnect()
            print("✅ DataWriter disconnected successfully")
        except Exception as e:
            pytest.fail(f"❌ Disconnect failed: {e}")


class TestStoreCandle:
    """Test store_candle() method."""
    
    @pytest.fixture
    async def writer(self):
        """Create and connect DataWriter."""
        w = RedisClickHouseDataWriter()
        await w.connect()
        yield w
        await w.disconnect()
    
    @pytest.mark.asyncio
    async def test_store_single_candle(self, writer):
        """Test storing a single candle."""
        candle = {
            'ts': datetime.now(),
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 103.0,
            'volume': 1000,
            'is_closed': 1
        }
        
        try:
            await writer.store_candle('TEST_CANDLE', '5m', candle)
            print("✅ Single candle stored")
        except Exception as e:
            pytest.fail(f"❌ Store candle failed: {e}")
    
    @pytest.mark.asyncio
    async def test_store_candle_updates_cache(self, writer):
        """Test that storing candle updates Redis cache."""
        candle = {
            'ts': datetime.now(),
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 103.0,
            'volume': 1000
        }
        
        await writer.store_candle('TEST_CACHE', '5m', candle)
        
        # Check Redis cache
        cached = await writer.redis_client.get('candles:TEST_CACHE:5m')
        assert cached is not None
        
        candles = json.loads(cached)
        assert len(candles) > 0
        assert candles[-1]['close'] == 103.0
        
        print("✅ Candle cache updated")
    
    @pytest.mark.asyncio
    async def test_store_candle_batch(self, writer):
        """Test storing multiple candles in batch."""
        candles = []
        base_time = datetime.now() - timedelta(minutes=50)
        
        for i in range(10):
            candles.append({
                'ts': base_time + timedelta(minutes=i*5),
                'open': 100.0 + i,
                'high': 105.0 + i,
                'low': 99.0 + i,
                'close': 103.0 + i,
                'volume': 1000 * (i + 1),
                'is_closed': 1
            })
        
        try:
            await writer.store_candles_batch('TEST_BATCH', '5m', candles)
            print(f"✅ Stored {len(candles)} candles in batch")
        except Exception as e:
            pytest.fail(f"❌ Batch store failed: {e}")
    
    @pytest.mark.asyncio
    async def test_store_empty_batch(self, writer):
        """Test storing empty batch (should not error)."""
        try:
            await writer.store_candles_batch('TEST_EMPTY', '5m', [])
            print("✅ Empty batch handled correctly")
        except Exception as e:
            pytest.fail(f"❌ Empty batch failed: {e}")


class TestStoreIndicator:
    """Test store_indicator() method."""
    
    @pytest.fixture
    async def writer(self):
        w = RedisClickHouseDataWriter()
        await w.connect()
        yield w
        await w.disconnect()
    
    @pytest.mark.asyncio
    async def test_store_single_indicator(self, writer):
        """Test storing a single indicator."""
        try:
            await writer.store_indicator(
                'TEST_IND',
                '5m',
                'EMA_20',
                25900.5,
                datetime.now()
            )
            print("✅ Single indicator stored")
        except Exception as e:
            pytest.fail(f"❌ Store indicator failed: {e}")
    
    @pytest.mark.asyncio
    async def test_store_indicator_updates_cache(self, writer):
        """Test that storing indicator updates Redis cache."""
        await writer.store_indicator(
            'TEST_IND_CACHE',
            '5m',
            'RSI_14',
            65.3,
            datetime.now()
        )
        
        # Check Redis cache
        cached = await writer.redis_client.get('indicators:TEST_IND_CACHE:5m')
        assert cached is not None
        
        indicators = json.loads(cached)
        assert 'RSI_14' in indicators
        assert indicators['RSI_14'] == 65.3
        
        print("✅ Indicator cache updated")
    
    @pytest.mark.asyncio
    async def test_store_indicators_batch(self, writer):
        """Test storing multiple indicators in batch."""
        indicators = {
            'EMA_20': 25900.5,
            'RSI_14': 65.3,
            'MACD': 12.5,
            'MACD_signal': 10.2
        }
        
        try:
            await writer.store_indicators_batch(
                'TEST_IND_BATCH',
                '5m',
                indicators,
                datetime.now()
            )
            print(f"✅ Stored {len(indicators)} indicators in batch")
        except Exception as e:
            pytest.fail(f"❌ Batch store failed: {e}")


class TestStoreTick:
    """Test store_tick() method."""
    
    @pytest.fixture
    async def writer(self):
        w = RedisClickHouseDataWriter()
        await w.connect()
        yield w
        await w.disconnect()
    
    @pytest.mark.asyncio
    async def test_store_tick(self, writer):
        """Test storing a tick."""
        tick = {
            'timestamp': datetime.now(),
            'ltp': 25900.0,
            'volume': 1000000,
            'oi': 50000,
            'bid': 25899.5,
            'ask': 25900.5,
            'bid_qty': 100,
            'ask_qty': 150
        }
        
        try:
            await writer.store_tick('TEST_TICK', 'NSE', tick)
            print("✅ Tick stored")
        except Exception as e:
            pytest.fail(f"❌ Store tick failed: {e}")
    
    @pytest.mark.asyncio
    async def test_store_tick_updates_ltp_cache(self, writer):
        """Test that storing tick updates LTP in Redis."""
        tick = {
            'timestamp': datetime.now(),
            'ltp': 26000.0,
            'volume': 1000000,
            'oi': 50000
        }
        
        await writer.store_tick('TEST_LTP', 'NSE', tick)
        
        # Check Redis cache
        cached = await writer.redis_client.get('ltp:TEST_LTP')
        assert cached is not None
        
        ltp_data = json.loads(cached)
        assert ltp_data['ltp'] == 26000.0
        
        print("✅ LTP cache updated")


class TestNodeVariables:
    """Test node variable operations."""
    
    @pytest.fixture
    async def writer(self):
        w = RedisClickHouseDataWriter()
        await w.connect()
        yield w
        await w.disconnect()
    
    @pytest.mark.asyncio
    async def test_update_node_variable(self, writer):
        """Test updating node variable."""
        try:
            await writer.update_node_variable(
                'test-user',
                'test-strategy',
                'entry-3',
                'entry_price',
                150.5
            )
            print("✅ Node variable updated")
        except Exception as e:
            pytest.fail(f"❌ Update node variable failed: {e}")
    
    @pytest.mark.asyncio
    async def test_node_variable_cache(self, writer):
        """Test node variable cache update."""
        await writer.update_node_variable(
            'test-user',
            'test-strategy',
            'entry-3',
            'test_var',
            123.45
        )
        
        # Check Redis cache
        cache_key = 'node_var:test-user:test-strategy:entry-3:test_var'
        cached = await writer.redis_client.get(cache_key)
        
        assert cached is not None
        assert float(cached) == 123.45
        
        print("✅ Node variable cache updated")


class TestNodeStates:
    """Test node state operations."""
    
    @pytest.fixture
    async def writer(self):
        w = RedisClickHouseDataWriter()
        await w.connect()
        yield w
        await w.disconnect()
    
    @pytest.mark.asyncio
    async def test_update_node_state(self, writer):
        """Test updating node state."""
        try:
            await writer.update_node_state(
                'test-user',
                'test-strategy',
                'entry-3',
                'Active',
                visited=False,
                re_entry_num=0
            )
            print("✅ Node state updated")
        except Exception as e:
            pytest.fail(f"❌ Update node state failed: {e}")
    
    @pytest.mark.asyncio
    async def test_node_state_cache(self, writer):
        """Test node state cache update."""
        await writer.update_node_state(
            'test-user',
            'test-strategy',
            'test-node',
            'Pending',
            visited=True,
            re_entry_num=1
        )
        
        # Check Redis cache
        cache_key = 'node_state:test-user:test-strategy:test-node'
        cached = await writer.redis_client.get(cache_key)
        
        assert cached is not None
        state = json.loads(cached)
        assert state['status'] == 'Pending'
        assert state['visited'] == True
        assert state['re_entry_num'] == 1
        
        print("✅ Node state cache updated")


class TestPositions:
    """Test position operations."""
    
    @pytest.fixture
    async def writer(self):
        w = RedisClickHouseDataWriter()
        await w.connect()
        yield w
        await w.disconnect()
    
    @pytest.mark.asyncio
    async def test_store_position(self, writer):
        """Test storing a position."""
        position = {
            'position_id': 'test-pos-1',
            'user_id': 'test-user',
            'strategy_id': 'test-strategy',
            'symbol': 'NIFTY28NOV2525900CE',
            'exchange': 'NFO',
            'transaction_type': 'BUY',
            'quantity': 75,
            'entry_price': 150.0,
            'current_price': 155.0,
            'pnl': 375.0,
            'status': 'OPEN',
            'entry_time': datetime.now()
        }
        
        try:
            await writer.store_position(position)
            print("✅ Position stored")
        except Exception as e:
            pytest.fail(f"❌ Store position failed: {e}")


class TestOrders:
    """Test order operations."""
    
    @pytest.fixture
    async def writer(self):
        w = RedisClickHouseDataWriter()
        await w.connect()
        yield w
        await w.disconnect()
    
    @pytest.mark.asyncio
    async def test_store_order(self, writer):
        """Test storing an order."""
        order = {
            'order_id': 'test-order-1',
            'user_id': 'test-user',
            'strategy_id': 'test-strategy',
            'position_id': 'test-pos-1',
            'symbol': 'NIFTY28NOV2525900CE',
            'exchange': 'NFO',
            'transaction_type': 'BUY',
            'order_type': 'MARKET',
            'quantity': 75,
            'filled_quantity': 75,
            'average_price': 150.0,
            'status': 'COMPLETE',
            'order_time': datetime.now()
        }
        
        try:
            await writer.store_order(order)
            print("✅ Order stored")
        except Exception as e:
            pytest.fail(f"❌ Store order failed: {e}")


def run_all_tests():
    """Run all DataWriter tests."""
    print("\n" + "="*60)
    print("🧪 RUNNING DATAWRITER TESTS")
    print("="*60 + "\n")
    
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--color=yes',
        '-s'
    ])


if __name__ == '__main__':
    run_all_tests()
