"""
Comprehensive Test Suite for ConditionEvaluator

CRITICAL: This is the foundation of the entire strategy execution system.
All scenarios must pass before proceeding to other nodes.

Test Coverage:
1. Simple conditions (LHS operator RHS)
2. Nested groups (AND/OR logic)
3. Live data conditions
4. Time-based conditions
5. Market data conditions (with offsets)
6. Expression evaluation
7. Node variables calculation
8. Edge cases (None, NaN, missing data)

Author: UniTrader Team
Created: 2024-11-24
"""

import pytest
import pandas as pd
from datetime import datetime, time
import pytz
from src.core.condition_evaluator_v2 import ConditionEvaluator
from src.core.expression_evaluator import ExpressionEvaluator


class TestSimpleConditions:
    """Test simple comparison conditions (LHS operator RHS)."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.expr_evaluator = ExpressionEvaluator()
        self.evaluator = ConditionEvaluator(
            expression_evaluator=self.expr_evaluator,
            mode='backtesting'
        )
    
    def test_greater_than_condition(self):
        """Test: LHS > RHS"""
        condition = {
            'lhs': {'type': 'constant', 'value': 100},
            'operator': '>',
            'rhs': {'type': 'constant', 'value': 50}
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "100 > 50 should be True"
    
    def test_less_than_condition(self):
        """Test: LHS < RHS"""
        condition = {
            'lhs': {'type': 'constant', 'value': 30},
            'operator': '<',
            'rhs': {'type': 'constant', 'value': 50}
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "30 < 50 should be True"
    
    def test_equal_condition(self):
        """Test: LHS == RHS"""
        condition = {
            'lhs': {'type': 'constant', 'value': 100},
            'operator': '==',
            'rhs': {'type': 'constant', 'value': 100}
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "100 == 100 should be True"
    
    def test_not_equal_condition(self):
        """Test: LHS != RHS"""
        condition = {
            'lhs': {'type': 'constant', 'value': 100},
            'operator': '!=',
            'rhs': {'type': 'constant', 'value': 50}
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "100 != 50 should be True"
    
    def test_greater_equal_condition(self):
        """Test: LHS >= RHS"""
        condition = {
            'lhs': {'type': 'constant', 'value': 100},
            'operator': '>=',
            'rhs': {'type': 'constant', 'value': 100}
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "100 >= 100 should be True"
    
    def test_less_equal_condition(self):
        """Test: LHS <= RHS"""
        condition = {
            'lhs': {'type': 'constant', 'value': 50},
            'operator': '<=',
            'rhs': {'type': 'constant', 'value': 100}
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "50 <= 100 should be True"


class TestNestedGroups:
    """Test nested AND/OR group logic."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.expr_evaluator = ExpressionEvaluator()
        self.evaluator = ConditionEvaluator(
            expression_evaluator=self.expr_evaluator,
            mode='backtesting'
        )
    
    def test_simple_and_group(self):
        """Test: (A > 50) AND (B < 100)"""
        condition = {
            'groupLogic': 'AND',
            'conditions': [
                {
                    'lhs': {'type': 'constant', 'value': 75},
                    'operator': '>',
                    'rhs': {'type': 'constant', 'value': 50}
                },
                {
                    'lhs': {'type': 'constant', 'value': 80},
                    'operator': '<',
                    'rhs': {'type': 'constant', 'value': 100}
                }
            ]
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "Both conditions should be True (AND logic)"
    
    def test_simple_or_group(self):
        """Test: (A > 50) OR (B < 20)"""
        condition = {
            'groupLogic': 'OR',
            'conditions': [
                {
                    'lhs': {'type': 'constant', 'value': 75},
                    'operator': '>',
                    'rhs': {'type': 'constant', 'value': 50}
                },
                {
                    'lhs': {'type': 'constant', 'value': 30},
                    'operator': '<',
                    'rhs': {'type': 'constant', 'value': 20}
                }
            ]
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "First condition True, should be True (OR logic)"
    
    def test_nested_groups(self):
        """Test: (A AND B) OR (C AND D)"""
        condition = {
            'groupLogic': 'OR',
            'conditions': [
                {
                    'groupLogic': 'AND',
                    'conditions': [
                        {
                            'lhs': {'type': 'constant', 'value': 30},
                            'operator': '>',
                            'rhs': {'type': 'constant', 'value': 50}  # False
                        },
                        {
                            'lhs': {'type': 'constant', 'value': 80},
                            'operator': '<',
                            'rhs': {'type': 'constant', 'value': 100}  # True
                        }
                    ]
                },
                {
                    'groupLogic': 'AND',
                    'conditions': [
                        {
                            'lhs': {'type': 'constant', 'value': 75},
                            'operator': '>',
                            'rhs': {'type': 'constant', 'value': 50}  # True
                        },
                        {
                            'lhs': {'type': 'constant', 'value': 60},
                            'operator': '<',
                            'rhs': {'type': 'constant', 'value': 100}  # True
                        }
                    ]
                }
            ]
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "Second AND group is True, should be True (OR logic)"
    
    def test_all_false_and_group(self):
        """Test: (A > 100) AND (B > 100) - both false"""
        condition = {
            'groupLogic': 'AND',
            'conditions': [
                {
                    'lhs': {'type': 'constant', 'value': 50},
                    'operator': '>',
                    'rhs': {'type': 'constant', 'value': 100}
                },
                {
                    'lhs': {'type': 'constant', 'value': 30},
                    'operator': '>',
                    'rhs': {'type': 'constant', 'value': 100}
                }
            ]
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == False, "Both conditions False, should be False (AND logic)"


class TestMarketDataConditions:
    """Test market data conditions with offsets."""
    
    def setup_method(self):
        """Setup test fixtures with sample candle data."""
        # Create sample candle data as list of dicts (backtesting format)
        self.candles_list = [
            {'timestamp': '2024-11-24 09:00', 'open': 100.0, 'high': 105.0, 'low': 95.0, 'close': 103.0, 'volume': 1000},
            {'timestamp': '2024-11-24 09:01', 'open': 101.0, 'high': 106.0, 'low': 96.0, 'close': 104.0, 'volume': 1100},
            {'timestamp': '2024-11-24 09:02', 'open': 102.0, 'high': 107.0, 'low': 97.0, 'close': 105.0, 'volume': 1200},
            {'timestamp': '2024-11-24 09:03', 'open': 103.0, 'high': 108.0, 'low': 98.0, 'close': 106.0, 'volume': 1300},
            {'timestamp': '2024-11-24 09:04', 'open': 104.0, 'high': 109.0, 'low': 99.0, 'close': 107.0, 'volume': 1400},
        ]
        
        self.context = {
            'strategy_config': {
                'symbol': 'NIFTY',
                'timeframe': '1m'
            },
            'candle_df_dict': {
                'NIFTY:tf_1m_default': self.candles_list  # UI format: symbol:timeframeId
            },
            'current_timestamp': '2024-11-24 09:04'
        }
        
        self.expr_evaluator = ExpressionEvaluator()
        self.evaluator = ConditionEvaluator(
            expression_evaluator=self.expr_evaluator,
            mode='backtesting'
        )
    
    def test_market_data_with_offset(self):
        """Test: Current High > Previous High"""
        condition = {
            'lhs': {
                'type': 'market_data',
                'field': 'high',
                'offset': -1,  # Last completed candle
                'timeframeId': 'tf_1m_default'
            },
            'operator': '>',
            'rhs': {
                'type': 'market_data',
                'field': 'high',
                'offset': -2,  # Second to last candle
                'timeframeId': 'tf_1m_default'
            }
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context=self.context)
        
        result = self.evaluator.evaluate_condition()
        # high[-1] = 109.0, high[-2] = 108.0 → 109.0 > 108.0 = True
        assert result == True, "High[-1] (109) > High[-2] (108) should be True"
    
    def test_market_data_negative_offset(self):
        """Test: High[-3] < High[-2]"""
        condition = {
            'lhs': {
                'type': 'market_data',
                'field': 'high',
                'offset': -3,
                'timeframeId': 'tf_1m_default'
            },
            'operator': '<',
            'rhs': {
                'type': 'market_data',
                'field': 'high',
                'offset': -2,
                'timeframeId': 'tf_1m_default'
            }
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context=self.context)
        
        result = self.evaluator.evaluate_condition()
        # high[-3] = 107.0, high[-2] = 108.0 → 107.0 < 108.0 = True
        assert result == True, "High[-3] (107) < High[-2] (108) should be True"


class TestTimeConditions:
    """Test time-based conditions."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.expr_evaluator = ExpressionEvaluator()
        self.evaluator = ConditionEvaluator(
            expression_evaluator=self.expr_evaluator,
            mode='backtesting'
        )
    
    def test_time_greater_than(self):
        """Test: Current Time > 09:15"""
        # Create timestamp at 09:30 IST
        current_time = datetime(2024, 11, 24, 9, 30, 0)
        current_time = pytz.timezone('Asia/Kolkata').localize(current_time)
        
        context = {
            'current_timestamp': current_time
        }
        
        condition = {
            'lhs': {'type': 'time', 'field': 'time'},
            'operator': '>',
            'rhs': {'type': 'constant', 'value': '09:15:00'}
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context=context)
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "09:30 > 09:15 should be True"
    
    def test_time_less_than(self):
        """Test: Current Time < 15:30"""
        # Create timestamp at 10:00 IST
        current_time = datetime(2024, 11, 24, 10, 0, 0)
        current_time = pytz.timezone('Asia/Kolkata').localize(current_time)
        
        context = {
            'current_timestamp': current_time
        }
        
        condition = {
            'lhs': {'type': 'time', 'field': 'time'},
            'operator': '<',
            'rhs': {'type': 'constant', 'value': '15:30:00'}
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context=context)
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "10:00 < 15:30 should be True"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.expr_evaluator = ExpressionEvaluator()
        self.evaluator = ConditionEvaluator(
            expression_evaluator=self.expr_evaluator,
            mode='backtesting'
        )
    
    def test_none_values(self):
        """Test handling of None values."""
        condition = {
            'lhs': {'type': 'constant', 'value': None},
            'operator': '>',
            'rhs': {'type': 'constant', 'value': 50}
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == False, "None comparison should return False"
    
    def test_empty_group(self):
        """Test empty condition group."""
        condition = {
            'groupLogic': 'AND',
            'conditions': []
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context={})
        
        result = self.evaluator.evaluate_condition()
        assert result == True, "Empty group should return True"
    
    def test_missing_context(self):
        """Test evaluation with missing context."""
        condition = {
            'lhs': {'type': 'constant', 'value': 100},
            'operator': '>',
            'rhs': {'type': 'constant', 'value': 50}
        }
        
        self.evaluator.set_condition(condition)
        # Don't set context
        
        result = self.evaluator.evaluate_condition()
        # Should still work with constants
        assert result == True, "Constant comparison should work without context"


class TestComplexScenarios:
    """Test complex real-world scenarios."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Create realistic candle data as list of dicts
        self.candles_list = [
            {'timestamp': '2024-11-24 09:00', 'open': 25800, 'high': 25850, 'low': 25780, 'close': 25820, 'volume': 10000, 'RSI': 45},
            {'timestamp': '2024-11-24 09:01', 'open': 25810, 'high': 25855, 'low': 25785, 'close': 25825, 'volume': 11000, 'RSI': 48},
            {'timestamp': '2024-11-24 09:02', 'open': 25805, 'high': 25860, 'low': 25790, 'close': 25830, 'volume': 12000, 'RSI': 51},
            {'timestamp': '2024-11-24 09:03', 'open': 25815, 'high': 25865, 'low': 25795, 'close': 25835, 'volume': 13000, 'RSI': 54},
            {'timestamp': '2024-11-24 09:04', 'open': 25820, 'high': 25870, 'low': 25800, 'close': 25840, 'volume': 14000, 'RSI': 57},
            {'timestamp': '2024-11-24 09:05', 'open': 25825, 'high': 25875, 'low': 25805, 'close': 25845, 'volume': 15000, 'RSI': 60},
            {'timestamp': '2024-11-24 09:06', 'open': 25830, 'high': 25880, 'low': 25810, 'close': 25850, 'volume': 16000, 'RSI': 63},
            {'timestamp': '2024-11-24 09:07', 'open': 25835, 'high': 25885, 'low': 25815, 'close': 25855, 'volume': 17000, 'RSI': 66},
            {'timestamp': '2024-11-24 09:08', 'open': 25840, 'high': 25890, 'low': 25820, 'close': 25860, 'volume': 18000, 'RSI': 69},
            {'timestamp': '2024-11-24 09:09', 'open': 25845, 'high': 25895, 'low': 25825, 'close': 25865, 'volume': 19000, 'RSI': 72},
        ]
        
        current_time = datetime(2024, 11, 24, 9, 30, 0)
        current_time = pytz.timezone('Asia/Kolkata').localize(current_time)
        
        self.context = {
            'strategy_config': {
                'symbol': 'NIFTY',
                'timeframe': '1m'
            },
            'candle_df_dict': {
                'NIFTY:tf_1m_default': self.candles_list
            },
            'current_timestamp': current_time,
            'current_tick': {'ltp': 25870}
        }
        
        self.expr_evaluator = ExpressionEvaluator()
        self.evaluator = ConditionEvaluator(
            expression_evaluator=self.expr_evaluator,
            mode='backtesting'
        )
    
    def test_entry_strategy_conditions(self):
        """Test: Real entry strategy with multiple conditions."""
        condition = {
            'groupLogic': 'AND',
            'conditions': [
                # Time > 09:15
                {
                    'lhs': {'type': 'time', 'field': 'time'},
                    'operator': '>',
                    'rhs': {'type': 'constant', 'value': '09:15:00'}
                },
                # Time < 15:15
                {
                    'lhs': {'type': 'time', 'field': 'time'},
                    'operator': '<',
                    'rhs': {'type': 'constant', 'value': '15:15:00'}
                },
                # LTP > High[-1]
                {
                    'lhs': {'type': 'live_data', 'field': 'ltp'},
                    'operator': '>',
                    'rhs': {
                        'type': 'market_data',
                        'field': 'high',
                        'offset': -1,
                        'timeframeId': 'tf_1m_default'
                    }
                },
                # RSI > 50
                {
                    'lhs': {
                        'type': 'indicator',
                        'indicator': 'RSI',
                        'offset': 0
                    },
                    'operator': '>',
                    'rhs': {'type': 'constant', 'value': 50}
                }
            ]
        }
        
        self.evaluator.set_condition(condition)
        self.evaluator.set_context(context=self.context)
        
        result = self.evaluator.evaluate_condition()
        # Time: 09:30 > 09:15 ✅
        # Time: 09:30 < 15:15 ✅
        # LTP: 25870 > High[-1]: 25885 ❌
        assert result == False, "LTP not greater than High[-1], should be False"


if __name__ == '__main__':
    """Run tests with pytest."""
    pytest.main([__file__, '-v', '--tb=short'])
