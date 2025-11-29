"""
Expression Evaluator - Async Version with DataReader

Evaluates all expression types using DataReader interface.
ZERO dependency on old context!
"""

import re
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from interfaces.data_reader import DataReaderInterface


logger = logging.getLogger(__name__)


class ExpressionEvaluator:
    """
    Evaluates expressions using DataReader.
    
    Supported expressions:
    - LTP: ltp_TI, ltp_SI, ltp_position_id
    - Candles: candle_TI_5m_close, candle_SI_1h_high
    - Indicators: ema_TI_5m_20, rsi_SI_15m_14
    - Node variables: node_var_entry_3_entry_price
    - Comparisons: >, <, >=, <=, ==, !=
    - Logical: AND, OR
    - Math: +, -, *, /, %
    """
    
    def __init__(self, data_reader: DataReaderInterface):
        """Initialize with DataReader."""
        self.data_reader = data_reader
    
    async def evaluate(
        self,
        expression: str,
        user_id: str,
        strategy_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Evaluate an expression.
        
        Args:
            expression: Expression string
            user_id: User ID
            strategy_id: Strategy ID
            context: Optional context with symbol, timeframe, etc.
        
        Returns:
            Evaluated result
        """
        try:
            # Handle empty expression
            if not expression or not expression.strip():
                return None
            
            expression = expression.strip()
            
            # Handle logical operators (AND, OR)
            if ' AND ' in expression.upper():
                parts = re.split(r'\s+AND\s+', expression, flags=re.IGNORECASE)
                results = []
                for part in parts:
                    result = await self.evaluate(part.strip(), user_id, strategy_id, context)
                    results.append(result)
                return all(results)
            
            if ' OR ' in expression.upper():
                parts = re.split(r'\s+OR\s+', expression, flags=re.IGNORECASE)
                results = []
                for part in parts:
                    result = await self.evaluate(part.strip(), user_id, strategy_id, context)
                    results.append(result)
                return any(results)
            
            # Handle comparison operators
            for op in ['>=', '<=', '==', '!=', '>', '<']:
                if op in expression:
                    left, right = expression.split(op, 1)
                    left_val = await self._evaluate_term(left.strip(), user_id, strategy_id, context)
                    right_val = await self._evaluate_term(right.strip(), user_id, strategy_id, context)
                    
                    if left_val is None or right_val is None:
                        return False
                    
                    if op == '>':
                        return float(left_val) > float(right_val)
                    elif op == '<':
                        return float(left_val) < float(right_val)
                    elif op == '>=':
                        return float(left_val) >= float(right_val)
                    elif op == '<=':
                        return float(left_val) <= float(right_val)
                    elif op == '==':
                        return float(left_val) == float(right_val)
                    elif op == '!=':
                        return float(left_val) != float(right_val)
            
            # Handle math operators
            for op in ['+', '-', '*', '/', '%']:
                if op in expression:
                    # Split carefully to handle negative numbers
                    parts = expression.split(op)
                    if len(parts) == 2:
                        left_val = await self._evaluate_term(parts[0].strip(), user_id, strategy_id, context)
                        right_val = await self._evaluate_term(parts[1].strip(), user_id, strategy_id, context)
                        
                        if left_val is None or right_val is None:
                            return None
                        
                        if op == '+':
                            return float(left_val) + float(right_val)
                        elif op == '-':
                            return float(left_val) - float(right_val)
                        elif op == '*':
                            return float(left_val) * float(right_val)
                        elif op == '/':
                            return float(left_val) / float(right_val) if float(right_val) != 0 else None
                        elif op == '%':
                            return float(left_val) % float(right_val) if float(right_val) != 0 else None
            
            # Single term
            return await self._evaluate_term(expression, user_id, strategy_id, context)
        
        except Exception as e:
            logger.error(f"Error evaluating expression '{expression}': {e}")
            return None
    
    async def _evaluate_term(
        self,
        term: str,
        user_id: str,
        strategy_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Evaluate a single term."""
        term = term.strip()
        
        # Numeric literal
        try:
            return float(term)
        except ValueError:
            pass
        
        # Boolean literal
        if term.upper() == 'TRUE':
            return True
        if term.upper() == 'FALSE':
            return False
        
        # LTP: ltp_TI, ltp_SI, ltp_position_123
        if term.startswith('ltp_'):
            return await self._get_ltp(term, context)
        
        # Candle: candle_TI_5m_close, candle_SI_1h_high
        if term.startswith('candle_'):
            return await self._get_candle_value(term, user_id, strategy_id, context)
        
        # Indicator: ema_TI_5m_20, rsi_SI_15m_14
        if '_' in term and any(term.startswith(ind) for ind in ['ema_', 'sma_', 'rsi_', 'macd_', 'bb_', 'atr_']):
            return await self._get_indicator_value(term, user_id, strategy_id, context)
        
        # Node variable: node_var_entry_3_entry_price
        if term.startswith('node_var_'):
            return await self._get_node_variable(term, user_id, strategy_id)
        
        # Unknown term
        logger.warning(f"Unknown term: {term}")
        return None
    
    async def _get_ltp(self, ltp_key: str, context: Optional[Dict[str, Any]] = None) -> Optional[float]:
        """Get LTP value."""
        try:
            # ltp_TI, ltp_SI, ltp_position_123
            role = ltp_key[4:]  # Remove 'ltp_'
            
            # Get symbol from context
            if not context or 'symbol' not in context:
                logger.warning(f"No symbol in context for {ltp_key}")
                return None
            
            symbol = context['symbol']
            
            # Get LTP from DataReader
            ltp_data = await self.data_reader.get_ltp(symbol, role)
            
            if ltp_data and 'ltp' in ltp_data:
                return float(ltp_data['ltp'])
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting LTP for {ltp_key}: {e}")
            return None
    
    async def _get_candle_value(
        self,
        candle_expr: str,
        user_id: str,
        strategy_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[float]:
        """
        Get candle value.
        
        Format: candle_TI_5m_close, candle_SI_1h_high[1]
        """
        try:
            # Parse: candle_TI_5m_close or candle_TI_5m_close[1]
            match = re.match(r'candle_(\w+)_(\w+)_(\w+)(?:\[(\d+)\])?', candle_expr)
            if not match:
                logger.warning(f"Invalid candle expression: {candle_expr}")
                return None
            
            role = match.group(1)  # TI, SI, position_123
            timeframe = match.group(2)  # 5m, 1h
            field = match.group(3)  # close, high, low, open
            offset = int(match.group(4)) if match.group(4) else 0
            
            # Get symbol from context
            if not context or 'symbol' not in context:
                logger.warning(f"No symbol in context for {candle_expr}")
                return None
            
            symbol = context['symbol']
            
            # Get candles from DataReader
            candles = await self.data_reader.get_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=offset + 2  # Get enough candles
            )
            
            if not candles or len(candles) <= offset:
                return None
            
            # Get the candle at offset (0 = latest, 1 = previous, etc.)
            candle = candles[-(offset + 1)]
            
            # Return the field value
            if field in candle:
                return float(candle[field])
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting candle value for {candle_expr}: {e}")
            return None
    
    async def _get_indicator_value(
        self,
        indicator_expr: str,
        user_id: str,
        strategy_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[float]:
        """
        Get indicator value.
        
        Format: ema_TI_5m_20, rsi_SI_15m_14
        """
        try:
            # Parse: ema_TI_5m_20
            parts = indicator_expr.split('_')
            if len(parts) < 4:
                logger.warning(f"Invalid indicator expression: {indicator_expr}")
                return None
            
            indicator_name = parts[0]  # ema, rsi, macd
            role = parts[1]  # TI, SI
            timeframe = parts[2]  # 5m, 1h
            period = parts[3] if len(parts) > 3 else ''  # 20, 14
            
            # Build full indicator name
            full_name = f"{indicator_name}_{period}" if period else indicator_name
            
            # Get symbol from context
            if not context or 'symbol' not in context:
                logger.warning(f"No symbol in context for {indicator_expr}")
                return None
            
            symbol = context['symbol']
            
            # Get indicator from DataReader
            value = await self.data_reader.get_indicator(
                symbol=symbol,
                timeframe=timeframe,
                indicator_name=full_name
            )
            
            return float(value) if value is not None else None
        
        except Exception as e:
            logger.error(f"Error getting indicator value for {indicator_expr}: {e}")
            return None
    
    async def _get_node_variable(
        self,
        var_expr: str,
        user_id: str,
        strategy_id: str
    ) -> Optional[float]:
        """
        Get node variable value.
        
        Format: node_var_entry_3_entry_price
        """
        try:
            # Parse: node_var_entry_3_entry_price
            parts = var_expr.split('_', 3)  # Split into max 4 parts
            if len(parts) < 4:
                logger.warning(f"Invalid node variable expression: {var_expr}")
                return None
            
            # parts = ['node', 'var', 'entry', '3_entry_price']
            # We need node_id and variable_name
            node_type = parts[2]  # entry, exit, condition
            rest = parts[3]  # 3_entry_price
            
            # Split rest to get node number and variable name
            rest_parts = rest.split('_', 1)
            if len(rest_parts) < 2:
                logger.warning(f"Invalid node variable format: {var_expr}")
                return None
            
            node_num = rest_parts[0]  # 3
            var_name = rest_parts[1]  # entry_price
            
            node_id = f"{node_type}-{node_num}"
            
            # Get variable from DataReader
            value = await self.data_reader.get_node_variable(
                user_id=user_id,
                strategy_id=strategy_id,
                node_id=node_id,
                variable_name=var_name
            )
            
            return float(value) if value is not None else None
        
        except Exception as e:
            logger.error(f"Error getting node variable for {var_expr}: {e}")
            return None
