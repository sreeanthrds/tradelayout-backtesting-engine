"""
OrderPlacer Interface

This interface defines how to place orders with brokers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class OrderPlacerInterface(ABC):
    """Interface for placing orders with brokers."""
    
    @abstractmethod
    async def place_order(
        self,
        user_id: str,
        symbol: str,
        exchange: str,
        transaction_type: str,  # 'BUY' or 'SELL'
        quantity: int,
        order_type: str = 'MARKET',  # 'MARKET', 'LIMIT', 'SL', 'SL-M'
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product_type: str = 'INTRADAY'  # 'INTRADAY', 'DELIVERY', 'CARRYFORWARD'
    ) -> Dict[str, Any]:
        """
        Place an order.
        
        Args:
            user_id: User ID
            symbol: Trading symbol
            exchange: Exchange (NSE, NFO, BSE, etc.)
            transaction_type: 'BUY' or 'SELL'
            quantity: Order quantity
            order_type: Order type
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for SL orders)
            product_type: Product type
        
        Returns:
            Order response:
            {
                'order_id': 'ORD123',
                'status': 'COMPLETE',  # 'PENDING', 'COMPLETE', 'REJECTED'
                'filled_quantity': 75,
                'average_price': 150.0,
                'broker_order_id': 'BROKER_ORD_456',
                'message': 'Order placed successfully'
            }
        """
        pass
    
    @abstractmethod
    async def cancel_order(
        self,
        user_id: str,
        order_id: str
    ) -> Dict[str, Any]:
        """Cancel an order."""
        pass
    
    @abstractmethod
    async def modify_order(
        self,
        user_id: str,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Modify an order."""
        pass
    
    @abstractmethod
    async def get_order_status(
        self,
        user_id: str,
        order_id: str
    ) -> Dict[str, Any]:
        """Get order status."""
        pass
