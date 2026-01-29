"""
Node Diagnostics System

Provides comprehensive diagnostic tracking for all nodes during strategy execution.
Records both real-time state and historical events for debugging and UI display.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import deque
import logging

logger = logging.getLogger(__name__)


class NodeDiagnostics:
    """
    Manages diagnostic data for all nodes in a strategy.
    
    Maintains two key data structures:
    1. node_events_history: Append-only timeline of significant events per node
    2. node_current_state: Real-time snapshot of active/pending nodes
    
    Usage:
        diagnostics = NodeDiagnostics(max_events_per_node=100)
        
        # When node logic completes
        diagnostics.record_event(node, context, 'logic_completed', evaluation_data)
        
        # Every tick for active nodes
        diagnostics.update_current_state(node, context, 'active', evaluation_data)
        
        # Every tick for pending nodes
        diagnostics.update_pending_state(node, context, reason='Waiting for order fill')
    """
    
    def __init__(self, max_events_per_node: int = 100):
        """
        Initialize diagnostics system.
        
        Args:
            max_events_per_node: Maximum events to store per node (circular buffer)
        """
        self.max_events_per_node = max_events_per_node
        logger.info(f"📊 NodeDiagnostics initialized (max {max_events_per_node} events per node)")
    
    def initialize_context(self, context: Dict[str, Any]) -> None:
        """
        Initialize diagnostic data structures in context.
        
        Args:
            context: Strategy execution context
        """
        if 'node_events_history' not in context:
            context['node_events_history'] = {}
        
        if 'node_current_state' not in context:
            context['node_current_state'] = {}
        
        if 'diagnostics' not in context:
            context['diagnostics'] = self
    
    def record_event(
        self,
        node: Any,
        context: Dict[str, Any],
        event_type: str,
        evaluation_data: Optional[Dict[str, Any]] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a significant event in node history (append-only).
        
        Args:
            node: Node instance
            context: Execution context
            event_type: Type of event ('logic_completed', 'activated', 'inactivated', etc.)
            evaluation_data: Condition evaluations, node variables, etc.
            additional_data: Any extra data (action details, etc.)
        """
        # Validate required attributes
        if not hasattr(node, 'id'):
            raise AttributeError(f"Node {node} missing 'id' attribute - cannot record diagnostic event")
        
        node_id = node.id
        current_tick = context.get('tick_count', 0)
        current_timestamp = context.get('current_timestamp')
        
        # Validate context has required keys
        if 'node_events_history' not in context:
            raise KeyError(f"Context missing 'node_events_history' - diagnostics not initialized properly")
        
        # Get execution ID from additional_data (required for new chain tracking)
        execution_id = (additional_data or {}).get('execution_id')
        parent_execution_id = (additional_data or {}).get('parent_execution_id')
        
        # Fallback to old behavior if execution_id not provided
        if not execution_id:
            import uuid
            ts_str = str(current_timestamp).replace(':', '').replace('-', '').replace(' ', '_')[:15] if current_timestamp else 'unknown'
            execution_id = f"exec_{node_id}_{ts_str}_{uuid.uuid4().hex[:6]}"
        
        # Get history dict (now keyed by execution_id, not node_id)
        history = context['node_events_history']
        
        # Build event record
        event = {
            # Execution chain tracking
            'execution_id': execution_id,
            'parent_execution_id': parent_execution_id,
            
            # Timing info
            'timestamp': str(current_timestamp) if current_timestamp else None,
            'event_type': event_type,
            
            # Node metadata
            'node_id': node_id,
            'node_name': getattr(node, 'name', node_id),
            'node_type': getattr(node, 'type', 'unknown'),
            
            # Relationships (children only - parent is redundant)
            'children_nodes': self._get_children_info(node, context),
        }
        
        # Add evaluation data if provided
        if evaluation_data:
            event.update(evaluation_data)
        
        # Add additional data if provided (but don't duplicate execution_id/parent_execution_id)
        if additional_data:
            for key, value in additional_data.items():
                if key not in ['execution_id', 'parent_execution_id']:
                    event[key] = value
        
        # Store event with execution_id as key (direct assignment, not append!)
        history[execution_id] = event
        
        # Push to SSE if session exists (live simulation mode)
        if 'session_id' in context:
            try:
                # Import here to avoid circular dependency
                from live_simulation_sse import sse_manager
                
                session = sse_manager.get_session(context['session_id'])
                if session:
                    # Push event to SSE queue (session.add_node_event handles sequence increment)
                    session.add_node_event(execution_id, event)
                    logger.debug(f"📡 SSE push: {execution_id} (session: {context['session_id']})")
            except Exception as e:
                logger.warning(f"Failed to push event to SSE: {e}")
        
        logger.debug(f"📝 Event recorded: {execution_id} (node: {node_id}) - {event_type}")
    
    def update_current_state(
        self,
        node: Any,
        context: Dict[str, Any],
        status: str,
        evaluation_data: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
        parent_execution_id: Optional[str] = None
    ) -> None:
        """
        Update current state for ACTIVE nodes (replaces previous state).
        
        Args:
            node: Node instance
            context: Execution context
            status: Current status ('active', 'pending', 'completed')
            evaluation_data: Fresh condition evaluations, node variables
            execution_id: Unique execution ID for this execution
            parent_execution_id: Parent's execution ID for chain tracking
        """
        # Validate required attributes
        if not hasattr(node, 'id'):
            raise AttributeError(f"Node {node} missing 'id' attribute - cannot update diagnostic state")
        
        node_id = node.id
        current_timestamp = context.get('current_timestamp')
        
        # Validate context has required keys
        if 'node_current_state' not in context:
            raise KeyError(f"Context missing 'node_current_state' - diagnostics not initialized properly")
        
        # Build current state
        state = {
            # Execution chain tracking (optional for current_state)
            'execution_id': execution_id,
            'parent_execution_id': parent_execution_id,
            
            # Timing info
            'timestamp': str(current_timestamp) if current_timestamp else None,
            'status': status,
            
            # Node metadata
            'node_id': node_id,
            'node_name': getattr(node, 'name', node_id),
            'node_type': getattr(node, 'type', 'unknown'),
            
            # Relationships
            'children_nodes': self._get_children_info(node, context),
        }
        
        # Add evaluation data if provided
        if evaluation_data:
            state.update(evaluation_data)
        
        # Replace current state (not append)
        # Keep using node_id as key for current_state (live UI needs to find by node_id)
        context['node_current_state'][node_id] = state
        
        logger.debug(f"🔄 State updated: {node_id} (exec: {execution_id}) - {status}")
    
    def update_pending_state(
        self,
        node: Any,
        context: Dict[str, Any],
        reason: str
    ) -> None:
        """
        Update current state for PENDING nodes (no new evaluation).
        
        Args:
            node: Node instance
            context: Execution context
            reason: Why the node is pending
        """
        # Validate required attributes
        if not hasattr(node, 'id'):
            raise AttributeError(f"Node {node} missing 'id' attribute - cannot update pending state")
        
        node_id = node.id
        current_timestamp = context.get('current_timestamp')
        
        # Validate context has required keys
        if 'node_current_state' not in context:
            raise KeyError(f"Context missing 'node_current_state' - diagnostics not initialized properly")
        
        # Get existing state (if any)
        existing_state = context['node_current_state'].get(node_id, {})
        
        # Update only timing and pending info (preserve last evaluation)
        state = {
            **existing_state,  # Keep previous evaluation data
            
            # Update timing
            'timestamp': str(current_timestamp) if current_timestamp else None,
            'status': 'pending',
            
            # Pending info
            'pending_reason': reason,
        }
        
        # Replace current state
        context['node_current_state'][node_id] = state
        
        logger.debug(f"⏳ Pending state updated: {node_id} - {reason}")
    
    def clear_current_state(self, node: Any, context: Dict[str, Any]) -> None:
        """
        Remove node from current state (when it becomes INACTIVE).
        
        Args:
            node: Node instance
            context: Execution context
        """
        # Validate required attributes
        if not hasattr(node, 'id'):
            raise AttributeError(f"Node {node} missing 'id' attribute - cannot clear diagnostic state")
        
        node_id = node.id
        
        # Validate context has required keys
        if 'node_current_state' not in context:
            raise KeyError(f"Context missing 'node_current_state' - diagnostics not initialized properly")
        
        if node_id in context['node_current_state']:
            del context['node_current_state'][node_id]
            logger.debug(f"🧹 State cleared: {node_id}")
    
    def get_events_for_node(
        self,
        node_id: str,
        context: Dict[str, Any],
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get events for a specific node.
        
        Args:
            node_id: Node identifier
            context: Execution context
            event_type: Filter by event type (optional)
        
        Returns:
            List of events
        """
        history = context.get('node_events_history', {})
        events = list(history.get(node_id, []))
        
        if event_type:
            events = [e for e in events if e.get('event_type') == event_type]
        
        return events
    
    def get_current_state_for_node(
        self,
        node_id: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get current state for a specific node.
        
        Args:
            node_id: Node identifier
            context: Execution context
        
        Returns:
            Current state or None if inactive
        """
        return context.get('node_current_state', {}).get(node_id)
    
    def get_all_current_states(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get all current states."""
        return context.get('node_current_state', {})
    
    def get_all_events(self, context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Get all events history.
        
        Returns dict keyed by execution_id (not node_id anymore).
        Each value is an event dict (not a list).
        """
        history = context.get('node_events_history', {})
        # History is already a dict[execution_id, event_dict], return as-is
        return history
    
    # ==================== Private Helper Methods ====================
    
    def _get_children_info(self, node: Any, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get children nodes information."""
        children_ids = getattr(node, 'children', [])
        if not children_ids:
            return []
        
        # Try to get children nodes from context
        all_nodes = context.get('all_nodes', {})
        children_info = []
        
        for child_id in children_ids:
            child_node = all_nodes.get(child_id)
            if child_node:
                children_info.append({
                    'id': child_id,
                    'name': getattr(child_node, 'name', child_id),
                    'type': getattr(child_node, 'type', 'unknown')
                })
            else:
                # Fallback: just return ID
                children_info.append({'id': child_id})
        
        return children_info
    
    def capture_tick_snapshot(self, context: Dict[str, Any]) -> None:
        """
        Capture per-tick snapshot of LTP store and candle store.
        Called on every tick to provide complete market data visibility.
        
        Args:
            context: Execution context with tick data, ltp_store, candle_df_dict
        """
        tick_data = context.get('current_tick', {})
        timestamp = context.get('current_timestamp')
        
        if not timestamp:
            return
        
        # Get or create tick_events storage
        if 'tick_events' not in context:
            context['tick_events'] = {}
        
        tick_events = context['tick_events']
        tick_key = str(timestamp)
        
        # Capture LTP store snapshot
        ltp_store = context.get('ltp_store', {})
        ltp_snapshot = {}
        if ltp_store:
            try:
                for sym, ltp_data in ltp_store.items():
                    try:
                        # Handle both dict format and float format
                        if isinstance(ltp_data, dict):
                            # Dict format: {'ltp': 24270.2, 'timestamp': ..., 'volume': 0, 'oi': 0}
                            ltp_snapshot[sym] = float(ltp_data.get('ltp', 0))
                        elif isinstance(ltp_data, (int, float)):
                            # Float format: 24270.2
                            ltp_snapshot[sym] = float(ltp_data)
                    except (ValueError, TypeError):
                        pass  # Skip invalid LTP values
            except Exception as e:
                logger.warning(f"Error capturing LTP snapshot: {e}")
        
        # Capture candle store snapshot (ALL 20 candles with indicators)
        candle_snapshot = {}
        candle_df_dict = context.get('candle_df_dict', {})
        for key, candle_data in candle_df_dict.items():
            try:
                if isinstance(candle_data, list) and len(candle_data) > 0:
                    # List of candle dicts - capture ALL candles (full buffer)
                    candle_snapshot[key] = []
                    for candle in candle_data:
                        candle_snapshot[key].append({
                            'timestamp': str(candle.get('timestamp', '')),
                            'open': float(candle.get('open', 0)),
                            'high': float(candle.get('high', 0)),
                            'low': float(candle.get('low', 0)),
                            'close': float(candle.get('close', 0)),
                            'volume': int(candle.get('volume', 0)),
                            'indicators': candle.get('indicators', {})
                        })
                elif hasattr(candle_data, 'tail') and len(candle_data) > 0:
                    # DataFrame - capture all candles
                    all_candles = candle_data.to_dict('records')
                    candle_snapshot[key] = []
                    for candle in all_candles:
                        candle_snapshot[key].append({
                            'timestamp': str(candle.get('timestamp', '')),
                            'open': float(candle.get('open', 0)),
                            'high': float(candle.get('high', 0)),
                            'low': float(candle.get('low', 0)),
                            'close': float(candle.get('close', 0)),
                            'volume': int(candle.get('volume', 0)),
                            'indicators': candle.get('indicators', {})
                        })
            except Exception as e:
                logger.warning(f"Error capturing candle snapshot for {key}: {e}")
        
        # Store tick snapshot
        tick_events[tick_key] = {
            'timestamp': str(timestamp),
            'tick_data': {
                'symbol': tick_data.get('symbol'),
                'ltp': float(tick_data.get('ltp', 0)) if tick_data.get('ltp') else None,
                'volume': int(tick_data.get('volume', 0)) if tick_data.get('volume') else None
            },
            'ltp_store': ltp_snapshot,
            'candle_store': candle_snapshot
        }
        
        logger.debug(f"📸 Tick snapshot: {tick_key} (LTP: {len(ltp_snapshot)} symbols, Candles: {len(candle_snapshot)} keys)")
