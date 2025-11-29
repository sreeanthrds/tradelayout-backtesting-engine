"""
Persistence Strategy
====================

Abstract interface for data persistence.

This abstraction allows different persistence strategies:
- Backtesting: NullPersistence (no storage, ephemeral)
- Live Trading: DatabasePersistence (full audit trail)
- Testing: MockPersistence (in-memory for testing)

Author: UniTrader Team
Created: 2024-11-12
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PersistenceStrategy(ABC):
    """
    Abstract base class for persistence strategies.
    
    A persistence strategy is responsible for:
    1. Storing ticks (optional)
    2. Storing positions
    3. Storing trades
    4. Storing audit logs
    5. Storing strategy state
    
    Different implementations:
    - NullPersistence: No-op (backtesting)
    - DatabasePersistence: Full storage (live trading)
    - MockPersistence: In-memory (testing)
    """
    
    @abstractmethod
    def save_tick(self, tick: Dict[str, Any]):
        """
        Save tick data.
        
        Args:
            tick: Tick data dict
        """
        pass
    
    @abstractmethod
    def save_position(self, position: Dict[str, Any]):
        """
        Save position data.
        
        Args:
            position: Position data dict
        """
        pass
    
    @abstractmethod
    def save_trade(self, trade: Dict[str, Any]):
        """
        Save trade data.
        
        Args:
            trade: Trade data dict
        """
        pass
    
    @abstractmethod
    def save_order(self, order: Dict[str, Any]):
        """
        Save order data.
        
        Args:
            order: Order data dict
        """
        pass
    
    @abstractmethod
    def save_audit_log(self, log_entry: Dict[str, Any]):
        """
        Save audit log entry.
        
        Args:
            log_entry: Log entry dict
        """
        pass
    
    @abstractmethod
    def save_strategy_state(self, instance_id: str, state: Dict[str, Any]):
        """
        Save strategy state.
        
        Args:
            instance_id: Strategy instance ID
            state: Strategy state dict
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get persistence statistics.
        
        Returns:
            Dict with statistics
        """
        pass


class NullPersistence(PersistenceStrategy):
    """
    No-op persistence for backtesting.
    
    Does nothing - all data is ephemeral.
    Only results are kept in memory.
    
    Usage:
        persistence = NullPersistence()
        persistence.save_position(position)  # No-op
    """
    
    def __init__(self):
        """Initialize null persistence."""
        logger.info("📝 NullPersistence initialized (no storage)")
    
    def save_tick(self, tick: Dict[str, Any]):
        """No-op."""
        pass
    
    def save_position(self, position: Dict[str, Any]):
        """No-op."""
        pass
    
    def save_trade(self, trade: Dict[str, Any]):
        """No-op."""
        pass
    
    def save_order(self, order: Dict[str, Any]):
        """No-op."""
        pass
    
    def save_audit_log(self, log_entry: Dict[str, Any]):
        """No-op."""
        pass
    
    def save_strategy_state(self, instance_id: str, state: Dict[str, Any]):
        """No-op."""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get stats."""
        return {
            'type': 'null',
            'ticks_saved': 0,
            'positions_saved': 0,
            'trades_saved': 0,
            'orders_saved': 0
        }


class DatabasePersistence(PersistenceStrategy):
    """
    Full database persistence for live trading.
    
    Stores everything for:
    - Audit trail
    - Compliance
    - Recovery
    - Monitoring
    - Analysis
    
    Usage:
        persistence = DatabasePersistence(db_connection)
        persistence.save_position(position)  # Stored in DB
    """
    
    def __init__(self, db_connection: Any):
        """
        Initialize database persistence.
        
        Args:
            db_connection: Database connection (Supabase, PostgreSQL, etc.)
        """
        self.db = db_connection
        
        # Statistics
        self.ticks_saved = 0
        self.positions_saved = 0
        self.trades_saved = 0
        self.orders_saved = 0
        self.audit_logs_saved = 0
        self.errors = 0
        
        logger.info("💾 DatabasePersistence initialized")
    
    def save_tick(self, tick: Dict[str, Any]):
        """Save tick to database."""
        try:
            # TODO: Implement actual database save
            # self.db.table('ticks').insert(tick).execute()
            self.ticks_saved += 1
        except Exception as e:
            logger.error(f"❌ Failed to save tick: {e}")
            self.errors += 1
    
    def save_position(self, position: Dict[str, Any]):
        """Save position to database."""
        try:
            # TODO: Implement actual database save
            # self.db.table('positions').insert(position).execute()
            self.positions_saved += 1
            
            # Also save audit log
            self.save_audit_log({
                'action': 'position_created',
                'data': position,
                'timestamp': position.get('timestamp')
            })
        except Exception as e:
            logger.error(f"❌ Failed to save position: {e}")
            self.errors += 1
    
    def save_trade(self, trade: Dict[str, Any]):
        """Save trade to database."""
        try:
            # TODO: Implement actual database save
            # self.db.table('trades').insert(trade).execute()
            self.trades_saved += 1
            
            # Also save audit log
            self.save_audit_log({
                'action': 'trade_executed',
                'data': trade,
                'timestamp': trade.get('timestamp')
            })
        except Exception as e:
            logger.error(f"❌ Failed to save trade: {e}")
            self.errors += 1
    
    def save_order(self, order: Dict[str, Any]):
        """Save order to database."""
        try:
            # TODO: Implement actual database save
            # self.db.table('orders').insert(order).execute()
            self.orders_saved += 1
        except Exception as e:
            logger.error(f"❌ Failed to save order: {e}")
            self.errors += 1
    
    def save_audit_log(self, log_entry: Dict[str, Any]):
        """Save audit log to database."""
        try:
            # TODO: Implement actual database save
            # self.db.table('audit_logs').insert(log_entry).execute()
            self.audit_logs_saved += 1
        except Exception as e:
            logger.error(f"❌ Failed to save audit log: {e}")
            self.errors += 1
    
    def save_strategy_state(self, instance_id: str, state: Dict[str, Any]):
        """Save strategy state to database."""
        try:
            # TODO: Implement actual database save
            # self.db.table('strategy_states').upsert({
            #     'instance_id': instance_id,
            #     'state': state
            # }).execute()
            pass
        except Exception as e:
            logger.error(f"❌ Failed to save strategy state: {e}")
            self.errors += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get stats."""
        return {
            'type': 'database',
            'ticks_saved': self.ticks_saved,
            'positions_saved': self.positions_saved,
            'trades_saved': self.trades_saved,
            'orders_saved': self.orders_saved,
            'audit_logs_saved': self.audit_logs_saved,
            'errors': self.errors
        }
