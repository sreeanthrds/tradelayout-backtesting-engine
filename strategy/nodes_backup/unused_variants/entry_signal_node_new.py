"""
EntrySignalNode - Evaluates entry conditions and captures market snapshot

Responsibilities:
1. Evaluate entry conditions using ConditionEvaluator
2. Calculate node variables (AFTER conditions satisfied) using ExpressionEvaluator
3. Store node variables in context for use by EntryNode

Author: UniTrader Team
Created: 2024-11-24
"""

from typing import Dict, Any
from strategy.nodes.base_node_clean import BaseNode
from src.core.condition_evaluator_v2 import ConditionEvaluator
from src.core.expression_evaluator import ExpressionEvaluator
from src.utils.logger import log_info, log_debug, log_error


class EntrySignalNode(BaseNode):
    """
    Entry Signal Node - Evaluates entry conditions.
    
    Flow:
    1. Evaluate conditions using ConditionEvaluator
    2. If TRUE:
       - Calculate node variables (market snapshot)
       - Store in context['node_variables'][node_id]
       - Return logic_completed=True → Activate EntryNode
    3. If FALSE:
       - Return logic_completed=False → Retry next tick
    """
    
    def __init__(self, node_id: str, data: Dict[str, Any]):
        """
        Initialize EntrySignalNode.
        
        Args:
            node_id: Unique node identifier
            data: Node configuration from strategy
        """
        super().__init__(node_id, 'EntrySignalNode', data.get('label'))
        
        # Extract configuration
        self.conditions = data.get('conditions', {})
        self.node_variables = data.get('nodeVariables', {})
        
        log_debug(f"📊 EntrySignalNode created: {node_id}")
        log_debug(f"   Conditions: {bool(self.conditions)}")
        log_debug(f"   Node variables: {list(self.node_variables.keys())}")
    
    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate entry conditions and capture market snapshot.
        
        Flow:
        1. Get ConditionEvaluatorV2 and ExpressionEvaluator from context
        2. Evaluate conditions
        3. If satisfied → Calculate node variables, return success
        4. If not satisfied → Return failure (retry next tick)
        
        Args:
            context: Execution context
            
        Returns:
            {'logic_completed': True} if conditions met
            {'logic_completed': False} if conditions not met
        """
        # ================================================================
        # STEP 1: Get evaluators from context
        # ================================================================
        expression_evaluator = context.get('expression_evaluator')
        if not expression_evaluator:
            log_error(f"❌ {self.id}: ExpressionEvaluator not found in context")
            return {'logic_completed': False, 'error': 'ExpressionEvaluator missing'}
        
        # ================================================================
        # STEP 2: Evaluate conditions using ConditionEvaluator
        # ================================================================
        try:
            # Create condition evaluator
            execution_mode = context.get('execution_mode', 'backtesting')
            condition_evaluator = ConditionEvaluator(
                expression_evaluator=expression_evaluator,
                mode=execution_mode
            )
            
            # Set condition and context
            condition_evaluator.set_condition(self.conditions)
            condition_evaluator.set_context(context=context)
            
            # Evaluate conditions
            conditions_satisfied = condition_evaluator.evaluate_condition()
            
            log_debug(f"🔍 {self.id}: Conditions evaluated → {conditions_satisfied}")
            
        except Exception as e:
            log_error(f"❌ {self.id}: Error evaluating conditions: {e}")
            return {'logic_completed': False, 'error': str(e)}
        
        # ================================================================
        # STEP 3: If conditions NOT satisfied → Retry next tick
        # ================================================================
        if not conditions_satisfied:
            log_debug(f"⏸️ {self.id}: Conditions not met - will retry next tick")
            return {'logic_completed': False}
        
        # ================================================================
        # STEP 4: Conditions satisfied → Calculate node variables
        # ================================================================
        log_info(f"✅ {self.id}: Entry conditions SATISFIED")
        
        # Calculate and store node variables (market snapshot)
        if self.node_variables:
            try:
                node_var_values = {}
                
                for var_name, expression in self.node_variables.items():
                    # Evaluate expression using ExpressionEvaluator
                    value = expression_evaluator.evaluate(expression, context)
                    node_var_values[var_name] = value
                    log_debug(f"   📌 {var_name} = {value}")
                
                # Store in context for use by other nodes
                context.setdefault('node_variables', {})[self.id] = node_var_values
                
                log_info(f"✅ {self.id}: Captured {len(node_var_values)} node variables")
                
            except Exception as e:
                log_error(f"❌ {self.id}: Error calculating node variables: {e}")
                # Still proceed even if node variables fail
        
        # ================================================================
        # STEP 5: Return success → BaseNode will activate EntryNode
        # ================================================================
        return {
            'logic_completed': True,
            'conditions_satisfied': True,
            'node_variables_count': len(self.node_variables)
        }
