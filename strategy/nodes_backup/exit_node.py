"""
Exit Node - Handles trade exits

Closes positions based on exit conditions.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from .base_node import BaseNode, NodeStatus
from interfaces.order_placer import OrderPlacerInterface


logger = logging.getLogger(__name__)


class ExitNode(BaseNode):
    """
    Exit node for closing positions.
    
    Features:
    - Exit condition evaluation
    - Position closure
    - PNL calculation
    - Three-state model (ACTIVE → PENDING → INACTIVE)
    """
    
    def __init__(self, order_placer: OrderPlacerInterface, **kwargs):
        """Initialize exit node."""
        super().__init__(**kwargs)
        self.order_placer = order_placer
        
        # Exit configuration
        self.exit_condition = self.config.get('exit_condition', '')
        self.position_id = self.config.get('position_id', '')
        
        # Order tracking
        self.order_id: Optional[str] = None
    
    async def _execute_logic(self, tick_data: Dict[str, Any]) -> Optional[List[str]]:
        """Execute exit node logic."""
        
        # Check if already visited (single exit)
        if self.visited:
            logger.debug(f"{self.node_id}: Already visited, skipping")
            return None
        
        # Get position
        position = await self._get_position()
        if not position:
            logger.warning(f"{self.node_id}: Position not found: {self.position_id}")
            return None
        
        # Check if position is still open
        if position.get('status') != 'OPEN':
            logger.debug(f"{self.node_id}: Position already closed")
            return None
        
        # Evaluate exit condition
        if not await self.evaluate_condition(self.exit_condition):
            logger.debug(f"{self.node_id}: Exit condition not met")
            return None
        
        # Condition met - close position
        logger.info(f"{self.node_id}: Exit condition met! Closing position...")
        
        # Mark as visited
        self.visited = True
        await self.save_state()
        
        # Place exit order
        order_result = await self._place_exit_order(position)
        
        if not order_result or not order_result.get('success'):
            logger.error(f"{self.node_id}: Exit order placement failed")
            return None
        
        # Mark as PENDING (waiting for order fill)
        self.mark_pending()
        await self.save_state()
        
        # Store order ID
        self.order_id = order_result.get('order_id')
        
        # Register callback for order fill
        await self._register_order_callback()
        
        return None  # Don't activate next nodes yet
    
    async def _get_position(self) -> Optional[Dict[str, Any]]:
        """Get position from database."""
        try:
            positions = await self.data_reader.get_positions(
                user_id=self.user_id,
                strategy_id=self.strategy_id,
                status='OPEN'
            )
            
            # Find position by ID
            for pos in positions:
                if pos.get('position_id') == self.position_id:
                    return pos
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None
    
    async def _place_exit_order(self, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place exit order."""
        try:
            # Get symbol and exchange from position (NOT from config!)
            symbol = position.get('symbol')
            exchange = position.get('exchange')
            quantity = position.get('quantity')
            
            # Determine exit transaction type (opposite of entry)
            entry_type = position.get('transaction_type')
            exit_type = 'SELL' if entry_type == 'BUY' else 'BUY'
            
            # Place order via OrderPlacer
            result = await self.order_placer.place_order(
                user_id=self.user_id,
                strategy_id=self.strategy_id,
                symbol=symbol,
                exchange=exchange,
                transaction_type=exit_type,
                order_type='MARKET',
                quantity=quantity,
                position_id=self.position_id
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error placing exit order: {e}")
            return None
    
    async def _register_order_callback(self):
        """Register callback for order fill notification."""
        # TODO: Implement order callback registration
        # For now, simulate immediate fill (for testing)
        await self._on_order_filled({
            'order_id': self.order_id,
            'position_id': self.position_id,
            'filled_quantity': 75,
            'average_price': 110.0  # Placeholder
        })
    
    async def _on_order_filled(self, fill_data: Dict[str, Any]):
        """Callback when exit order is filled."""
        logger.info(f"{self.node_id}: Exit order filled! {fill_data}")
        
        # Save exit price as node variable
        exit_price = fill_data.get('average_price', 0)
        await self.save_variable('exit_price', exit_price)
        
        # Update position to CLOSED
        await self._close_position(fill_data)
        
        # Mark as INACTIVE (exit complete)
        self.mark_inactive()
        await self.save_state()
        
        # Activate next nodes (if any)
        await self._activate_next_nodes()
    
    async def _close_position(self, fill_data: Dict[str, Any]):
        """Close position and calculate PNL."""
        try:
            # Get position
            position = await self._get_position()
            if not position:
                return
            
            # Calculate PNL
            entry_price = position.get('entry_price', 0)
            exit_price = fill_data.get('average_price', 0)
            quantity = position.get('quantity', 0)
            transaction_type = position.get('transaction_type', 'BUY')
            
            if transaction_type == 'BUY':
                pnl = (exit_price - entry_price) * quantity
            else:
                pnl = (entry_price - exit_price) * quantity
            
            # Update position
            position.update({
                'status': 'CLOSED',
                'exit_time': datetime.now(),
                'exit_price': exit_price,
                'pnl': pnl,
                'current_price': exit_price
            })
            
            await self.data_writer.store_position(position)
            
            logger.info(f"{self.node_id}: Position closed. PNL: {pnl}")
        
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    async def _activate_next_nodes(self):
        """Activate next nodes in the strategy."""
        # TODO: Implement node activation logic
        # This will be handled by Strategy Executor
        pass
