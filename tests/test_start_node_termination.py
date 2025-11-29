#!/usr/bin/env python3
"""
Test StartNode Strategy Termination Logic
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.utils.context_manager import ContextManager
from strategy.nodes.start_node_new import StartNode


def test_start_node_terminates_when_all_inactive():
    """Test: StartNode terminates strategy when all nodes are Inactive"""
    print("\n" + "="*60)
    print("TEST: StartNode - Terminate When All Nodes Inactive")
    print("="*60)
    
    # Create StartNode
    start_config = {
        'label': 'Start',
        'tradingInstrumentConfig': {
            'symbol': 'NIFTY',
            'timeframes': [{'timeframe': '5m'}]
        },
        'exchange': 'NSE',
        'strategy_name': 'Test Strategy'
    }
    
    start_node = StartNode('start-1', start_config)
    
    # Setup context
    context_manager = ContextManager()
    context_manager.reset_for_new_strategy_run()
    
    context = {
        'context_manager': context_manager,
        'node_states': {
            'start-1': {'status': 'Inactive'},
            'entry-signal-1': {'status': 'Inactive'},
            'entry-1': {'status': 'Inactive'},
            'exit-signal-1': {'status': 'Inactive'},
            'exit-1': {'status': 'Inactive'}
        },
        'current_timestamp': datetime.now()
    }
    
    # First tick - initialization
    start_node.mark_active(context)
    result1 = start_node.execute(context)
    
    print(f"\n✅ First Tick (Initialization):")
    print(f"   logic_completed: {result1.get('logic_completed')}")
    print(f"   strategy_terminated: {result1.get('strategy_terminated')}")
    
    assert result1.get('logic_completed') == True, "Should complete initialization"
    assert result1.get('strategy_terminated') != True, "Should not terminate on first tick"
    
    # Second tick - all nodes inactive (should terminate)
    result2 = start_node.execute(context)
    
    print(f"\n✅ Second Tick (All Inactive):")
    print(f"   executed: {result2.get('executed')}")
    print(f"   strategy_terminated: {result2.get('strategy_terminated')}")
    print(f"   reason: {result2.get('reason')}")
    print(f"   context['strategy_terminated']: {context.get('strategy_terminated')}")
    
    assert result2.get('strategy_terminated') == True, "Should terminate when all nodes inactive"
    assert context.get('strategy_terminated') == True, "Context flag should be set"
    
    print("\n✅ TEST PASSED: Strategy terminated when all nodes inactive")


def test_start_node_continues_when_nodes_active():
    """Test: StartNode continues strategy when some nodes are Active/Pending"""
    print("\n" + "="*60)
    print("TEST: StartNode - Continue When Nodes Active/Pending")
    print("="*60)
    
    # Create StartNode
    start_config = {
        'label': 'Start',
        'tradingInstrumentConfig': {
            'symbol': 'NIFTY',
            'timeframes': [{'timeframe': '5m'}]
        },
        'exchange': 'NSE',
        'strategy_name': 'Test Strategy'
    }
    
    start_node = StartNode('start-1', start_config)
    
    # Setup context
    context_manager = ContextManager()
    context_manager.reset_for_new_strategy_run()
    
    context = {
        'context_manager': context_manager,
        'node_states': {
            'start-1': {'status': 'Inactive'},
            'entry-signal-1': {'status': 'Active'},  # Active node
            'entry-1': {'status': 'Inactive'},
            'exit-signal-1': {'status': 'Inactive'}
        },
        'current_timestamp': datetime.now()
    }
    
    # First tick - initialization
    start_node.mark_active(context)
    result1 = start_node.execute(context)
    
    print(f"\n✅ First Tick (Initialization):")
    print(f"   logic_completed: {result1.get('logic_completed')}")
    
    # Second tick - one node active (should continue)
    result2 = start_node.execute(context)
    
    print(f"\n✅ Second Tick (One Node Active):")
    print(f"   strategy_terminated: {result2.get('strategy_terminated')}")
    print(f"   context['strategy_terminated']: {context.get('strategy_terminated')}")
    
    assert result2.get('strategy_terminated') != True, "Should not terminate when nodes are active"
    assert context.get('strategy_terminated') != True, "Context flag should not be set"
    
    # Third tick - one node pending (should continue)
    context['node_states']['entry-signal-1']['status'] = 'Inactive'
    context['node_states']['entry-1']['status'] = 'Pending'  # Pending node
    
    result3 = start_node.execute(context)
    
    print(f"\n✅ Third Tick (One Node Pending):")
    print(f"   strategy_terminated: {result3.get('strategy_terminated')}")
    print(f"   context['strategy_terminated']: {context.get('strategy_terminated')}")
    
    assert result3.get('strategy_terminated') != True, "Should not terminate when nodes are pending"
    assert context.get('strategy_terminated') != True, "Context flag should not be set"
    
    print("\n✅ TEST PASSED: Strategy continues when nodes are Active/Pending")


def test_start_node_termination_count():
    """Test: StartNode correctly counts Active/Pending nodes"""
    print("\n" + "="*60)
    print("TEST: StartNode - Active/Pending Node Counting")
    print("="*60)
    
    # Create StartNode
    start_config = {
        'label': 'Start',
        'tradingInstrumentConfig': {
            'symbol': 'NIFTY',
            'timeframes': [{'timeframe': '5m'}]
        },
        'exchange': 'NSE',
        'strategy_name': 'Test Strategy'
    }
    
    start_node = StartNode('start-1', start_config)
    
    # Setup context
    context_manager = ContextManager()
    context_manager.reset_for_new_strategy_run()
    
    # Test 1: Multiple Active nodes
    context1 = {
        'context_manager': context_manager,
        'node_states': {
            'start-1': {'status': 'Inactive'},
            'node-1': {'status': 'Active'},
            'node-2': {'status': 'Active'},
            'node-3': {'status': 'Inactive'}
        }
    }
    
    # Initialize first
    start_node.mark_active(context1)
    start_node.execute(context1)
    
    should_terminate_1 = start_node._should_terminate_strategy(context1)
    print(f"\n📊 Test 1 - Multiple Active nodes:")
    print(f"   Active: 2, Pending: 0, Inactive: 2")
    print(f"   Should terminate: {should_terminate_1}")
    assert should_terminate_1 == False, "Should not terminate with active nodes"
    
    # Test 2: Multiple Pending nodes
    context2 = {
        'context_manager': context_manager,
        'node_states': {
            'start-1': {'status': 'Inactive'},
            'node-1': {'status': 'Pending'},
            'node-2': {'status': 'Pending'},
            'node-3': {'status': 'Inactive'}
        }
    }
    
    should_terminate_2 = start_node._should_terminate_strategy(context2)
    print(f"\n📊 Test 2 - Multiple Pending nodes:")
    print(f"   Active: 0, Pending: 2, Inactive: 2")
    print(f"   Should terminate: {should_terminate_2}")
    assert should_terminate_2 == False, "Should not terminate with pending nodes"
    
    # Test 3: Mix of Active and Pending
    context3 = {
        'context_manager': context_manager,
        'node_states': {
            'start-1': {'status': 'Inactive'},
            'node-1': {'status': 'Active'},
            'node-2': {'status': 'Pending'},
            'node-3': {'status': 'Inactive'}
        }
    }
    
    should_terminate_3 = start_node._should_terminate_strategy(context3)
    print(f"\n📊 Test 3 - Mix of Active and Pending:")
    print(f"   Active: 1, Pending: 1, Inactive: 2")
    print(f"   Should terminate: {should_terminate_3}")
    assert should_terminate_3 == False, "Should not terminate with active or pending nodes"
    
    # Test 4: All Inactive
    context4 = {
        'context_manager': context_manager,
        'node_states': {
            'start-1': {'status': 'Inactive'},
            'node-1': {'status': 'Inactive'},
            'node-2': {'status': 'Inactive'},
            'node-3': {'status': 'Inactive'}
        }
    }
    
    should_terminate_4 = start_node._should_terminate_strategy(context4)
    print(f"\n📊 Test 4 - All Inactive:")
    print(f"   Active: 0, Pending: 0, Inactive: 4")
    print(f"   Should terminate: {should_terminate_4}")
    assert should_terminate_4 == True, "Should terminate when all nodes inactive"
    
    print("\n✅ TEST PASSED: Active/Pending counting is correct")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("START NODE TERMINATION LOGIC - COMPREHENSIVE TESTS")
    print("="*60)
    
    try:
        test_start_node_terminates_when_all_inactive()
        test_start_node_continues_when_nodes_active()
        test_start_node_termination_count()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED (3/3)")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
