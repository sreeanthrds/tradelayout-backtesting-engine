"""
Persistence Interface

Defines the contract for persisting orders and positions.
Implementations:
- Live Trading: SupabaseRealtimeWriter (writes to Supabase immediately)
- Backtesting: InMemoryWriter (stores in-memory, returns JSON at end)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class PersistenceInterface(ABC):
    """Interface for persisting orders and positions."""
    
    @abstractmethod
    def save_order(self, order: Dict) -> bool:
        """
        Save a new order.
        
        Args:
            order: Order data with keys:
                - order_id: str
                - symbol: str
                - transaction_type: str (BUY/SELL)
                - order_type: str (MARKET/LIMIT)
                - quantity: int
                - price: float (optional)
                - status: str (PENDING/FILLED/REJECTED)
                - timestamp: datetime
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def update_order(self, order_id: str, updates: Dict) -> bool:
        """
        Update an existing order.
        
        Args:
            order_id: Order ID
            updates: Dictionary of fields to update
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def save_position(self, position: Dict) -> bool:
        """
        Save a new position.
        
        Args:
            position: Position data with keys:
                - position_id: str
                - symbol: str
                - quantity: int
                - entry_price: float
                - current_price: float
                - pnl: float
                - status: str (OPEN/CLOSED)
                - entry_time: datetime
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def update_position(self, position_id: str, updates: Dict) -> bool:
        """
        Update an existing position.
        
        Args:
            position_id: Position ID
            updates: Dictionary of fields to update
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Dict]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
        
        Returns:
            Order dictionary or None
        """
        pass
    
    @abstractmethod
    def get_position(self, position_id: str) -> Optional[Dict]:
        """
        Get position by ID.
        
        Args:
            position_id: Position ID
        
        Returns:
            Position dictionary or None
        """
        pass
    
    @abstractmethod
    def get_all_orders(self) -> List[Dict]:
        """
        Get all orders.
        
        Returns:
            List of order dictionaries
        """
        pass
    
    @abstractmethod
    def get_all_positions(self) -> List[Dict]:
        """
        Get all positions.
        
        Returns:
            List of position dictionaries
        """
        pass
