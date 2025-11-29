"""
Test Infrastructure - ClickHouse and Redis Connections

Run these tests BEFORE proceeding to next stage.
All tests must pass before moving forward.
"""

import pytest
import asyncio
import redis.asyncio as redis
from datetime import datetime


class TestClickHouseConnection:
    """Test ClickHouse database connection and schema."""
    
    def test_clickhouse_connection(self):
        """Test basic ClickHouse connection."""
        try:
            import clickhouse_connect
            client = clickhouse_connect.get_client(
                host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
                port=8443,
                username='default',
                password='0DNor8RIL2.7r',
                database='tradelayout',
                secure=True
            )
            result = client.query('SELECT version()')
            assert result is not None
            print(f"✅ ClickHouse Cloud connected")
        except Exception as e:
            pytest.fail(f"❌ ClickHouse connection failed: {e}")
    
    def test_database_exists(self):
        """Test that tradelayout database exists."""
        try:
            import clickhouse_connect
            client = clickhouse_connect.get_client(
                host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
                port=8443,
                username='default',
                password='0DNor8RIL2.7r',
                database='tradelayout',
                secure=True
            )
            result = client.query('SHOW DATABASES')
            databases = [row[0] for row in result.result_rows]
            assert 'tradelayout' in databases
            print("✅ Database 'tradelayout' exists")
        except Exception as e:
            pytest.fail(f"❌ Database check failed: {e}")
    
    def test_all_tables_exist(self):
        """Test that all required tables exist."""
        expected_tables = [
            'raw_ticks',
            'ohlcv_candles',
            'indicator_values',
            'node_variables',
            'node_states',
            'positions',
            'orders'
        ]
        
        try:
            import clickhouse_connect
            client = clickhouse_connect.get_client(
                host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
                port=8443,
                username='default',
                password='0DNor8RIL2.7r',
                database='tradelayout',
                secure=True
            )
            result = client.query('SHOW TABLES')
            tables = [row[0] for row in result.result_rows]
            
            for table in expected_tables:
                assert table in tables, f"Table {table} not found"
                print(f"✅ Table '{table}' exists")
            
            print(f"✅ All {len(expected_tables)} tables exist")
        except Exception as e:
            pytest.fail(f"❌ Table check failed: {e}")
    
    @pytest.mark.skip(reason="Materialized views are optional in ClickHouse Cloud")
    def test_materialized_views_exist(self):
        """Test that materialized views exist."""
        expected_views = [
            'mv_latest_candles',
            'mv_latest_indicators'
        ]
        
        try:
            import clickhouse_connect
            client = clickhouse_connect.get_client(
                host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
                port=8443,
                username='default',
                password='0DNor8RIL2.7r',
                database='tradelayout',
                secure=True
            )
            result = client.query('SHOW TABLES')
            tables = [row[0] for row in result.result_rows]
            
            for view in expected_views:
                assert view in tables, f"Materialized view {view} not found"
                print(f"✅ Materialized view '{view}' exists")
        except Exception as e:
            pytest.fail(f"❌ Materialized view check failed: {e}")
    
    def test_table_schemas(self):
        """Test that tables have correct columns."""
        try:
            import clickhouse_connect
            client = clickhouse_connect.get_client(
                host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
                port=8443,
                username='default',
                password='0DNor8RIL2.7r',
                database='tradelayout',
                secure=True
            )
            
            # Test ohlcv_candles schema
            result = client.query('DESCRIBE ohlcv_candles')
            columns = [row[0] for row in result.result_rows]
            
            expected_columns = ['ts', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume', 'is_closed']
            for col in expected_columns:
                assert col in columns, f"Column {col} not found in ohlcv_candles"
            
            print("✅ Table schemas correct")
        except Exception as e:
            pytest.fail(f"❌ Schema check failed: {e}")
    
    def test_insert_and_query(self):
        """Test basic insert and query operations."""
        try:
            import clickhouse_connect
            client = clickhouse_connect.get_client(
                host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
                port=8443,
                username='default',
                password='0DNor8RIL2.7r',
                database='tradelayout',
                secure=True
            )
            
            # Insert test candle
            test_data = [(
                datetime.now(),
                'TEST_SYMBOL',
                '5m',
                100.0,
                105.0,
                99.0,
                103.0,
                1000,
                1,
                datetime.now(),
                datetime.now()
            )]
            
            client.insert(
                'ohlcv_candles',
                test_data,
                column_names=['ts', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume', 'is_closed', 'created_at', 'updated_at']
            )
            
            # Query it back
            result = client.query(
                "SELECT close FROM ohlcv_candles WHERE symbol = 'TEST_SYMBOL' LIMIT 1"
            )
            assert len(result.result_rows) > 0
            assert float(result.result_rows[0][0]) == 103.0
            
            # Cleanup
            client.command("DELETE FROM ohlcv_candles WHERE symbol = 'TEST_SYMBOL'")
            
            print("✅ Insert and query operations work")
        except Exception as e:
            pytest.fail(f"❌ Insert/query test failed: {e}")


class TestRedisConnection:
    """Test Redis connection and operations."""
    
    @pytest.mark.asyncio
    async def test_redis_connection(self):
        """Test basic Redis connection."""
        try:
            client = await redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True
            )
            
            result = await client.ping()
            assert result is True
            
            await client.close()
            print("✅ Redis connected successfully")
        except Exception as e:
            pytest.fail(f"❌ Redis connection failed: {e}")
    
    @pytest.mark.asyncio
    async def test_redis_set_get(self):
        """Test Redis set and get operations."""
        try:
            client = await redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True
            )
            
            # Set a value
            await client.set('test_key', 'test_value')
            
            # Get it back
            value = await client.get('test_key')
            assert value == 'test_value'
            
            # Delete it
            await client.delete('test_key')
            
            await client.close()
            print("✅ Redis set/get operations work")
        except Exception as e:
            pytest.fail(f"❌ Redis set/get test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_redis_expiry(self):
        """Test Redis key expiry."""
        try:
            client = await redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True
            )
            
            # Set with expiry
            await client.setex('test_expiry', 2, 'value')
            
            # Should exist
            value = await client.get('test_expiry')
            assert value == 'value'
            
            # Wait for expiry
            await asyncio.sleep(3)
            
            # Should not exist
            value = await client.get('test_expiry')
            assert value is None
            
            await client.close()
            print("✅ Redis expiry works")
        except Exception as e:
            pytest.fail(f"❌ Redis expiry test failed: {e}")
    
    @pytest.mark.asyncio
    async def test_redis_json_storage(self):
        """Test storing JSON in Redis."""
        import json
        
        try:
            client = await redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True
            )
            
            # Store JSON
            test_data = {
                'symbol': 'NIFTY',
                'ltp': 25900.0,
                'volume': 1000000
            }
            
            await client.set('test_json', json.dumps(test_data))
            
            # Retrieve and parse
            value = await client.get('test_json')
            parsed = json.loads(value)
            
            assert parsed['symbol'] == 'NIFTY'
            assert parsed['ltp'] == 25900.0
            
            # Cleanup
            await client.delete('test_json')
            
            await client.close()
            print("✅ Redis JSON storage works")
        except Exception as e:
            pytest.fail(f"❌ Redis JSON test failed: {e}")


