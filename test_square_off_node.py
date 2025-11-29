#!/usr/bin/env python3
"""
Test SquareOffNode with all three exit types
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, time
from strategy.nodes.square_off_node import SquareOffNode

# Mock context for testing
def create_mock_context(current_time=None, total_pnl=0, open_positions_count=2):
    """Create a mock context for testing."""
    
    # Mock GPS
    class MockGPS:
        def get_open_positions(self):
            return {f'pos_{i}': {'entry_price': 100, 'quantity': 1} for i in range(open_positions_count)}
        
        def get_closed_positions(self):
            return {}
    
    # Mock Context Manager
    class MockContextManager:
        def __init__(self):
            self.closed_positions = []
        
        def get_gps(self):
            return MockGPS()
        
        def close_position(self, position_id, exit_data, timestamp):
            """Mock close position."""
            self.closed_positions.append({
                'position_id': position_id,
                'exit_data': exit_data,
                'timestamp': timestamp
            })
            return {'success': True}
    
    context = {
        'mode': 'backtesting',
        'current_timestamp': current_time or datetime.now(),
        'current_tick': {'ltp': 105, 'close': 105},
        'context_manager': MockContextManager(),
        'strategy_config': {'symbol': 'NIFTY'},
        'node_states': {
            'entry-1': {'status': 'Active'},
            'exit-1': {'status': 'Active'}
        },
        'ltp_store': {'ltp_TI': {'ltp': 105}}
    }
    
    return context


def test_immediate_exit():
    """Test Immediate Exit (triggered by parent condition)."""
    print("\n" + "="*80)
    print("TEST 1: IMMEDIATE EXIT")
    print("="*80)
    
    config = {
        "id": "square-off-immediate",
        "type": "SquareOffNode",
        "data": {
            "label": "Emergency Exit",
            "endConditions": {
                "immediateExit": {
                    "enabled": True
                }
            }
        }
    }
    
    node = SquareOffNode(config['id'], config['data'])
    context = create_mock_context()
    
    # Add node state to context
    context['node_states'][config['id']] = {'status': 'Inactive'}
    
    # Mark node as Active (simulating parent activation)
    node.mark_active(context)
    
    # Execute
    result = node._execute_node_logic(context)
    
    print(f"\n✅ Test Result:")
    print(f"  Executed: {result.get('executed')}")
    print(f"  Reason: {result.get('reason')}")
    print(f"  Condition Type: {result.get('condition_type')}")
    print(f"  Logic Completed: {result.get('logic_completed')}")
    print(f"  Positions Closed: {result.get('positions_closed', 0)}")
    
    assert result.get('executed') == True, "Should execute square-off"
    assert result.get('condition_type') == 'immediateExit', "Should be immediate exit"
    assert result.get('logic_completed') == True, "Should complete logic"
    assert context.get('strategy_ended') == True, "Should end strategy"
    
    print("\n✅ IMMEDIATE EXIT TEST PASSED")


def test_time_based_exit_before_market_close():
    """Test Time-based Exit (5 minutes before market close)."""
    print("\n" + "="*80)
    print("TEST 2: TIME-BASED EXIT (Market Close)")
    print("="*80)
    
    config = {
        "id": "square-off-time",
        "type": "SquareOffNode",
        "data": {
            "label": "Market Close Exit",
            "endConditions": {
                "timeBasedExit": {
                    "enabled": True,
                    "exitAtMarketClose": True,
                    "minutesBeforeClose": 5
                }
            }
        }
    }
    
    node = SquareOffNode(config['id'], config['data'])
    
    # Test 1: Before exit time (should NOT execute)
    print("\n--- Test 2a: Before Exit Time (15:20) ---")
    context = create_mock_context(current_time=datetime(2024, 10, 1, 15, 20))
    node.mark_active(context)
    result = node._execute_node_logic(context)
    
    print(f"  Executed: {result.get('executed')}")
    print(f"  Reason: {result.get('reason')}")
    print(f"  Logic Completed: {result.get('logic_completed')}")
    
    assert result.get('executed') == False, "Should NOT execute before exit time"
    assert result.get('logic_completed') == False, "Should stay active"
    
    # Test 2: At exit time (should execute)
    print("\n--- Test 2b: At Exit Time (15:25) ---")
    context = create_mock_context(current_time=datetime(2024, 10, 1, 15, 25))
    node.mark_active(context)
    result = node._execute_node_logic(context)
    
    print(f"  Executed: {result.get('executed')}")
    print(f"  Reason: {result.get('reason')}")
    print(f"  Condition Type: {result.get('condition_type')}")
    print(f"  Logic Completed: {result.get('logic_completed')}")
    
    assert result.get('executed') == True, "Should execute at exit time"
    assert result.get('condition_type') == 'timeBasedExit', "Should be time-based exit"
    assert result.get('logic_completed') == True, "Should complete logic"
    
    print("\n✅ TIME-BASED EXIT (MARKET CLOSE) TEST PASSED")


def test_time_based_exit_specific_time():
    """Test Time-based Exit (specific time)."""
    print("\n" + "="*80)
    print("TEST 3: TIME-BASED EXIT (Specific Time)")
    print("="*80)
    
    config = {
        "id": "square-off-time",
        "type": "SquareOffNode",
        "data": {
            "label": "Fixed Time Exit",
            "endConditions": {
                "timeBasedExit": {
                    "enabled": True,
                    "exitTime": "15:00:00"
                }
            }
        }
    }
    
    node = SquareOffNode(config['id'], config['data'])
    
    # Test 1: Before exit time (should NOT execute)
    print("\n--- Test 3a: Before Exit Time (14:55) ---")
    context = create_mock_context(current_time=datetime(2024, 10, 1, 14, 55))
    node.mark_active(context)
    result = node._execute_node_logic(context)
    
    print(f"  Executed: {result.get('executed')}")
    print(f"  Reason: {result.get('reason')}")
    
    assert result.get('executed') == False, "Should NOT execute before exit time"
    
    # Test 2: At exit time (should execute)
    print("\n--- Test 3b: At Exit Time (15:00) ---")
    context = create_mock_context(current_time=datetime(2024, 10, 1, 15, 0))
    node.mark_active(context)
    result = node._execute_node_logic(context)
    
    print(f"  Executed: {result.get('executed')}")
    print(f"  Reason: {result.get('reason')}")
    
    assert result.get('executed') == True, "Should execute at exit time"
    
    print("\n✅ TIME-BASED EXIT (SPECIFIC TIME) TEST PASSED")


def test_performance_based_exit_profit():
    """Test Performance-based Exit (profit target reached)."""
    print("\n" + "="*80)
    print("TEST 4: PERFORMANCE-BASED EXIT (Profit Target)")
    print("="*80)
    
    config = {
        "id": "square-off-pnl",
        "type": "SquareOffNode",
        "data": {
            "label": "P&L Target Exit",
            "endConditions": {
                "performanceBasedExit": {
                    "enabled": True,
                    "dailyPnLTarget": {
                        "enabled": True,
                        "targetType": "absolute",
                        "targetAmount": 100
                    }
                }
            }
        }
    }
    
    node = SquareOffNode(config['id'], config['data'])
    
    # Test 1: P&L below target (should NOT execute)
    print("\n--- Test 4a: P&L Below Target (50) ---")
    context = create_mock_context(current_time=datetime(2024, 10, 1, 14, 0))
    # Mock: 2 open positions with entry_price=100, current_price=105 → P&L = 5*2 = 10
    context['current_tick']['ltp'] = 105
    node.mark_active(context)
    result = node._execute_node_logic(context)
    
    print(f"  Executed: {result.get('executed')}")
    print(f"  Reason: {result.get('reason')}")
    
    assert result.get('executed') == False, "Should NOT execute below profit target"
    
    # Test 2: P&L at/above target (should execute)
    print("\n--- Test 4b: P&L Above Target (100+) ---")
    context = create_mock_context(current_time=datetime(2024, 10, 1, 14, 30))
    # Mock: 2 open positions with entry_price=100, current_price=150 → P&L = 50*2 = 100
    context['current_tick']['ltp'] = 150
    node.mark_active(context)
    result = node._execute_node_logic(context)
    
    print(f"  Executed: {result.get('executed')}")
    print(f"  Reason: {result.get('reason')}")
    print(f"  Condition Type: {result.get('condition_type')}")
    
    assert result.get('executed') == True, "Should execute at profit target"
    assert result.get('condition_type') == 'performanceBasedExit', "Should be performance exit"
    assert 'profit target' in result.get('reason', '').lower(), "Should mention profit target"
    
    print("\n✅ PERFORMANCE-BASED EXIT (PROFIT) TEST PASSED")


def test_performance_based_exit_loss():
    """Test Performance-based Exit (loss limit reached)."""
    print("\n" + "="*80)
    print("TEST 5: PERFORMANCE-BASED EXIT (Loss Limit)")
    print("="*80)
    
    config = {
        "id": "square-off-pnl",
        "type": "SquareOffNode",
        "data": {
            "label": "P&L Loss Limit Exit",
            "endConditions": {
                "performanceBasedExit": {
                    "enabled": True,
                    "dailyPnLTarget": {
                        "enabled": True,
                        "targetType": "absolute",
                        "targetAmount": 100
                    }
                }
            }
        }
    }
    
    node = SquareOffNode(config['id'], config['data'])
    
    # Test: P&L at/below loss limit (should execute)
    print("\n--- Test 5: P&L Below Loss Limit (-100) ---")
    context = create_mock_context(current_time=datetime(2024, 10, 1, 14, 30))
    # Mock: 2 open positions with entry_price=100, current_price=50 → P&L = -50*2 = -100
    context['current_tick']['ltp'] = 50
    node.mark_active(context)
    result = node._execute_node_logic(context)
    
    print(f"  Executed: {result.get('executed')}")
    print(f"  Reason: {result.get('reason')}")
    print(f"  Condition Type: {result.get('condition_type')}")
    
    assert result.get('executed') == True, "Should execute at loss limit"
    assert result.get('condition_type') == 'performanceBasedExit', "Should be performance exit"
    assert 'loss limit' in result.get('reason', '').lower(), "Should mention loss limit"
    
    print("\n✅ PERFORMANCE-BASED EXIT (LOSS) TEST PASSED")


def test_priority_order():
    """Test that exit conditions are evaluated in correct priority order."""
    print("\n" + "="*80)
    print("TEST 6: PRIORITY ORDER (Immediate > Performance > Time)")
    print("="*80)
    
    config = {
        "id": "square-off-all",
        "type": "SquareOffNode",
        "data": {
            "label": "All Exit Types",
            "endConditions": {
                "immediateExit": {
                    "enabled": True
                },
                "performanceBasedExit": {
                    "enabled": True,
                    "dailyPnLTarget": {
                        "enabled": True,
                        "targetType": "absolute",
                        "targetAmount": 100
                    }
                },
                "timeBasedExit": {
                    "enabled": True,
                    "exitTime": "15:25:00"
                }
            }
        }
    }
    
    node = SquareOffNode(config['id'], config['data'])
    
    # All conditions met - should trigger immediate exit (highest priority)
    context = create_mock_context(current_time=datetime(2024, 10, 1, 15, 25))
    context['current_tick']['ltp'] = 150  # P&L = 100 (profit target met)
    node.mark_active(context)
    result = node._execute_node_logic(context)
    
    print(f"  Executed: {result.get('executed')}")
    print(f"  Condition Type: {result.get('condition_type')}")
    print(f"  Reason: {result.get('reason')}")
    
    assert result.get('executed') == True, "Should execute"
    assert result.get('condition_type') == 'immediateExit', "Should prioritize immediate exit"
    
    print("\n✅ PRIORITY ORDER TEST PASSED")


def test_duplicate_execution_prevention():
    """Test that square-off doesn't execute twice."""
    print("\n" + "="*80)
    print("TEST 7: DUPLICATE EXECUTION PREVENTION")
    print("="*80)
    
    config = {
        "id": "square-off-dup",
        "type": "SquareOffNode",
        "data": {
            "label": "Duplicate Test",
            "endConditions": {
                "immediateExit": {
                    "enabled": True
                }
            }
        }
    }
    
    node = SquareOffNode(config['id'], config['data'])
    context = create_mock_context()
    node.mark_active(context)
    
    # First execution
    print("\n--- First Execution ---")
    result1 = node._execute_node_logic(context)
    print(f"  Executed: {result1.get('executed')}")
    print(f"  Positions Closed: {result1.get('positions_closed', 0)}")
    
    assert result1.get('executed') == True, "First execution should succeed"
    
    # Second execution (should be prevented)
    print("\n--- Second Execution (should be prevented) ---")
    result2 = node._execute_node_logic(context)
    print(f"  Executed: {result2.get('executed')}")
    print(f"  Reason: {result2.get('reason')}")
    
    assert result2.get('executed') == False, "Second execution should be prevented"
    assert 'already executed' in result2.get('reason', '').lower(), "Should mention already executed"
    
    print("\n✅ DUPLICATE EXECUTION PREVENTION TEST PASSED")


if __name__ == "__main__":
    print("\n")
    print("="*80)
    print("SQUARE-OFF NODE TEST SUITE")
    print("="*80)
    
    try:
        test_immediate_exit()
        test_time_based_exit_before_market_close()
        test_time_based_exit_specific_time()
        test_performance_based_exit_profit()
        test_performance_based_exit_loss()
        test_priority_order()
        test_duplicate_execution_prevention()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nSquareOffNode is production-ready! 🚀")
        print("- Immediate exit: ✅")
        print("- Time-based exit: ✅")
        print("- Performance-based exit: ✅")
        print("- Priority order: ✅")
        print("- Duplicate prevention: ✅")
        print("="*80 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
