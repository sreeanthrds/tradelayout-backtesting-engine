"""
Tests for Order Placer
"""

import pytest
import asyncio
from datetime import datetime

import sys
sys.path.append('..')

from adapters.order_placer_impl import OrderPlacerImpl
from adapters.redis_clickhouse_data_writer import RedisClickHouseDataWriter


class MockDataWriter:
    """Mock DataWriter for testing."""
    
    def __init__(self):
        self.orders = []
    
    async def store_order(self, order):
        """Mock store order."""
        self.orders.append(order)


class TestOrderPlacer:
    """Test Order Placer."""
    
    @pytest.fixture
    def order_placer(self):
        """Create order placer with mock writer."""
        mock_writer = MockDataWriter()
        return OrderPlacerImpl(data_writer=mock_writer)
    
    @pytest.mark.asyncio
    async def test_place_market_order(self, order_placer):
        """Test placing market order."""
        result = await order_placer.place_order(
            user_id='user-123',
            strategy_id='strat-456',
            symbol='NIFTY',
            exchange='NSE',
            transaction_type='BUY',
            order_type='MARKET',
            quantity=75
        )
        
        assert result['success'] == True
        assert 'order_id' in result
        assert result['symbol'] == 'NIFTY'
        print("✅ Market order placement works")
    
    @pytest.mark.asyncio
    async def test_place_limit_order(self, order_placer):
        """Test placing limit order."""
        result = await order_placer.place_order(
            user_id='user-123',
            strategy_id='strat-456',
            symbol='NIFTY',
            exchange='NSE',
            transaction_type='BUY',
            order_type='LIMIT',
            quantity=75,
            price=25900.0
        )
        
        assert result['success'] == True
        assert 'order_id' in result
        print("✅ Limit order placement works")
    
    @pytest.mark.asyncio
    async def test_order_tracking(self, order_placer):
        """Test order tracking."""
        result = await order_placer.place_order(
            user_id='user-123',
            strategy_id='strat-456',
            symbol='NIFTY',
            exchange='NSE',
            transaction_type='BUY',
            order_type='MARKET',
            quantity=75
        )
        
        order_id = result['order_id']
        
        # Wait for simulated fill
        await asyncio.sleep(0.2)
        
        # Check order moved to filled
        filled_orders = order_placer.get_filled_orders()
        assert order_id in filled_orders
        print("✅ Order tracking works")
    
    @pytest.mark.asyncio
    async def test_order_callback(self, order_placer):
        """Test order fill callback."""
        callback_called = False
        callback_order = None
        
        async def on_fill(order):
            nonlocal callback_called, callback_order
            callback_called = True
            callback_order = order
        
        # Place order
        result = await order_placer.place_order(
            user_id='user-123',
            strategy_id='strat-456',
            symbol='NIFTY',
            exchange='NSE',
            transaction_type='BUY',
            order_type='MARKET',
            quantity=75
        )
        
        order_id = result['order_id']
        
        # Register callback
        order_placer.register_fill_callback(order_id, on_fill)
        
        # Wait for fill
        await asyncio.sleep(0.3)
        
        # Check callback was called
        assert callback_called == True
        assert callback_order is not None
        assert callback_order['order_id'] == order_id
        print("✅ Order callback works")
    
    @pytest.mark.asyncio
    async def test_get_order_status(self, order_placer):
        """Test getting order status."""
        result = await order_placer.place_order(
            user_id='user-123',
            strategy_id='strat-456',
            symbol='NIFTY',
            exchange='NSE',
            transaction_type='BUY',
            order_type='MARKET',
            quantity=75
        )
        
        order_id = result['order_id']
        
        # Get status immediately (should be pending)
        status = await order_placer.get_order_status('user-123', order_id)
        assert status is not None
        assert status['order_id'] == order_id
        
        # Wait for fill
        await asyncio.sleep(0.2)
        
        # Get status after fill (should be complete)
        status = await order_placer.get_order_status('user-123', order_id)
        assert status['status'] == 'COMPLETE'
        print("✅ Get order status works")
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, order_placer):
        """Test cancelling order."""
        result = await order_placer.place_order(
            user_id='user-123',
            strategy_id='strat-456',
            symbol='NIFTY',
            exchange='NSE',
            transaction_type='BUY',
            order_type='LIMIT',
            quantity=75,
            price=25900.0
        )
        
        order_id = result['order_id']
        
        # Cancel quickly (before simulated fill at 0.1s)
        await asyncio.sleep(0.05)  # Small delay to ensure order is registered
        cancel_result = await order_placer.cancel_order('user-123', order_id)
        
        assert cancel_result['success'] == True
        
        # Check order is not in pending
        pending = order_placer.get_pending_orders()
        assert order_id not in pending
        print("✅ Order cancellation works")
    
    @pytest.mark.asyncio
    async def test_multiple_orders(self, order_placer):
        """Test placing multiple orders."""
        orders = []
        
        for i in range(5):
            result = await order_placer.place_order(
                user_id='user-123',
                strategy_id='strat-456',
                symbol=f'SYMBOL{i}',
                exchange='NSE',
                transaction_type='BUY',
                order_type='MARKET',
                quantity=75
            )
            orders.append(result['order_id'])
        
        # Wait for fills
        await asyncio.sleep(0.5)
        
        # Check all filled
        filled = order_placer.get_filled_orders()
        for order_id in orders:
            assert order_id in filled
        
        print("✅ Multiple orders work")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("🧪 RUNNING ORDER PLACER TESTS")
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
