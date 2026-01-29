"""
Base Node - Foundation for all node types

Implements three-state model: ACTIVE, PENDING, INACTIVE
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from interfaces.data_reader import DataReaderInterface
from interfaces.data_writer import DataWriterInterface
from strategy.expression_evaluator import ExpressionEvaluator


logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """Node execution status."""
    ACTIVE = "Active"      # Execute logic on each tick
    PENDING = "Pending"    # Waiting for async operation (order fill)
    INACTIVE = "Inactive"  # Completed, no execution


class BaseNode:
    """
    Base class for all nodes.
    
    Features:
    - Three-state model (ACTIVE, PENDING, INACTIVE)
    - Async execution
    - DataReader/DataWriter integration
    - Expression evaluation
    - State management
    """
    
    def __init__(
        self,
        node_id: str,
        node_type: str,
        config: Dict[str, Any],
        data_reader: DataReaderInterface,
        data_writer: DataWriterInterface,
        expression_evaluator: ExpressionEvaluator,
        user_id: str,
        strategy_id: str
    ):
        """Initialize base node."""
        self.node_id = node_id
        self.node_type = node_type
        self.config = config
        self.data_reader = data_reader
        self.data_writer = data_writer
        self.expression_evaluator = expression_evaluator
        self.user_id = user_id
        self.strategy_id = strategy_id
        
        # Node state
        self.status = NodeStatus.ACTIVE
        self.visited = False
        self.re_entry_num = 0
        
        # Next nodes
        self.next_nodes: List[str] = config.get('next', [])
        
        # Context
        self.context: Dict[str, Any] = {}
    
    async def execute(self, tick_data: Dict[str, Any]) -> Optional[List[str]]:
        """
        Execute node logic.
        
        Returns:
            List of next node IDs to activate, or None
        """
        # Skip if PENDING or INACTIVE
        if self.status != NodeStatus.ACTIVE:
            return None
        
        # Update context with tick data
        self.context.update(tick_data)
        
        # Execute node-specific logic
        try:
            result = await self._execute_logic(tick_data)
            return result
        except Exception as e:
            logger.error(f"Error executing {self.node_id}: {e}")
            return None
    
    async def _execute_logic(self, tick_data: Dict[str, Any]) -> Optional[List[str]]:
        """
        Node-specific logic (override in subclasses).
        
        Returns:
            List of next node IDs to activate, or None
        """
        raise NotImplementedError("Subclasses must implement _execute_logic")
    
    def is_active(self) -> bool:
        """Check if node is active."""
        return self.status == NodeStatus.ACTIVE
    
    def is_pending(self) -> bool:
        """Check if node is pending."""
        return self.status == NodeStatus.PENDING
    
    def is_inactive(self) -> bool:
        """Check if node is inactive."""
        return self.status == NodeStatus.INACTIVE
    
    def mark_pending(self):
        """Mark node as pending (waiting for async operation)."""
        self.status = NodeStatus.PENDING
        logger.debug(f"{self.node_id} marked as PENDING")
    
    def mark_inactive(self):
        """Mark node as inactive (completed)."""
        self.status = NodeStatus.INACTIVE
        logger.debug(f"{self.node_id} marked as INACTIVE")
    
    def mark_active(self):
        """Mark node as active."""
        self.status = NodeStatus.ACTIVE
        logger.debug(f"{self.node_id} marked as ACTIVE")
    
    async def save_state(self):
        """Save node state to database."""
        try:
            await self.data_writer.update_node_state(
                user_id=self.user_id,
                strategy_id=self.strategy_id,
                node_id=self.node_id,
                status=self.status.value,
                visited=self.visited,
                re_entry_num=self.re_entry_num
            )
        except Exception as e:
            logger.error(f"Error saving state for {self.node_id}: {e}")
    
    async def load_state(self):
        """Load node state from database."""
        try:
            state = await self.data_reader.get_node_state(
                user_id=self.user_id,
                strategy_id=self.strategy_id,
                node_id=self.node_id
            )
            
            if state:
                self.status = NodeStatus(state.get('status', 'Active'))
                self.visited = state.get('visited', False)
                self.re_entry_num = state.get('re_entry_num', 0)
        except Exception as e:
            logger.error(f"Error loading state for {self.node_id}: {e}")
    
    async def save_variable(self, variable_name: str, value: float):
        """Save node variable."""
        try:
            await self.data_writer.update_node_variable(
                user_id=self.user_id,
                strategy_id=self.strategy_id,
                node_id=self.node_id,
                variable_name=variable_name,
                value=value
            )
        except Exception as e:
            logger.error(f"Error saving variable {variable_name} for {self.node_id}: {e}")
    
    async def get_variable(self, variable_name: str) -> Optional[float]:
        """Get node variable."""
        try:
            return await self.data_reader.get_node_variable(
                user_id=self.user_id,
                strategy_id=self.strategy_id,
                node_id=self.node_id,
                variable_name=variable_name
            )
        except Exception as e:
            logger.error(f"Error getting variable {variable_name} for {self.node_id}: {e}")
            return None
    
    async def evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition expression."""
        try:
            result = await self.expression_evaluator.evaluate(
                expression=condition,
                user_id=self.user_id,
                strategy_id=self.strategy_id,
                context=self.context
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False
    
    def get_next_nodes(self) -> List[str]:
        """Get list of next node IDs."""
        return self.next_nodes
    
    def __repr__(self) -> str:
        return f"{self.node_type}(id={self.node_id}, status={self.status.value})"
