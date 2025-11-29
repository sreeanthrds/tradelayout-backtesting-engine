"""
Context Manager
===============

Handles context preparation for strategy execution.
Merges data from DataManager with execution context.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Manages context preparation for strategy execution.
    
    Responsibilities:
    - Prepare context for each tick
    - Merge data from DataManager
    - Handle legacy compatibility
    """
    
    def __init__(self, context_adapter: Any):
        """
        Initialize context manager.
        
        Args:
            context_adapter: ContextAdapter instance for legacy compatibility
        """
        self.context_adapter = context_adapter
        logger.info("🎯 Context Manager initialized")
    
    def prepare_context(
        self,
        tick: Dict[str, Any],
        data_context: Dict[str, Any],
        nodes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare context for strategy execution.
        
        Args:
            tick: Processed tick data
            data_context: Context from DataManager (candles, LTP, cache)
            nodes: Node instances
        
        Returns:
            Complete context for strategy execution
        """
        # Get base context from adapter (GPS, node states, etc.)
        context = self.context_adapter.get_context(
            current_tick=tick,
            current_timestamp=tick['timestamp']
        )
        
        # Merge data from DataManager
        context['candle_df_dict'] = data_context['candle_df_dict']
        context['ltp_store'] = data_context['ltp_store']
        context['cache'] = data_context['cache']
        context['node_instances'] = nodes
        
        return context
    
    def get_initial_context(self, nodes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get initial context for node state initialization.
        
        Args:
            nodes: Node instances
        
        Returns:
            Initial context
        """
        context = self.context_adapter.get_context()
        context['node_instances'] = nodes
        return context
