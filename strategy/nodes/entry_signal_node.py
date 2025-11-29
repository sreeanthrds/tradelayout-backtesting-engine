#!/usr/bin/env python3

import os
import sys
from typing import Dict, Any, List

# Add current directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from .base_node import BaseNode
from src.core.condition_evaluator_v2 import ConditionEvaluator
from src.core.expression_evaluator import ExpressionEvaluator
from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical, is_per_tick_log_enabled

# Performance mode flag - can be toggled
PERFORMANCE_MODE = False


class EntrySignalNode(BaseNode):
    """
    EntrySignalNode evaluates conditions and emits entry signals for tick-by-tick live trading.
    - Supports complex nested conditions with AND/OR logic
    - Calculates node variables for use by child nodes
    - Emits one-shot signals (triggers once per condition satisfaction)
    - Uses direct live processing for tick-by-tick evaluation
    """

    def __init__(self, node_id: str, data: Dict[str, Any]):
        """
        Initialize Entry Signal Node.
        
        Args:
            node_id: Unique identifier for the node
            data: Node configuration data
        """
        # Extract label/name from config
        name = data.get('label', 'Entry Signal')
        super().__init__(node_id, 'EntrySignalNode', name)

        # Extract configuration from data
        self.data = data
        self.conditions = data.get('conditions', [])
        # Note: Entry Signal uses 'reEntryConditions' (different from Exit Signal's 'reEntryExitConditions')
        self.has_reentry_conditions = bool(data.get('hasReEntryConditions', False))
        self.reentry_conditions = data.get('reEntryConditions', [])  # UI uses 'reEntryConditions' for entries
        self.variables_config = data.get('variables', [])
        self.alert_config = data.get('alertNotification', {})

        # Initialize evaluators
        self.condition_evaluator = ConditionEvaluator()
        self.expression_evaluator = ExpressionEvaluator()  # Will be set in set_context

        # Node state
        self.signal_triggered = False
        self.trigger_time = None
        self.trigger_price = None
        self.node_variables = {}

        # Remove incorrect self-activation - only parent should activate children
        # self._active = True  # REMOVED - violates parent-child activation principle

        # log_info(f"📊 Entry Signal Node {self.id} initialized with {len(self.conditions)} conditions")

    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the entry signal node logic for tick-by-tick processing.
        
        Args:
            context: Execution context containing current state, data, etc.
            
        Returns:
            Dict containing execution results with 'logic_completed' flag
        """
        # If entering re-entry mode, allow a fresh trigger by resetting the one-shot flag
        try:
            re_entry_num_raw = self._get_node_state(context).get('reEntryNum', 0) or 0
            re_entry_num = int(re_entry_num_raw)
            in_reentry_mode_boot = re_entry_num > 0
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"EntrySignalNode {self.id}: Invalid reEntryNum '{re_entry_num_raw}' "
                f"(type: {type(re_entry_num_raw).__name__}): {e}"
            ) from e

        # Check if signal already triggered (one-shot per mode). Reset in re-entry mode.
        if self.signal_triggered and not in_reentry_mode_boot:
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Signal already triggered',
                'signal_emitted': False,
                'logic_completed': False
            }
        elif self.signal_triggered and in_reentry_mode_boot:
            # Allow re-trigger in re-entry phase
            self.signal_triggered = False
            log_info(f"EntrySignalNode {self.id}: resetting signal_triggered for re-entry mode")

        # Set up evaluators for this tick
        self._setup_evaluators(context)

        # Get current timestamp for logging
        current_timestamp = context.get('current_timestamp')

        # Evaluate all conditions
        signal_emitted = self._evaluate_conditions(context)

        if signal_emitted:
            # Signal triggered - calculate variables and mark as triggered
            log_info(f"🚨 SIGNAL TRIGGERED: {self.id} at {current_timestamp}, activating {len(self.children)} children")

            # Calculate variables
            signal_variables = self._calculate_variables(context)

            # Update node state
            self.signal_triggered = True
            self.trigger_time = current_timestamp
            self.node_variables = signal_variables

            # Trigger alert if configured
            self._trigger_alert()

            return {
                'node_id': self.id,
                'executed': True,
                'signal_emitted': True,
                'signal_time': current_timestamp,
                'signal_price': self.trigger_price,
                'logic_completed': True
            }
        else:
            # No signal - continue monitoring (node remains active)
            return {
                'node_id': self.id,
                'executed': True,
                'signal_emitted': False,
                'conditions_evaluated': len(self.conditions),
                'logic_completed': False  # Still monitoring = logic not completed
            }

    def _setup_evaluators(self, context: Dict[str, Any]):
        """Set up condition and expression evaluators with context."""
        # Set context for both evaluators - they will access data from context
        # (ltp_store, candle_df_dict, current_timestamp, etc.)
        self.condition_evaluator.set_context(context=context)
        self.expression_evaluator.set_context(context=context)

    def _evaluate_conditions(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate all conditions using direct live processing.
        
        Args:
            context: Execution context
            
        Returns:
            bool: True if all conditions are satisfied
        """
        # Choose condition set depending on re-entry mode
        in_reentry_mode = int(self._get_node_state(context).get('reEntryNum', 0) or 0) > 0
        
        # CRITICAL: When in re-entry mode, ONLY evaluate re-entry conditions
        # Do NOT fall back to regular conditions
        if in_reentry_mode:
            if not self.has_reentry_conditions or not self.reentry_conditions:
                # RAISE ERROR: Re-entry conditions must be configured when in re-entry mode
                reentry_num = self._get_node_state(context).get('reEntryNum', 0)
                error_msg = (
                    f"❌ CONFIGURATION ERROR in {self.id}: "
                    f"reEntryNum={reentry_num} but no re-entry entry conditions defined! "
                    f"You must configure re-entry conditions or disable re-entry."
                )
                log_error(error_msg)
                raise ValueError(error_msg)
            active_conditions = self.reentry_conditions
        else:
            active_conditions = self.conditions

        tick_count = context.get('tick_count', 0)
        current_timestamp = context.get('current_timestamp')
        current_ltp = context.get('current_tick', {}).get('ltp', 0)
        
        if not active_conditions:
            if not PERFORMANCE_MODE:
                log_warning(f"⚠️  Entry Signal Node {self.id}: No conditions configured for {'re-entry' if in_reentry_mode else 'normal'} mode")
            return False

        # PERFORMANCE: Conditional logging
        # if not PERFORMANCE_MODE:
        # log_info(f"   Evaluating {len(self.conditions)} condition(s):")

        # For now, let's handle simple conditions first
        # Each condition in the list should be satisfied (AND logic)
        for i, condition in enumerate(active_conditions):
            try:
                # Use direct live evaluation
                result = self.condition_evaluator.evaluate_condition(condition)

                # Handle both boolean and dict results
                if isinstance(result, dict):
                    satisfied = result.get('satisfied', False)
                    stage = result.get('stage', 'live_evaluation')
                else:
                    satisfied = bool(result)
                    stage = 'live_evaluation'
                
                if satisfied:
                    pass  # Condition satisfied
                else:
                    return False  # All conditions must be satisfied

            except Exception as e:
                import traceback
                log_error(f"     ❌ CRITICAL: Error evaluating condition {i + 1}: {e}")
                log_error(f"     Condition: {condition}")
                log_error(f"     Full traceback:\n{traceback.format_exc()}")
                
                # Re-raise - condition evaluation errors are critical
                raise RuntimeError(f"EntrySignalNode {self.id}: Condition evaluation failed: {e}") from e
        
        return True

    def _calculate_variables(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate node variables with iterative dependency resolution.
        
        Args:
            context: Execution context
            
        Returns:
            Dict containing calculated variable values
        """
        if not self.variables_config:
            return {}

        # PERFORMANCE: Conditional logging
        # if not PERFORMANCE_MODE:
        # log_info(f"   📊 Calculating {len(self.variables_config)} variables with iterative dependency resolution:")

        # PERFORMANCE: Cache dependency graph after first calculation
        if not hasattr(self, '_cached_dependency_graph'):
            # Step 1: Build dependency graph
            dependency_graph = self._build_dependency_graph()

            # Step 2: Detect self-references
            self._detect_self_references(dependency_graph)

            # Cache the dependency graph
            self._cached_dependency_graph = dependency_graph
        else:
            # Use cached dependency graph
            dependency_graph = self._cached_dependency_graph

        # Step 3: Calculate variables using iterative approach
        variables = self._calculate_variables_iterative(context, dependency_graph)

        return variables

    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """
        Build dependency graph for variables in this node.
        
        Returns:
            Dictionary mapping variable names to their dependencies
        """
        dependency_graph = {}

        for var_config in self.variables_config:
            var_name = var_config.get('name')
            if not var_name:
                continue

            dependencies = self._extract_variable_dependencies(var_config.get('expression', {}))
            dependency_graph[var_name] = dependencies

        return dependency_graph

    def _detect_self_references(self, dependency_graph: Dict[str, List[str]]):
        """
        Detect and raise error for self-references.
        
        Args:
            dependency_graph: Dependency graph
            
        Raises:
            ValueError: If any variable references itself
        """
        for var_name, dependencies in dependency_graph.items():
            if var_name in dependencies:
                raise ValueError(f"Variable '{var_name}' in node {self.id} references itself")

    def _calculate_variables_iterative(self, context: Dict[str, Any], dependency_graph: Dict[str, List[str]]) -> Dict[
        str, Any]:
        """
        Calculate variables using iterative multi-level approach.
        
        Args:
            context: Execution context
            dependency_graph: Dependency graph
            
        Returns:
            Dict containing calculated variable values
        """
        variables = {}
        pending_vars = list(dependency_graph.keys())  # All variables start as pending
        max_iterations = len(pending_vars) * 2  # Prevent infinite loops
        iteration = 0

        while pending_vars and iteration < max_iterations:
            iteration += 1
            # PERFORMANCE: Conditional logging
            # if not PERFORMANCE_MODE:
            # log_info(f"     Iteration {iteration}: Processing {len(pending_vars)} pending variables")

            # Variables that can be calculated in this iteration
            ready_vars = []

            for var_name in pending_vars:
                dependencies = dependency_graph.get(var_name, [])

                # Check if all dependencies are satisfied
                all_deps_satisfied = True
                missing_deps = []

                for dep in dependencies:
                    if dep not in variables:
                        all_deps_satisfied = False
                        missing_deps.append(dep)

                if all_deps_satisfied:
                    ready_vars.append(var_name)
                else:
                    # PERFORMANCE: Conditional logging
                    if not PERFORMANCE_MODE:
                        log_warning(f"       {var_name} waiting for: {missing_deps}")

            # If no variables are ready, we have a circular dependency
            if not ready_vars:
                # Check for circular dependencies
                circular_deps = self._detect_circular_dependencies_in_pending(pending_vars, dependency_graph)
                if circular_deps:
                    raise ValueError(f"Circular dependency detected in node {self.id}: {circular_deps}")
                else:
                    # Check for missing dependencies
                    missing_vars = self._detect_missing_dependencies(pending_vars, dependency_graph, variables)
                    if missing_vars:
                        raise ValueError(
                            f"Variables reference non-existent variables in node {self.id}: {missing_vars}")
                    else:
                        raise ValueError(
                            f"Unable to resolve dependencies for variables in node {self.id}: {pending_vars}")

            # Calculate ready variables
            for var_name in ready_vars:
                try:
                    var_config = next(vc for vc in self.variables_config if vc.get('name') == var_name)
                    var_expression = var_config.get('expression')

                    if var_expression:
                        # Calculate the variable
                        var_value = self.expression_evaluator.evaluate(var_expression)

                        # Store the result
                        variables[var_name] = var_value
                        self.node_variables[var_name] = var_value

                        # Store in GPS for global access
                        self.set_node_variable(context, var_name, var_value)

                        # Update context for immediate availability
                        self._update_context_node_variables(context, var_name, var_value)

                        # Log each calculated variable value
                        log_info(f"       ✅ {self.id} -> {var_name} = {var_value}")
                    else:
                        if not PERFORMANCE_MODE:
                            log_warning(f"       ⚠️  Invalid variable config: {var_config}")
                        variables[var_name] = None
                        self.node_variables[var_name] = None
                        # Store in GPS for global access (even if None)
                        self.set_node_variable(context, var_name, None)

                except Exception as e:
                    import traceback
                    log_error(f"       ❌ CRITICAL: Error calculating variable {var_name}: {e}")
                    log_error(f"       Variable config: {var_config}")
                    log_error(f"       Full traceback:\n{traceback.format_exc()}")
                    # Re-raise - variable calculation errors are critical
                    raise RuntimeError(f"EntrySignalNode {self.id}: Variable calculation failed for {var_name}: {e}") from e

            # Remove calculated variables from pending list
            pending_vars = [var for var in pending_vars if var not in ready_vars]

        if iteration >= max_iterations:
            raise ValueError(
                f"Maximum iterations reached while calculating variables in node {self.id}. Possible circular dependency.")

        return variables

    def _detect_circular_dependencies_in_pending(self, pending_vars: List[str],
                                                 dependency_graph: Dict[str, List[str]]) -> List[str]:
        """
        Detect circular dependencies among pending variables.
        
        Args:
            pending_vars: List of pending variable names
            dependency_graph: Dependency graph
            
        Returns:
            List of variables involved in circular dependency, or empty list if none
        """
        # Create subgraph with only pending variables
        subgraph = {var: [dep for dep in deps if dep in pending_vars]
                    for var, deps in dependency_graph.items()
                    if var in pending_vars}

        # Use DFS to detect cycles
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> List[str]:
            if node in rec_stack:
                # Found circular dependency
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]

            if node in visited:
                return []

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in subgraph.get(node, []):
                cycle = dfs(neighbor, path)
                if cycle:
                    return cycle

            path.pop()
            rec_stack.remove(node)
            return []

        for node in pending_vars:
            if node not in visited:
                cycle = dfs(node, [])
                if cycle:
                    return cycle

        return []

    def _detect_missing_dependencies(self, pending_vars: List[str], dependency_graph: Dict[str, List[str]],
                                     calculated_vars: Dict[str, Any]) -> List[str]:
        """
        Detect variables that reference non-existent variables.
        
        Args:
            pending_vars: List of pending variable names
            dependency_graph: Dependency graph
            calculated_vars: Already calculated variables
            
        Returns:
            List of missing variable names
        """
        all_vars = set(pending_vars) | set(calculated_vars.keys())
        missing_vars = set()

        for var_name in pending_vars:
            dependencies = dependency_graph.get(var_name, [])
            for dep in dependencies:
                if dep not in all_vars:
                    missing_vars.add(dep)

        return list(missing_vars)

    def _extract_variable_dependencies(self, expression: Dict[str, Any]) -> List[str]:
        """
        Extract variable dependencies from an expression.
        
        Args:
            expression: Expression configuration
            
        Returns:
            List of variable names this expression depends on
        """
        dependencies = []

        if not isinstance(expression, dict):
            return dependencies

        # Check if this is a node_variable reference
        if expression.get('type') == 'node_variable':
            node_id = expression.get('nodeId')
            var_name = expression.get('variableName')

            # Only include dependencies from the same node
            if node_id == self.id and var_name:
                dependencies.append(var_name)

        # Check for nested expressions
        elif expression.get('type') == 'expression':
            # Check left operand
            left_deps = self._extract_variable_dependencies(expression.get('left', {}))
            dependencies.extend(left_deps)

            # Check right operand
            right_deps = self._extract_variable_dependencies(expression.get('right', {}))
            dependencies.extend(right_deps)

        return list(set(dependencies))  # Remove duplicates

    def _update_context_node_variables(self, context: Dict[str, Any], var_name: str, var_value: Any):
        """
        Update node_variables in context for immediate availability.
        
        Args:
            context: Execution context
            var_name: Variable name
            var_value: Variable value
        """
        if 'node_variables' not in context:
            context['node_variables'] = []

        # Check if this variable already exists in context
        existing_var = None
        for var_item in context['node_variables']:
            if var_item.get('nodeId') == self.id and var_item.get('name') == var_name:
                existing_var = var_item
                break

        if existing_var:
            # Update existing variable
            existing_var['value'] = var_value
        else:
            # Add new variable
            context['node_variables'].append({
                'nodeId': self.id,
                'name': var_name,
                'value': var_value
            })

    def _trigger_alert(self) -> bool:
        """
        Trigger alert notification if configured.
        
        Returns:
            True if alert was triggered, False otherwise
        """
        if not self.alert_config.get('enabled', False):
            return False

        # TODO: Implement alert notification logic
        # This could send emails, webhooks, etc.
        log_critical(f"🚨 Alert triggered for {self.id}: Entry signal conditions met")
        return True

    def reset(self, context: Dict[str, Any] = None):
        """Reset the node to active state for re-execution."""
        if context:
            self.mark_active(context)
        else:
            # For testing purposes, mark as active without context
            # self._active = True # REMOVED - violates parent-child activation principle
            pass  # No-op as children are not self-activated

        self.signal_triggered = False
        self.trigger_time = None
        self.trigger_price = None
        self.node_variables = {}
        # log_info(f"🔄 Entry Signal Node {self.id} reset to active state")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current node status.
        
        Returns:
            Dictionary containing node status information
        """
        return {
            'node_id': self.id,
            'node_type': 'entrySignalNode',
            'state': 'active' if self.is_active() else 'inactive',
            'signal_triggered': self.signal_triggered,
            'trigger_time': self.trigger_time,
            'trigger_price': self.trigger_price,
            'node_variables': self.node_variables.copy(),
            'conditions_count': len(self.conditions),
            'variables_count': len(self.variables_config)
        }

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process data through the entry signal node.
        This is the required implementation of the abstract method.
        
        Args:
            data: Market data to process
            
        Returns:
            Processing results
        """
        # For EntrySignalNode, we call the template method execute()
        return self.execute(data)
