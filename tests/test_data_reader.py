"""
Test DataReader Implementation

Comprehensive tests for RedisClickHouseDataReader.
All tests must pass before proceeding to Expression Evaluator.
"""

import pytest
import asyncio
import pandas as pd
import json
from datetime import datetime, timedelta
import clickhouse_connect
import redis.asyncio as redis

import sys
sys.path.append('..')

from adapters.redis_clickhouse_data_reader import RedisClickHouseDataReader


class TestDataReaderConnection:
    """Test DataReader connection and initialization."""
    
    @pytest.mark.asyncio
    async def test_connection(self):
        """Test DataReader can connect to Redis and ClickHouse."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            assert reader.redis_client is not None
            assert reader.clickhouse_client is not None
            print("✅ DataReader connected successfully")
        except Exception as e:
            pytest.fail(f"❌ Connection failed: {e}")
        finally:
            await reader.disconnect()
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test DataReader can disconnect cleanly."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            await reader.disconnect()
            print("✅ DataReader disconnected successfully")
        except Exception as e:
            pytest.fail(f"❌ Disconnect failed: {e}")


class TestGetCandles:
    """Test get_candles() method."""
    
    @pytest.fixture
    async def setup_test_data(self):
        """Setup test candles in ClickHouse."""
        client = clickhouse_connect.get_client(
            host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
            port=8443,
            username='default',
            password='0DNor8RIL2.7r',
            database='tradelayout',
            secure=True
        )
        
        # Insert 10 test candles
        test_candles = []
        base_time = datetime.now() - timedelta(minutes=50)
        
        for i in range(10):
            test_candles.append((
                base_time + timedelta(minutes=i*5),
                'TEST_CANDLES',
                '5m',
                100.0 + i,
                105.0 + i,
                99.0 + i,
                103.0 + i,
                1000 * (i + 1),
                1,  # is_closed
                datetime.now(),
                datetime.now()
            ))
        
        client.insert('ohlcv_candles', test_candles,
                     column_names=['ts', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume', 'is_closed', 'created_at', 'updated_at'])
        
        yield
        
        # Cleanup
        client.command("DELETE FROM ohlcv_candles WHERE symbol = 'TEST_CANDLES'")
    
    @pytest.mark.asyncio
    async def test_get_candles_from_clickhouse(self, setup_test_data):
        """Test getting candles from ClickHouse (cache miss)."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            
            # Get candles (should come from ClickHouse)
            df = await reader.get_candles('TEST_CANDLES', '5m', 10)
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 10
            assert 'open' in df.columns
            assert 'high' in df.columns
            assert 'low' in df.columns
            assert 'close' in df.columns
            assert 'volume' in df.columns
            
            # Check values
            assert df.iloc[0]['open'] == 100.0
            assert df.iloc[-1]['open'] == 109.0
            
            print(f"✅ Got {len(df)} candles from ClickHouse")
        except Exception as e:
            pytest.fail(f"❌ Get candles test failed: {e}")
        finally:
            await reader.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_candles_from_cache(self, setup_test_data):
        """Test getting candles from Redis cache (cache hit)."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            
            # First call - loads from ClickHouse and caches
            df1 = await reader.get_candles('TEST_CANDLES', '5m', 10)
            
            # Second call - should come from cache
            df2 = await reader.get_candles('TEST_CANDLES', '5m', 10)
            
            assert len(df1) == len(df2)
            assert df1.iloc[0]['close'] == df2.iloc[0]['close']
            
            print("✅ Cache hit working correctly")
        except Exception as e:
            pytest.fail(f"❌ Cache test failed: {e}")
        finally:
            await reader.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_candles_empty_result(self):
        """Test getting candles for non-existent symbol."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            
            df = await reader.get_candles('NONEXISTENT', '5m', 10)
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 0
            
            print("✅ Empty result handled correctly")
        except Exception as e:
            pytest.fail(f"❌ Empty result test failed: {e}")
        finally:
            await reader.disconnect()


