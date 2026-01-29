"""
Context Adapter

Bridges the new backtesting architecture with the node expectations from full_trading_engine.
Converts our DataFrameWriter, DictCache, and LTP store into the format nodes expect.
"""

from typing import Dict, Any, Optional
import logging
from src.core.gps import GlobalPositionStore
from src.utils.node_diagnostics import NodeDiagnostics

logger = logging.getLogger(__name__)


class ContextAdapter:
    """
    Adapts backtesting components to provide context in the format nodes expect.
    
    Converts:
    - DataFrameWriter → candle_df_dict
    - InstrumentLTPStore → last_tick_by_role
    - InMemoryPersistence → position_manager interface
    """
    
    def __init__(
        self,
        data_writer,
        cache,
        ltp_store,
        persistence,
        candle_builders=None
    ):
        """
        Initialize context adapter.
        
        Args:
            data_writer: DataFrameWriter instance
            cache: DictCache instance
            ltp_store: InstrumentLTPStore instance
            persistence: InMemoryPersistence instance
            candle_builders: Dict of candle builders {timeframe: builder}
        
        Note:
            strategy_config is NOT stored here - each strategy creates its own
            via StartNode.execute() dynamically at runtime.
        """
        self.data_writer = data_writer
        self.cache = cache
        self.ltp_store = ltp_store
        self.persistence = persistence
        self.candle_builders = candle_builders or {}
        
        # Initialize GPS
        self.gps = GlobalPositionStore()
        
        # ClickHouse client (will be set externally for F&O resolution)
        self.clickhouse_client = None
        
        # Persistent node state across ticks
        self.node_variables = {}
        self.node_order_status = {}
        self.node_states = {}  # Note: plural!
        self.node_instances = {}  # Will be set by orchestrator
        
        # Initialize diagnostics system
        self.diagnostics = NodeDiagnostics(max_events_per_node=100)
        self.node_events_history = {}  # Will be populated by diagnostics
        self.node_current_state = {}   # Will be populated by diagnostics
        
        logger.info("📦 Context Adapter initialized")
    
    def get_context(
        self,
        current_tick: Optional[Dict] = None,
        current_timestamp: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Get context in the format nodes expect.
        
        Args:
            current_tick: Current tick data
            current_timestamp: Current timestamp
        
        Returns:
            Context dictionary
        """
        context = {
            # Mode
            'mode': 'backtesting',
            
            # Candle DataFrames (unified key)
            'candle_df_dict': self._get_candle_df_dict(),
            
            # GPS and LTP store
            'gps': self.gps,
            'ltp_store': self.ltp_store,
            'clickhouse_client': self.clickhouse_client,  # For F&O resolution in backtesting
            
            # Context manager (self) - provides GPS access methods for nodes
            'context_manager': self,
            
            # Note: strategy_config is created by StartNode.execute() at runtime
            # and injected into each strategy's context individually
            
            # Node variables (persistent across ticks)
            'node_variables': self.node_variables,
            'node_order_status': self.node_order_status,
            'node_states': self.node_states,  # Note: plural!
            'node_instances': self.node_instances,  # For child activation
            
            # Position manager (adapter for InMemoryPersistence)
            'position_manager': self._get_position_manager_adapter(),
            
            # Current tick and timestamp
            'current_tick': current_tick,
            'current_timestamp': current_timestamp,
            
            # Diagnostics system
            'diagnostics': self.diagnostics,
            'node_events_history': self.node_events_history,
            'node_current_state': self.node_current_state,
        }
        
        return context
    
    def _get_candle_df_dict(self) -> Dict[str, Any]:
        """
        Get candle DataFrames in the format nodes expect.
        
        IMPORTANT: Includes BOTH completed candles AND the current candle being built.
        - offset 0 = current candle (being built)
        - offset -1 = previous completed candle
        - offset -2 = two candles ago, etc.
        
        Format: {'{timeframe}_{instrumentType}': DataFrame}
        Example: {'1m_TI': DataFrame, '5m_TI': DataFrame}
        
        Returns:
            Dictionary of DataFrames with completed + current candles
        """
        import pandas as pd
        candle_df_dict = {}
        
        # Convert DataFrameWriter.dataframes to expected format
        for key, df in self.data_writer.dataframes.items():
            # key format: 'SYMBOL:TIMEFRAME' (e.g., 'NIFTY:1m')
            # nodes expect: 'TIMEFRAME_INSTRUMENTTYPE' (e.g., '1m_TI')
            
            if ':' in key:
                symbol, timeframe = key.split(':', 1)
                
                # Determine instrument type (TI for underlying, SI for strategy instrument)
                # For now, assume TI (Trading Instrument = underlying)
                instrument_type = 'TI'
                
                # Create key in expected format
                node_key = f"{timeframe}_{instrument_type}"
                
                # Start with completed candles
                df_with_current = df.copy()
                
                # Add current candle being built (if exists)
                if timeframe in self.candle_builders:
                    builder = self.candle_builders[timeframe]
                    if symbol in builder.current_candles:
                        current_candle = builder.current_candles[symbol]
                        # Append current candle as the last row
                        current_df = pd.DataFrame([current_candle])
                        df_with_current = pd.concat([df_with_current, current_df], ignore_index=True)
                
                candle_df_dict[node_key] = df_with_current
        
        return candle_df_dict
    
    # NOTE: _get_last_tick_by_role method removed - no longer needed
    # Context now uses ltp_store directly with keys like 'ltp_TI', 'ltp_SI'
    # This eliminates redundant data transformation and memory usage
    
    def _get_position_manager_adapter(self):
        """
        Get position manager adapter.
        
        Returns:
            Adapter object with position manager interface
        """
        # Create a simple adapter that wraps InMemoryPersistence
        class PositionManagerAdapter:
            def __init__(self, persistence):
                self.persistence = persistence
            
            def get_all_positions(self):
                """Get all positions."""
                return self.persistence.get_all_positions()
            
            def get_position(self, position_id):
                """Get position by ID."""
                return self.persistence.get_position(position_id)
        
        return PositionManagerAdapter(self.persistence)
    
    def update_node_variables(self, context: Dict, node_id: str, variables: Dict):
        """
        Update node variables in context.
        
        Args:
            context: Context dictionary
            node_id: Node ID
            variables: Variables to update
        """
        if 'node_variables' not in context:
            context['node_variables'] = {}
        
        if node_id not in context['node_variables']:
            context['node_variables'][node_id] = {}
        
        context['node_variables'][node_id].update(variables)
    
    # ==========================================================================
    # GPS ACCESS METHODS (for nodes to use via context_manager)
    # ==========================================================================
    
    def get_gps(self):
        """Get GPS instance."""
        return self.gps
    
    def get_position(self, position_id: str):
        """Get position by ID from GPS."""
        return self.gps.get_position(position_id)
    
    def get_open_positions(self):
        """Get all open positions from GPS."""
        return self.gps.get_open_positions()
    
    def get_closed_positions(self):
        """Get all closed positions from GPS."""
        return self.gps.get_closed_positions()
    
    def close_position(self, position_id: str, exit_data: Dict[str, Any], timestamp: Any):
        """Close a position in GPS."""
        return self.gps.close_position(position_id, exit_data, timestamp)
