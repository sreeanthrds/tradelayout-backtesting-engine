#!/usr/bin/env python3
"""
Comprehensive Tests for Exit Node and Square-off Node
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.utils.context_manager import ContextManager
from strategy.nodes.exit_node import ExitNode
from strategy.nodes.square_off_node import SquareOffNode


def setup_context_with_position():
    """Setup context with an open position"""
    context_manager = ContextManager()
    context_manager.reset_for_new_strategy_run()
    
    context = {
        'context_manager': context_manager,
        'ltp_store': {
            'ltp_TI': {'ltp': 25200, 'symbol': 'NIFTY'}
        },
        'current_timestamp': datetime.now(),
        'mode': 'backtesting',
        'node_states': {},
        'node_order_status': {}
    }
    
    # Add open position
    context_manager.gps.add_position(
        position_id='test-pos-1',
        entry_data={
            'price': 25000,
            'quantity': 50,
            'lot_size': 50,
            'lots': 1,
            'side': 'buy',
            'instrument': 'NIFTY',
            'symbol': 'NIFTY24NOV25000CE',
            'exchange': 'NFO',
            'order_id': 'ENTRY_123',
            'node_id': 'entry-1',
            'underlying_price_on_entry': 25000,
            'node_variables': {},
            'position_config': {'productType': 'intraday'}
        },
        tick_time=datetime.now()
    )
    
    return context


# ============================================================================
# EXIT NODE TESTS
# ============================================================================

def test_exit_node_closes_position():
    """Test: Exit Node closes position and calculates PnL"""
    print("\n" + "="*60)
    print("TEST: Exit Node - Basic Position Close")
    print("="*60)
    
    context = setup_context_with_position()
    
    # Create Exit Node
    exit_config = {
        'label': 'Exit',
        'exitConfig': {
            'targetPositionVpi': 'test-pos-1',
            'orderType': 'market'
        }
    }
    
    exit_node = ExitNode('exit-1', exit_config)
    exit_node.mark_active(context)
    
    # Execute
    result = exit_node.execute(context)
    
    print(f"\n✅ Exit Node Executed:")
    print(f"   executed: {result.get('executed')}")
    print(f"   logic_completed: {result.get('logic_completed')}")
    print(f"   positions_closed: {result.get('positions_closed')}")
    
    # Check position is closed
    position = context['context_manager'].gps.get_position('test-pos-1')
    
    print(f"\n📦 Position after exit:")
    print(f"   status: {position.get('status')}")
    print(f"   entry_price: {position.get('entry_price')}")
    print(f"   exit_price: {position.get('exit_price')}")
    print(f"   pnl: {position.get('pnl')}")
    
    assert result.get('logic_completed') == True, "Should complete logic"
    assert result.get('positions_closed') == 1, "Should close 1 position"
    assert position.get('status') == 'closed', "Position should be closed"
    assert position.get('exit_price') == 25200, "Exit price should be 25200"
    # PnL = (25200 - 25000) * 50 = 10,000
    assert position.get('pnl') == 10000, f"PnL should be 10000, got {position.get('pnl')}"
    
    print("\n✅ TEST PASSED: Position closed with correct PnL")


def test_exit_node_opposite_side():
    """Test: Exit Node executes opposite side (BUY→SELL, SELL→BUY)"""
    print("\n" + "="*60)
    print("TEST: Exit Node - Opposite Side Logic")
    print("="*60)
    
    # Test BUY position → SELL exit
    context = setup_context_with_position()
    
    exit_config = {
        'label': 'Exit',
        'exitConfig': {
            'targetPositionVpi': 'test-pos-1',
            'orderType': 'market'
        }
    }
    
    exit_node = ExitNode('exit-1', exit_config)
    position = context['context_manager'].gps.get_position('test-pos-1')
    
    # Create exit order
    exit_order = exit_node._create_exit_order(context, position)
    
    print(f"\n📊 Position side: {position.get('side')}")
    print(f"📊 Exit order side: {exit_order.get('side')}")
    
    assert position.get('side') == 'buy', "Position should be BUY"
    assert exit_order.get('side') == 'SELL', "Exit should be SELL"
    
    # Test SELL position → BUY exit
    context_manager = ContextManager()
    context_manager.reset_for_new_strategy_run()
    
    context_manager.gps.add_position(
        position_id='test-pos-2',
        entry_data={
            'price': 25000,
            'quantity': 50,
            'side': 'sell',  # SELL position
            'instrument': 'NIFTY',
            'symbol': 'NIFTY24NOV25000PE',
            'order_id': 'ENTRY_456'
        },
        tick_time=datetime.now()
    )
    
    position2 = context_manager.gps.get_position('test-pos-2')
    exit_order2 = exit_node._create_exit_order(context, position2)
    
    print(f"\n📊 Position2 side: {position2.get('side')}")
    print(f"📊 Exit2 order side: {exit_order2.get('side')}")
    
    assert position2.get('side') == 'sell', "Position should be SELL"
    assert exit_order2.get('side') == 'BUY', "Exit should be BUY"
    
    print("\n✅ TEST PASSED: Opposite side logic working")


def test_exit_node_no_position():
    """Test: Exit Node handles missing position gracefully"""
    print("\n" + "="*60)
    print("TEST: Exit Node - Missing Position")
    print("="*60)
    
    context = setup_context_with_position()
    
    # Try to exit non-existent position
    exit_config = {
        'label': 'Exit',
        'exitConfig': {
            'targetPositionVpi': 'non-existent-pos',
            'orderType': 'market'
        }
    }
    
    exit_node = ExitNode('exit-1', exit_config)
    exit_node.mark_active(context)
    
    result = exit_node.execute(context)
    
    print(f"\n✅ Exit Node Executed:")
    print(f"   executed: {result.get('executed')}")
    print(f"   reason: {result.get('reason')}")
    print(f"   positions_closed: {result.get('positions_closed')}")
    
    assert result.get('executed') == True, "Should execute"
    assert result.get('positions_closed') == 0, "Should close 0 positions"
    assert 'not found' in result.get('reason', '').lower(), "Should mention not found"
    
    print("\n✅ TEST PASSED: Handles missing position gracefully")


def test_exit_node_already_closed():
    """Test: Exit Node handles already closed position gracefully"""
    print("\n" + "="*60)
    print("TEST: Exit Node - Already Closed Position")
    print("="*60)
    
    context = setup_context_with_position()
    
    # Close the position first
    context['context_manager'].gps.close_position(
        position_id='test-pos-1',
        exit_data={'price': 25100, 'reason': 'test_close'},
        tick_time=datetime.now()
    )
    
    # Try to exit again
    exit_config = {
        'label': 'Exit',
        'exitConfig': {
            'targetPositionVpi': 'test-pos-1',
            'orderType': 'market'
        }
    }
    
    exit_node = ExitNode('exit-1', exit_config)
    exit_node.mark_active(context)
    
    result = exit_node.execute(context)
    
    print(f"\n✅ Exit Node Executed:")
    print(f"   executed: {result.get('executed')}")
    print(f"   reason: {result.get('reason')}")
    print(f"   positions_closed: {result.get('positions_closed')}")
    
    assert result.get('executed') == True, "Should execute"
    assert result.get('positions_closed') == 0, "Should close 0 positions"
    assert 'no open positions' in result.get('reason', '').lower(), "Should mention no open positions"
    
    print("\n✅ TEST PASSED: Handles already closed position gracefully")


def test_exit_node_pnl_calculation():
    """Test: Exit Node correctly calculates PnL for profit and loss"""
    print("\n" + "="*60)
    print("TEST: Exit Node - PnL Calculation (Profit & Loss)")
    print("="*60)
    
    # Test 1: Profit scenario (BUY at 25000, SELL at 25200)
    context = setup_context_with_position()
    
    exit_config = {
        'label': 'Exit',
        'exitConfig': {
            'targetPositionVpi': 'test-pos-1',
            'orderType': 'market'
        }
    }
    
    exit_node = ExitNode('exit-1', exit_config)
    exit_node.mark_active(context)
    exit_node.execute(context)
    
    position = context['context_manager'].gps.get_position('test-pos-1')
    pnl_profit = position.get('pnl')
    
    print(f"\n📊 Profit Scenario:")
    print(f"   Entry: 25000, Exit: 25200, Qty: 50")
    print(f"   PnL: {pnl_profit} (expected: 10000)")
    
    assert pnl_profit == 10000, f"Profit PnL should be 10000, got {pnl_profit}"
    
    # Test 2: Loss scenario (BUY at 25000, SELL at 24800)
    context2 = ContextManager()
    context2.reset_for_new_strategy_run()
    
    context2.gps.add_position(
        position_id='test-pos-2',
        entry_data={
            'price': 25000,
            'quantity': 50,
            'lot_size': 50,
            'lots': 1,
            'side': 'buy',
            'instrument': 'NIFTY',
            'symbol': 'NIFTY24NOV25000CE',
            'exchange': 'NFO',
            'order_id': 'ENTRY_789',
            'node_id': 'entry-2',
            'position_config': {'productType': 'intraday'}
        },
        tick_time=datetime.now()
    )
    
    # Create exit config for test-pos-2
    exit_config2 = {
        'label': 'Exit',
        'exitConfig': {
            'targetPositionVpi': 'test-pos-2',
            'orderType': 'market'
        }
    }
    
    context_loss = {
        'context_manager': context2,
        'ltp_store': {
            'ltp_TI': {'ltp': 24800, 'symbol': 'NIFTY'}  # Loss
        },
        'current_timestamp': datetime.now(),
        'mode': 'backtesting',
        'node_states': {},
        'node_order_status': {}
    }
    
    exit_node2 = ExitNode('exit-2', exit_config2)
    exit_node2.mark_active(context_loss)
    exit_node2.execute(context_loss)
    
    position2 = context2.gps.get_position('test-pos-2')
    pnl_loss = position2.get('pnl')
    
    print(f"\n📊 Loss Scenario:")
    print(f"   Entry: 25000, Exit: 24800, Qty: 50")
    print(f"   PnL: {pnl_loss} (expected: -10000)")
    
    assert pnl_loss == -10000, f"Loss PnL should be -10000, got {pnl_loss}"
    
    print("\n✅ TEST PASSED: PnL calculation correct for profit and loss")


# ============================================================================
# SQUARE-OFF NODE TESTS
# ============================================================================

def test_squareoff_closes_all_positions():
    """Test: Square-off Node closes all open positions"""
    print("\n" + "="*60)
    print("TEST: Square-off Node - Close All Positions")
    print("="*60)
    
    context_manager = ContextManager()
    context_manager.reset_for_new_strategy_run()
    
    # Add 3 open positions
    for i in range(1, 4):
        context_manager.gps.add_position(
            position_id=f'pos-{i}',
            entry_data={
                'price': 25000 + (i * 100),
                'quantity': 50,
                'lot_size': 50,
                'lots': 1,
                'side': 'buy',
                'instrument': 'NIFTY',
                'symbol': f'NIFTY24NOV{25000 + (i * 100)}CE',
                'exchange': 'NFO',
                'order_id': f'ENTRY_{i}',
                'node_id': f'entry-{i}',
                'position_config': {'productType': 'intraday'}
            },
            tick_time=datetime.now()
        )
    
    context = {
        'context_manager': context_manager,
        'ltp_store': {
            'ltp_TI': {'ltp': 25500, 'symbol': 'NIFTY'}
        },
        'current_timestamp': datetime.now(),
        'mode': 'backtesting',
        'node_states': {
            'node-1': {'status': 'Active'},
            'node-2': {'status': 'Pending'},
            'node-3': {'status': 'Inactive'}
        }
    }
    
    # Create Square-off Node
    squareoff_node = SquareOffNode('squareoff-1', {'label': 'Square-off'})
    squareoff_node.mark_active(context)
    
    # Execute
    result = squareoff_node.execute(context)
    
    print(f"\n✅ Square-off Node Executed:")
    print(f"   executed: {result.get('executed')}")
    print(f"   positions_closed: {result.get('positions_closed')}")
    print(f"   orders_cancelled: {result.get('orders_cancelled')}")
    
    # Check all positions closed
    for i in range(1, 4):
        pos = context_manager.gps.get_position(f'pos-{i}')
        print(f"\n📦 Position pos-{i}:")
        print(f"   status: {pos.get('status')}")
        print(f"   pnl: {pos.get('pnl')}")
        assert pos.get('status') == 'closed', f"Position pos-{i} should be closed"
    
    # Check all nodes inactive
    for node_id, state in context['node_states'].items():
        print(f"\n🔴 Node {node_id}: {state.get('status')}")
        assert state.get('status') == 'Inactive', f"Node {node_id} should be Inactive"
    
    assert result.get('positions_closed') == 3, "Should close 3 positions"
    assert result.get('logic_completed') == True, "Should complete logic"
    
    print("\n✅ TEST PASSED: All positions closed, all nodes inactive")


def test_squareoff_empty_portfolio():
    """Test: Square-off Node handles empty portfolio gracefully"""
    print("\n" + "="*60)
    print("TEST: Square-off Node - Empty Portfolio")
    print("="*60)
    
    context_manager = ContextManager()
    context_manager.reset_for_new_strategy_run()
    
    context = {
        'context_manager': context_manager,
        'ltp_store': {
            'ltp_TI': {'ltp': 25000, 'symbol': 'NIFTY'}
        },
        'current_timestamp': datetime.now(),
        'mode': 'backtesting',
        'node_states': {
            'node-1': {'status': 'Active'}
        }
    }
    
    squareoff_node = SquareOffNode('squareoff-1', {'label': 'Square-off'})
    squareoff_node.mark_active(context)
    
    result = squareoff_node.execute(context)
    
    print(f"\n✅ Square-off Node Executed:")
    print(f"   positions_closed: {result.get('positions_closed')}")
    print(f"   logic_completed: {result.get('logic_completed')}")
    
    assert result.get('positions_closed') == 0, "Should close 0 positions"
    assert result.get('logic_completed') == True, "Should complete logic"
    
    print("\n✅ TEST PASSED: Handles empty portfolio gracefully")


def test_squareoff_backtesting_no_order_cancel():
    """Test: Square-off Node doesn't cancel orders in backtesting mode"""
    print("\n" + "="*60)
    print("TEST: Square-off Node - No Order Cancel in Backtesting")
    print("="*60)
    
    context = setup_context_with_position()
    
    squareoff_node = SquareOffNode('squareoff-1', {'label': 'Square-off'})
    squareoff_node.mark_active(context)
    
    result = squareoff_node.execute(context)
    
    print(f"\n✅ Square-off Node Executed:")
    print(f"   mode: {context.get('mode')}")
    print(f"   orders_cancelled: {result.get('orders_cancelled')}")
    print(f"   positions_closed: {result.get('positions_closed')}")
    
    assert result.get('orders_cancelled') == 0, "Should not cancel orders in backtesting"
    assert result.get('positions_closed') == 1, "Should close 1 position"
    
    print("\n✅ TEST PASSED: No order cancellation in backtesting mode")


