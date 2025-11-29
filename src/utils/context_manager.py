"""
Context Manager for Live Trading Engine
Manages all state and communication between components with robust scoping
Enhanced with batched multi-instrument tick updates for new architecture
"""

import uuid
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Callable

from .logger import log_info
import pandas as pd
import numpy as np

# Import GPS from the correct location
from ..core.gps import GlobalPositionStore


class ContextManager:
    """
    Centralized context manager for live trading engine.
    Manages strategy-level, day-level, and current-level contexts.
    Enhanced with batched multi-instrument tick updates.
    """

    def __init__(self, candles_updater: Optional[Callable] = None, indicators_updater: Optional[Callable] = None,
                 session_id: Optional[str] = None, user_id: Optional[str] = None, 
                 connection_id: Optional[str] = None, strategy_id: Optional[str] = None):
        # Initialize GPS (Global Position Store)
        self.gps = GlobalPositionStore()

        # Session tracking for CARRYFORWARD persistence
        self.session_id = session_id
        self.user_id = user_id
        self.connection_id = connection_id
        self.strategy_id = strategy_id
        self.strategy_type = 'INTRADAY'  # Will be set during initialization

        # Simplified main context - contains only essential data
        self.context = {
            'candle_df_dict': {},     # Market data with indicators
            'ltp_store': {},          # Latest tick data per symbol
            'current_timestamp': None, # Current time (with milliseconds)
            'node_states': {},        # Node activation/visited flags
            'node_instances': {},     # Global node instances store
            'strategy_config': None   # Strategy JSON configuration
        }

        # NEW: Multi-instrument batched updates
        self._latest_by_instrument = {}  # {instrument_key: {ltp, ltq, oi, ts}}
        self._candles_by_key = {}  # {timeframe_instrument_type: DataFrame}
        self._staged_ticks = {}  # Staged updates for current timestamp
        self._staged_ts = None
        self._candles_updater = candles_updater
        self._indicators_updater = indicators_updater
        self._lock = threading.RLock()

    def set_current_tick_time(self, tick_time: datetime):
        """Set the current tick time for GPS operations."""
        self.gps.set_current_tick_time(tick_time)

    def reset_for_new_day(self, new_date: str, tick_time: Optional[datetime] = None):
        """
        Reset context for new trading day.
        
        Args:
            new_date: Date string in format 'YYYY-MM-DD'
            tick_time: Current tick time for GPS operations
        """
        # Reset GPS for new day
        self.gps.reset_day(tick_time)

        # Reset node states for new day
        self.context['node_states'] = {}
        
        # Reset current timestamp
        self.context['current_timestamp'] = None

        # Keep other context data (candle_df_dict, ltp_store, node_instances, strategy_config)
        # as they persist across days

        # log_info(f"🔄 Reset context for new day: {new_date}")

    def reset_for_new_strategy_run(self, tick_time: Optional[datetime] = None):
        """
        Reset everything for new strategy execution.
        
        Args:
            tick_time: Current tick time for GPS operations
        """
        # Reset GPS for new strategy
        self.gps.reset_strategy(tick_time)

        # Reset all context data for new strategy
        self.context = {
            'candle_df_dict': {},
            'ltp_store': {},
            'current_timestamp': None,
            'node_states': {},
            'node_instances': {},
            'strategy_config': None
        }

        # log_info(f"🔄 Reset context for new strategy run")

    def accumulate_daily_results(self):
        """
        Accumulate daily results to GPS.
        Call this at the end of each day.
        """
        # GPS handles accumulation internally
        # This method is kept for compatibility but GPS manages totals
        pass

        # log_info(f"📊 Accumulated daily results to GPS")

    def set(self, key: str, value: Any, scope: str = 'main'):
        """
        Set a value in the main context.
        
        Args:
            key: Key to set
            value: Value to set
            scope: Context scope (only 'main' supported now)
        """
        if scope == 'main':
            self.context[key] = value
        else:
            raise ValueError(f"Invalid scope: {scope}. Only 'main' scope is supported.")

    def get(self, key: str, default: Any = None, scope: str = 'main'):
        """
        Get a value from the main context.
        
        Args:
            key: Key to get
            default: Default value if key not found
            scope: Context scope (only 'main' supported now)
            
        Returns:
            Value from context or default
        """
        if scope == 'main':
            return self.context.get(key, default)
        else:
            raise ValueError(f"Invalid scope: {scope}. Only 'main' scope is supported.")

    def log_event(self, event: dict):
        """Log an event to GPS."""
        # GPS handles event logging internally
        # This method is kept for compatibility
        pass

    def append_candle(self, candle_summary: Dict[str, Any]):
        """
        Append a completed candle to GPS.
        
        Args:
            candle_summary: Candle data to append
        """
        # GPS handles candle logging internally
        # This method is kept for compatibility
        pass

    def reset_visited_flags(self):
        """
        Reset visited flags for all nodes (called on every tick).
        """
        for node_id in self.context.get('node_states', {}):
            # if 'visited' in self.context['node_states'][node_id]:
            self.context['node_states'][node_id]['visited'] = False

    def initialize_node_statuses(self, nodes_data: List[Dict[str, Any]]):
        """
        Initialize node statuses before starting tick loop.
        Start node will be Active, all other nodes will be Inactive.
        
        Args:
            nodes_data: List of node dictionaries from strategy JSON
        """
        log_info(f"🔧 initialize_node_statuses called with {len(nodes_data)} nodes")
        
        if 'node_states' not in self.context:
            self.context['node_states'] = {}

        for node in nodes_data:
            node_id = node['id']
            node_type = node['type']

            # Initialize node state (simplified - only status and visited)
            self.context['node_states'][node_id] = {
                'status': 'Active' if node_type.lower() == 'startnode' else 'Inactive',
                'visited': False
            }

        # log_info(f"🎯 Initialized {len(nodes_data)} nodes:")
        start_nodes = [n['id'] for n in nodes_data if n['type'].lower() == 'startnode']
        other_nodes = [n['id'] for n in nodes_data if n['type'].lower() != 'startnode']
        log_info(f"🎯 Initialized {len(nodes_data)} nodes:")
        log_info(f"   Active (Start): {start_nodes}")
        log_info(f"   Inactive: {other_nodes}")

    def get_context_size(self) -> Dict[str, int]:
        """
        Get the size of the main context for monitoring.
        
        Returns:
            Dictionary with context size
        """
        return {
            'main': len(str(self.context))
        }

    def print_context_summary(self):
        """
        Print a summary of current context state.
        """
        # log_info(f"📊 Context Summary:")
        # log_info(f"   Main Context: {self.get_context_size()['main']} chars")
        # log_info(f"   Strategy Config: {self.context.get('strategy_config') is not None}")
        # log_info(f"   Node States: {len(self.context.get('node_states', {}))}")
        # log_info(f"   Node Instances: {len(self.context.get('node_instances', {}))}")
        # log_info(f"   Candle DataFrames: {len(self.context.get('candle_df_dict', {}))}")
        # log_info(f"   LTP Store: {len(self.context.get('ltp_store', {}))}")
        # log_info(f"   Current Timestamp: {self.context.get('current_timestamp')}")

    def get_strategy_summary(self) -> Dict[str, Any]:
        """
        Get a summary of strategy performance.
        
        Returns:
            Dictionary with strategy performance metrics
        """
        # Get GPS summary
        gps_summary = {
            'open_positions': len(self.gps.get_open_positions()),
            'closed_positions': len(self.gps.get_closed_positions()),
            'total_positions': len(self.gps.get_all_positions()),
            'node_variables': len(self.gps.get_all_node_variables())
        }

        return {
            'strategy_id': self.strategy_id,
            'strategy_config': self.context.get('strategy_config') is not None,
            'node_states': len(self.context.get('node_states', {})),
            'node_instances': len(self.context.get('node_instances', {})),
            'candle_dataframes': len(self.context.get('candle_df_dict', {})),
            'ltp_store': len(self.context.get('ltp_store', {})),
            'current_timestamp': self.context.get('current_timestamp'),
            'gps_summary': gps_summary
        }

    # GPS Access Methods
    def get_gps(self) -> GlobalPositionStore:
        """Get the GPS instance."""
        return self.gps

    def add_position(self, position_id: str, entry_data: Dict[str, Any], tick_time: Optional[datetime] = None):
        """Add a position to GPS."""
        self.gps.add_position(position_id, entry_data, tick_time)

    def close_position(self, position_id: str, exit_data: Dict[str, Any], tick_time: Optional[datetime] = None):
        """Close a position in GPS."""
        self.gps.close_position(position_id, exit_data, tick_time)

    def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get position data from GPS."""
        return self.gps.get_position(position_id)

    def get_open_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all open positions from GPS."""
        return self.gps.get_open_positions()

    def get_closed_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all closed positions from GPS."""
        return self.gps.get_closed_positions()

    def set_node_variable(self, node_id: str, variable_name: str, value: Any):
        """Set a node variable in GPS."""
        self.gps.set_node_variable(node_id, variable_name, value)

    def get_node_variable(self, node_id: str, variable_name: str) -> Optional[Any]:
        """Get a node variable from GPS."""
        return self.gps.get_node_variable(node_id, variable_name)

    def get_node_variables(self, node_id: str) -> Dict[str, Any]:
        """Get all variables for a node from GPS."""
        return self.gps.get_node_variables(node_id)

    # NEW: Multi-instrument batched update methods
    def begin_update(self, ts: pd.Timestamp) -> None:
        """Start a new batch update for the given timestamp."""
        with self._lock:
            if self._staged_ts is not None and ts != self._staged_ts:
                # Force commit previous batch if advancing in time
                self.commit(self._staged_ts)
            self._staged_ts = ts
            self._staged_ticks.clear()

    def upsert_tick(self, instrument_id: str, instrument_type: str, tick: Dict[str, Any]) -> None:
        """Stage a tick for the current batch timestamp."""
        with self._lock:
            if self._staged_ts is None:
                raise RuntimeError("begin_update(ts) must be called before upsert_tick()")
            
            key = f"{instrument_id}_{instrument_type}"
            # Use the actual timestamp from tick data, not the staged timestamp
            tick_timestamp = tick.get('timestamp', self._staged_ts)
            self._staged_ticks[key] = {
                'ltp': self._safe_float(tick.get("ltp") or tick.get("price")),
                'ltq': self._safe_float(tick.get("ltq") or tick.get("qty")),
                'oi': self._safe_float(tick.get("oi")),
                'timestamp': tick_timestamp,  # Use actual tick timestamp
                'ts': tick_timestamp,  # Keep both for compatibility
                'instrument_id': instrument_id,
                'instrument_type': instrument_type
            }

    def set_batch_latest(self, ts: pd.Timestamp, batch: Dict[Tuple[str, str], Dict[str, Any]]) -> None:
        """Convenience: stage multiple ticks in one call."""
        self.begin_update(ts)
        for (instrument_id, instrument_type), tick in (batch or {}).items():
            self.upsert_tick(instrument_id, instrument_type, tick or {})

    def update_candles_and_indicators(self, ts: Optional[pd.Timestamp] = None, 
                                     timeframes_per_instrument: Optional[Dict[str, List[str]]] = None) -> None:
        """Apply staged ticks into candles and indicators per timeframe/instrument."""
        with self._lock:
            if self._staged_ts is None:
                return
            if ts is not None and ts != self._staged_ts:
                return

            # Update candles for proper candle formation
            # Group ticks by instrument for proper candle formation
            for key, tick_data in self._staged_ticks.items():
                instrument_id = tick_data.get('instrument_id')
                instrument_type = tick_data.get('instrument_type', 'TI')
                
                # Get timeframes for this instrument
                timeframes = timeframes_per_instrument.get(instrument_id, []) if timeframes_per_instrument else []
                
                # Update each timeframe for this instrument
                for timeframe in timeframes:
                    df_key = f"{timeframe}_{instrument_type}_{instrument_id}"
                    try:
                        # Get existing DataFrame for this timeframe/instrument
                        df_existing = self._candles_by_key.get(df_key)
                        
                        # Use proper candle updater that handles OHLCV logic
                        df_updated = self._update_candle_with_tick(df_existing, tick_data, timeframe, df_key)
                        
                        if df_updated is not None:
                            # Apply indicators for each tick (not waiting for candle completion)
                            if self._indicators_updater:
                                df_updated = self._indicators_updater(df_updated, df_key)
                            self._candles_by_key[df_key] = df_updated
                    except Exception as e:
                        from src.utils.exception_patterns import handle_data_processing_error
                        handle_data_processing_error(e, "context_manager_candles_update", {
                            "df_key": df_key,
                            "instrument_id": instrument_id,
                            "timeframe": timeframe
                        })
    
    def _update_candle_with_tick(self, existing_df: Optional[pd.DataFrame], tick_data: Dict[str, Any], 
                                timeframe: str, df_key: str) -> Optional[pd.DataFrame]:
        """Update candle DataFrame with proper OHLCV logic based on timeframe."""
        if existing_df is None:
            df = pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
            df.index = pd.DatetimeIndex([])
        else:
            df = existing_df.copy()
        
        timestamp = tick_data.get('timestamp', datetime.now())
        ltp = self._safe_float(tick_data.get('ltp', 0))
        ltq = self._safe_float(tick_data.get('ltq', 0))
        
        # Calculate candle start time based on timeframe
        candle_start = self._get_candle_start_time(timestamp, timeframe)
        
        # Check if candle already exists for this timeframe
        if candle_start in df.index:
            # Update existing candle (OHLCV logic)
            existing_candle = df.loc[candle_start]
            new_candle = pd.Series({
                'open': existing_candle['open'],  # Keep original open
                'high': max(existing_candle['high'], ltp),
                'low': min(existing_candle['low'], ltp),
                'close': ltp,  # Update close with latest price
                'volume': existing_candle['volume'] + ltq
            }, name=candle_start)
            df.loc[candle_start] = new_candle
        else:
            # Create new candle
            new_candle = pd.Series({
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': ltq
            }, name=candle_start)
            df.loc[candle_start] = new_candle
        
        return df.sort_index()
    
    def _get_candle_start_time(self, timestamp: pd.Timestamp, timeframe: str) -> pd.Timestamp:
        """Calculate candle start time based on timeframe."""
        if timestamp is None:
            # Fallback to current time if timestamp is None
            timestamp = datetime.now()
        
        if timeframe == '1m':
            return timestamp.replace(second=0, microsecond=0)
        elif timeframe == '5m':
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == '15m':
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif timeframe == '1h':
            return timestamp.replace(minute=0, second=0, microsecond=0)
        else:
            # Default to 1-minute
            return timestamp.replace(second=0, microsecond=0)

    def commit(self, ts: Optional[pd.Timestamp] = None) -> None:
        """Publish staged ticks as the latest snapshot."""
        with self._lock:
            if self._staged_ts is None:
                return
            if ts is not None and ts != self._staged_ts:
                return

            # Publish latest snapshots
            for key, tick_data in self._staged_ticks.items():
                self._latest_by_instrument[key] = tick_data

            # Clear staging
            self._staged_ticks.clear()
            self._staged_ts = None

    def get_latest(self, instrument_id: str, instrument_type: str) -> Dict[str, Any]:
        """Get latest tick data for an instrument."""
        with self._lock:
            key = f"{instrument_id}_{instrument_type}"
            return self._latest_by_instrument.get(key, {
                'ltp': None, 'ltq': None, 'oi': None, 'ts': None
            })

    def get_last_tick_by_role(self) -> Dict[str, Dict[str, Any]]:
        """Get latest tick data by role (instrument_type)."""
        with self._lock:
            result = {}
            for key, tick_data in self._latest_by_instrument.items():
                instrument_type = tick_data.get('instrument_type', 'TI')
                result[instrument_type] = {
                    'ltp': tick_data['ltp'],
                    'ltq': tick_data['ltq'],
                    'oi': tick_data['oi'],
                    'ts': tick_data['ts']
                }
            return result

    def get_dataframe(self, key: str) -> Optional[pd.DataFrame]:
        """Get DataFrame by key (timeframe_instrument_type)."""
        with self._lock:
            return self._candles_by_key.get(key)

    def get_dataframe_by(self, timeframe: str, instrument_type: str) -> Optional[pd.DataFrame]:
        """Get DataFrame by timeframe and instrument type."""
        return self.get_dataframe(f"{timeframe}_{instrument_type}")

    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float, handling None and invalid values."""
        if value is None:
            return 0.0
        try:
            result = float(value)
            # Handle NaN and infinity
            if pd.isna(result) or np.isinf(result):
                return 0.0
            return result
        except (ValueError, TypeError):
            return 0.0

    # CARRYFORWARD State Persistence Methods
    def serialize_state(self) -> Dict[str, Any]:
        """Serialize complete state for CARRYFORWARD persistence."""
        with self._lock:
            return {
                # Core state
                'latest_by_instrument': self._latest_by_instrument,
                'candles_by_key': self._candles_by_key,
                'context': self.context,
                'gps_state': self.gps.serialize_state() if hasattr(self.gps, 'serialize_state') else {},
                'timestamp': self._staged_ts,
                
                # Session info
                'session_info': {
                    'session_id': self.session_id,
                    'user_id': self.user_id,
                    'connection_id': self.connection_id,
                    'strategy_id': self.strategy_id,
                    'strategy_type': self.strategy_type
                }
            }
    
    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore complete state for CARRYFORWARD restoration."""
        with self._lock:
            # Restore core state
            self._latest_by_instrument = state.get('latest_by_instrument', {})
            self._candles_by_key = state.get('candles_by_key', {})
            self.context = state.get('context', {})
            
            # Restore GPS state if available
            if hasattr(self.gps, 'restore_state') and 'gps_state' in state:
                self.gps.restore_state(state['gps_state'])
            
            # Validate session info matches
            session_info = state.get('session_info', {})
            if (self.session_id != session_info.get('session_id') or
                self.user_id != session_info.get('user_id') or
                self.connection_id != session_info.get('connection_id') or
                self.strategy_id != session_info.get('strategy_id')):
                raise ValueError("Session info mismatch during state restoration")
            
            # Update strategy type
            self.strategy_type = session_info.get('strategy_type', 'INTRADAY')
    
    def initialize_with_historical_data(self, candles_df_dict: Dict[str, Any], 
                                      indicators_by_key: Dict[str, Dict[str, Any]]) -> None:
        """Initialize ContextManager with preloaded historical data."""
        with self._lock:
            # Store preloaded candles data
            for key, candle_builder in candles_df_dict.items():
                if hasattr(candle_builder, 'get_dataframe'):
                    self._candles_by_key[key] = candle_builder.get_dataframe()
                elif isinstance(candle_builder, pd.DataFrame):
                    self._candles_by_key[key] = candle_builder
            
            # Store indicators configuration and candles in main context
            self.context['indicators_by_key'] = indicators_by_key
            self.context['candle_df_dict'] = candles_df_dict
