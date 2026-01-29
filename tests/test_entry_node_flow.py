#!/usr/bin/env python3
"""
Test Entry Node Flow
- Entry Signal calculates variables
- Entry Node places order and stores position
- GPS updates position prices
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.utils.context_manager import ContextManager
from src.core.expression_evaluator import ExpressionEvaluator
from src.core.condition_evaluator_v2 import ConditionEvaluator
from strategy.nodes.entry_signal_node import EntrySignalNode
from strategy.nodes.entry_node import EntryNode


def test_entry_signal_calculates_variables():
    """Test: Entry Signal Node calculates and stores variables"""
    print("\n" + "="*60)
    print("TEST: Entry Signal Node Variables")
    print("="*60)
    
    # Setup
    context_manager = ContextManager()
    context_manager.reset_for_new_strategy_run()
    
    context = {
        'context_manager': context_manager,
        'expression_evaluator': ExpressionEvaluator(),
        'condition_evaluator': ConditionEvaluator(),
        'ltp_store': {
            'ltp_TI': {'ltp': 25000, 'symbol': 'NIFTY'}
        },
        'current_timestamp': datetime.now(),
        'mode': 'backtesting',
        'node_states': {}
    }
    
    # Entry Signal Node config with variables
    signal_config = {
        'label': 'Entry Signal',
        'conditions': [
            {
                'id': 'root',
                'conditions': [
                    {
                        'id': 'c1',
                        'lhs': {'type': 'constant', 'value': 100, 'valueType': 'number'},
                        'operator': '>',
                        'rhs': {'type': 'constant', 'value': 50, 'valueType': 'number'}
                    }
                ],
                'groupLogic': 'AND'
            }
        ],
        'variables': [
            {
                'name': 'SignalHigh',
                'expression': {'type': 'constant', 'value': 25100, 'valueType': 'number'}
            },
            {
                'name': 'SignalLow',
                'expression': {'type': 'constant', 'value': 24900, 'valueType': 'number'}
            }
        ]
    }
    
    # Create and activate Entry Signal Node
    signal_node = EntrySignalNode('entry-signal-1', signal_config)
    signal_node.mark_active(context)
    
    # Execute
    result = signal_node.execute(context)
    
    print(f"\n✅ Signal Node Executed:")
    print(f"   logic_completed: {result.get('logic_completed')}")
    print(f"   conditions_met: {result.get('conditions_met')}")
    
    # Check variables in GPS
    variables = context_manager.gps.node_variables.get('entry-signal-1', {})
    print(f"\n📊 Variables stored in GPS:")
    for var_name, var_value in variables.items():
        print(f"   {var_name}: {var_value}")
    
    assert variables.get('SignalHigh') == 25100, "SignalHigh should be 25100"
    assert variables.get('SignalLow') == 24900, "SignalLow should be 24900"
    
    print("\n✅ TEST PASSED: Variables calculated and stored")
    return context


def test_entry_node_stores_position(context):
    """Test: Entry Node stores position with variables snapshot"""
    print("\n" + "="*60)
    print("TEST: Entry Node Position Storage")
    print("="*60)
    
    # Entry Node config
    entry_config = {
        'label': 'Entry',
        'positions': [
            {
                'quantity': 1,
                'lotSize': 50,
                'positionType': 'buy',
                'orderType': 'market',
                'productType': 'intraday',
                'vpi': 'test-position-1'
            }
        ],
        'variables': [
            {
                'name': 'EntryLTP',
                'expression': {'type': 'live_data', 'field': 'underlying_ltp', 'instrumentType': 'TI'}
            }
        ]
    }
    
    # Create Entry Node
    entry_node = EntryNode('entry-node-1', entry_config)
    entry_node.instrument = 'NIFTY'
    
    # Add to context
    context['node_instances'] = {
        'entry-signal-1': EntrySignalNode('entry-signal-1', {}),
        'entry-node-1': entry_node
    }
    context['strategy_config'] = {
        'symbol': 'NIFTY',
        'strategy_name': 'Test Strategy'
    }
    
    # Activate Entry Node (simulating activation from Signal Node)
    entry_node.mark_active(context)
    
    # Execute
    result = entry_node.execute(context)
    
    print(f"\n✅ Entry Node Executed:")
    print(f"   executed: {result.get('executed')}")
    print(f"   logic_completed: {result.get('logic_completed')}")
    print(f"   position_stored: {result.get('position_stored')}")
    
    # Check position in GPS
    position = context['context_manager'].gps.get_position('test-position-1')
    
    if position:
        print(f"\n📦 Position stored in GPS:")
        print(f"   position_id: test-position-1")
        print(f"   entry_price: {position.get('entry_price')}")
        print(f"   underlying_price_on_entry: {position.get('underlying_price_on_entry')}")
        print(f"   quantity: {position.get('quantity')}")
        print(f"   lot_size: {position.get('lot_size')}")
        
        # Check node variables snapshot
        node_vars = position.get('node_variables', {})
        print(f"\n📊 Node variables snapshot:")
        for node_id, vars_dict in node_vars.items():
            print(f"   {node_id}:")
            for var_name, var_value in vars_dict.items():
                print(f"      {var_name}: {var_value}")
        
        assert position.get('underlying_price_on_entry') == 25000, "Should capture underlying price"
        assert 'entry-signal-1' in node_vars, "Should have signal node variables"
        assert node_vars['entry-signal-1']['SignalHigh'] == 25100, "Should have SignalHigh"
        
        print("\n✅ TEST PASSED: Position stored with variables")
    else:
        print("\n❌ TEST FAILED: Position not found in GPS")
        return False
    
    return True


def test_gps_updates():
    """Test: GPS updates position prices"""
    print("\n" + "="*60)
    print("TEST: GPS Position Price Updates")
    print("="*60)
    
    # Setup
    context_manager = ContextManager()
    context_manager.reset_for_new_strategy_run()
    
    # Add test position
    context_manager.gps.add_position(
        position_id='test-pos',
        entry_data={
            'price': 100,
            'quantity': 50,
            'side': 'buy',
            'instrument': 'NIFTY'
        },
        tick_time=datetime.now()
    )
    
    # Simulate tick with new price
    ltp_store = {
        'ltp_TI': {'ltp': 110, 'symbol': 'NIFTY'}
    }
    
    context_manager.gps.update_position_prices(ltp_store)
    
    # Check position
    position = context_manager.gps.get_position('test-pos')
    
    print(f"\n📊 Position after update:")
    print(f"   current_price: {position.get('current_price')}")
    print(f"   unrealized_pnl: {position.get('unrealized_pnl')}")
    
    assert position.get('current_price') == 110, "Should update current price"
    assert position.get('unrealized_pnl') == 500, "Should calculate PnL (110-100)*50"
    
    print("\n✅ TEST PASSED: GPS updates working")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("ENTRY NODE FLOW TESTS")
    print("="*60)
    
    try:
        # Test 1: Entry Signal calculates variables
        context = test_entry_signal_calculates_variables()
        
        # Test 2: Entry Node stores position
        test_entry_node_stores_position(context)
        
        # Test 3: GPS updates
        test_gps_updates()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
