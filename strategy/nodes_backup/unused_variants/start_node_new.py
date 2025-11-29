"""
Start Node - Strategy Initialization
Simplified implementation following delegation pattern.
"""

from typing import Dict, Any
from src.utils.logger import log_info
from .base_node import BaseNode


class StartNode(BaseNode):
    """
    Start Node: Initialize strategy configuration.
    
    Responsibilities:
    - First tick: Store strategy config in context
    - That's it! Goes INACTIVE after first tick.
    
    Note: Square-off is handled by SquareOffNode (separate node)
    """
    
    def __init__(self, node_id: str, data: Dict[str, Any]):
        """
        Initialize Start Node.
        
        Args:
            node_id: Unique identifier ('strategy-controller')
            data: Node configuration from strategy JSON
        """
        super().__init__(node_id, 'StartNode', data.get('label', 'Start'))
        
        # Extract configuration
        tic = data.get('tradingInstrumentConfig', {}) or {}
        
        self.symbol = tic.get('symbol') or data.get('symbol')
        if not self.symbol:
            raise ValueError("❌ Symbol not found in start node configuration!")
        
        # Extract timeframes and indicators
        timeframes = tic.get('timeframes', []) or []
        self.timeframe = timeframes[0].get('timeframe') if timeframes else '5m'
        self.timeframes = timeframes  # Store all timeframes
        
        self.exchange = data.get('exchange', 'NSE')
        self.trading_instrument = data.get('tradingInstrument', {'type': 'stock'})
        self.strategy_name = data.get('strategy_name', 'Unknown Strategy')
        
        # Children will be set by graph builder (via add_child or direct assignment)
        # BaseNode initializes self.children = [] in its __init__
        
        # Flag
        self._initialized = False
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Override execute to add strategy termination check before processing.
        
        Args:
            context: Execution context
            
        Returns:
            Execution result
        """
        # CRITICAL CHECK: Before any execution, check if strategy should terminate
        # If no nodes are Active or Pending (except StartNode itself), end strategy
        if self._initialized and self._should_terminate_strategy(context):
            log_info("🏁 Start Node: No Active/Pending nodes - Terminating strategy")
            context['strategy_terminated'] = True
            return {
                'node_id': self.id,
                'executed': False,
                'strategy_terminated': True,
                'reason': 'No Active or Pending nodes in strategy'
            }
        
        # Continue with normal execution
        return super().execute(context)
    
    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute start node logic.
        
        First tick: Store strategy config, then goes INACTIVE
        
        Args:
            context: Execution context
            
        Returns:
            {'logic_completed': True} - Completes on first tick
        """
        # First tick only: Initialize
        if not self._initialized:
            log_info(f"🚀 Start Node: Initializing strategy {self.strategy_name}")
            
            # Store strategy config in context
            context['strategy_config'] = {
                'symbol': self.symbol,
                'timeframe': self.timeframe,
                'timeframes': self.timeframes,
                'exchange': self.exchange,
                'trading_instrument': self.trading_instrument,
                'strategy_name': self.strategy_name
            }
            
            # Store strategy ID for position/order tracking
            context['strategy_id'] = context.get('strategy_id', self.id)
            
            self._initialized = True
            log_info(f"✅ Start Node: Strategy initialized")
        
        # Complete (go INACTIVE, children become ACTIVE)
        return {'logic_completed': True}
    
    def _should_terminate_strategy(self, context: Dict[str, Any]) -> bool:
        """
        Check if strategy should terminate.
        Returns True if no nodes are Active or Pending.
        
        Args:
            context: Execution context
            
        Returns:
            True if strategy should terminate, False otherwise
        """
        node_states = context.get('node_states', {})
        
        # Count Active and Pending nodes
        active_count = 0
        pending_count = 0
        
        for node_id, state in node_states.items():
            status = state.get('status', 'Inactive')
            if status == 'Active':
                active_count += 1
            elif status == 'Pending':
                pending_count += 1
        
        # Strategy should terminate if no nodes are Active or Pending
        return active_count == 0 and pending_count == 0
    
    def get_strategy_config(self) -> Dict[str, Any]:
        """Get the strategy configuration."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'timeframes': self.timeframes,
            'exchange': self.exchange,
            'trading_instrument': self.trading_instrument,
            'strategy_name': self.strategy_name
        }
