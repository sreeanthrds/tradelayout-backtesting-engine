#!/usr/bin/env python3

from .condition_analyzer import ConditionAnalyzer
from .expression_evaluator import ExpressionEvaluator
from src.utils.logger import log_info, log_error, log_warning


class ConditionEvaluator:
    """
    Core condition evaluator with 2-stage evaluation using cached analysis.
    
    CRITICAL COMPONENT: Foundation of entire strategy execution system.
    Evaluates complex condition logic with nested groups (AND/OR).
    
    Provides modular functions for different evaluation tasks.
    """

    def __init__(self, context=None, condition=None, expression_evaluator=None, mode='backtesting'):
        """
        Initialize ConditionEvaluatorV2.
        
        Args:
            context: Optional execution context
            condition: Optional initial condition to evaluate
            expression_evaluator: Optional ExpressionEvaluator instance
            mode: Evaluation mode ('backtesting' or 'live_trading')
        """
        self.mode = mode
        self.context = context or {}
        self.condition = condition
        
        # Use provided evaluator or create new one
        if expression_evaluator is not None:
            self.expression_evaluator = expression_evaluator
        else:
            self.expression_evaluator = ExpressionEvaluator()
            self.expression_evaluator.set_context(context=self.context)
        
        # Store last evaluation result for debugging
        self.last_evaluation_result = None
        
        # Store diagnostic information for detailed analysis
        self.diagnostic_data = {
            'conditions_evaluated': [],
            'expression_values': {},
            'candle_data': {}
        }

    def set_condition(self, condition):
        """
        Set the condition and perform one-time analysis.
        
        Args:
            condition: Condition structure to evaluate
        """
        self.condition = condition  # Store condition for later use
        self.condition_analyzer = ConditionAnalyzer(condition)
        return self

    def set_context(self, candle=None, current_timestamp=None, tick_data=None, current_tick=None, previous_candle=None,
                    current_candle_index=None, candles_df=None, context=None):
        """
        Set evaluation context.
        
        Args:
            candle: Current candle data
            current_timestamp: Current candle timestamp
            tick_data: Tick data for the current period
            current_tick: Current tick data for live data evaluation
            previous_candle: Previous candle data
            current_candle_index: Current candle index
            candles_df: Candles dataframe for offset calculations
            context: Full context dictionary for GPS access
        """
        if context is not None:
            self.context = context  # Store the original context reference
        else:
            self.context = {
                'candle': candle,
                'current_timestamp': current_timestamp,
                'tick_data': tick_data,
                'current_tick': current_tick,
                'previous_candle': previous_candle,
                'current_candle_index': current_candle_index,
                'candles_df': candles_df
            }
        return self
    
    def reset_diagnostic_data(self):
        """Reset diagnostic data for a new evaluation"""
        self.diagnostic_data = {
            'conditions_evaluated': [],
            'expression_values': {},
            'candle_data': {}
        }
    
    def get_diagnostic_data(self):
        """Get captured diagnostic data from the last evaluation"""
        return self.diagnostic_data.copy()
    
    def _capture_candle_data(self):
        """Capture current and previous candle data for diagnostic purposes"""
        candle_cache = self.context.get('candle_cache') or self.context.get('candle_df_dict', {})
        if candle_cache:
            # Store current candle for primary instruments
            for key, candles in candle_cache.items():
                if ':1m' in key or ':tf_1m' in key:  # Only 1-minute candles
                    symbol = key.replace(':1m', '').replace(':tf_1m_default', '').replace(':tf_1m', '')
                    if isinstance(candles, list):
                        # List format (backtesting)
                        self.diagnostic_data['candle_data'][symbol] = {
                            'current': candles[-1] if candles else {},
                            'previous': candles[-2] if len(candles) >= 2 else {}
                        }
                    else:
                        # DataFrame or builder format
                        import pandas as pd
                        df = None
                        if isinstance(candles, pd.DataFrame):
                            df = candles
                        elif hasattr(candles, 'get_dataframe'):
                            df = candles.get_dataframe()
                        
                        if df is not None and len(df) > 0:
                            current = df.iloc[-1].to_dict() if len(df) > 0 else {}
                            previous = df.iloc[-2].to_dict() if len(df) >= 2 else {}
                            self.diagnostic_data['candle_data'][symbol] = {
                                'current': current,
                                'previous': previous
                            }

    def clear_diagnostic_data(self):
        """
        Clear diagnostic data to avoid accumulation across ticks.
        Should be called before each evaluation to store only current tick's data.
        """
        self.diagnostic_data = {
            'conditions_evaluated': [],
            'expression_values': {},
            'candle_data': {}
        }

    def evaluate_condition(self, condition=None):
        """
        Evaluate a condition and return boolean result.
        
        Args:
            condition: Condition to evaluate (uses self.condition if None)
            
        Returns:
            bool: True if condition is satisfied, False otherwise
        """
        if condition is None:
            condition = self.condition

        if condition is None:
            return False

        # Clear diagnostic data to avoid accumulation from previous ticks
        self.clear_diagnostic_data()

        # Store the evaluation result for access by nodes
        result = self._evaluate_recursive(condition)
        self.last_evaluation_result = result

        # Handle both boolean and dict results
        if isinstance(result, dict):
            return result.get('satisfied', False)
        else:
            return bool(result)

    def evaluate_condition_stage1(self, condition=None):
        """
        Stage 1: Evaluate condition at candle level to check if it's possible to satisfy.
        This only validates non-live conditions and checks if live conditions are possible
        within the candle's OHLC range.
        
        Args:
            condition: Condition to evaluate (uses self.condition if None)
            
        Returns:
            bool: True if condition is possible to satisfy within the candle
        """
        if condition is None:
            condition = self.condition

        if condition is None:
            return False

        # Clear diagnostic data to avoid accumulation from previous ticks
        self.clear_diagnostic_data()

        # Store the evaluation result for access by nodes
        result = self._evaluate_recursive_stage1(condition)
        self.last_evaluation_result = result

        # Handle both boolean and dict results
        if isinstance(result, dict):
            return result.get('satisfied', False)
        else:
            return bool(result)

    def _evaluate_recursive(self, condition):
        """
        Recursively evaluate condition while respecting group structure.
        
        Args:
            condition: Condition to evaluate
            
        Returns:
            bool: Evaluation result
        """
        # Check if it's a group condition
        if self._is_group_condition(condition):
            return self._evaluate_group_condition(condition)

        # Single condition evaluation
        return self._evaluate_single_condition(condition)

    def _evaluate_recursive_stage1(self, condition):
        """
        Stage 1: Recursively evaluate condition at candle level while respecting group structure.
        This only validates non-live conditions and checks if live conditions are possible
        within the candle's OHLC range.
        
        Args:
            condition: Condition to evaluate
            
        Returns:
            bool: Stage 1 evaluation result
        """
        # Check if it's a group condition
        if self._is_group_condition(condition):
            return self._evaluate_group_condition_stage1(condition)

        # Single condition evaluation
        return self._evaluate_single_condition_stage1(condition)

    def _evaluate_group_condition(self, condition):
        """
        Evaluate a group condition (AND/OR).
        
        Args:
            condition: Group condition to evaluate
            
        Returns:
            bool: Group evaluation result
        """
        group_logic = condition.get('groupLogic', 'AND')
        sub_conditions = condition.get('conditions', [])

        if not sub_conditions:
            return True

        # Evaluate all sub-conditions
        results = []
        for sub_condition in sub_conditions:
            result = self._evaluate_recursive(sub_condition)
            results.append(result)
            if group_logic == 'AND' and not result:
                return all(results)
            elif group_logic == 'OR' and result:
                return any(results)

        # # Apply group logic
        return self._apply_group_logic(results, group_logic)

    def _evaluate_group_condition_stage1(self, condition):
        """
        Stage 1: Evaluate a group condition (AND/OR) at candle level.
        
        Args:
            condition: Group condition to evaluate
            
        Returns:
            bool: Group evaluation result
        """
        group_logic = condition.get('groupLogic', 'AND')
        sub_conditions = condition.get('conditions', [])

        if not sub_conditions:
            return True

        # Evaluate all sub-conditions
        results = []
        for sub_condition in sub_conditions:
            result = self._evaluate_recursive_stage1(sub_condition)
            results.append(result)

        # Apply group logic
        return self._apply_group_logic(results, group_logic)

    def _evaluate_single_condition(self, condition):
        """
        Evaluate a single condition with 2-stage logic.
        
        Args:
            condition: Single condition to evaluate
            
        Returns:
            bool or dict: Condition evaluation result (dict for live data, bool for others)
        """
        # Check if condition is time-based
        is_time_condition = self._is_time_condition(condition)
        if is_time_condition:
            return self._evaluate_time_condition(condition)
        
        # Check if condition involves live_data
        is_live_data = self._is_live_data_condition(condition)

        if is_live_data:
            result = self._handle_live_data_condition(condition)
            # Return the full result dict for live data conditions
            return result
        else:
            return self._evaluate_non_live_condition(condition)

    def _evaluate_single_condition_stage1(self, condition):
        """
        Stage 1: Evaluate a single condition at candle level.
        
        Args:
            condition: Single condition to evaluate
            
        Returns:
            bool: Stage 1 evaluation result
        """
        # Check if condition involves live_data
        is_live_data = self._is_live_data_condition(condition)

        if is_live_data:
            # For live data conditions, directly evaluate using current tick data
            return self._evaluate_live_data_condition(condition)
        else:
            # For non-live conditions, evaluate normally
            return self._evaluate_non_live_condition(condition)

    def _handle_live_data_condition(self, condition):
        """
        Handle live data condition evaluation.
        
        Args:
            condition: Live data condition to evaluate
            
        Returns:
            bool: Live data condition evaluation result
        """
        # For live data conditions, directly evaluate using current tick data
        # No need for two-stage checking since we have direct access to current tick
        return self._evaluate_live_data_condition(condition)

    def _evaluate_live_data_condition(self, condition):
        """
        Evaluate a live_data condition using current tick data.
        
        Args:
            condition: Live data condition to evaluate
            
        Returns:
            bool: Live data condition evaluation result
        """
        try:
            # Get current timestamp from context
            current_timestamp = self.context.get('current_timestamp')
            if current_timestamp is None:
                return False

            # Use ExpressionEvaluator to evaluate both sides
            lhs_value = self._evaluate_value(condition['lhs'], current_timestamp)
            rhs_value = self._evaluate_value(condition['rhs'], current_timestamp)
            operator = condition['operator']
            
            # DIAGNOSTIC: Capture expression values for detailed analysis
            # Build human-readable text
            lhs_text = self._expression_to_text(condition.get('lhs'))
            rhs_text = self._expression_to_text(condition.get('rhs'))
            
            # Apply operator and return result
            result = self._apply_operator(lhs_value, operator, rhs_value)
            
            # Format values for display
            lhs_display = f"{lhs_value:.2f}" if isinstance(lhs_value, (int, float)) else str(lhs_value)
            rhs_display = f"{rhs_value:.2f}" if isinstance(rhs_value, (int, float)) else str(rhs_value)
            result_icon = '✓' if result else '✗'
            
            # Build condition text with values
            condition_text = f"{lhs_text} {operator} {rhs_text}  [{lhs_display} {operator} {rhs_display}] {result_icon}"
            
            condition_diagnostic = {
                'lhs_expression': condition.get('lhs'),
                'rhs_expression': condition.get('rhs'),
                'lhs_value': lhs_value,
                'rhs_value': rhs_value,
                'operator': operator,
                'timestamp': str(current_timestamp),
                'tick_count': self.context.get('tick_count', 0),
                'result': result,
                'condition_type': 'live',
                'condition_text': condition_text  # Human-readable text with values
            }
            
            # Store in diagnostic data
            self.diagnostic_data['conditions_evaluated'].append(condition_diagnostic)
            
            # Capture candle data using centralized function
            self._capture_candle_data()
            
            return result
        except Exception as e:
            import traceback
            log_error(f"❌ CRITICAL: Error evaluating live data condition: {e}")
            log_error(f"   Condition: {condition}")
            log_error(f"   Full traceback:\n{traceback.format_exc()}")
            # Re-raise - condition evaluation errors are critical
            raise RuntimeError(f"Condition evaluation failed: {e}") from e

    def _is_group_condition(self, condition):
        """
        Check if condition is a group condition.
        
        Args:
            condition: Condition to check
            
        Returns:
            bool: True if condition is a group
        """
        return isinstance(condition, dict) and 'groupLogic' in condition

    def _is_time_condition(self, condition):
        """
        Check if condition is time-based.
        
        Args:
            condition: Condition to check
            
        Returns:
            bool: True if condition is time-based
        """
        if not isinstance(condition, dict):
            return False
        
        # Check LHS
        if 'lhs' in condition and isinstance(condition['lhs'], dict):
            if condition['lhs'].get('type') == 'time':
                return True
        
        # Check RHS
        if 'rhs' in condition and isinstance(condition['rhs'], dict):
            if condition['rhs'].get('type') == 'time':
                return True
        
        return False
    
    def _is_live_data_condition(self, condition):
        """
        Check if condition involves live_data, including nested expressions.
        
        Args:
            condition: Condition to check
            
        Returns:
            bool: True if condition involves live_data
        """
        if not isinstance(condition, dict):
            return False

        # Check LHS
        if 'lhs' in condition and isinstance(condition['lhs'], dict):
            if self._contains_live_data(condition['lhs']):
                return True

        # Check RHS
        if 'rhs' in condition and isinstance(condition['rhs'], dict):
            if self._contains_live_data(condition['rhs']):
                return True

        return False

    def _contains_live_data(self, expression):
        """
        Recursively check if an expression contains live_data type anywhere in the tree.
        
        Args:
            expression: Expression to check
            
        Returns:
            bool: True if expression contains live_data
        """
        if not isinstance(expression, dict):
            return False

        # Check if this expression is live_data
        if expression.get('type') == 'live_data':
            return True

        # Recursively check all dictionary values
        for key, value in expression.items():
            if isinstance(value, dict):
                if self._contains_live_data(value):
                    return True
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and self._contains_live_data(item):
                        return True

        return False

    def _extract_ltp_field(self, condition):
        """
        Extract the LTP field name from a live_data condition.
        
        Args:
            condition: Live data condition
            
        Returns:
            str: LTP field name
        """
        field = 'ltp'  # Default

        if 'lhs' in condition and condition['lhs'].get('type') == 'live_data':
            field = condition['lhs'].get('field', 'ltp')
        elif 'rhs' in condition and condition['rhs'].get('type') == 'live_data':
            field = condition['rhs'].get('field', 'ltp')

        # Map field names to tick data columns (consistent with expression evaluator)
        field_mapping = {
            "LTP": "ltp",
            "ltp": "ltp",
            "last_traded_price": "ltp",
            "price": "ltp",
            "mark": "ltp",  # Add mark field mapping
            "volume": "volume",
            "oi": "oi"
        }

        return field_mapping.get(field, field.lower())

    def _apply_operator(self, lhs, operator, rhs):
        """
        Apply comparison operator.
        
        Args:
            lhs: Left-hand side value
            operator: Comparison operator
            rhs: Right-hand side value
            
        Returns:
            bool: Comparison result
        """
        # Handle None values (which occur when indicator values are NaN)
        if lhs is None or rhs is None:
            return False

        if operator == '<':
            return lhs < rhs
        elif operator == '<=':
            return lhs <= rhs
        elif operator == '>':
            return lhs > rhs
        elif operator == '>=':
            return lhs >= rhs
        elif operator == '==':
            return lhs == rhs
        elif operator == '!=':
            return lhs != rhs
        else:
            return False

    def _apply_group_logic(self, results, group_logic='AND'):
        """
        Apply group logic to results.
        
        Args:
            results: List of boolean results
            group_logic: Group logic ('AND' or 'OR')
            
        Returns:
            bool: Group logic result
        """
        if not results:
            return True

        if group_logic == 'AND':
            return all(results)
        elif group_logic == 'OR':
            return any(results)
        else:
            return all(results)  # Default to AND

    def get_analysis_summary(self):
        """
        Get analysis summary.
        
        Returns:
            dict: Analysis summary
        """
        if self.condition_analyzer is None:
            return None

        return self.condition_analyzer.get_analysis_summary()

    def _evaluate_time_condition(self, condition):
        """
        Evaluate a time-based condition.
        
        Args:
            condition: Time condition to evaluate
                Format: {'lhs': {'type': 'time', 'field': 'time'}, 
                        'operator': '>', 
                        'rhs': {'type': 'constant', 'value': '09:15:00'}}
            
        Returns:
            bool: Time condition evaluation result
        """
        try:
            current_timestamp = self.context.get('current_timestamp')
            if current_timestamp is None:
                return False

            operator = condition.get('operator', '>=')
            
            # Extract time value from RHS
            rhs = condition.get('rhs', {})
            if isinstance(rhs, dict):
                time_value_str = rhs.get('value', '00:00:00')
            else:
                time_value_str = condition.get('value', '00:00:00')  # Fallback for old format

            # Parse the time value (e.g., "09:45:00")
            from datetime import datetime, time
            import pytz

            # Handle different time formats
            if len(time_value_str.split(':')) == 2:
                # Format: "09:45"
                time_obj = datetime.strptime(time_value_str, '%H:%M').time()
            else:
                # Format: "09:45:00"
                time_obj = datetime.strptime(time_value_str, '%H:%M:%S').time()

            # Create target datetime for comparison
            if current_timestamp.tzinfo is None:
                # If naive timestamp, assume it's in UTC
                target_datetime = datetime.combine(current_timestamp.date(), time_obj)
                target_datetime = pytz.UTC.localize(target_datetime)
            else:
                # If timezone-aware, use the same timezone
                target_datetime = datetime.combine(current_timestamp.date(), time_obj)
                target_datetime = current_timestamp.tzinfo.localize(target_datetime)
                # Convert to UTC for comparison
                target_datetime = target_datetime.astimezone(pytz.UTC)

            # Convert current timestamp to UTC for comparison
            if current_timestamp.tzinfo is None:
                current_utc = pytz.UTC.localize(current_timestamp)
            else:
                current_utc = current_timestamp.astimezone(pytz.UTC)

            # Apply the operator
            if operator == '>=':
                return current_utc >= target_datetime
            elif operator == '>':
                return current_utc > target_datetime
            elif operator == '<=':
                return current_utc <= target_datetime
            elif operator == '<':
                return current_utc < target_datetime
            elif operator == '==':
                return current_utc == target_datetime
            else:
                log_warning(f"Unknown time operator: {operator}")
                return False

        except Exception as e:
            import traceback
            log_error(f"❌ CRITICAL: Error evaluating time condition: {e}")
            log_error(f"   Operator: {operator}")
            log_error(f"   Full traceback:\n{traceback.format_exc()}")
            # Re-raise - condition evaluation errors are critical
            raise RuntimeError(f"Time condition evaluation failed: {e}") from e

    def _evaluate_non_live_condition(self, condition):
        """
        Evaluate a non-live_data condition using ExpressionEvaluator.
        
        Args:
            condition: Non-live data condition to evaluate
            
        Returns:
            bool: Condition evaluation result
        """
        try:
            # Get current timestamp from context (may be None for constant comparisons)
            current_timestamp = self.context.get('current_timestamp')

            # Use ExpressionEvaluator to evaluate both sides
            lhs_value = self._evaluate_value(condition['lhs'], current_timestamp)
            rhs_value = self._evaluate_value(condition['rhs'], current_timestamp)
            operator = condition['operator']

            # Debug: log evaluated values with node id (if available)
            try:
                node_id = None
                ctx = getattr(self, 'context', {}) or {}
                node_id = ctx.get('current_node_id') or ctx.get('node_id')
                if not node_id:
                    state = (ctx.get('node_states') or {})
                    node_id = next(iter(state.keys())) if state else 'unknown'
                # log_info(f"[COND EVAL] node_id={node_id} lhs={lhs_value} op={operator} rhs={rhs_value}")
            except Exception as log_err:
                log_warning(f"ConditionEvaluator debug logging failed: {log_err}")

            # DIAGNOSTIC: Capture expression values for detailed analysis (non-live conditions)
            # Build human-readable text
            lhs_text = self._expression_to_text(condition.get('lhs'))
            rhs_text = self._expression_to_text(condition.get('rhs'))
            
            # Apply operator and return result
            result = self._apply_operator(lhs_value, operator, rhs_value)
            
            # Format values for display
            lhs_display = f"{lhs_value:.2f}" if isinstance(lhs_value, (int, float)) else str(lhs_value)
            rhs_display = f"{rhs_value:.2f}" if isinstance(rhs_value, (int, float)) else str(rhs_value)
            result_icon = '✓' if result else '✗'
            
            # Build condition text with values
            condition_text = f"{lhs_text} {operator} {rhs_text}  [{lhs_display} {operator} {rhs_display}] {result_icon}"
            
            condition_diagnostic = {
                'lhs_expression': condition.get('lhs'),
                'rhs_expression': condition.get('rhs'),
                'lhs_value': lhs_value,
                'rhs_value': rhs_value,
                'operator': operator,
                'timestamp': str(current_timestamp) if current_timestamp else None,
                'condition_type': 'non_live',
                'result': result,
                'condition_text': condition_text  # Human-readable text with values
            }
            
            # Store in diagnostic data
            self.diagnostic_data['conditions_evaluated'].append(condition_diagnostic)
            
            # Capture candle data if available
            self._capture_candle_data()

            return result
        except Exception as e:
            import traceback
            log_error(f"❌ CRITICAL: Error evaluating non-live condition: {e}")
            log_error(f"   LHS: {condition.get('lhs')}, RHS: {condition.get('rhs')}, Operator: {condition.get('operator')}")
            log_error(f"   Full traceback:\n{traceback.format_exc()}")
            # Re-raise - condition evaluation errors are critical
            raise RuntimeError(f"Condition evaluation failed: {e}") from e

    def _evaluate_value(self, value_config, current_timestamp):
        """
        Evaluate a value configuration using ExpressionEvaluator.
        
        Args:
            value_config: Value configuration to evaluate
            current_timestamp: Current timestamp for data access
            
        Returns:
            float: The evaluated value
        """
        if self.expression_evaluator is None:
            raise ValueError("ExpressionEvaluator required for value evaluation")

        # Set context for expression evaluator using our context data
        self.expression_evaluator.set_context(
            tick=self.context.get('current_tick'),
            current_timestamp=current_timestamp,
            tick_data=self.context.get('tick_data'),
            candles_df=self.context.get('candles_df'),
            context=self.context  # Pass full context for GPS access
        )

        # Use ExpressionEvaluator to handle all value types without data_processor
        return self.expression_evaluator.evaluate(value_config)
    
    def _expression_to_text(self, expr):
        """
        Convert expression JSON to human-readable text.
        
        Args:
            expr: Expression configuration (dict, number, or string)
            
        Returns:
            str: Human-readable expression text
        """
        if expr is None:
            return "null"
        
        # Handle simple values
        if isinstance(expr, (int, float)):
            return str(expr)
        if isinstance(expr, str):
            return expr
        if not isinstance(expr, dict):
            return str(expr)
        
        expr_type = expr.get('type', '')
        
        # Indicator
        if expr_type == 'indicator':
            name = expr.get('name', 'INDICATOR')
            symbol = expr.get('symbol', '')
            timeframe = expr.get('timeframe', '')
            params = expr.get('params', {})
            
            # Build parameter text
            param_text = f"{symbol}, {timeframe}"
            if params:
                param_values = ', '.join([f"{k}={v}" for k, v in params.items() if k not in ['symbol', 'timeframe']])
                if param_values:
                    param_text += f", {param_values}"
            
            return f"{name}({param_text})"
        
        # Candle field
        elif expr_type == 'candle':
            field = expr.get('field', 'close')
            symbol = expr.get('symbol', '')
            offset = expr.get('offset', 0)
            offset_text = f"[{offset}]" if offset != 0 else ""
            return f"{symbol}.{field}{offset_text}"
        
        # Live data (LTP)
        elif expr_type == 'live_data':
            symbol = expr.get('symbol', '')
            field = expr.get('field', 'ltp')
            return f"{symbol}.{field}"
        
        # Node variable
        elif expr_type == 'node_variable':
            node_id = expr.get('nodeId', 'NODE')
            var_name = expr.get('variableName', 'VAR')
            return f"{node_id}.{var_name}"
        
        # Expression (nested)
        elif expr_type == 'expression':
            left = self._expression_to_text(expr.get('left'))
            right = self._expression_to_text(expr.get('right'))
            op = expr.get('operator', '+')
            return f"({left} {op} {right})"
        
        # Constant/number
        elif expr_type == 'number' or expr_type == 'constant':
            return str(expr.get('value', 0))
        
        # Time
        elif expr_type == 'time':
            field = expr.get('field', 'time')
            return f"TIME.{field}"
        
        # Fallback
        return str(expr)