def test_squareoff_deactivates_all_nodes():
    """Test: Square-off Node marks all nodes as Inactive"""
    print("\n" + "="*60)
    print("TEST: Square-off Node - Deactivate All Nodes")
    print("="*60)
    
    context = setup_context_with_position()
    
    # Add multiple nodes with different states
    context['node_states'] = {
        'start': {'status': 'Active', 'visited': True},
        'entry-signal': {'status': 'Inactive', 'visited': True},
        'entry': {'status': 'Active', 'visited': False},
        'exit-signal': {'status': 'Pending', 'visited': False},
        'exit': {'status': 'Inactive', 'visited': True}
    }
    
    squareoff_node = SquareOffNode('squareoff-1', {'label': 'Square-off'})
    squareoff_node.mark_active(context)
    
    result = squareoff_node.execute(context)
    
    print(f"\n✅ Node States After Square-off:")
    for node_id, state in context['node_states'].items():
        print(f"   {node_id}: {state.get('status')} (visited: {state.get('visited')})")
        assert state.get('status') == 'Inactive', f"Node {node_id} should be Inactive"
    
    print("\n✅ TEST PASSED: All nodes deactivated")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("EXIT NODE & SQUARE-OFF NODE - COMPREHENSIVE TESTS")
    print("="*60)
    
    try:
        # Exit Node Tests
        test_exit_node_closes_position()
        test_exit_node_opposite_side()
        test_exit_node_no_position()
        test_exit_node_already_closed()
        test_exit_node_pnl_calculation()
        
        # Square-off Node Tests
        test_squareoff_closes_all_positions()
        test_squareoff_empty_portfolio()
        test_squareoff_backtesting_no_order_cancel()
        test_squareoff_deactivates_all_nodes()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED (9/9)")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
