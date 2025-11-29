"""
Condition Node - Evaluates conditions and routes flow

Acts as a decision point in the strategy.
"""

from typing import Dict, Any, Optional, List
import logging

from .base_node import BaseNode, NodeStatus


logger = logging.getLogger(__name__)


class ConditionNode(BaseNode):
    """
    Condition node for flow control.
    
    Features:
    - Condition evaluation
    - Conditional routing (true_next, false_next)
    - Re-entry support
    """
    
    def __init__(self, **kwargs):
        """Initialize condition node."""
        super().__init__(**kwargs)
        
        # Condition configuration
        self.condition = self.config.get('condition', '')
        self.true_next = self.config.get('true_next', [])
        self.false_next = self.config.get('false_next', [])
        self.allow_re_entry = self.config.get('allow_re_entry', False)
        self.max_re_entries = self.config.get('max_re_entries', 0)
    
    async def _execute_logic(self, tick_data: Dict[str, Any]) -> Optional[List[str]]:
        """Execute condition node logic."""
        
        # Check re-entry limits
        if self.visited and not self.allow_re_entry:
            logger.debug(f"{self.node_id}: Already visited, no re-entry allowed")
            return None
        
        if self.allow_re_entry and self.re_entry_num >= self.max_re_entries:
            logger.debug(f"{self.node_id}: Max re-entries reached")
            return None
        
        # Evaluate condition
        condition_met = await self.evaluate_condition(self.condition)
        
        logger.debug(f"{self.node_id}: Condition '{self.condition}' = {condition_met}")
        
        # Update state
        if not self.visited:
            self.visited = True
        else:
            self.re_entry_num += 1
        
        await self.save_state()
        
        # Return appropriate next nodes
        if condition_met:
            logger.info(f"{self.node_id}: Condition TRUE, activating: {self.true_next}")
            return self.true_next
        else:
            logger.info(f"{self.node_id}: Condition FALSE, activating: {self.false_next}")
            return self.false_next
