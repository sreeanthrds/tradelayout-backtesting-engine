"""
Tests for Expression Evaluator
"""

import pytest
import asyncio
from datetime import datetime

import sys
sys.path.append('..')

from strategy.expression_evaluator import ExpressionEvaluator
from adapters.redis_clickhouse_data_reader import RedisClickHouseDataReader


class MockDataReader:
    """Mock DataReader for testing."""
    
    async def get_ltp(self, symbol: str, role: str):
        """Mock LTP."""
        return {'ltp': 25900.0, 'timestamp': datetime.now()}
    
    async def get_candles(self, symbol: str, timeframe: str, limit: int = 100):
        """Mock candles."""
        return [
            {'ts': datetime.now(), 'open': 100, 'high': 105, 'low': 99, 'close': 103, 'volume': 1000},
            {'ts': datetime.now(), 'open': 103, 'high': 107, 'low': 102, 'close': 106, 'volume': 1200}
        ]
    
    async def get_indicator(self, symbol: str, timeframe: str, indicator_name: str):
        """Mock indicator."""
        if 'ema' in indicator_name.lower():
            return 25850.5
        if 'rsi' in indicator_name.lower():
            return 65.3
        return None
    
    async def get_node_variable(self, user_id: str, strategy_id: str, node_id: str, variable_name: str):
        """Mock node variable."""
        if variable_name == 'entry_price':
            return 150.0
        return None


class TestExpressionEvaluator:
    """Test Expression Evaluator."""
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator with mock data reader."""
        mock_reader = MockDataReader()
        return ExpressionEvaluator(mock_reader)
    
    @pytest.mark.asyncio
    async def test_numeric_literal(self, evaluator):
        """Test numeric literal."""
        result = await evaluator.evaluate('100', 'user1', 'strat1')
        assert result == 100.0
        print("✅ Numeric literal works")
    
    @pytest.mark.asyncio
    async def test_boolean_literal(self, evaluator):
        """Test boolean literal."""
        result = await evaluator.evaluate('TRUE', 'user1', 'strat1')
        assert result == True
        
        result = await evaluator.evaluate('FALSE', 'user1', 'strat1')
        assert result == False
        print("✅ Boolean literals work")
    
    @pytest.mark.asyncio
    async def test_comparison_greater(self, evaluator):
        """Test greater than comparison."""
        result = await evaluator.evaluate('150 > 100', 'user1', 'strat1')
        assert result == True
        
        result = await evaluator.evaluate('50 > 100', 'user1', 'strat1')
        assert result == False
        print("✅ Greater than comparison works")
    
    @pytest.mark.asyncio
    async def test_comparison_less(self, evaluator):
        """Test less than comparison."""
        result = await evaluator.evaluate('50 < 100', 'user1', 'strat1')
        assert result == True
        
        result = await evaluator.evaluate('150 < 100', 'user1', 'strat1')
        assert result == False
        print("✅ Less than comparison works")
    
    @pytest.mark.asyncio
    async def test_comparison_equal(self, evaluator):
        """Test equality comparison."""
        result = await evaluator.evaluate('100 == 100', 'user1', 'strat1')
        assert result == True
        
        result = await evaluator.evaluate('100 == 50', 'user1', 'strat1')
        assert result == False
        print("✅ Equality comparison works")
    
    @pytest.mark.asyncio
    async def test_math_addition(self, evaluator):
        """Test addition."""
        result = await evaluator.evaluate('100 + 50', 'user1', 'strat1')
        assert result == 150.0
        print("✅ Addition works")
    
    @pytest.mark.asyncio
    async def test_math_subtraction(self, evaluator):
        """Test subtraction."""
        result = await evaluator.evaluate('100 - 50', 'user1', 'strat1')
        assert result == 50.0
        print("✅ Subtraction works")
    
    @pytest.mark.asyncio
    async def test_math_multiplication(self, evaluator):
        """Test multiplication."""
        result = await evaluator.evaluate('100 * 2', 'user1', 'strat1')
        assert result == 200.0
        print("✅ Multiplication works")
    
    @pytest.mark.asyncio
    async def test_math_division(self, evaluator):
        """Test division."""
        result = await evaluator.evaluate('100 / 2', 'user1', 'strat1')
        assert result == 50.0
        print("✅ Division works")
    
    @pytest.mark.asyncio
    async def test_logical_and(self, evaluator):
        """Test AND operator."""
        result = await evaluator.evaluate('100 > 50 AND 200 > 100', 'user1', 'strat1')
        assert result == True
        
        result = await evaluator.evaluate('100 > 50 AND 50 > 100', 'user1', 'strat1')
        assert result == False
        print("✅ AND operator works")
    
    @pytest.mark.asyncio
    async def test_logical_or(self, evaluator):
        """Test OR operator."""
        result = await evaluator.evaluate('100 > 50 OR 50 > 100', 'user1', 'strat1')
        assert result == True
        
        result = await evaluator.evaluate('50 > 100 OR 25 > 100', 'user1', 'strat1')
        assert result == False
        print("✅ OR operator works")
    
    @pytest.mark.asyncio
    async def test_ltp_expression(self, evaluator):
        """Test LTP expression."""
        context = {'symbol': 'NIFTY'}
        result = await evaluator.evaluate('ltp_TI', 'user1', 'strat1', context)
        assert result == 25900.0
        print("✅ LTP expression works")
    
    @pytest.mark.asyncio
    async def test_ltp_comparison(self, evaluator):
        """Test LTP comparison."""
        context = {'symbol': 'NIFTY'}
        result = await evaluator.evaluate('ltp_TI > 25000', 'user1', 'strat1', context)
        assert result == True
        print("✅ LTP comparison works")
    
    @pytest.mark.asyncio
    async def test_candle_expression(self, evaluator):
        """Test candle expression."""
        context = {'symbol': 'NIFTY'}
        result = await evaluator.evaluate('candle_TI_5m_close', 'user1', 'strat1', context)
        assert result == 106.0  # Latest candle close
        print("✅ Candle expression works")
    
    @pytest.mark.asyncio
    async def test_candle_offset(self, evaluator):
        """Test candle with offset."""
        context = {'symbol': 'NIFTY'}
        result = await evaluator.evaluate('candle_TI_5m_close[1]', 'user1', 'strat1', context)
        assert result == 103.0  # Previous candle close
        print("✅ Candle offset works")
    
    @pytest.mark.asyncio
    async def test_indicator_expression(self, evaluator):
        """Test indicator expression."""
        context = {'symbol': 'NIFTY'}
        result = await evaluator.evaluate('ema_TI_5m_20', 'user1', 'strat1', context)
        assert result == 25850.5
        print("✅ Indicator expression works")
    
    @pytest.mark.asyncio
    async def test_complex_expression(self, evaluator):
        """Test complex expression."""
        context = {'symbol': 'NIFTY'}
        result = await evaluator.evaluate(
            'ltp_TI > 25000 AND ltp_TI < 26000',
            'user1', 'strat1', context
        )
        assert result == True
        print("✅ Complex expression works")
    
    @pytest.mark.asyncio
    async def test_empty_expression(self, evaluator):
        """Test empty expression."""
        result = await evaluator.evaluate('', 'user1', 'strat1')
        assert result is None
        print("✅ Empty expression handled")
    
    @pytest.mark.asyncio
    async def test_invalid_expression(self, evaluator):
        """Test invalid expression."""
        result = await evaluator.evaluate('invalid_expr', 'user1', 'strat1')
        assert result is None
        print("✅ Invalid expression handled")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("🧪 RUNNING EXPRESSION EVALUATOR TESTS")
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