class TestGetIndicators:
    """Test get_indicators() method."""
    
    @pytest.fixture
    async def setup_test_indicators(self):
        """Setup test indicators in ClickHouse."""
        client = clickhouse_connect.get_client(
            host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
            port=8443,
            username='default',
            password='0DNor8RIL2.7r',
            database='tradelayout',
            secure=True
        )
        
        # Insert test indicators
        test_indicators = [
            (datetime.now(), 'TEST_IND', '5m', 'EMA_20', 25900.5, datetime.now()),
            (datetime.now(), 'TEST_IND', '5m', 'RSI_14', 65.3, datetime.now()),
            (datetime.now(), 'TEST_IND', '5m', 'MACD', 12.5, datetime.now()),
        ]
        
        client.insert('indicator_values', test_indicators,
                     column_names=['ts', 'symbol', 'timeframe', 'indicator_name', 'value', 'created_at'])
        
        yield
        
        # Cleanup
        client.command("DELETE FROM indicator_values WHERE symbol = 'TEST_IND'")
    
    @pytest.mark.asyncio
    async def test_get_indicators(self, setup_test_indicators):
        """Test getting indicators."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            
            indicators = await reader.get_indicators('TEST_IND', '5m')
            
            assert isinstance(indicators, dict)
            assert 'EMA_20' in indicators
            assert 'RSI_14' in indicators
            assert 'MACD' in indicators
            
            assert indicators['EMA_20'] == 25900.5
            assert indicators['RSI_14'] == 65.3
            
            print(f"✅ Got {len(indicators)} indicators")
        except Exception as e:
            pytest.fail(f"❌ Get indicators test failed: {e}")
        finally:
            await reader.disconnect()


class TestGetLTP:
    """Test get_ltp() method."""
    
    @pytest.mark.asyncio
    async def test_get_ltp_from_redis(self):
        """Test getting LTP from Redis."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            
            # Manually set LTP in Redis
            ltp_data = {
                'ltp': 25900.0,
                'timestamp': datetime.now().isoformat(),
                'volume': 1000000,
                'oi': 50000
            }
            
            await reader.redis_client.setex(
                'ltp:TEST_LTP',
                60,
                json.dumps(ltp_data, default=str)
            )
            
            # Get LTP
            result = await reader.get_ltp('TEST_LTP')
            
            assert isinstance(result, dict)
            assert result['ltp'] == 25900.0
            assert result['volume'] == 1000000
            
            print("✅ Got LTP from Redis")
        except Exception as e:
            pytest.fail(f"❌ Get LTP test failed: {e}")
        finally:
            await reader.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_ltp_not_found(self):
        """Test getting LTP for non-existent symbol."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            
            result = await reader.get_ltp('NONEXISTENT')
            
            assert isinstance(result, dict)
            assert result['ltp'] == 0
            
            print("✅ LTP not found handled correctly")
        except Exception as e:
            pytest.fail(f"❌ LTP not found test failed: {e}")
        finally:
            await reader.disconnect()


class TestGetPositions:
    """Test get_positions() method."""
    
    @pytest.fixture
    async def setup_test_positions(self):
        """Setup test positions in ClickHouse."""
        client = clickhouse_connect.get_client(
            host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
            port=8443,
            username='default',
            password='0DNor8RIL2.7r',
            database='tradelayout',
            secure=True
        )
        
        # Insert test positions
        test_positions = [
            (
                'test-pos-1',
                'test-user',
                'test-strategy',
                'NIFTY28NOV2525900CE',
                'NFO',
                'BUY',
                75,
                150.0,
                155.0,
                375.0,
                'OPEN',
                datetime.now(),
                None,
                None,
                datetime.now(),
                datetime.now()
            )
        ]
        
        client.insert('positions', test_positions,
                     column_names=['position_id', 'user_id', 'strategy_id', 'symbol', 'exchange', 'transaction_type', 
                                  'quantity', 'entry_price', 'current_price', 'pnl', 'status', 'entry_time', 
                                  'exit_time', 'exit_price', 'created_at', 'updated_at'])
        
        yield
        
        # Cleanup
        client.command("DELETE FROM positions WHERE user_id = 'test-user'")
    
    @pytest.mark.asyncio
    async def test_get_positions(self, setup_test_positions):
        """Test getting positions."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            
            positions = await reader.get_positions('test-user')
            
            assert isinstance(positions, list)
            assert len(positions) > 0
            
            pos = positions[0]
            assert pos['position_id'] == 'test-pos-1'
            assert pos['symbol'] == 'NIFTY28NOV2525900CE'
            assert pos['quantity'] == 75
            assert pos['pnl'] == 375.0
            
            print(f"✅ Got {len(positions)} positions")
        except Exception as e:
            pytest.fail(f"❌ Get positions test failed: {e}")
        finally:
            await reader.disconnect()


