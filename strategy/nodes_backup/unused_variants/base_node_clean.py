"""
Base Node - Foundation for all node types

Implements core node execution pattern with three states: ACTIVE, PENDING, INACTIVE
Keeps it simple - delegates complex operations to services.

Author: UniTrader Team  
Created: 2024-11-22
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import threading
from src.utils.logger import log_debug, log_info, log_warning, log_error


class BaseNode(ABC):
    """
    Abstract base class for all nodes.
    
    Core Responsibilities:
    - State management (ACTIVE → PENDING → INACTIVE)
    - Visited flag (prevents loops)
    - reEntryNum tracking (for re-entries)
    - Children execution (recursive pattern)
    - Standard execution flow
    
    What it DOES NOT do (delegate to services):
    - GPS operations → Use context['gps'] or helpers
    - F&O resolution → Use FO_Resolver service
    - Order placement → Use OrderManager
    - Expression evaluation → Use ExpressionEvaluator
    """
    
    def __init__(self, node_id: str, node_type: str, label: str = ''):
        """
        Initialize base node.
        
        Args:
            node_id: Unique identifier for this node
            node_type: Type of node (StartNode, EntryNode, etc.)
            label: Human-readable label
        """
        self.id = node_id
        self.type = node_type
        self.label = label or node_id
        
        # Children nodes (connected in graph)
        self.children: List[str] = []
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standard execution pattern - DO NOT OVERRIDE in subclasses.
        
        Flow:
        1. Check visited → Skip if already processed
        2. Mark visited (prevent loops)
        3. If ACTIVE → Execute logic
        4. Update status based on result
        5. Execute children (regardless of status)
        
        Args:
            context: Execution context with all shared data
            
        Returns:
            Dict with execution results
        """
        # ================================================================
        # STEP 1: Check visited flag (terminate sub-tree if visited)
        # ================================================================
        if self.is_visited(context):
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Already visited - subtree terminated',
                'child_results': []
            }
        
        # Mark as visited to prevent infinite loops
        self.mark_visited(context)
        
        # ================================================================
        # STEP 2: Execute node logic (ONLY if ACTIVE)
        # ================================================================
        node_result = {'node_id': self.id, 'executed': False}
        
        if self.is_active(context):
            # ============================================================
            # SPECIAL CHECK: ReEntrySignalNode - Check limit BEFORE logic
            # ============================================================
            if self.type == 'ReEntrySignalNode':
                my_reentry = self._get_node_state(context).get('reEntryNum', 0)
                max_reentries = getattr(self, 'max_reentries', 1)
                
                if my_reentry >= max_reentries:
                    # Limit reached: HARD STOP - no logic, no children
                    log_info(f"🛑 {self.id}: Re-entry limit reached ({my_reentry}/{max_reentries}) - HARD STOP")
                    self.mark_inactive(context)
                    return {
                        'node_id': self.id,
                        'executed': False,
                        'reason': f'Re-entry limit reached ({my_reentry}/{max_reentries}) - subtree terminated',
                        'logic_completed': False,
                        'child_results': []  # ✅ No children execution!
                    }
            
            # ============================================================
            # NORMAL EXECUTION: Execute node logic
            # ============================================================
            # Mark PENDING before executing (critical for shutdown detection)
            self.mark_pending(context)
            
            # Check if should execute in separate thread
            execution_mode = context.get('execution_mode', 'backtesting')
            is_action_node = self.type in ['EntryNode', 'ExitNode']
            
            if execution_mode == 'live' and is_action_node:
                # ========================================================
                # ASYNC EXECUTION: Action nodes in LIVE mode
                # ========================================================
                log_debug(f"🔄 {self.id}: Executing in separate thread (LIVE mode)")
                
                # Execute in thread, callback will update status
                self._execute_node_logic_async(context)
                
                # Node stays PENDING, callback will update status later
                node_result = {
                    'node_id': self.id,
                    'executed': True,
                    'async': True,
                    'status': 'PENDING'
                }
            else:
                # ========================================================
                # SYNC EXECUTION: Backtesting or signal nodes
                # ========================================================
                try:
                    # Execute node-specific logic (implemented by subclass)
                    node_result = self._execute_node_logic(context)
                    
                    # Update status based on result
                    if node_result.get('logic_completed', False):
                        # SUCCESS: Calculate variables, activate children, mark self INACTIVE
                        self._calculate_and_store_node_variables(context)
                        self._activate_children(context)
                        self.mark_inactive(context)
                    else:
                        # FAILURE/RETRY: Revert to ACTIVE for next tick
                        self.mark_active(context)
                        
                except Exception as e:
                    log_error(f"❌ Error in {self.type}({self.id}): {e}")
                    self.mark_active(context)  # Retry on next tick
                    node_result = {
                        'node_id': self.id,
                        'executed': False,
                        'reason': f'Exception: {str(e)}',
                        'error': str(e)
                    }
        else:
            # Node not active - skip logic
            node_result = {
                'node_id': self.id,
                'executed': False,
                'reason': 'Node not active'
            }
        
        # ================================================================
        # STEP 3: Execute children REGARDLESS of parent status
        # This ensures entire tree is traversed every tick
        # ================================================================
        child_results = self._execute_children(context)
        node_result['child_results'] = child_results
        
        return node_result
    
    @abstractmethod
    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Node-specific logic - MUST be implemented by subclasses.
        
        Args:
            context: Execution context
            
        Returns:
            Dict with 'logic_completed': True/False
            - True: Logic succeeded, move to children
            - False: Logic failed, retry on next tick
        """
        raise NotImplementedError(f"{self.type} must implement _execute_node_logic()")
    
    def _execute_node_logic_async(self, context: Dict[str, Any]):
        """
        Execute node logic in a separate thread (for action nodes in LIVE mode).
        
        Thread will call _on_logic_complete callback when done.
        
        Args:
            context: Execution context
        """
        def worker():
            try:
                # Execute node logic in background
                result = self._execute_node_logic(context)
                
                # Callback to update status
                self._on_logic_complete(context, result)
                
            except Exception as e:
                log_error(f"❌ Async error in {self.type}({self.id}): {e}")
                # Callback with error
                self._on_logic_complete(context, {
                    'logic_completed': False,
                    'error': str(e)
                })
        
        # Spawn thread (daemon so it closes on shutdown)
        thread = threading.Thread(target=worker, daemon=True, name=f"{self.type}-{self.id}")
        thread.start()
        
        log_debug(f"🚀 {self.id}: Thread started (ID: {thread.ident})")
    
    def _on_logic_complete(self, context: Dict[str, Any], result: Dict[str, Any]):
        """
        Callback when async node logic completes.
        
        Updates node status and activates children if successful.
        
        Args:
            context: Execution context
            result: Result from _execute_node_logic()
        """
        if result.get('logic_completed', False):
            # SUCCESS: Calculate variables, activate children, mark self INACTIVE
            log_info(f"✅ {self.id}: Async logic completed successfully")
            self._calculate_and_store_node_variables(context)
            self._activate_children(context)
            self.mark_inactive(context)
        else:
            # FAILURE: Revert to ACTIVE for retry
            log_warning(f"⚠️ {self.id}: Async logic failed - will retry")
            self.mark_active(context)
    
    # ========================================================================
    # State Management
    # ========================================================================
    
    def is_active(self, context: Dict[str, Any]) -> bool:
        """Check if node is ACTIVE."""
        node_state = self._get_node_state(context)
        return node_state.get('status') == 'Active'
    
    def is_pending(self, context: Dict[str, Any]) -> bool:
        """Check if node is PENDING."""
        node_state = self._get_node_state(context)
        return node_state.get('status') == 'Pending'
    
    def is_inactive(self, context: Dict[str, Any]) -> bool:
        """Check if node is INACTIVE."""
        node_state = self._get_node_state(context)
        return node_state.get('status') == 'Inactive'
    
    def is_visited(self, context: Dict[str, Any]) -> bool:
        """Check if node was visited this tick."""
        node_state = self._get_node_state(context)
        return node_state.get('visited', False)
    
    def mark_active(self, context: Dict[str, Any]):
        """Mark node as ACTIVE."""
        node_state = self._get_node_state(context)
        node_state['status'] = 'Active'
    
    def mark_pending(self, context: Dict[str, Any]):
        """Mark node as PENDING."""
        node_state = self._get_node_state(context)
        node_state['status'] = 'Pending'
    
    def mark_inactive(self, context: Dict[str, Any]):
        """Mark node as INACTIVE."""
        node_state = self._get_node_state(context)
        node_state['status'] = 'Inactive'
    
    def mark_visited(self, context: Dict[str, Any]):
        """Mark node as visited this tick."""
        node_state = self._get_node_state(context)
        node_state['visited'] = True
    
    def reset_visited(self, context: Dict[str, Any]):
        """Reset visited flag for new tick."""
        node_state = self._get_node_state(context)
        node_state['visited'] = False
    
    def _get_node_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get node state dict from context."""
        node_states = context.get('node_states', {})
        if self.id not in node_states:
            # Initialize default state
            node_states[self.id] = {
                'status': 'Inactive',  # Default to inactive
                'visited': False,
                'reEntryNum': 0
            }
        return node_states[self.id]
    
    # ========================================================================
    # Children Management
    # ========================================================================
    
    def _activate_children(self, context: Dict[str, Any]):
        """
        Activate all immediate children and propagate reEntryNum.
        
        Called when this node completes successfully.
        
        CRITICAL: For ReEntrySignalNode:
        - If my_reentry == max_reentries: DON'T activate children (stop propagation)
        - If my_reentry < max_reentries: Increment, then activate children
        """
        my_reentry = self._get_node_state(context).get('reEntryNum', 0)
        
        # ====================================================================
        # SPECIAL CASE: ReEntrySignalNode
        # ====================================================================
        if self.type == 'ReEntrySignalNode':
            max_reentries = getattr(self, 'max_reentries', 1)
            
            # Check if we've hit the limit
            if my_reentry >= max_reentries:
                # STOP: Don't activate children, don't propagate
                log_info(f"🛑 {self.id}: Re-entry limit reached ({my_reentry}/{max_reentries}) - stopping propagation")
                return  # ✅ Hard stop - no children activation!
            
            # We can re-enter: increment reEntryNum
            my_reentry += 1
            self._get_node_state(context)['reEntryNum'] = my_reentry
            log_info(f"🔄 {self.id}: Re-entry {my_reentry}/{max_reentries}")
        
        # ====================================================================
        # NORMAL CASE: Activate all children
        # ====================================================================
        for child_id in self.children:
            if child_id in context.get('node_instances', {}):
                child_node = context['node_instances'][child_id]
                child_state = child_node._get_node_state(context)
                
                # Activate child
                child_state['status'] = 'Active'
                
                # Reset visited flag so child can execute
                child_state['visited'] = False
                
                # Propagate reEntryNum from parent to child
                child_state['reEntryNum'] = my_reentry
    
    def _execute_children(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute all children nodes recursively.
        
        IMPORTANT: DO NOT override this in subclasses.
        This implements the core recursive pattern.
        
        Args:
            context: Execution context
            
        Returns:
            List of child execution results
        """
        # Track recursion depth
        depth = context.get('_exec_depth', 0)
        context['_exec_depth'] = depth + 1
        
        # Track maximum depth
        max_depth = context.get('_max_exec_depth', 0)
        if depth + 1 > max_depth:
            context['_max_exec_depth'] = depth + 1
            if depth + 1 > 100 and (depth + 1) % 50 == 0:
                log_warning(f"⚠️ Deep recursion: {depth + 1} levels at {self.id}")
        
        # Execute all children
        results = []
        node_instances = context.get('node_instances', {})
        
        for child_id in self.children:
            if child_id in node_instances:
                child_node = node_instances[child_id]
                # Recursive call - child handles its own logic
                child_result = child_node.execute(context)
                results.append(child_result)
            else:
                log_warning(f"⚠️ Child {child_id} not found in node instances")
        
        # Reset depth
        context['_exec_depth'] = depth
        
        return results
    
    # ========================================================================
    # Node Variables
    # ========================================================================
    
    def _calculate_and_store_node_variables(self, context: Dict[str, Any]):
        """
        Calculate and store node variables in GPS.
        Called after logic_completed=True, before activating children.
        
        Args:
            context: Execution context
        """
        # Get variables config from node data
        variables_config = getattr(self, 'variables_config', None) or getattr(self, 'node_variables_config', None)
        
        if not variables_config:
            return  # No variables to calculate
        
        # Get evaluator from context
        expression_evaluator = context.get('expression_evaluator')
        if not expression_evaluator:
            log_warning(f"⚠️ {self.id}: No expression_evaluator in context")
            return
        
        # Get context_manager (GPS)
        context_manager = context.get('context_manager')
        if not context_manager:
            log_warning(f"⚠️ {self.id}: No context_manager in context")
            return
        
        # Calculate each variable
        calculated_vars = {}
        for var_config in variables_config:
            var_name = var_config.get('name')
            var_expression = var_config.get('expression')
            
            if not var_name or not var_expression:
                continue
            
            try:
                # Evaluate expression
                var_value = expression_evaluator.evaluate(var_expression, context)
                calculated_vars[var_name] = var_value
                
                # Store in GPS
                context_manager.set_node_variable(self.id, var_name, var_value)
                
            except Exception as e:
                log_error(f"❌ {self.id}: Error calculating variable '{var_name}': {e}")
        
        if calculated_vars:
            log_debug(f"📊 {self.id}: Calculated {len(calculated_vars)} variables")
    
    # ========================================================================
    # Helper Methods (for subclasses to use)
    # ========================================================================
    
    def get_reentry_num(self, context: Dict[str, Any]) -> int:
        """Get current reEntryNum for this node."""
        return self._get_node_state(context).get('reEntryNum', 0)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.type}(id={self.id}, label={self.label})"
