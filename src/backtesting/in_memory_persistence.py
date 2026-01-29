"""
In-Memory Persistence - Backtesting Implementation

Stores orders and positions in-memory during backtest.
Returns consolidated results as JSON at end.
NO database writes.
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class InMemoryPersistence:
    """
    In-memory persistence for backtesting.
    
    Stores all orders and positions in Python lists.
    Returns consolidated results as JSON at end of backtest.
    Zero database writes.
    """
    
    def __init__(self):
        """Initialize in-memory persistence."""
        self.orders: List[Dict] = []
        self.positions: List[Dict] = []
        self.trades: List[Dict] = []
        
        logger.info("💾 In-Memory Persistence initialized (no DB writes)")
    
    def save_order(self, order: Dict) -> bool:
        """
        Save order in-memory.
        
        Args:
            order: Order dictionary
        
        Returns:
            True if successful
        """
        try:
            # Add timestamp if not present
            if 'created_at' not in order:
                order['created_at'] = datetime.now()
            
            self.orders.append(order.copy())
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving order: {e}")
            return False
    
    def update_order(self, order_id: str, updates: Dict) -> bool:
        """
        Update order in-memory.
        
        Args:
            order_id: Order ID
            updates: Updates dictionary
        
        Returns:
            True if successful
        """
        try:
            for order in self.orders:
                if order.get('order_id') == order_id:
                    order.update(updates)
                    order['updated_at'] = datetime.now()
                    return True
            
            logger.warning(f"⚠️  Order {order_id} not found")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error updating order: {e}")
            return False
    
    def save_position(self, position: Dict) -> bool:
        """
        Save position in-memory.
        
        Args:
            position: Position dictionary
        
        Returns:
            True if successful
        """
        try:
            # Add timestamp if not present
            if 'created_at' not in position:
                position['created_at'] = datetime.now()
            
            self.positions.append(position.copy())
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving position: {e}")
            return False
    
    def update_position(self, position_id: str, updates: Dict) -> bool:
        """
        Update position in-memory.
        
        Args:
            position_id: Position ID
            updates: Updates dictionary
        
        Returns:
            True if successful
        """
        try:
            for position in self.positions:
                if position.get('position_id') == position_id:
                    position.update(updates)
                    position['updated_at'] = datetime.now()
                    
                    # If position closed, create trade record
                    if updates.get('status') == 'CLOSED' and position.get('exit_price'):
                        self._create_trade_from_position(position)
                    
                    return True
            
            logger.warning(f"⚠️  Position {position_id} not found")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error updating position: {e}")
            return False
    
    def _create_trade_from_position(self, position: Dict):
        """Create trade record from closed position."""
        try:
            trade = {
                'trade_id': f"trade_{len(self.trades) + 1}",
                'position_id': position.get('position_id'),
                'symbol': position.get('symbol'),
                'quantity': position.get('quantity'),
                'entry_price': position.get('entry_price'),
                'exit_price': position.get('exit_price'),
                'entry_time': position.get('entry_time'),
                'exit_time': position.get('exit_time'),
                'pnl': position.get('pnl', 0),
                'pnl_percentage': position.get('pnl_percentage', 0),
                'duration': None  # Calculate if needed
            }
            
            # Calculate duration
            if trade['entry_time'] and trade['exit_time']:
                if isinstance(trade['entry_time'], str):
                    entry = datetime.fromisoformat(trade['entry_time'])
                    exit = datetime.fromisoformat(trade['exit_time'])
                else:
                    entry = trade['entry_time']
                    exit = trade['exit_time']
                
                trade['duration'] = (exit - entry).total_seconds()
            
            self.trades.append(trade)
            
        except Exception as e:
            logger.error(f"❌ Error creating trade: {e}")
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
        
        Returns:
            Order dictionary or None
        """
        for order in self.orders:
            if order.get('order_id') == order_id:
                return order.copy()
        return None
    
    def get_position(self, position_id: str) -> Optional[Dict]:
        """
        Get position by ID.
        
        Args:
            position_id: Position ID
        
        Returns:
            Position dictionary or None
        """
        for position in self.positions:
            if position.get('position_id') == position_id:
                return position.copy()
        return None
    
    def get_all_orders(self) -> List[Dict]:
        """Get all orders."""
        return [order.copy() for order in self.orders]
    
    def get_all_positions(self) -> List[Dict]:
        """Get all positions."""
        return [position.copy() for position in self.positions]
    
    def get_results(self) -> Dict:
        """
        Get consolidated backtest results as JSON.
        
        Returns:
            Dictionary with all backtest results
        """
        try:
            # Calculate metrics
            total_trades = len(self.trades)
            winning_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
            losing_trades = [t for t in self.trades if t.get('pnl', 0) < 0]
            
            total_pnl = sum(t.get('pnl', 0) for t in self.trades)
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
            
            avg_win = sum(t.get('pnl', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(t.get('pnl', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0
            
            # Calculate max drawdown
            equity_curve = self._calculate_equity_curve()
            max_drawdown = self._calculate_max_drawdown(equity_curve)
            
            results = {
                'summary': {
                    'total_trades': total_trades,
                    'winning_trades': len(winning_trades),
                    'losing_trades': len(losing_trades),
                    'win_rate': round(win_rate * 100, 2),
                    'total_pnl': round(total_pnl, 2),
                    'avg_win': round(avg_win, 2),
                    'avg_loss': round(avg_loss, 2),
                    'profit_factor': round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0,
                    'max_drawdown': round(max_drawdown, 2)
                },
                'orders': self.orders,
                'positions': self.positions,
                'trades': self.trades,
                'equity_curve': equity_curve
            }
            
            logger.info(f"📊 Backtest Results: {total_trades} trades, ₹{total_pnl:.2f} P&L, {win_rate*100:.1f}% win rate")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error generating results: {e}")
            return {
                'summary': {},
                'orders': self.orders,
                'positions': self.positions,
                'trades': self.trades,
                'equity_curve': []
            }
    
    def _calculate_equity_curve(self) -> List[Dict]:
        """Calculate equity curve over time."""
        try:
            equity_curve = []
            cumulative_pnl = 0
            
            # Sort trades by exit time
            sorted_trades = sorted(
                [t for t in self.trades if t.get('exit_time')],
                key=lambda x: x['exit_time']
            )
            
            for trade in sorted_trades:
                cumulative_pnl += trade.get('pnl', 0)
                equity_curve.append({
                    'timestamp': trade['exit_time'],
                    'pnl': cumulative_pnl,
                    'trade_id': trade.get('trade_id')
                })
            
            return equity_curve
            
        except Exception as e:
            logger.error(f"❌ Error calculating equity curve: {e}")
            return []
    
    def _calculate_max_drawdown(self, equity_curve: List[Dict]) -> float:
        """Calculate maximum drawdown from equity curve."""
        try:
            if not equity_curve:
                return 0.0
            
            peak = equity_curve[0]['pnl']
            max_dd = 0.0
            
            for point in equity_curve:
                pnl = point['pnl']
                if pnl > peak:
                    peak = pnl
                drawdown = peak - pnl
                if drawdown > max_dd:
                    max_dd = drawdown
            
            return max_dd
            
        except Exception as e:
            logger.error(f"❌ Error calculating max drawdown: {e}")
            return 0.0
    
    def clear(self):
        """Clear all data."""
        self.orders.clear()
        self.positions.clear()
        self.trades.clear()
        logger.info("🧹 Persistence cleared")
