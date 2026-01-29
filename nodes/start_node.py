"""
Start Node - Entry point for strategy execution.

The Start Node:
- Is Active at first tick (reEntryNum = 0)
- Has no specific node logic to perform
- Simply activates its children and deactivates itself
- Follows sequence: Pending → Activate Children → Inactive
"""

from typing import Dict, Any
import logging
from nodes.base_node import BaseNode

logger = logging.getLogger(__name__)


class StartNode(BaseNode):
    """
    Start Node - Entry point of the strategy tree.
    
    Behavior:
    - Active at first tick
    - No specific logic (just activates children)
    - Immediately completes and deactivates
    """
    
    def __init__(self, node_id: str, name: str = "Start"):
        """Initialize Start Node."""
        super().__init__(node_id, "StartNode", name)
    
    def _execute_node_logic(self, context: Dict[str, Any], node_instances: Dict[str, Any]) -> Dict[str, Any]:
        """
        Start node logic: No specific logic, just signal completion.
        
        The Start node doesn't have any specific logic to perform.
        It just needs to activate its children and deactivate itself.
        
        Returns:
            Dict with logic_completed=True to trigger children activation
        """
        logger.info(f"🚀 Start Node {self.id}: Executing (activating children)")
        
        return {
            'node_id': self.id,
            'executed': True,
            'logic_completed': True,  # ✅ Signal to activate children and deactivate self
            'signal_emitted': False
        }
