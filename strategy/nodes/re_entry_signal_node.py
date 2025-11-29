from typing import Dict, Any, List

from .base_node import BaseNode
from src.core.condition_evaluator_v2 import ConditionEvaluator
from src.core.expression_evaluator import ExpressionEvaluator
from src.utils.logger import log_info, log_warning, log_error, log_critical


class ReEntrySignalNode(BaseNode):
    """
    Re-Entry Signal Node
    - Behaves like EntrySignalNode for condition evaluation and variable calculation
    - Adds retry logic via `retryConfig.maxReEntries`
    - Updates context variable `reEntryNum` starting from 0
    """

    def __init__(self, node_id: str, data: Dict[str, Any]):
        super().__init__(node_id, 'ReEntrySignalNode', data.get('label', 'Re-Entry node'))
        self.data = data
        self.conditions: List[Dict[str, Any]] = data.get('conditions', [])
        self.variables_config: List[Dict[str, Any]] = data.get('variables', [])
        self.retry_config: Dict[str, Any] = data.get('retryConfig', {})

        # Evaluators
        self.condition_evaluator = ConditionEvaluator()
        self.expression_evaluator = ExpressionEvaluator()

        # Cache for variables
        self._cached_dependency_graph = None

    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        current_timestamp = context.get('current_timestamp')
        max_re_entries = int(self.retry_config.get('maxReEntries', 0) or 0)

        # Initialize from this node's own state (defaults to 0)
        state = self._get_node_state(context)
        re_entry_num = int(state.get('reEntryNum', 0) or 0)

        # Time-specific debug marker to verify execution at 11:49:36
        # try:
        #     if hasattr(current_timestamp, 'strftime') and current_timestamp.strftime('%H:%M:%S') == '11:44:33':
        #         log_critical(
        #             f"[MARKER 11:49:36] ReEntrySignalNode {self.id} reached. reEntryNum={re_entry_num}, maxReEntries={max_re_entries}"
        #         )
        # except Exception:
        #     pass

        # DEBUG: starting state
        # log_info(f"ReEntrySignalNode {self.id}: start exec at {current_timestamp}, reEntryNum={re_entry_num}, maxReEntries={max_re_entries}")

        # CRITICAL: Check if re-entry limit reached
        # If max_re_entries = 0 → No re-entries allowed (skip)
        # If max_re_entries = N → Allow up to N re-entries (re_entry_num: 0, 1, ..., N-1)
        # Execute only when: re_entry_num < max_re_entries (or max_re_entries is not set)
        if max_re_entries == 0:
            # No re-entries configured - DON'T activate children!
            log_warning(f"ReEntrySignalNode {self.id}: maxReEntries=0, no re-entries allowed")
            return {
                'node_id': self.id,
                'reason': 'No re-entries configured (maxReEntries=0)',
                'signal_emitted': False,
                'logic_completed': False  # DON'T activate children when no re-entries allowed
            }
        elif re_entry_num >= max_re_entries:
            # Limit reached - DON'T activate children!
            # Return logic_completed=False to prevent BaseNode from calling _activate_children()
            log_info(f"ReEntrySignalNode {self.id}: Max re-entries reached (reEntryNum={re_entry_num}, max={max_re_entries})")
            return {
                'node_id': self.id,
                'reason': f'Max re-entries reached ({re_entry_num}/{max_re_entries})',
                'signal_emitted': False,
                'logic_completed': False  # DON'T activate children when limit reached!
            }

        # Set up evaluators
        self._setup_evaluators(context)

        # Set context for condition evaluator
        try:
            context['current_node_id'] = self.id
        except Exception:
            pass

        # Evaluate conditions FIRST
        cond_ok = self._evaluate_conditions(context)
        # log_info(f"ReEntrySignalNode {self.id}: conditions_satisfied={cond_ok}")
        if not cond_ok:
            # Deep-log values for leaf conditions to aid debugging
            try:
                self._log_condition_values_recursive(self.conditions[0] if isinstance(self.conditions, list) else self.conditions, context, prefix="1")
            except Exception:
                pass
            # Conditions not met - stay active and try again next tick
            return {
                'node_id': self.id,
                'executed': True,
                'signal_emitted': False,
                'logic_completed': False
            }

        # Conditions MET! Now increment reEntryNum (only when re-entry actually happens)
        try:
            state = self._get_node_state(context)
            current_val = int(state.get('reEntryNum', 0) or 0)
            next_val = current_val + 1
            if max_re_entries == 0 or next_val <= max_re_entries:
                self._set_node_state(context, {'reEntryNum': next_val})
                log_info(f"ReEntrySignalNode {self.id}: reEntryNum incremented to {next_val} after conditions met")
            else:
                log_warning(f"ReEntrySignalNode {self.id}: cannot increment reEntryNum beyond max {max_re_entries}")
        except Exception as e:
            log_error(f"Error incrementing reEntryNum: {e}", exc_info=True)

        # Calculate variables
        variables = self._calculate_variables(context)
        #     else:
        #         log_info(f"ReEntrySignalNode {self.id}: no variables computed")
        # except Exception:
        #     pass

        # NOTE: DO NOT call _activate_children() manually here!
        # BaseNode.execute() will automatically call _activate_children() when logic_completed=True
        # This ensures proper order: children activated FIRST, then parent marked INACTIVE
        # Calling it manually would cause double activation (inefficient)
        
        try:
            children_count = len(self.children)
            cur_re = int(self._get_node_state(context).get('reEntryNum', 0) or 0)
            log_info(f"ReEntrySignalNode {self.id}: will activate {children_count} children with reEntryNum={cur_re}")
        except Exception:
            pass

        # Mark completion - BaseNode will handle children activation
        return {
            'node_id': self.id,
            'executed': True,
            'signal_emitted': True,
            'node_variables': variables,
            'logic_completed': True
        }

    def _log_condition_values_recursive(self, condition: Dict[str, Any], context: Dict[str, Any], prefix: str = ""):
        """
        Recursively evaluate and log LHS/RHS values for leaf conditions within a group.
        Only logs for leaf conditions containing lhs/rhs.
        """
        if not isinstance(condition, dict):
            return
        # Group condition
        if 'conditions' in condition and isinstance(condition.get('conditions'), list):
            for idx, sub in enumerate(condition['conditions'], start=1):
                self._log_condition_values_recursive(sub, context, prefix=f"{prefix}.{idx}")
            return
        # Leaf condition with lhs/rhs
        if 'lhs' in condition and 'rhs' in condition:
            try:
                ts = context.get('current_timestamp')
                lhs_val = self.condition_evaluator._evaluate_value(condition['lhs'], ts)
                rhs_val = self.condition_evaluator._evaluate_value(condition['rhs'], ts)
                op = condition.get('operator')
                # log_debug(f"🔍 ReEntrySignalNode {self.id}: Condition {prefix}")  # Removed for performance
                # log_debug(f"   LHS: {condition.get('lhs')} = {lhs_val}")
                # log_debug(f"   Operator: {op}")
                # log_debug(f"   RHS: {condition.get('rhs')} = {rhs_val}")
            except Exception as e:
                log_error(f"Error evaluating condition {prefix}: {e}")

    def _setup_evaluators(self, context: Dict[str, Any]):
        """Set up condition and expression evaluators with context."""
        # Set context for both evaluators - they will access data from context
        # (ltp_store, candle_df_dict, current_timestamp, etc.)
        self.condition_evaluator.set_context(context=context)
        self.expression_evaluator.set_context(context=context)

    def _evaluate_conditions(self, context: Dict[str, Any]) -> bool:
        if not self.conditions:
            log_warning(f"ReEntrySignalNode {self.id}: No conditions configured")
            return False
        try:
            result = self.condition_evaluator.evaluate_condition(self.conditions[0] if isinstance(self.conditions, list) else self.conditions)
            if isinstance(result, dict):
                return bool(result.get('satisfied', False))
            return bool(result)
        except Exception as e:
            log_error(f"Error evaluating re-entry conditions: {e}", exc_info=True)
            return False

    def _calculate_variables(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.variables_config:
            return {}
        # Build dependency graph once
        if self._cached_dependency_graph is None:
            dependency_graph: Dict[str, List[str]] = {}
            for var_cfg in self.variables_config:
                name = var_cfg.get('name')
                if not name:
                    continue
                expr = var_cfg.get('expression', {})
                deps = self._extract_variable_dependencies(expr)
                dependency_graph[name] = deps
            self._cached_dependency_graph = dependency_graph
        return self._calculate_variables_iterative(context, self._cached_dependency_graph)

    def _extract_variable_dependencies(self, expression: Dict[str, Any]) -> List[str]:
        deps: List[str] = []
        if not isinstance(expression, Dict):
            return deps
        if expression.get('type') == 'node_variable':
            node_id = expression.get('nodeId')
            var_name = expression.get('variableName')
            if node_id == self.id and var_name:
                deps.append(var_name)
        elif expression.get('type') == 'expression':
            deps.extend(self._extract_variable_dependencies(expression.get('left', {})))
            deps.extend(self._extract_variable_dependencies(expression.get('right', {})))
        # Deduplicate
        return list(dict.fromkeys(deps))

    def _calculate_variables_iterative(self, context: Dict[str, Any], dependency_graph: Dict[str, List[str]]) -> Dict[str, Any]:
        variables: Dict[str, Any] = {}
        pending = list(dependency_graph.keys())
        max_iterations = len(pending) * 2 if pending else 0
        iters = 0
        while pending and iters < max_iterations:
            iters += 1
            progressed: List[str] = []
            for var_name in list(pending):
                deps = dependency_graph.get(var_name, [])
                if all(d in variables for d in deps):
                    try:
                        var_cfg = next(vc for vc in self.variables_config if vc.get('name') == var_name)
                        value = self.expression_evaluator.evaluate(var_cfg.get('expression'))
                        variables[var_name] = value
                        # Store for global access
                        self.set_node_variable(context, var_name, value)
                        # Update context immediate cache
                        if 'node_variables' not in context:
                            context['node_variables'] = []
                        context['node_variables'].append({'nodeId': self.id, 'name': var_name, 'value': value})
                        progressed.append(var_name)
                    except Exception as e:
                        log_error(f"Error calculating re-entry variable {var_name}: {e}", exc_info=True)
                        variables[var_name] = None
                        self.set_node_variable(context, var_name, None)
                        progressed.append(var_name)
            pending = [p for p in pending if p not in progressed]
            if not progressed:
                break
        return variables

    def _activate_children(self, context: Dict[str, Any]):
        """
        Override to reset children for re-entry scenarios.
        
        When ReEntrySignalNode successfully completes (conditions met, under max re-entries),
        it needs to:
        1. Reset visited flags to allow children to execute again in the same tick
        2. Reset order status for entry nodes to allow new orders to be placed
        
        Normal nodes do NOT reset visited flags or order status to preserve cycle protection.
        """
        # Call parent implementation to activate children and propagate reEntryNum
        super()._activate_children(context)
        
        # SPECIAL CASE: Reset children for re-entry
        node_instances = context.get('node_instances', {})
        for child_id in self.children:
            if child_id in node_instances:
                child_node = node_instances[child_id]
                
                # Reset visited flag to allow execution in same tick
                child_node.reset_visited(context)
                
                # Reset order status for entry nodes to allow new orders
                # This is crucial for re-entry to work properly
                if hasattr(child_node, 'reset'):
                    child_node.reset(context)


