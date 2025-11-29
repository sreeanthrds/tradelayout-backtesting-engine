"""
Exit Signal Node - Evaluates exit conditions with re-entry support.

This node:
1. Evaluates exit conditions (normal or re-entry based on reEntryNum)
2. Calculates node variables from expressions
3. Stores variables in GPS for use by exit nodes
4. Activates children when conditions pass

Author: UniTrader Team
Created: 2024-11-24
"""

from typing import Dict, Any, Optional
from strategy.nodes.base_node_clean import BaseNode
from src.utils.logger import log_info, log_debug


class ExitSignalNode(BaseNode):
    """
    Exit Signal Node that evaluates exit conditions with re-entry support.
    
    Similar to EntrySignalNode but supports dual condition sets:
    - Normal exit conditions (reEntryNum == 0)
    - Re-entry exit conditions (reEntryNum > 0)
    """
    
    def __init__(self, node_id: str, node_config: Dict[str, Any]):
        """
        Initialize Exit Signal Node.
        
        Args:
            node_id: Unique identifier for this node
            node_config: Configuration dictionary containing:
                - type: Node type
                - data: Node data with conditions, variables, etc.
        """
        # Extract data
        node_data = node_config.get('data', {})
        node_type = node_config.get('type', 'exitSignalNode')
        label = node_data.get('label', 'Exit Signal')
        
        # Call parent constructor
        super().__init__(node_id, node_type, label)
        
        # Store config
        self.node_config = node_config
        self.node_data = node_data
        
        # Extract conditions
        # Note: Exit Signal uses 'reEntryExitConditions' (different from Entry Signal's 'reEntryConditions')
        self.conditions = node_data.get('conditions', [])
        self.reentry_conditions = node_data.get('reEntryExitConditions', [])  # UI uses 'reEntryExitConditions' for exits
        self.has_reentry_conditions = node_data.get('hasReEntryExitConditions', False)
        
        # Extract node variables
        self.node_variables_config = node_data.get('node_variables', [])
        
        log_debug(f"ExitSignalNode {node_id} initialized:")
        log_debug(f"  Normal conditions: {len(self.conditions)} groups")
        log_debug(f"  Re-entry conditions: {len(self.reentry_conditions)} groups")
        log_debug(f"  Has re-entry: {self.has_reentry_conditions}")
        log_debug(f"  Variables: {len(self.node_variables_config)}")
    
    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute exit signal node logic:
        1. Get reEntryNum from node state
        2. If reEntryNum == 0: use 'conditions', else use 'reEntryExitConditions'
        3. Evaluate chosen conditions
        4. Calculate node variables if conditions pass
        5. Store variables in GPS
        
        Args:
            context: Execution context with condition_evaluator, GPS, etc.
            
        Returns:
            Dictionary with execution results
        """
        try:
            # Get reEntryNum from node state
            re_entry_num = self.get_reentry_num(context)
            
            # Choose conditions: reEntryNum == 0 → 'conditions', else → 'reEntryExitConditions'
            if re_entry_num == 0:
                conditions_to_evaluate = self.conditions
                condition_type = 'normal'
            else:
                conditions_to_evaluate = self.reentry_conditions
                condition_type = 're-entry'
            
            log_debug(f"ExitSignalNode {self.id}: reEntryNum={re_entry_num}, evaluating {condition_type} conditions")
            
            # If no conditions, fail
            if not conditions_to_evaluate:
                return {
                    'node_id': self.id,
                    'executed': True,
                    'logic_completed': False,
                    'conditions_met': False,
                    'reason': f'No {condition_type} conditions configured'
                }
            
            # Evaluate conditions
            conditions_met = self._evaluate_conditions(conditions_to_evaluate, context)
            
            if not conditions_met:
                return {
                    'node_id': self.id,
                    'executed': True,
                    'logic_completed': False,
                    'conditions_met': False,
                    'reason': f'{condition_type.capitalize()} exit conditions not met'
                }
            
            # Conditions passed - calculate node variables
            variables_calculated = self._calculate_node_variables(context)
            
            # Store variables in GPS
            self._store_node_variables(context, variables_calculated)
            
            log_info(f"✅ ExitSignalNode {self.id}: {condition_type} conditions passed, {len(variables_calculated)} variables calculated")
            
            return {
                'node_id': self.id,
                'executed': True,
                'logic_completed': True,
                'conditions_met': True,
                'reason': f'{condition_type.capitalize()} exit conditions passed',
                'variables_calculated': variables_calculated,
                'condition_type': condition_type,
                're_entry_num': re_entry_num
            }
            
        except Exception as e:
            from src.utils.error_handler import handle_exception
            handle_exception(
                e,
                "exit_signal_node_execute",
                {
                    "node_id": self.id,
                    "re_entry_num": re_entry_num if 're_entry_num' in locals() else None
                },
                is_critical=False,
                continue_execution=True
            )
            return {
                'node_id': self.id,
                'executed': False,
                'logic_completed': False,
                'conditions_met': False,
                'reason': f'Error evaluating conditions: {str(e)}'
            }
    
    def _evaluate_conditions(self, conditions: list, context: Dict[str, Any]) -> bool:
        """
        Evaluate conditions using ConditionEvaluator.
        
        Args:
            conditions: List of condition groups to evaluate
            context: Execution context
            
        Returns:
            True if all conditions pass, False otherwise
        """
        # Get condition evaluator from context
        condition_evaluator = context.get('condition_evaluator')
        if not condition_evaluator:
            log_debug(f"ExitSignalNode {self.id}: No condition evaluator in context")
            return False
        
        # Prepare condition structure for evaluator
        if not conditions:
            return False
        
        # If conditions is already a root structure, use as-is
        if len(conditions) == 1 and conditions[0].get('id') == 'root':
            condition_structure = conditions[0]
        else:
            # Wrap in root if needed
            condition_structure = {
                'id': 'root',
                'conditions': conditions,
                'groupLogic': 'AND'
            }
        
        # Set condition and context
        condition_evaluator.set_condition(condition_structure)
        condition_evaluator.set_context(context=context)
        
        # Evaluate
        try:
            result = condition_evaluator.evaluate_condition()
            return bool(result)
        except Exception as e:
            log_debug(f"ExitSignalNode {self.id}: Condition evaluation error: {e}")
            return False
    
    def _calculate_node_variables(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate node variables from expressions.
        
        Args:
            context: Execution context with expression_evaluator
            
        Returns:
            Dictionary of {variable_name: calculated_value}
        """
        if not self.node_variables_config:
            return {}
        
        # Get expression evaluator from context
        expression_evaluator = context.get('expression_evaluator')
        if not expression_evaluator:
            log_debug(f"ExitSignalNode {self.id}: No expression evaluator in context")
            return {}
        
        # Set context for expression evaluator
        expression_evaluator.set_context(
            tick=context.get('current_tick'),
            current_timestamp=context.get('current_timestamp'),
            tick_data=context.get('tick_data'),
            candles_df=context.get('candles_df'),
            context=context
        )
        
        # Calculate each variable
        variables = {}
        for var_config in self.node_variables_config:
            var_name = var_config.get('name')
            var_expression = var_config.get('expression')
            
            if not var_name or not var_expression:
                continue
            
            try:
                # Evaluate expression
                value = expression_evaluator._get_scalar_value(var_expression)
                variables[var_name] = value
                log_debug(f"  Variable '{var_name}' = {value}")
            except Exception as e:
                log_debug(f"  Variable '{var_name}' calculation error: {e}")
                variables[var_name] = None
        
        return variables
    
    def _store_node_variables(self, context: Dict[str, Any], variables: Dict[str, Any]):
        """
        Store calculated variables in GPS for access by other nodes.
        
        Args:
            context: Execution context with context_manager
            variables: Dictionary of calculated variables
        """
        if not variables:
            return
        
        # Get context manager (GPS)
        context_manager = context.get('context_manager')
        if not context_manager:
            log_debug(f"ExitSignalNode {self.id}: No context manager in context")
            return
        
        # Store each variable
        for var_name, var_value in variables.items():
            try:
                context_manager.set_node_variable(
                    node_id=self.id,
                    variable_name=var_name,
                    value=var_value
                )
                log_debug(f"  Stored: {self.id}.{var_name} = {var_value}")
            except Exception as e:
                log_debug(f"  Error storing {var_name}: {e}")
    
    def get_node_type(self) -> str:
        """Return the node type identifier."""
        return "exitSignal"
