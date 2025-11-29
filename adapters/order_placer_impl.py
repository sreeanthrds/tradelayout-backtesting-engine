"""
Order Placer Implementation

Handles order placement, tracking, and callbacks.
"""

from typing import Dict, Any, Optional, Callable
from datetime import datetime
import logging
import uuid
import asyncio

from interfaces.order_placer import OrderPlacerInterface
from interfaces.data_writer import DataWriterInterface


logger = logging.getLogger(__name__)


class OrderPlacerImpl(OrderPlacerInterface):
    """
    Order placer implementation.
    
    Features:
    - Order placement
    - Order tracking
    - Fill callbacks
    - Broker integration
    - Error handling
    """
    
    def __init__(
        self,
        data_writer: DataWriterInterface,
        broker_adapter: Optional[Any] = None
    ):
        """
        Initialize order placer.
        
        Args:
            data_writer: DataWriter for storing orders
            broker_adapter: Optional broker adapter for live trading
        """
        self.data_writer = data_writer
        self.broker_adapter = broker_adapter
        
        # Order tracking
        self.pending_orders: Dict[str, Dict[str, Any]] = {}
        self.filled_orders: Dict[str, Dict[str, Any]] = {}
        
        # Callbacks
        self.fill_callbacks: Dict[str, Callable] = {}
    
    async def place_order(
        self,
        user_id: str,
        strategy_id: str,
        symbol: str,
        exchange: str,
        transaction_type: str,
        order_type: str,
        quantity: int,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        position_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place an order.
        
        Args:
            user_id: User ID
            strategy_id: Strategy ID
            symbol: Trading symbol
            exchange: Exchange (NSE, NFO, etc.)
            transaction_type: BUY or SELL
            order_type: MARKET, LIMIT, SL, SL-M
            quantity: Order quantity
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for SL orders)
            position_id: Associated position ID
        
        Returns:
            Order result with success, order_id, etc.
        """
        try:
            # Generate order ID
            order_id = f"ord-{uuid.uuid4().hex[:12]}"
            
            # Create order record
            order = {
                'order_id': order_id,
                'user_id': user_id,
                'strategy_id': strategy_id,
                'position_id': position_id,
                'symbol': symbol,
                'exchange': exchange,
                'transaction_type': transaction_type,
                'order_type': order_type,
                'quantity': quantity,
                'price': price,
                'trigger_price': trigger_price,
                'filled_quantity': 0,
                'average_price': None,
                'status': 'PENDING',
                'order_time': datetime.now(),
                'fill_time': None,
                'broker_order_id': None,
                'error_message': None
            }
            
            # Store order
            await self.data_writer.store_order(order)
            
            # Add to pending orders
            self.pending_orders[order_id] = order
            
            logger.info(f"Order placed: {order_id} - {transaction_type} {quantity} {symbol}")
            
            # Place order with broker (if live trading)
            if self.broker_adapter:
                broker_result = await self._place_with_broker(order)
                
                if broker_result.get('success'):
                    order['broker_order_id'] = broker_result.get('broker_order_id')
                    order['status'] = 'SUBMITTED'
                    await self.data_writer.store_order(order)
                else:
                    # Order rejected by broker
                    order['status'] = 'REJECTED'
                    order['error_message'] = broker_result.get('error')
                    await self.data_writer.store_order(order)
                    
                    return {
                        'success': False,
                        'order_id': order_id,
                        'error': broker_result.get('error')
                    }
            else:
                # Simulated fill (for testing/backtesting)
                # Schedule as background task so it doesn't block
                asyncio.create_task(self._simulate_fill(order))
            
            return {
                'success': True,
                'order_id': order_id,
                'position_id': position_id,
                'symbol': symbol,
                'exchange': exchange,
                'quantity': quantity
            }
        
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _place_with_broker(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Place order with broker adapter."""
        try:
            # Call broker adapter's place_order method
            result = await self.broker_adapter.place_order(
                symbol=order['symbol'],
                exchange=order['exchange'],
                transaction_type=order['transaction_type'],
                order_type=order['order_type'],
                quantity=order['quantity'],
                price=order.get('price'),
                trigger_price=order.get('trigger_price')
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error placing order with broker: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _simulate_fill(self, order: Dict[str, Any]):
        """Simulate order fill (for testing/backtesting)."""
        try:
            # Simulate immediate fill at market price
            # In real scenario, this would be triggered by broker callback
            
            # Wait a bit to simulate processing
            await asyncio.sleep(0.1)
            
            # Get simulated fill price
            fill_price = order.get('price', 100.0)  # Use limit price or default
            
            # Update order
            order['status'] = 'COMPLETE'
            order['filled_quantity'] = order['quantity']
            order['average_price'] = fill_price
            order['fill_time'] = datetime.now()
            
            # Store updated order
            await self.data_writer.store_order(order)
            
            # Move to filled orders
            order_id = order['order_id']
            if order_id in self.pending_orders:
                del self.pending_orders[order_id]
            self.filled_orders[order_id] = order
            
            # Trigger callback
            await self._trigger_fill_callback(order)
            
            logger.info(f"Order filled: {order_id} at {fill_price}")
        
        except Exception as e:
            logger.error(f"Error simulating fill: {e}")
    
    async def on_order_update(self, order_update: Dict[str, Any]):
        """
        Handle order update from broker.
        
        Called by broker adapter when order status changes.
        """
        try:
            broker_order_id = order_update.get('broker_order_id')
            status = order_update.get('status')
            
            # Find our order
            order_id = None
            for oid, order in self.pending_orders.items():
                if order.get('broker_order_id') == broker_order_id:
                    order_id = oid
                    break
            
            if not order_id:
                logger.warning(f"Order not found for broker_order_id: {broker_order_id}")
                return
            
            order = self.pending_orders[order_id]
            
            # Update order
            order['status'] = status
            
            if status == 'COMPLETE':
                order['filled_quantity'] = order_update.get('filled_quantity', order['quantity'])
                order['average_price'] = order_update.get('average_price')
                order['fill_time'] = datetime.now()
                
                # Move to filled orders
                del self.pending_orders[order_id]
                self.filled_orders[order_id] = order
                
                # Trigger callback
                await self._trigger_fill_callback(order)
            
            elif status == 'REJECTED':
                order['error_message'] = order_update.get('error_message')
                del self.pending_orders[order_id]
            
            # Store updated order
            await self.data_writer.store_order(order)
        
        except Exception as e:
            logger.error(f"Error handling order update: {e}")
    
    def register_fill_callback(self, order_id: str, callback: Callable):
        """Register callback for order fill."""
        self.fill_callbacks[order_id] = callback
    
    async def _trigger_fill_callback(self, order: Dict[str, Any]):
        """Trigger fill callback."""
        try:
            order_id = order['order_id']
            callback = self.fill_callbacks.get(order_id)
            
            if callback:
                # Call callback
                if asyncio.iscoroutinefunction(callback):
                    await callback(order)
                else:
                    callback(order)
                
                # Remove callback
                del self.fill_callbacks[order_id]
        
        except Exception as e:
            logger.error(f"Error triggering fill callback: {e}")
    
    async def modify_order(
        self,
        user_id: str,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Modify an order."""
        try:
            order = self.pending_orders.get(order_id)
            
            if not order:
                return {
                    'success': False,
                    'error': 'Order not found or already filled'
                }
            
            # Update order details
            if quantity is not None:
                order['quantity'] = quantity
            if price is not None:
                order['price'] = price
            if trigger_price is not None:
                order['trigger_price'] = trigger_price
            
            # Store updated order
            await self.data_writer.store_order(order)
            
            logger.info(f"Order modified: {order_id}")
            
            return {
                'success': True,
                'order_id': order_id
            }
        
        except Exception as e:
            logger.error(f"Error modifying order: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def cancel_order(self, user_id: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order."""
        try:
            order = self.pending_orders.get(order_id)
            
            if not order:
                return {
                    'success': False,
                    'error': 'Order not found or already filled'
                }
            
            # Cancel with broker if live
            if self.broker_adapter and order.get('broker_order_id'):
                result = await self.broker_adapter.cancel_order(
                    broker_order_id=order['broker_order_id']
                )
                
                if not result.get('success'):
                    return result
            
            # Update order status
            order['status'] = 'CANCELLED'
            await self.data_writer.store_order(order)
            
            # Remove from pending
            del self.pending_orders[order_id]
            
            logger.info(f"Order cancelled: {order_id}")
            
            return {
                'success': True,
                'order_id': order_id
            }
        
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_order_status(self, user_id: str, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status."""
        # Check pending orders
        if order_id in self.pending_orders:
            return self.pending_orders[order_id]
        
        # Check filled orders
        if order_id in self.filled_orders:
            return self.filled_orders[order_id]
        
        return None
    
    def get_pending_orders(self) -> Dict[str, Dict[str, Any]]:
        """Get all pending orders."""
        return self.pending_orders.copy()
    
    def get_filled_orders(self) -> Dict[str, Dict[str, Any]]:
        """Get all filled orders."""
        return self.filled_orders.copy()
