"""
Integration Tests - End-to-end testing
"""

import pytest
import asyncio
from datetime import datetime

import sys
sys.path.append('..')

from strategy.strategy_executor import StrategyExecutor
from adapters.redis_clickhouse_data_reader import RedisClickHouseDataReader
from adapters.redis_clickhouse_data_writer import RedisClickHouseDataWriter


class MockOrderPlacer:
    """Mock order placer for testing."""
    
    async def place_order(self, **kwargs):
        """Mock order placement."""
        return {
            'success': True,
            'order_id': 'test-order-123',
            'position_id': kwargs.get('position_id'),
            'symbol': kwargs.get('symbol'),
            'exchange': kwargs.get('exchange')
        }


class TestIntegration:
    """Integration tests."""
    
    @pytest.fixture
    async def executor(self):
        """Create strategy executor."""
        # Simple strategy config
        strategy_config = {
            'start_node': 'entry-1',
            'nodes': [
                {
                    'id': 'entry-1',
                    'type': 'entry',
                    'entry_condition': 'ltp_TI > 25000',
                    'instrument': 'NIFTY',
                    'transaction_type': 'BUY',
                    'quantity': 75,
                    'order_type': 'MARKET',
                    'exchange': 'NSE',
                    'next': ['exit-1']
                },
                {
                    'id': 'exit-1',
                    'type': 'exit',
                    'exit_condition': 'ltp_TI > 26000',
                    'position_id': 'pos-123'
                }
            ]
        }
        
        # Create components (mock for now)
        data_reader = RedisClickHouseDataReader(
            clickhouse_host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
            clickhouse_port=8443,
            clickhouse_user='default',
            clickhouse_password='0DNor8RIL2.7r',
            clickhouse_database='tradelayout',
            clickhouse_secure=True
        )
        
        data_writer = RedisClickHouseDataWriter(
            clickhouse_host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
            clickhouse_port=8443,
            clickhouse_user='default',
            clickhouse_password='0DNor8RIL2.7r',
            clickhouse_database='tradelayout',
            clickhouse_secure=True
        )
        
        order_placer = MockOrderPlacer()
        
        # Connect
        await data_reader.connect()
        await data_writer.connect()
        
        # Create executor
        executor = StrategyExecutor(
            user_id='test-user',
            strategy_id='test-strategy',
            strategy_config=strategy_config,
            data_reader=data_reader,
            data_writer=data_writer,
            order_placer=order_placer
        )
        
        await executor.initialize()
        
        yield executor
        
        # Cleanup
        await data_reader.disconnect()
        await data_writer.disconnect()
    
    @pytest.mark.asyncio
    async def test_executor_initialization(self, executor):
        """Test executor initializes correctly."""
        assert executor is not None
        assert len(executor.nodes) == 2
        assert 'entry-1' in executor.nodes
        assert 'exit-1' in executor.nodes
        print("✅ Executor initialization works")
    
    @pytest.mark.asyncio
    async def test_executor_start_stop(self, executor):
        """Test executor start and stop."""
        await executor.start()
        assert executor.is_running == True
        
        await executor.stop()
        assert executor.is_running == False
        print("✅ Executor start/stop works")
    
    @pytest.mark.asyncio
    async def test_tick_processing(self, executor):
        """Test tick processing."""
        await executor.start()
        
        # Process a tick
        tick_data = {
            'symbol': 'NIFTY',
            'ltp': 25500.0,
            'timestamp': datetime.now()
        }
        
        await executor.process_tick(tick_data)
        
        assert executor.tick_count == 1
        print("✅ Tick processing works")
    
    @pytest.mark.asyncio
    async def test_get_status(self, executor):
        """Test get status."""
        status = await executor.get_status()
        
        assert 'strategy_id' in status
        assert 'is_running' in status
        assert 'tick_count' in status
        assert 'node_statuses' in status
        print("✅ Get status works")
    
    @pytest.mark.asyncio
    async def test_can_shutdown(self, executor):
        """Test can shutdown logic."""
        # Initially should be able to shutdown (no pending orders)
        can_shutdown = executor.can_shutdown()
        assert isinstance(can_shutdown, bool)
        print("✅ Can shutdown check works")


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*60)
    print("🧪 RUNNING INTEGRATION TESTS")
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
