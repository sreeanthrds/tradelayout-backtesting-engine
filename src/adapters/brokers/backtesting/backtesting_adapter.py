"""
Backtesting Broker Adapter

Simulates broker functionality for backtesting.
- Simulated order placement
- Simulated order fills based on tick data
- Position tracking
- P&L calculation
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from .symbol_mapper import BacktestingSymbolMapper
from src.utils.logger import log_info, log_debug, log_warning, log_error


class BacktestingBrokerAdapter:
    """
    Backtesting broker adapter - simulates broker functionality.
    
    Features:
    - Instant order fills at market price
    - Position tracking
    - P&L calculation
    - No real broker connection
    """
    
    def __init__(self, initial_capital: float = 1000000.0):
        """
        Initialize backtesting adapter.
        
        Args:
            initial_capital: Starting capital for backtesting
        """
        self.broker_name = "BACKTESTING"
        self.is_connected = False
        self.initial_capital = initial_capital
        self.available_capital = initial_capital
        
        # Simulated state
        self.orders: Dict[str, Dict] = {}  # order_id -> order
        self.positions: Dict[str, Dict] = {}  # symbol -> position
        self.trades: List[Dict] = []
        
        # Current market data (from ticks)
        self.current_prices: Dict[str, float] = {}  # symbol -> ltp
        
        # Symbol mapper
        self.symbol_mapper = BacktestingSymbolMapper()
        
        # Statistics
        self.total_orders = 0
        self.filled_orders = 0
        self.rejected_orders = 0
        
        log_info(f"🎯 Backtesting Broker initialized with capital: ₹{initial_capital:,.2f}")
    
    def connect(self) -> bool:
        """Connect to broker (simulated)."""
        self.is_connected = True
        log_info("✅ Backtesting Broker connected (simulated)")
        return True
    
    def disconnect(self) -> bool:
        """Disconnect from broker (simulated)."""
        self.is_connected = False
        log_info("🔌 Backtesting Broker disconnected")
        return True
    
    def place_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str = 'MARKET',
        price: float = 0.0,
        product_type: str = 'INTRADAY',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Place simulated order.
        
        Args:
            symbol: Trading symbol (universal format)
            exchange: Exchange (NSE/NFO)
            transaction_type: BUY/SELL
            quantity: Order quantity
            order_type: MARKET/LIMIT
            price: Limit price
            product_type: INTRADAY/DELIVERY
            
        Returns:
            Order response
        """
        self.total_orders += 1
        
        # Convert to ClickHouse format
        ch_symbol = self.symbol_mapper.universal_to_backtesting(symbol)
        
        # Generate order ID
        order_id = f"BT{self.total_orders:06d}"
        
        # Get current price
        current_price = self.current_prices.get(ch_symbol, 0.0)
        
        if current_price == 0.0:
            # No price data available
            self.rejected_orders += 1
            log_warning(f"⚠️  Order rejected: No price data for {ch_symbol}")
            return {
                'success': False,
                'order_id': order_id,
                'message': f'No price data for {ch_symbol}',
                'status': 'REJECTED'
            }
        
        # Calculate order value
        fill_price = current_price if order_type == 'MARKET' else price
        order_value = fill_price * quantity
        
        # Check capital availability (for BUY orders)
        if transaction_type.upper() == 'BUY':
            if order_value > self.available_capital:
                self.rejected_orders += 1
                log_warning(f"⚠️  Order rejected: Insufficient capital. Required: ₹{order_value:,.2f}, Available: ₹{self.available_capital:,.2f}")
                return {
                    'success': False,
                    'order_id': order_id,
                    'message': 'Insufficient capital',
                    'status': 'REJECTED'
                }
        
        # Create order
        order = {
            'order_id': order_id,
            'symbol': symbol,  # Universal format
            'ch_symbol': ch_symbol,  # ClickHouse format
            'exchange': exchange,
            'transaction_type': transaction_type.upper(),
            'quantity': quantity,
            'order_type': order_type.upper(),
            'price': price,
            'product_type': product_type.upper(),
            'status': 'PENDING',
            'filled_quantity': 0,
            'average_price': 0.0,
            'order_timestamp': datetime.now(),
            'fill_timestamp': None
        }
        
        self.orders[order_id] = order
        
        # Instant fill for MARKET orders (simulated)
        if order_type.upper() == 'MARKET':
            self._fill_order(order_id, fill_price, quantity)
        
        log_info(f"📝 Order placed: {order_id} | {transaction_type} {quantity} {ch_symbol} @ {fill_price:.2f}")
        
        return {
            'success': True,
            'order_id': order_id,
            'broker_order_id': order_id,
            'message': 'Order placed successfully',
            'status': order['status']
        }
    
    def _fill_order(self, order_id: str, fill_price: float, quantity: int):
        """
        Fill order (simulated).
        
        Args:
            order_id: Order ID
            fill_price: Fill price
            quantity: Fill quantity
        """
        order = self.orders.get(order_id)
        if not order:
            return
        
        # Update order
        order['status'] = 'COMPLETE'
        order['filled_quantity'] = quantity
        order['average_price'] = fill_price
        order['fill_timestamp'] = datetime.now()
        
        self.filled_orders += 1
        
        # Update position
        self._update_position(
            symbol=order['ch_symbol'],
            transaction_type=order['transaction_type'],
            quantity=quantity,
            price=fill_price
        )
        
        # Update capital
        order_value = fill_price * quantity
        if order['transaction_type'] == 'BUY':
            self.available_capital -= order_value
        else:  # SELL
            self.available_capital += order_value
        
        # Record trade
        trade = {
            'trade_id': f"T{len(self.trades) + 1:06d}",
            'order_id': order_id,
            'symbol': order['ch_symbol'],
            'transaction_type': order['transaction_type'],
            'quantity': quantity,
            'price': fill_price,
            'value': order_value,
            'timestamp': order['fill_timestamp']
        }
        self.trades.append(trade)
        
        log_info(f"✅ Order filled: {order_id} | {quantity} @ {fill_price:.2f} | Capital: ₹{self.available_capital:,.2f}")
    
    def _update_position(self, symbol: str, transaction_type: str, quantity: int, price: float):
        """
        Update position.
        
        Args:
            symbol: Symbol (ClickHouse format)
            transaction_type: BUY/SELL
            quantity: Quantity
            price: Price
        """
        if symbol not in self.positions:
            self.positions[symbol] = {
                'symbol': symbol,
                'quantity': 0,
                'average_price': 0.0,
                'invested_value': 0.0
            }
        
        position = self.positions[symbol]
        
        if transaction_type == 'BUY':
            # Add to position
            total_value = (position['quantity'] * position['average_price']) + (quantity * price)
            position['quantity'] += quantity
            position['average_price'] = total_value / position['quantity'] if position['quantity'] > 0 else 0.0
            position['invested_value'] = total_value
        else:  # SELL
            # Reduce position
            position['quantity'] -= quantity
            if position['quantity'] <= 0:
                # Position closed
                del self.positions[symbol]
            else:
                position['invested_value'] = position['quantity'] * position['average_price']
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get order status.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order status
        """
        order = self.orders.get(order_id)
        
        if not order:
            return {
                'success': False,
                'message': 'Order not found'
            }
        
        return {
            'success': True,
            'order_id': order_id,
            'status': order['status'],
            'filled_quantity': order['filled_quantity'],
            'average_price': order['average_price']
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all positions.
        
        Returns:
            List of positions
        """
        positions_list = []
        
        for symbol, position in self.positions.items():
            current_price = self.current_prices.get(symbol, position['average_price'])
            current_value = position['quantity'] * current_price
            pnl = current_value - position['invested_value']
            pnl_percent = (pnl / position['invested_value'] * 100) if position['invested_value'] > 0 else 0.0
            
            positions_list.append({
                'symbol': position['symbol'],
                'quantity': position['quantity'],
                'average_price': position['average_price'],
                'current_price': current_price,
                'invested_value': position['invested_value'],
                'current_value': current_value,
                'pnl': pnl,
                'pnl_percent': pnl_percent
            })
        
        return positions_list
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings (same as positions for backtesting)."""
        return self.get_positions()
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel order (simulated).
        
        Args:
            order_id: Order ID
            
        Returns:
            Cancel response
        """
        order = self.orders.get(order_id)
        
        if not order:
            return {
                'success': False,
                'message': 'Order not found'
            }
        
        if order['status'] == 'COMPLETE':
            return {
                'success': False,
                'message': 'Order already filled'
            }
        
        order['status'] = 'CANCELLED'
        
        return {
            'success': True,
            'message': 'Order cancelled'
        }
    
    def update_market_price(self, symbol: str, price: float):
        """
        Update current market price (called by tick processor).
        
        Args:
            symbol: Symbol (ClickHouse format)
            price: Current price
        """
        self.current_prices[symbol] = price
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get backtesting statistics.
        
        Returns:
            Statistics dictionary
        """
        total_pnl = sum(
            (self.current_prices.get(pos['symbol'], pos['average_price']) * pos['quantity']) - pos['invested_value']
            for pos in self.positions.values()
        )
        
        return {
            'initial_capital': self.initial_capital,
            'available_capital': self.available_capital,
            'invested_capital': self.initial_capital - self.available_capital,
            'current_portfolio_value': self.available_capital + sum(
                self.current_prices.get(pos['symbol'], pos['average_price']) * pos['quantity']
                for pos in self.positions.values()
            ),
            'total_pnl': total_pnl,
            'total_pnl_percent': (total_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0.0,
            'total_orders': self.total_orders,
            'filled_orders': self.filled_orders,
            'rejected_orders': self.rejected_orders,
            'open_positions': len(self.positions),
            'total_trades': len(self.trades)
        }
    
    def get_trades(self) -> List[Dict[str, Any]]:
        """Get all trades."""
        return self.trades.copy()
    
    def reset(self):
        """Reset backtesting state."""
        self.available_capital = self.initial_capital
        self.orders.clear()
        self.positions.clear()
        self.trades.clear()
        self.current_prices.clear()
        self.total_orders = 0
        self.filled_orders = 0
        self.rejected_orders = 0
        
        log_info("🔄 Backtesting state reset")