class TestGetNodeVariable:
    """Test get_node_variable() method."""
    
    @pytest.fixture
    async def setup_test_variables(self):
        """Setup test node variables in ClickHouse."""
        client = clickhouse_connect.get_client(
            host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
            port=8443,
            username='default',
            password='0DNor8RIL2.7r',
            database='tradelayout',
            secure=True
        )
        
        # Insert test variable
        test_vars = [
            ('test-user', 'test-strategy', 'entry-3', 'entry_price', 150.5, datetime.now())
        ]
        
        client.insert('node_variables', test_vars,
                     column_names=['user_id', 'strategy_id', 'node_id', 'variable_name', 'value', 'updated_at'])
        
        yield
        
        # Cleanup
        client.command("DELETE FROM node_variables WHERE user_id = 'test-user'")
    
    @pytest.mark.asyncio
    async def test_get_node_variable(self, setup_test_variables):
        """Test getting node variable."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            
            value = await reader.get_node_variable(
                'test-user',
                'test-strategy',
                'entry-3',
                'entry_price'
            )
            
            assert value == 150.5
            
            print("✅ Got node variable")
        except Exception as e:
            pytest.fail(f"❌ Get node variable test failed: {e}")
        finally:
            await reader.disconnect()


class TestGetNodeState:
    """Test get_node_state() method."""
    
    @pytest.fixture
    async def setup_test_states(self):
        """Setup test node states in ClickHouse."""
        client = clickhouse_connect.get_client(
            host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
            port=8443,
            username='default',
            password='0DNor8RIL2.7r',
            database='tradelayout',
            secure=True
        )
        
        # Insert test state
        test_states = [
            ('test-user', 'test-strategy', 'entry-3', 'Active', 0, 0, datetime.now())
        ]
        
        client.insert('node_states', test_states,
                     column_names=['user_id', 'strategy_id', 'node_id', 'status', 'visited', 're_entry_num', 'updated_at'])
        
        yield
        
        # Cleanup
        client.command("DELETE FROM node_states WHERE user_id = 'test-user'")
    
    @pytest.mark.asyncio
    async def test_get_node_state(self, setup_test_states):
        """Test getting node state."""
        reader = RedisClickHouseDataReader()
        
        try:
            await reader.connect()
            
            state = await reader.get_node_state(
                'test-user',
                'test-strategy',
                'entry-3'
            )
            
            assert isinstance(state, dict)
            assert state['status'] == 'Active'
            assert state['visited'] == False
            assert state['re_entry_num'] == 0
            
            print("✅ Got node state")
        except Exception as e:
            pytest.fail(f"❌ Get node state test failed: {e}")
        finally:
            await reader.disconnect()


def run_all_tests():
    """Run all DataReader tests."""
    print("\n" + "="*60)
    print("🧪 RUNNING DATAREADER TESTS")
    print("="*60 + "\n")
    
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--color=yes',
        '-s'  # Show print statements
    ])


if __name__ == '__main__':
    run_all_tests()