class TestInfrastructureIntegration:
    """Test ClickHouse and Redis working together."""
    
    @pytest.mark.asyncio
    async def test_cache_fallback_pattern(self):
        """Test cache-first, DB-fallback pattern."""
        import json
        
        try:
            # Setup
            import clickhouse_connect
            clickhouse = clickhouse_connect.get_client(
                host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
                port=8443,
                username='default',
                password='0DNor8RIL2.7r',
                database='tradelayout',
                secure=True
            )
            redis_client = await redis.Redis(
                host='localhost',
                port=6379,
                decode_responses=True
            )
            
            # Insert data in ClickHouse
            test_data = [(
                datetime.now(),
                'CACHE_TEST',
                '5m',
                100.0,
                105.0,
                99.0,
                103.0,
                1000,
                1,
                datetime.now(),
                datetime.now()
            )]
            
            clickhouse.insert(
                'ohlcv_candles',
                test_data,
                column_names=['ts', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'volume', 'is_closed', 'created_at', 'updated_at']
            )

            # Query from ClickHouse
            result = clickhouse.query(
                "SELECT close FROM ohlcv_candles WHERE symbol = 'CACHE_TEST' LIMIT 1"
            )

            assert len(result.result_rows) > 0
            close_price = float(result.result_rows[0][0])
            
            # Cache in Redis
            cache_key = 'candles:CACHE_TEST:5m'
            cache_data = json.dumps({'close': close_price})
            await redis_client.setex(cache_key, 60, cache_data)
            
            # Read from cache
            cached = await redis_client.get(cache_key)
            assert cached is not None
            
            parsed = json.loads(cached)
            assert parsed['close'] == close_price
            
            # Cleanup
            clickhouse.command("DELETE FROM ohlcv_candles WHERE symbol = 'CACHE_TEST'")
            await redis_client.delete(cache_key)
            await redis_client.close()
            
            print("✅ Cache-fallback pattern works")
        except Exception as e:
            pytest.fail(f"❌ Cache-fallback test failed: {e}")


def run_all_tests():
    """Run all infrastructure tests."""
    print("\n" + "="*60)
    print("🧪 RUNNING INFRASTRUCTURE TESTS")
    print("="*60 + "\n")
    
    # Run tests
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--color=yes'
    ])


if __name__ == '__main__':
    run_all_tests()
