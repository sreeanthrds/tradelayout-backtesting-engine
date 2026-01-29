"""
Entry Node - Handles trade entries

Places orders and creates positions.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import uuid

from .base_node import BaseNode, NodeStatus
from interfaces.order_placer import OrderPlacerInterface


logger = logging.getLogger(__name__)


class EntryNode(BaseNode):
    """
    Entry node for placing entry orders.
    
    Features:
    - Condition evaluation
    - Order placement
    - Position creation
    - F&O resolution support
    - Three-state model (ACTIVE → PENDING → INACTIVE)
    """
    
    def __init__(self, order_placer: OrderPlacerInterface, **kwargs):
        """Initialize entry node."""
        super().__init__(**kwargs)
        self.order_placer = order_placer
        
        # Entry configuration
        self.entry_condition = self.config.get('entry_condition', '')
        self.instrument = self.config.get('instrument', '')
        self.transaction_type = self.config.get('transaction_type', 'BUY')
        self.quantity = self.config.get('quantity', 1)
        self.order_type = self.config.get('order_type', 'MARKET')
        self.exchange = self.config.get('exchange', 'NSE')
        
        # Position tracking
        self.position_id: Optional[str] = None
        self.order_id: Optional[str] = None
    
    async def _execute_logic(self, tick_data: Dict[str, Any]) -> Optional[List[str]]:
        """Execute entry node logic."""
        
        # Check if already visited (single entry)
        if self.visited:
            logger.debug(f"{self.node_id}: Already visited, skipping")
            return None
        
        # Evaluate entry condition
        try:
            condition_result = await self.evaluate_condition(self.entry_condition)
            if not condition_result:
                # Only log every 1000th tick to avoid spam
                if hasattr(self, '_tick_count'):
                    self._tick_count += 1
                else:
                    self._tick_count = 1
                
                if self._tick_count % 1000 == 0:
                    logger.info(f"{self.node_id}: Entry condition not met (checked {self._tick_count} times)")
                return None
        except Exception as e:
            logger.error(f"{self.node_id}: Error evaluating condition: {e}")
            return None
        
        # Condition met - place order
        logger.info(f"{self.node_id}: Entry condition met! Placing order...")
        
        # Mark as visited
        self.visited = True
        await self.save_state()
        
        # Resolve instrument (handle F&O)
        trading_symbol = await self._resolve_instrument()
        if not trading_symbol:
            logger.error(f"{self.node_id}: Failed to resolve instrument")
            return None
        
        # Determine exchange (NFO for options/futures)
        trading_exchange = self._determine_exchange(trading_symbol)
        
        # Place order
        order_result = await self._place_order(trading_symbol, trading_exchange)
        
        if not order_result or not order_result.get('success'):
            logger.error(f"{self.node_id}: Order placement failed")
            return None
        
        # Mark as PENDING (waiting for order fill)
        self.mark_pending()
        await self.save_state()
        
        # Store order ID
        self.order_id = order_result.get('order_id')
        
        # Register callback for order fill
        await self._register_order_callback()
        
        return None  # Don't activate next nodes yet
    
    async def _resolve_instrument(self) -> Optional[str]:
        """
        Resolve instrument to trading symbol.
        
        Handles:
        - Simple symbols: NIFTY → NIFTY
        - F&O: NIFTY:W0:ATM:CE → NIFTY28NOV2525900CE
        """
        instrument = self.instrument
        
        # Simple symbol (no F&O)
        if ':' not in instrument:
            return instrument
        
        # F&O symbol - needs resolution
        # Format: NIFTY:W0:ATM:CE
        try:
            # TODO: Implement F&O resolver integration
            # For now, return as-is
            logger.warning(f"F&O resolution not yet implemented: {instrument}")
            return instrument
        except Exception as e:
            logger.error(f"Error resolving instrument {instrument}: {e}")
            return None
    
    def _determine_exchange(self, symbol: str) -> str:
        """Determine exchange based on symbol."""
        # Options and futures go to NFO
        if ':OPT:' in symbol or ':FUT:' in symbol:
            return 'NFO'
        
        # Otherwise use configured exchange
        return self.exchange
    
    async def _place_order(self, symbol: str, exchange: str) -> Optional[Dict[str, Any]]:
        """Place entry order."""
        try:
            # Generate position ID
            self.position_id = f"pos-{uuid.uuid4().hex[:8]}"
            
            # Place order via OrderPlacer
            result = await self.order_placer.place_order(
                user_id=self.user_id,
                strategy_id=self.strategy_id,
                symbol=symbol,
                exchange=exchange,
                transaction_type=self.transaction_type,
                order_type=self.order_type,
                quantity=self.quantity,
                position_id=self.position_id
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    async def _register_order_callback(self):
        """Register callback for order fill notification."""
        # TODO: Implement order callback registration
        # For now, simulate immediate fill (for testing)
        await self._on_order_filled({
            'order_id': self.order_id,
            'position_id': self.position_id,
            'filled_quantity': self.quantity,
            'average_price': 100.0  # Placeholder
        })
    
    async def _on_order_filled(self, fill_data: Dict[str, Any]):
        """Callback when order is filled."""
        logger.info(f"{self.node_id}: Order filled! {fill_data}")
        
        # Save entry price as node variable
        entry_price = fill_data.get('average_price', 0)
        await self.save_variable('entry_price', entry_price)
        
        # Create position record
        await self._create_position(fill_data)
        
        # Mark as INACTIVE (entry complete)
        self.mark_inactive()
        await self.save_state()
        
        # Activate next nodes
        await self._activate_next_nodes()
    
    async def _create_position(self, fill_data: Dict[str, Any]):
        """Create position record."""
        try:
            position = {
                'position_id': self.position_id,
                'user_id': self.user_id,
                'strategy_id': self.strategy_id,
                'symbol': fill_data.get('symbol', self.instrument),
                'exchange': fill_data.get('exchange', self.exchange),
                'transaction_type': self.transaction_type,
                'quantity': fill_data.get('filled_quantity', self.quantity),
                'entry_price': fill_data.get('average_price', 0),
                'current_price': fill_data.get('average_price', 0),
                'pnl': 0,
                'status': 'OPEN',
                'entry_time': datetime.now()
            }
            
            await self.data_writer.store_position(position)
            logger.info(f"{self.node_id}: Position created: {self.position_id}")
        
        except Exception as e:
            logger.error(f"Error creating position: {e}")
    
    async def _activate_next_nodes(self):
        """Activate next nodes in the strategy."""
        # TODO: Implement node activation logic
        # This will be handled by Strategy Executor
        pass
