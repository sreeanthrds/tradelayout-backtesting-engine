"""
Base Node - Foundation for all nodes in the strategy execution tree.

Implements the core node execution principles:
1. Status management: Active, Inactive, Pending
2. Always invoke children regardless of parent status
3. Sequence: Pending → Node Logic → Activate Children → Inactive
4. Threading for node logic execution
5. Reset visited_flag when activating children
6. Stop condition detection
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
import threading
import logging

logger = logging.getLogger(__name__)


class NodeStatus:
    """Node status constants."""
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    PENDING = "Pending"


class BaseNode:
    """
    Base class for all nodes with proper status management.
    
    Key Principles:
    - At first tick: Start node is Active, all others are Inactive
    - Children are ALWAYS invoked regardless of parent status
    - Sequence: Active → Pending → Execute Logic → Activate Children → Inactive
    - Node logic executes in separate thread
    - visited_flag is reset when activating children
    - System stops when no Active or Pending nodes exist
    """
    
    def __init__(self, node_id: str, node_type: str, name: str):
        """
        Initialize base node.
        
        Args:
            node_id: Unique identifier for the node
            node_type: Type of node (StartNode, EntryNode, etc.)
            name: Display name
        """
        self.id = node_id
        self.type = node_type
        self.name = name
        
        # Node relationships
        self.parents: List[str] = []
        self.children: List[str] = []
        
        # Threading for node logic
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"Node-{node_id}")
        self.pending_future: Optional[Future] = None
        self.logic_lock = threading.Lock()
        
        logger.debug(f"Initialized {self.type} node: {self.id}")
    
    def set_relations(self, parents: List[str], children: List[str]):
        """Set parent-child relationships."""
        self.parents = parents
        self.children = children
    
    # ==================== State Management ====================
    
    def _get_node_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get node state from context.
        
        Returns:
            Dict with: status, visited, reEntryNum
        """
        node_states = context.get('node_states', {})
        if self.id not in node_states:
            # Initialize with default state
            node_states[self.id] = {
                'status': NodeStatus.INACTIVE,
                'visited': False,
                'reEntryNum': 0
            }
            context['node_states'] = node_states
        return node_states[self.id]
    
    def _set_node_state(self, context: Dict[str, Any], state_updates: Dict[str, Any]):
        """Update node state in context."""
        node_states = context.get('node_states', {})
        if self.id not in node_states:
            node_states[self.id] = {
                'status': NodeStatus.INACTIVE,
                'visited': False,
                'reEntryNum': 0
            }
        node_states[self.id].update(state_updates)
        context['node_states'] = node_states
    
    # ==================== Status Methods ====================
    
    def get_status(self, context: Dict[str, Any]) -> str:
        """Get current node status."""
        state = self._get_node_state(context)
        return state.get('status', NodeStatus.INACTIVE)
    
    def set_status(self, context: Dict[str, Any], status: str):
        """Set node status."""
        self._set_node_state(context, {'status': status})
        logger.debug(f"Node {self.id} status: {status}")
    
    def is_active(self, context: Dict[str, Any]) -> bool:
        """Check if node is active."""
        return self.get_status(context) == NodeStatus.ACTIVE
    
    def is_inactive(self, context: Dict[str, Any]) -> bool:
        """Check if node is inactive."""
        return self.get_status(context) == NodeStatus.INACTIVE
    
    def is_pending(self, context: Dict[str, Any]) -> bool:
        """Check if node is pending (executing logic)."""
        return self.get_status(context) == NodeStatus.PENDING
    
    def mark_active(self, context: Dict[str, Any]):
        """Mark node as active."""
        self.set_status(context, NodeStatus.ACTIVE)
    
    def mark_inactive(self, context: Dict[str, Any]):
        """Mark node as inactive."""
        self.set_status(context, NodeStatus.INACTIVE)
    
    def mark_pending(self, context: Dict[str, Any]):
        """Mark node as pending (executing logic)."""
        self.set_status(context, NodeStatus.PENDING)
    
    # ==================== Visited Flag ====================
    
    def is_visited(self, context: Dict[str, Any]) -> bool:
        """Check if node has been visited in current tick."""
        state = self._get_node_state(context)
        return state.get('visited', False)
    
    def mark_visited(self, context: Dict[str, Any]):
        """Mark node as visited for current tick."""
        self._set_node_state(context, {'visited': True})
    
    def reset_visited(self, context: Dict[str, Any]):
        """Reset visited flag (for new tick or when activating)."""
        self._set_node_state(context, {'visited': False})
    
    # ==================== Children Management ====================
    
    def activate_children(self, context: Dict[str, Any], node_instances: Dict[str, Any]):
        """
        Activate all child nodes and reset their visited flags.
        
        CRITICAL: This resets visited_flag for re-entry logic.
        
        Args:
            context: Execution context
            node_instances: Dictionary of all node instances
        """
        for child_id in self.children:
            if child_id in node_instances:
                child_node = node_instances[child_id]
                child_node.mark_active(context)
                child_node.reset_visited(context)  # ✅ Principle 5: Reset visited flag
                logger.debug(f"Activated child {child_id} (visited flag reset)")
    
    def get_children(self) -> List[str]:
        """Get list of child node IDs."""
        return self.children
    
    def get_parents(self) -> List[str]:
        """Get list of parent node IDs."""
        return self.parents
    
    # ==================== Core Execution ====================
    
    def execute(self, context: Dict[str, Any], node_instances: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute node following the proper sequence.
        
        Sequence:
        1. Check if already visited (prevent loops)
        2. Mark as visited
        3. If Active: Set to Pending → Execute logic in thread
        4. If Pending: Check if logic completed → Activate children → Set Inactive
        5. Always execute children (regardless of status)
        6. Return results
        
        Args:
            context: Execution context
            node_instances: Dictionary of all node instances
            
        Returns:
            Dict with execution results
        """
        # STEP 1: Check visited status (prevent infinite loops)
        if self.is_visited(context):
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Already visited',
                'signal_emitted': False,
                'child_results': []
            }
        
        # STEP 2: Mark as visited
        self.mark_visited(context)
        
        node_result = {
            'node_id': self.id,
            'executed': False,
            'signal_emitted': False
        }
        
        # STEP 3: If Active, start node logic in thread
        if self.is_active(context):
            # ✅ Principle 3: Set to PENDING before executing logic
            self.mark_pending(context)
            
            # ✅ Principle 4: Execute node logic in separate thread
            with self.logic_lock:
                if self.pending_future is None or self.pending_future.done():
                    self.pending_future = self.executor.submit(
                        self._execute_node_logic_safe, context, node_instances
                    )
                    logger.debug(f"Node {self.id}: Started logic execution in thread")
            
            node_result['reason'] = 'Logic started (PENDING)'
        
        # STEP 4: If Pending, check if logic completed
        elif self.is_pending(context):
            with self.logic_lock:
                if self.pending_future and self.pending_future.done():
                    try:
                        logic_result = self.pending_future.result()
                        node_result.update(logic_result)
                        
                        # If logic completed successfully
                        if logic_result.get('logic_completed', False):
                            # ✅ Principle 3: Activate children (with visited flag reset)
                            self.activate_children(context, node_instances)
                            
                            # ✅ Principle 3: Set self to Inactive
                            self.mark_inactive(context)
                            
                            logger.info(f"✅ Node {self.id}: Logic completed, children activated, self deactivated")
                        else:
                            # Logic not completed - rollback to Active
                            self.mark_active(context)
                            logger.debug(f"Node {self.id}: Logic not completed, rolled back to Active")
                        
                        # Clear future
                        self.pending_future = None
                        
                    except Exception as e:
                        # On error, rollback to Active
                        self.mark_active(context)
                        self.pending_future = None
                        logger.error(f"❌ Node {self.id}: Logic failed: {e}", exc_info=True)
                        node_result['error'] = str(e)
                else:
                    node_result['reason'] = 'Logic still executing (PENDING)'
        
        else:
            # Inactive - do nothing
            node_result['reason'] = 'Node not active'
        
        # STEP 5: ✅ Principle 2: Always execute children regardless of status
        child_results = self._execute_children(context, node_instances)
        node_result['child_results'] = child_results
        
        return node_result
    
    def _execute_node_logic_safe(self, context: Dict[str, Any], node_instances: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safe wrapper for node logic execution.
        Catches exceptions and returns proper result.
        """
        try:
            return self._execute_node_logic(context, node_instances)
        except Exception as e:
            logger.error(f"Exception in node {self.id} logic: {e}", exc_info=True)
            return {
                'node_id': self.id,
                'executed': False,
                'logic_completed': False,
                'error': str(e)
            }
    
    def _execute_node_logic(self, context: Dict[str, Any], node_instances: Dict[str, Any]) -> Dict[str, Any]:
        """
        Abstract method - subclasses must implement their specific logic.
        
        This method runs in a separate thread.
        
        Args:
            context: Execution context
            node_instances: Dictionary of all node instances
            
        Returns:
            Dict with:
                - executed: bool
                - logic_completed: bool (True to deactivate and activate children)
                - signal_emitted: bool
                - ... other node-specific data
        """
        raise NotImplementedError("Subclasses must implement _execute_node_logic")
    
    def _execute_children(self, context: Dict[str, Any], node_instances: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute all children nodes recursively.
        
        IMPORTANT: Children are ALWAYS executed regardless of parent status.
        
        Args:
            context: Execution context
            node_instances: Dictionary of all node instances
            
        Returns:
            List of child execution results
        """
        child_results = []
        
        for child_id in self.children:
            if child_id in node_instances:
                child_node = node_instances[child_id]
                child_result = child_node.execute(context, node_instances)
                child_results.append(child_result)
        
        return child_results
    
    def cleanup(self):
        """Cleanup resources (threading)."""
        if self.executor:
            self.executor.shutdown(wait=False)
