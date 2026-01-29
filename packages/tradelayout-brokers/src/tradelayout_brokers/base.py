"""Base broker adapter interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional


class OrderStatus(Enum):
    """Order status enum."""
    PENDING = "pending"
    OPEN = "open"
    COMPLETE = "complete"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class Tick:
    """Tick data structure."""
    symbol: str
    price: float
    volume: float
    timestamp: datetime
    exchange: str = "NSE"


@dataclass
class Order:
    """Order data structure."""
    symbol: str
    side: str  # BUY or SELL
    quantity: int
    order_type: str  # MARKET or LIMIT
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    order_id: Optional[str] = None
    filled_price: Optional[float] = None
    filled_quantity: int = 0
    timestamp: Optional[datetime] = None


class BrokerAdapter(ABC):
    """
    Unified broker adapter interface.
    
    All brokers (live and backtest) must implement this interface.
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to broker."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from broker."""
        pass
    
    @abstractmethod
    async def subscribe(self, symbols: List[str]) -> None:
        """Subscribe to symbols for tick data."""
        pass
    
    @abstractmethod
    def on_tick(self, callback: Callable[[Tick], None]) -> None:
        """Register callback for tick data."""
        pass
    
    @abstractmethod
    async def place_order(self, order: Order) -> Order:
        """Place an order and return updated order with status."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[dict]:
        """Get current positions."""
        pass
    
    @abstractmethod
    async def get_orders(self) -> List[Order]:
        """Get all orders."""
        pass
