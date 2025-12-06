from typing import Dict, Any

from src.core.condition_evaluator_v2 import ConditionEvaluator
from src.core.expression_evaluator import ExpressionEvaluator
from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical, is_per_tick_log_enabled

from .base_node import BaseNode

# Performance mode flag - can be toggled
PERFORMANCE_MODE = False


class ExitSignalNode(BaseNode):
    """
    Exit Signal Node - Evaluates exit conditions and triggers exit signals.
    
    This node monitors exit conditions and activates when conditions are met.
    It can be triggered by various conditions like:
    - Price-based exits (stop loss, take profit)
    - Time-based exits
    - Technical indicator exits
    - Position-based exits
    """

    def __init__(self, node_id: str, data: Dict[str, Any]):
        """
        Initialize Exit Signal Node.
        
        Args:
            node_id: Unique identifier for the node
            data: Node configuration data containing conditions
        """
        super().__init__(node_id, 'ExitSignalNode', data.get('label', 'Exit Signal'))

        # Extract configuration from data
        self.data = data
        self.conditions = data.get('conditions', [])
        self.has_reentry_exit_conditions = bool(data.get('hasReEntryExitConditions', False))
        self.reentry_exit_conditions = data.get('reEntryExitConditions', [])
        self.exit_reason = data.get('exitReason', 'condition_met')

        # Initialize evaluators
        self.condition_evaluator = ConditionEvaluator()
        self.expression_evaluator = ExpressionEvaluator()

        # Tracking
        self._signals_generated = 0

        # log_info(f"🚨 Exit Signal Node {self.id} initialized with {len(self.conditions)} conditions")

    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the exit signal node logic for tick-by-tick processing.
        
        Args:
            context: Execution context containing current state, data, etc.
            
        Returns:
            Dict containing execution results with 'logic_completed' flag
        """
        # Set up evaluators for this tick
        self._setup_evaluators(context)

        # Evaluate exit conditions (switch to re-entry conditions if in re-entry mode)
        conditions_met = self._evaluate_exit_conditions(context)

        if conditions_met:
            # if is_per_tick_log_enabled():
            # log_info(f"✅ Exit Signal Triggered: {self.id}")
            exit_signal_data = self._trigger_exit_signal(context)
            self._signals_generated += 1

            # Activate children (parent responsibility)
            # if is_per_tick_log_enabled():
            # log_debug(f"[DEBUG] ExitSignalNode {self.id} activating children: {self.children}")
            self._activate_children(context)

            return {
                'node_id': self.id,
                'executed': True,
                'signal_emitted': True,
                'exit_signal_data': exit_signal_data,
                'logic_completed': True  # Exit signal nodes complete after triggering
            }
        else:
            # # log_info(f"❌ Exit Signal Not Triggered: {self.id}")
            return {
                'node_id': self.id,
                'executed': True,
                'signal_emitted': False,
                'logic_completed': False  # Keep monitoring for next tick
            }

    def _evaluate_exit_conditions(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate exit conditions based on strategy configuration.
        
        CRITICAL: When reEntryNum > 0, only evaluate re-entry exit conditions.
        If no re-entry conditions are configured, return False (don't evaluate regular conditions).
        This prevents premature exit signals immediately after re-entry.
        
        Args:
            context: Execution context containing condition evaluator and data
            
        Returns:
            bool: True if exit conditions are met, False otherwise
        """
        # Check if we're in re-entry mode by getting position_num from GPS
        in_reentry_mode = self._is_in_reentry_mode(context)
        
        # When in re-entry mode, use re-entry exit conditions if configured
        # Otherwise fall back to normal conditions (allows flexibility)
        if in_reentry_mode:
            if not self.has_reentry_exit_conditions or not self.reentry_exit_conditions:
                # If no re-entry exit conditions configured, fall back to normal conditions
                log_info(f"ExitSignalNode {self.id}: In re-entry mode but no re-entry exit conditions configured, using normal conditions")
                active_conditions = self.conditions
            else:
                active_conditions = self.reentry_exit_conditions
        else:
            active_conditions = self.conditions

        if not active_conditions:
            log_warning(f"  ⚠️  No exit conditions configured for {self.id} ({'re-entry' if in_reentry_mode else 'normal'})")
            return False

        # PERFORMANCE: Conditional logging
        # if not PERFORMANCE_MODE:
        # log_info(f"   Evaluating {len(self.conditions)} exit condition(s):")

        # For now, let's handle simple conditions first
        # Each condition in the list should be satisfied (AND logic)
        for i, condition in enumerate(active_conditions):
            try:
                # Evaluate this top-level condition using our evaluator
                result = self.condition_evaluator.evaluate_condition(condition)

                if isinstance(result, dict):
                    satisfied = result.get('satisfied', False)
                    stage = result.get('stage', 'live_evaluation')
                else:
                    satisfied = bool(result)
                    stage = 'live_evaluation'

                if satisfied:
                    log_info(f"     ✅ Exit condition {i + 1} satisfied (stage: {stage})")
                    # Deep-log values for all satisfied leaf conditions
                    try:
                        self._log_condition_values_recursive(condition, context, prefix=f"{i + 1}")
                    except Exception as e:
                        log_warning(f"ExitSignalNode {self.id}: Failed to log condition values: {e}")
                else:
                    return False  # All conditions must be satisfied

            except Exception as e:
                import traceback
                log_error(f"     ❌ CRITICAL: Error evaluating exit condition {i + 1}: {e}")
                log_error(f"     Condition: {condition}")
                log_error(f"     Full traceback:\n{traceback.format_exc()}")
                # Re-raise - condition evaluation errors are critical
                raise RuntimeError(f"ExitSignalNode {self.id}: Condition evaluation failed: {e}") from e

        # PERFORMANCE: Conditional logging
        # if not PERFORMANCE_MODE:
        # log_info(f"   🎯 All {len(self.conditions)} exit conditions satisfied!")
        
        # DIAGNOSTIC: Store diagnostic data and condition preview in node state for exit node to retrieve
        if hasattr(self.condition_evaluator, 'get_diagnostic_data'):
            diagnostic_data = self.condition_evaluator.get_diagnostic_data()
            
            # Also include condition preview text
            condition_preview = self.data.get('conditionsPreview')
            
            self._set_node_state(context, {
                'diagnostic_data': diagnostic_data,
                'condition_preview': condition_preview
            })
        
        return True

    def _setup_evaluators(self, context: Dict[str, Any]):
        """Set up condition and expression evaluators with context."""
        # Set context for both evaluators - they will access data from context
        # (ltp_store, candle_df_dict, current_timestamp, etc.)
        self.condition_evaluator.set_context(context=context)
        self.expression_evaluator.set_context(context=context)

    def _trigger_exit_signal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger exit signal and prepare for exit execution.
        
        Args:
            context: Execution context
            
        Returns:
            Dict containing exit signal data
        """
        current_timestamp = context.get('current_timestamp')

        # Create exit signal data
        exit_signal_data = {
            'exit_signal_time': current_timestamp,
            'exit_signal_price': 0,  # Not meaningful with multiple symbols
            'exit_reason': self.exit_reason,
            'node_id': self.id,
            'conditions_met': self.conditions
        }

        # Store exit signal data in context for exit node to access
        exit_signals = context.get('exit_signals', [])
        exit_signals.append(exit_signal_data)
        context['exit_signals'] = exit_signals

        # log_info(f"🚨 Exit Signal Data: {exit_signal_data}")

        return exit_signal_data

    def get_statistics(self) -> Dict[str, Any]:
        """Get Exit Signal Node statistics."""
        return {
            'node_id': self.id,
            'signals_generated': self._signals_generated,
            'conditions_count': len(self.conditions),
            'exit_reason': self.exit_reason
        }
    
    def _is_in_reentry_mode(self, context: Dict[str, Any]) -> bool:
        """
        Check if we're in re-entry mode by getting position_num from GPS.
        position_num > 1 means we're in re-entry mode (position 2, 3, etc.)
        
        Args:
            context: Execution context
            
        Returns:
            bool: True if position_num > 1 (re-entry mode), False otherwise
        """
        try:
            # Get the position_id that this exit signal is monitoring
            # We need to find the associated entry node
            node_instances = context.get('node_instances', {})
            
            # Search for entry nodes to get position_id
            # Exit signals are typically children of entry nodes or parallel to them
            position_id = None
            
            # Try to get position_id from GPS by looking at open positions
            context_manager = context.get('context_manager')
            if not context_manager:
                return False
            
            gps = context_manager.gps
            
            # Check if there are any open positions
            if not gps.positions:
                return False
            
            # Get the first open position (assumes single position trading)
            for pos_id, pos_data in gps.positions.items():
                if pos_data.get('status') == 'open':
                    position_num = pos_data.get('position_num', 1)
                    # In re-entry mode if position_num > 1
                    return position_num > 1
            
            return False
            
        except Exception as e:
            log_warning(f"ExitSignalNode {self.id}: Error checking re-entry mode: {e}")
            return False
