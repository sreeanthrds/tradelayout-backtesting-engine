import traceback
from datetime import datetime
from typing import Dict, Any, List

from src.config.market_timings import get_session_times, detect_exchange_from_symbol
from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical, is_per_tick_log_enabled
from src.utils.recursive_processor import process_recursive
from src.services.end_condition_manager import EndConditionManager
from src.utils.pnl_debug_logger import PnLDebugLogger

from .base_node import BaseNode

# Performance mode flag - can be toggled
PERFORMANCE_MODE = False


class StartNode(BaseNode):
    """
    Start Node for initializing strategy parameters and data processing.
    - Sets up timeframe, exchange, symbol, and trading instrument.
    - Initializes indicators configuration.
    - Configures end conditions for strategy termination.
    - Always active at the beginning of each day.
    - First tick: Complete processing + activate children
    - Subsequent ticks: Skip activation + invoke children + set visited flag
    """

    def __init__(self, node_id: str, data: Dict[str, Any]):
        """
        Initialize Start Node.
        
        Args:
            node_id: Unique identifier for the node
            data: Node configuration data
        """
        super().__init__(node_id, 'StartNode', data.get('label', 'Start'))

        # Extract configuration from data
        self.data = data
        
        # Extract symbol from tradingInstrumentConfig (new format) or fallback to direct symbol field
        tic = data.get('tradingInstrumentConfig', {}) or {}
        self.symbol = tic.get('symbol') or data.get('symbol')
        if not self.symbol:
            raise ValueError("❌ Symbol not found in start node configuration! Check tradingInstrumentConfig.")
        
        # Extract timeframe from tradingInstrumentConfig or fallback
        timeframes = [tf.get('timeframe') for tf in (tic.get('timeframes', []) or []) if tf.get('timeframe')]
        self.timeframe = timeframes[0] if timeframes else data.get('timeframe', '5m')
        
        self.exchange = data.get('exchange', 'NSE')
        self.trading_instrument = data.get('tradingInstrument', {'type': 'stock'})
        self.end_conditions = data.get('endConditions', {})
        self.strategy_name = data.get('strategy_name', 'Unknown Strategy')
        self.indicators = data.get('indicators', [])  # ✅ Fixed: Initialize indicators attribute

        # Track if children have been activated (first tick only)
        self._children_activated = False
        # Track if initialization is complete
        self._initialization_complete = False
        
        # Initialize services
        self.end_condition_manager = EndConditionManager()
        self.pnl_logger = PnLDebugLogger()

    def initialize_day(self, context):
        """
        Initialize the Start Node for a new trading day.
        Start Node is always active at the beginning of each day.
        
        Args:
            context: Execution context
        """
        # Start Node is always active at the beginning of each day
        self.mark_active(context)
        self.reset_visited(context)

        # Reset children activation flag for new day
        self._children_activated = False

        # Reset GPS for new day
        context_manager = context.get('context_manager')
        if context_manager:
            context_manager.reset_for_new_day(None)

        # Clear F&O resolution cache for new day
        self.resolved_symbols = {}

        # Store configuration in context for other components to use
        context['strategy_config'] = {
            'timeframe': self.timeframe,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'trading_instrument': self.trading_instrument,
            'indicators': self.indicators,
            'end_conditions': self.end_conditions,
            'strategy_name': getattr(self, 'strategy_name', 'Unknown Strategy')
        }

        # log_info(f"🚀 Start Node initialized for {self.symbol} on {self.timeframe} timeframe")

    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the start node logic for tick-by-tick processing.
        
        Args:
            context: Execution context containing current state, data, etc.
            
        Returns:
            Dict containing execution results with 'logic_completed' flag
        """
        # If strategy has ended, skip logic
        if context.get('strategy_ended', False):
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Strategy already ended due to end condition',
                'logic_completed': True
            }
        # Check if this is the first tick (children not yet activated)
        is_first_tick = not self._children_activated

        if is_first_tick:
            # FIRST TICK: Complete Start Node processing
            log_debug(f"🎯 Start Node: First tick - executing complete logic")

            # Execute initialization logic (only once)
            if not self._initialization_complete:
                try:
                    self._execute_initialization_logic(context)
                    self._initialization_complete = True
                except Exception as e:
                    import traceback
                    log_error(f"❌ CRITICAL: EXCEPTION in _execute_initialization_logic: {e}")
                    log_error(f"   Full traceback:\n{traceback.format_exc()}")
                    # Re-raise - StartNode initialization failure is critical
                    raise RuntimeError(f"StartNode initialization failed: {e}") from e

            # Mark that children have been activated
            # Note: Base class will call _activate_children() when logic_completed=True
            # We don't call it manually here to avoid double activation
            self._children_activated = True
            return {
                'node_id': self.id,
                'executed': True,
                'first_tick': True,
                'children_activated': True,
                'logic_completed': True  # ✅ CRITICAL: Completes after first tick → INACTIVE
            }
        else:
            # SUBSEQUENT TICKS: Should never reach here (node will be INACTIVE)
            # This is a safety fallback in case node is somehow still ACTIVE
            log_debug(f"⚠️ Start Node: Subsequent tick - should be INACTIVE by now")
            return {
                'node_id': self.id,
                'executed': True,
                'first_tick': False,
                'children_activated': False,  # Already activated
                'logic_completed': True  # ✅ Mark as completed (should already be INACTIVE)
            }

    def _execute_children(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute all children nodes and additional modules.
        
        Args:
            context: Execution context
            
        Returns:
            List of child execution results
        """
        # If strategy has ended, skip children
        if context.get('strategy_ended', False):
            return [{
                'module': 'end_conditions',
                'result': {'should_end': True, 'reason': 'Strategy already ended'}
            }]
        results = []
        node_instances = context.get('node_instances', {})

        # Execute children (inherited from BaseNode)
        child_results = super()._execute_children(context)
        results.extend(child_results)

        # Execute additional modules (position store)
        # End conditions are now checked in execute() method using EndConditionManager

        # Execute position store logic (skeleton for now)
        position_result = self._execute_position_store_logic(context)
        results.append({
            'module': 'position_store',
            'result': position_result
        })

        return results

    # REMOVED: _log_pnl_snapshot_if_due() - Moved to PnLDebugLogger service

    # REMOVED: _log_pnl_stream_if_due() - Moved to PnLDebugLogger service

    def _execute_position_store_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute GPS position store logic."""
        try:
            # Get GPS from context manager
            context_manager = context.get('context_manager')
            if context_manager:
                gps = context_manager.get_gps()

                # Get position statistics
                open_positions = len(gps.get_open_positions())
                closed_positions = len(gps.get_closed_positions())
                total_positions = len(gps.get_all_positions())

                return {
                    'executed': True,
                    'message': 'GPS position store logic executed',
                    'open_positions': open_positions,
                    'closed_positions': closed_positions,
                    'total_positions': total_positions
                }
            else:
                return {
                    'executed': False,
                    'message': 'No context manager available for GPS'
                }
        except Exception as e:
            return {
                'executed': False,
                'message': f'GPS position store logic error: {str(e)}'
            }

    def _execute_initialization_logic(self, context: Dict[str, Any]):
        """Execute the initialization logic for the Start node."""
        
        # Resolve trading instrument if it's a dynamic F&O symbol
        resolved_trading_instrument = self.trading_instrument
        
        # Check if trading instrument is a string (dynamic F&O format)
        if isinstance(self.trading_instrument, str):
            if self.is_dynamic_fo_symbol(self.trading_instrument):
                # Get spot prices from context
                spot_prices = self.get_spot_prices_from_context(context)
                
                # Get reference date from context
                reference_date = context.get('current_timestamp')
                
                # Resolve the trading instrument
                resolved_trading_instrument = self.resolve_fo_symbol(
                    self.trading_instrument,
                    spot_prices,
                    reference_date
                )
                
                log_info(f"🎯 Start Node: Resolved Trading Instrument")
                log_info(f"   Dynamic: {self.trading_instrument}")
                log_info(f"   Resolved: {resolved_trading_instrument}")
        
        # Store configuration in context for other components to use
        context['strategy_config'] = {
            'timeframe': self.timeframe,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'trading_instrument': self.trading_instrument,  # Original dynamic symbol
            'resolved_trading_instrument': resolved_trading_instrument,  # Resolved symbol
            'indicators': self.indicators,
            'end_conditions': self.end_conditions,
            'strategy_name': getattr(self, 'strategy_name', 'Unknown Strategy')
        }

        # Position store is managed by GPS (Global Position Store) in context
        # No need for skeleton initialization - GPS handles all position management
        
        # log_info(f"  ⚙️  Start Node: Initialized strategy config")

    def _trigger_exit_node(self, context, reason: str):
        """
        Execute end condition exit logic as a new node execution with ID 'end-1'.
        This clones the _exit_all_positions logic from ExitNode but executes it
        as a new node to avoid conflicts with existing ExitNode IDs.
        """
        # log_debug(f"[DEBUG] Executing end condition exit for reason: {reason}")

        # Execute the cloned exit logic with new node ID
        result = self._execute_end_condition_exit(context, reason)

        # Mark strategy as ended
        context['strategy_ended'] = True

        # log_debug(f"[DEBUG] End condition exit completed: {result}")
        return result

    def _execute_end_condition_exit(self, context: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """
        Execute end condition exit logic as a new node execution.
        This clones the _exit_all_positions logic from ExitNode.
        
        Args:
            context: Execution context
            reason: Reason for exit (e.g., "Time-based exit", "Daily profit target reached")
            
        Returns:
            Dict containing execution results
        """
        current_tick = context.get('current_tick')
        current_timestamp = context.get('current_timestamp')

        # Get all open positions from GPS
        open_positions = self.get_open_positions(context)

        if not open_positions:
            # log_info(f"  ℹ️  No open positions to close for end condition: {reason}")
            return {
                'node_id': 'end-1',
                'executed': True,
                'reason': f'No open positions to close - {reason}',
                'order_generated': False,
                'positions_closed': 0,
                'logic_completed': True
            }

        # Process exit orders for each open position
        closed_positions = []
        for position_id in open_positions:
            exit_result = self._process_end_condition_exit_order(context, position_id, reason)
            if exit_result.get('success', False):
                closed_positions.append(position_id)

        if closed_positions:
            # log_info(f"✅ End Condition Exit (end-1): Closed {len(closed_positions)} positions - {reason}")
            return {
                'node_id': 'end-1',
                'executed': True,
                'order_generated': True,
                'positions_closed': len(closed_positions),
                'closed_position_ids': closed_positions,
                'logic_completed': True,
                'exit_reason': reason
            }
        else:
            log_warning(f"❌ End Condition Exit (end-1): Failed to close any positions - {reason}")
            return {
                'node_id': 'end-1',
                'executed': False,
                'reason': f'Failed to close positions - {reason}',
                'order_generated': False,
                'positions_closed': 0
            }

    def _process_end_condition_exit_order(self, context: Dict[str, Any], position_id: str, reason: str) -> Dict[
        str, Any]:
        """
        Process exit order for a single position during end condition execution.
        This clones the _process_exit_order logic from ExitNode.
        
        Args:
            context: Execution context
            position_id: Position identifier
            reason: Reason for exit
            
        Returns:
            Dict containing exit order result
        """
        current_tick = context.get('current_tick')
        current_timestamp = context.get('current_timestamp')

        # Get position from GPS
        position = self.get_position(context, position_id)
        if not position:
            return {
                'success': False,
                'reason': f'Position {position_id} not found in GPS'
            }

        # Create exit order with end-1 node ID
        exit_order = {
            'order_id': f"END_EXIT_end-1_{position_id}_{current_timestamp.strftime('%Y%m%d_%H%M%S') if current_timestamp else 'unknown'}",
            'node_id': 'end-1',
            'position_id': position_id,
            'symbol': position.get('instrument', 'RELIANCE'),
            'order_type': 'MARKET',  # Always market order for end conditions
            'side': 'BUY' if position.get('side', 'SELL') == 'SELL' else 'SELL',  # Reverse the position
            'quantity': position.get('quantity', 1),
            'price': current_tick.get('ltp', 0),
            'timestamp': current_timestamp,
            'status': 'FILLED',  # For backtesting, market orders are filled immediately
            'fill_time': current_timestamp,
            'fill_price': current_tick.get('ltp', 0)
        }

        # Create exit data for GPS with end-1 node ID
        exit_data = {
            'node_id': 'end-1',
            'price': exit_order['fill_price'],
            'reason': reason,
            'order_id': exit_order['order_id'],
            'order_type': exit_order['order_type'],
            'exit_time': current_timestamp.isoformat() if hasattr(current_timestamp, 'isoformat') else str(
                current_timestamp),
            'fill_time': exit_order['fill_time'].isoformat() if hasattr(exit_order['fill_time'], 'isoformat') else str(
                exit_order['fill_time']),
            'fill_price': exit_order['fill_price']
        }

        # Close position in GPS with tick time
        self.close_position(context, position_id, exit_data)

        # log_info(f"  📤 End Exit Order: {position_id} @ {exit_order['fill_price']} - {reason}")
        # log_debug(f"  🎯 END EXIT DETAILS:")
        # log_debug(f"     📅 Exit Time: {current_timestamp}")
        # log_debug(f"     💰 Exit Price: {exit_order['fill_price']}")
        # log_debug(f"     📊 Order ID: {exit_order['order_id']}")
        # log_debug(f"     🏷️  Symbol: {exit_order['symbol']}")
        # log_debug(f"     📈 Side: {exit_order['side']}")
        # log_debug(f"     🔢 Quantity: {exit_order['quantity']}")
        # log_debug(f"     🚪 Close Reason: {reason}")

        return {
            'success': True,
            'exit_order': exit_order,
            'position_id': position_id
        }

    # ========================================================================
    # REMOVED: End Condition Evaluation Methods - Moved to EndConditionManager
    # ========================================================================
    # - _check_end_conditions() → EndConditionManager.check_end_conditions()
    # - _evaluate_time_based_exit() → EndConditionManager.evaluate_time_based_exit()
    # - _evaluate_performance_based_exit() → EndConditionManager.evaluate_performance_based_exit()
    # - _evaluate_alert_notification() → EndConditionManager.evaluate_alert_notification()

    # ========================================================================
    # REMOVED: Unused/Dead Code Methods
    # ========================================================================
    # - _evaluate_time_condition() - Never called, unused
    # - _evaluate_complex_condition() - Never called, unused
    # - _create_position_store_skeleton() - Never called, returns empty dict
    # - _create_data_processor_for_evaluation() - Never called, unused

    def get_strategy_config(self) -> Dict[str, Any]:
        """Get the strategy configuration."""
        return {
            'timeframe': self.timeframe,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'trading_instrument': self.trading_instrument,
            'indicators': self.indicators,
            'end_conditions': self.end_conditions
        }

    # REMOVED: configure_data_processor() - Called once, should be inlined

    def reset_all_nodes_visited(self):
        """Reset visited flags for all nodes in the tree"""
        self.reset_visited()
        for child in self.children:
            child.reset_visited()

    # REMOVED: process_candle() - Never called, old candle-based logic

    def get_all_nodes(self) -> List[BaseNode]:
        """Get all nodes in the tree"""
        nodes = [self]
        for child in self.children:
            nodes.extend(child.get_all_nodes())
        return nodes

    # REMOVED: process_tick_mode() - Never called, old tick-mode logic

    # REMOVED: process_tick() - Never called, tick processing is in tick_processor.py

    def execute(self, context):
        """
        Execute StartNode following the standard node execution pattern:
        1. Delegate to base class for standard execution (visited check, mark visited, 
           execute logic, activate children, execute children)
        2. Add StartNode-specific post-processing (end conditions, P&L logging)
        
        Note: Base class (BaseNode.execute) handles the visited check as the FIRST step.
        No need to duplicate it here.
        """
        # ====================================================================
        # STEP 1-4: Execute using base class template method
        # This handles: check visited, mark visited, check active, mark pending, 
        # execute logic, activate children, mark inactive/active, execute children
        # ====================================================================
        result = super().execute(context)

        # Store the last execution result for end condition checking
        self._last_execution_result = result

        # ====================================================================
        # STEP 5: StartNode-specific logic (end conditions and P&L logging)
        # ====================================================================
        current_tick = context.get('current_tick')
        current_timestamp = context.get('current_timestamp')

        # Debug-only: emit P&L snapshot and stream (if not in performance mode)
        if not PERFORMANCE_MODE:
            self.pnl_logger.log_pnl_snapshot_if_due(context)
            self.pnl_logger.log_pnl_stream_if_due(context)

        # Check end conditions using EndConditionManager service
        end_condition_result = self.end_condition_manager.check_end_conditions(
            context=context,
            end_conditions=self.end_conditions,
            current_timestamp=current_timestamp,
            current_tick=current_tick,
            symbol=self.symbol
        )
        result['end_condition_result'] = end_condition_result

        # If an end condition is satisfied, trigger exit and mark strategy as ended
        if end_condition_result.get('should_end', False):
            reason = end_condition_result.get('reason', 'End condition met')
            self._trigger_exit_node(context, reason)
            context['strategy_ended'] = True
            
        return result

    # REMOVED: _check_all_nodes_inactive() - Moved to EndConditionManager.check_all_nodes_inactive()
    # REMOVED: _close_all_positions_at_market() - Never called, placeholder method
    # REMOVED: _send_alert_notification() - Never called, placeholder method
