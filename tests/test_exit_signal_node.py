"""
Comprehensive tests for Exit Signal Node.

Tests:
1. Normal exit conditions (reEntryNum == 0)
2. Re-entry exit conditions (reEntryNum > 0)
3. Variable calculation and storage
4. Condition evaluation with GPS data
5. Node activation flow

Author: UniTrader Team
Created: 2024-11-24
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import directly to avoid package init issues
from strategy.nodes.exit_signal_node_new import ExitSignalNode
from src.core.condition_evaluator_v2 import ConditionEvaluator
from src.core.expression_evaluator import ExpressionEvaluator
from src.utils.context_manager import ContextManager


class TestExitSignalNodeBasic:
    """Test basic exit signal node functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create context manager (GPS)
        self.context_manager = ContextManager()
        self.context_manager.reset_for_new_strategy_run()
        
        # Create evaluators
        self.expression_evaluator = ExpressionEvaluator()
        self.condition_evaluator = ConditionEvaluator(
            expression_evaluator=self.expression_evaluator,
            mode='backtesting'
        )
        
        # Create base context
        self.context = {
            'context_manager': self.context_manager,
            'expression_evaluator': self.expression_evaluator,
            'condition_evaluator': self.condition_evaluator,
            'current_timestamp': datetime(2024, 11, 24, 9, 30, 0),
            'current_tick': {'ltp': 25900, 'symbol': 'NIFTY'},
            'ltp_store': {
                'ltp_TI': {'ltp': 25900, 'symbol': 'NIFTY'}
            },
            'node_states': {}
        }
    
    def test_normal_exit_conditions_pass(self):
        """Test: Normal exit conditions pass (reEntryNum == 0)."""
        # Create node with normal exit conditions
        node_config = {
            'id': 'exit-condition-1',
            'type': 'exitSignalNode',
            'data': {
                'label': 'Exit Condition',
                'conditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-1',
                                'lhs': {'type': 'constant', 'value': 100, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 50, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'hasReEntryExitConditions': False
            }
        }
        
        node = ExitSignalNode('exit-condition-1', node_config)
        
        # Initialize node state with reEntryNum = 0
        
        # Mark node as active
        node.mark_active(self.context)

        # Execute node
        result = node.execute(self.context)
        
        # Verify
        assert result['executed'] == True, "Node should execute"
        assert result.get('logic_completed') == True, "Logic should complete"
        assert result.get('conditions_met') == True, "Conditions should pass"
        assert result.get('condition_type') == 'normal', "Should use normal conditions"
        assert result.get('re_entry_num') == 0, "reEntryNum should be 0"
    
    def test_normal_exit_conditions_fail(self):
        """Test: Normal exit conditions fail."""
        # Create node with failing conditions
        node_config = {
            'id': 'exit-condition-1',
            'type': 'exitSignalNode',
            'data': {
                'label': 'Exit Condition',
                'conditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-1',
                                'lhs': {'type': 'constant', 'value': 50, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 100, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'hasReEntryExitConditions': False
            }
        }
        
        node = ExitSignalNode('exit-condition-1', node_config)
        
        # Mark node as active
        node.mark_active(self.context)

        # Execute node
        result = node.execute(self.context)
        
        # Verify
        assert result['executed'] == True, "Node should execute"
        assert result.get('logic_completed') == False, "Logic should not complete"
        assert result.get('conditions_met') == False, "Conditions should fail"


class TestExitSignalNodeReEntry:
    """Test re-entry exit condition functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.context_manager = ContextManager()
        self.context_manager.reset_for_new_strategy_run()
        
        self.expression_evaluator = ExpressionEvaluator()
        self.condition_evaluator = ConditionEvaluator(
            expression_evaluator=self.expression_evaluator,
            mode='backtesting'
        )
        
        self.context = {
            'context_manager': self.context_manager,
            'expression_evaluator': self.expression_evaluator,
            'condition_evaluator': self.condition_evaluator,
            'current_timestamp': datetime(2024, 11, 24, 9, 30, 0),
            'current_tick': {'ltp': 25900, 'symbol': 'NIFTY'},
            'ltp_store': {
                'ltp_TI': {'ltp': 25900, 'symbol': 'NIFTY'}
            },
            'node_states': {}
        }
    
    def test_reentry_conditions_with_reentry_num_1(self):
        """Test: Re-entry conditions used when reEntryNum == 1."""
        # Create node with both normal and re-entry conditions
        node_config = {
            'id': 'exit-condition-1',
            'type': 'exitSignalNode',
            'data': {
                'label': 'Exit Condition',
                'conditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-1',
                                'lhs': {'type': 'constant', 'value': 50, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 100, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'reEntryExitConditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-2',
                                'lhs': {'type': 'constant', 'value': 200, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 100, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'hasReEntryExitConditions': True
            }
        }
        
        node = ExitSignalNode('exit-condition-1', node_config)
        
        # Set reEntryNum to 1
        self.context["node_states"][node.id] = {"status": "Active", "visited": False, "reEntryNum": 1}
        
        # Mark node as active
        node.mark_active(self.context)

        # Execute node
        result = node.execute(self.context)
        
        # Verify
        assert result['executed'] == True, "Node should execute"
        assert result.get('logic_completed') == True, "Logic should complete (re-entry conditions pass)"
        assert result.get('conditions_met') == True, "Re-entry conditions should pass"
        assert result.get('condition_type') == 're-entry', "Should use re-entry conditions"
        assert result.get('re_entry_num') == 1, "reEntryNum should be 1"
    
    def test_reentry_num_2_uses_reentry_conditions(self):
        """Test: Re-entry conditions used when reEntryNum == 2."""
        node_config = {
            'id': 'exit-condition-1',
            'type': 'exitSignalNode',
            'data': {
                'label': 'Exit Condition',
                'conditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-1',
                                'lhs': {'type': 'constant', 'value': 50, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 100, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'reEntryExitConditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-2',
                                'lhs': {'type': 'constant', 'value': 300, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 200, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'hasReEntryExitConditions': True
            }
        }
        
        node = ExitSignalNode('exit-condition-1', node_config)
        self.context["node_states"][node.id] = {"status": "Active", "visited": False, "reEntryNum": 2}
        
        result = node.execute(self.context)
        
        assert result.get('condition_type') == 're-entry', "Should use re-entry conditions with reEntryNum=2"
        assert result.get('re_entry_num') == 2, "reEntryNum should be 2"
    
    def test_reentry_with_reentrynum_greater_than_zero(self):
        """Test: Re-entry conditions used when reEntryNum > 0 (flag is ignored)."""
        node_config = {
            'id': 'exit-condition-1',
            'type': 'exitSignalNode',
            'data': {
                'label': 'Exit Condition',
                'conditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-1',
                                'lhs': {'type': 'constant', 'value': 100, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 50, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'reEntryExitConditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-2',
                                'lhs': {'type': 'constant', 'value': 200, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 100, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'hasReEntryExitConditions': False  # Flag is ignored!
            }
        }
        
        node = ExitSignalNode('exit-condition-1', node_config)
        self.context["node_states"][node.id] = {"status": "Active", "visited": False, "reEntryNum": 1}
        
        result = node.execute(self.context)
        
        # Should use re-entry conditions because reEntryNum > 0 (flag is ignored)
        assert result.get('condition_type') == 're-entry', "Should use re-entry conditions when reEntryNum > 0"
        assert result.get('logic_completed') == True, "Re-entry conditions should pass"


class TestExitSignalNodeVariables:
    """Test node variable calculation and storage."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.context_manager = ContextManager()
        self.context_manager.reset_for_new_strategy_run()
        
        self.expression_evaluator = ExpressionEvaluator()
        self.condition_evaluator = ConditionEvaluator(
            expression_evaluator=self.expression_evaluator,
            mode='backtesting'
        )
        
        self.context = {
            'context_manager': self.context_manager,
            'expression_evaluator': self.expression_evaluator,
            'condition_evaluator': self.condition_evaluator,
            'current_timestamp': datetime(2024, 11, 24, 9, 30, 0),
            'current_tick': {'ltp': 25900, 'symbol': 'NIFTY'},
            'ltp_store': {
                'ltp_TI': {'ltp': 25900, 'symbol': 'NIFTY'}
            },
            'node_states': {}
        }
    
    def test_calculate_and_store_variables(self):
        """Test: Calculate node variables and store in GPS."""
        # Create node with variables
        node_config = {
            'id': 'exit-condition-1',
            'type': 'exitSignalNode',
            'data': {
                'label': 'Exit Condition',
                'conditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-1',
                                'lhs': {'type': 'constant', 'value': 100, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 50, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'node_variables': [
                    {
                        'id': 'var-1',
                        'name': 'ExitLTP',
                        'nodeId': 'exit-condition-1',
                        'expression': {
                            'type': 'live_data',
                            'field': 'ltp',
                            'instrumentType': 'TI'
                        }
                    },
                    {
                        'id': 'var-2',
                        'name': 'ExitConstant',
                        'nodeId': 'exit-condition-1',
                        'expression': {
                            'type': 'constant',
                            'value': 100,
                            'valueType': 'number'
                        }
                    }
                ],
                'hasReEntryExitConditions': False
            }
        }
        
        node = ExitSignalNode('exit-condition-1', node_config)
        
        # Mark node as active
        node.mark_active(self.context)

        # Execute node
        result = node.execute(self.context)
        
        # Verify execution
        assert result.get('logic_completed') == True, "Logic should complete"
        assert result.get('conditions_met') == True, "Conditions should pass"
        
        # Verify variables calculated
        variables = result.get('variables_calculated', {})
        assert 'ExitLTP' in variables, "ExitLTP should be calculated"
        assert variables['ExitLTP'] == 25900, "ExitLTP should match current LTP"
        assert 'ExitConstant' in variables, "ExitConstant should be calculated"
        assert variables['ExitConstant'] == 100, "ExitConstant should be 100"
        
        # Verify variables stored in GPS
        stored_ltp = self.context_manager.get_node_variable('exit-condition-1', 'ExitLTP')
        stored_constant = self.context_manager.get_node_variable('exit-condition-1', 'ExitConstant')
        assert stored_ltp == 25900, "ExitLTP should be stored in GPS"
        assert stored_constant == 100, "ExitConstant should be stored in GPS"
    
    def test_variables_not_calculated_when_conditions_fail(self):
        """Test: Variables not calculated when conditions fail."""
        node_config = {
            'id': 'exit-condition-1',
            'type': 'exitSignalNode',
            'data': {
                'label': 'Exit Condition',
                'conditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-1',
                                'lhs': {'type': 'constant', 'value': 50, 'valueType': 'number'},
                                'operator': '>',
                                'rhs': {'type': 'constant', 'value': 100, 'valueType': 'number'}
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'node_variables': [
                    {
                        'id': 'var-1',
                        'name': 'ExitLTP',
                        'nodeId': 'exit-condition-1',
                        'expression': {
                            'type': 'live_data',
                            'field': 'ltp',
                            'instrumentType': 'TI'
                        }
                    }
                ],
                'hasReEntryExitConditions': False
            }
        }
        
        node = ExitSignalNode('exit-condition-1', node_config)
        
        # Mark node as active
        node.mark_active(self.context)

        result = node.execute(self.context)
        
        # Verify conditions failed
        assert result.get('conditions_met') == False, "Conditions should fail"
        
        # Verify variables not calculated
        variables = result.get('variables_calculated')
        assert variables is None, "Variables should not be calculated when conditions fail"
        
        # Verify variables not in GPS
        stored_value = self.context_manager.get_node_variable('exit-condition-1', 'ExitLTP')
        assert stored_value is None, "Variable should not be in GPS"


class TestExitSignalNodeWithRealConditions:
    """Test with realistic exit conditions using live data and node variables."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.context_manager = ContextManager()
        self.context_manager.reset_for_new_strategy_run()
        
        # Store entry signal variable
        self.context_manager.set_node_variable('entry-condition-1', 'SignalLow', 25800)
        
        self.expression_evaluator = ExpressionEvaluator()
        self.condition_evaluator = ConditionEvaluator(
            expression_evaluator=self.expression_evaluator,
            mode='backtesting'
        )
        
        self.context = {
            'context_manager': self.context_manager,
            'expression_evaluator': self.expression_evaluator,
            'condition_evaluator': self.condition_evaluator,
            'current_timestamp': datetime(2024, 11, 24, 9, 30, 0),
            'current_tick': {'ltp': 25900, 'symbol': 'NIFTY'},
            'ltp_store': {
                'ltp_TI': {'ltp': 25900, 'symbol': 'NIFTY'}
            },
            'node_states': {}
        }
    
    def test_real_exit_condition_ltp_greater_than_signal_low(self):
        """Test: Exit when LTP > Entry SignalLow (realistic condition)."""
        # Condition: underlying_ltp > entry-condition-1.SignalLow
        node_config = {
            'id': 'exit-condition-1',
            'type': 'exitSignalNode',
            'data': {
                'label': 'Exit Condition',
                'conditions': [
                    {
                        'id': 'root',
                        'conditions': [
                            {
                                'id': 'cond-1',
                                'lhs': {
                                    'type': 'live_data',
                                    'field': 'ltp',
                                    'instrumentType': 'TI'
                                },
                                'operator': '>',
                                'rhs': {
                                    'type': 'node_variable',
                                    'nodeId': 'entry-condition-1',
                                    'variableName': 'SignalLow'
                                }
                            }
                        ],
                        'groupLogic': 'AND'
                    }
                ],
                'hasReEntryExitConditions': False
            }
        }
        
        node = ExitSignalNode('exit-condition-1', node_config)
        
        # Mark node as active
        node.mark_active(self.context)

        result = node.execute(self.context)
        
        # Verify: LTP (25900) > SignalLow (25800) = True
        assert result.get('conditions_met') == True, "Exit condition should pass (25900 > 25800)"
        assert result.get('logic_completed') == True, "Logic should complete"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
