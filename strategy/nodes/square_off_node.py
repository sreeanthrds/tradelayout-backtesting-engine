from typing import Dict, Any

from .base_node import BaseNode
from src.services.end_condition_manager import EndConditionManager
from src.utils.logger import log_info, log_warning, log_error


class SquareOffNode(BaseNode):
    """
    Square Off Node - Strategy-level exit mechanism
    
    Triggers square-off based on:
    1. **Immediate Exit**: Parent condition node triggers exit (attached to condition)
    2. **Time-based Exit**: Market close or specific time (mutually exclusive)
    3. **Performance-based Exit**: Daily profit target or loss limit
    
    Once triggered:
    - Cancels all pending orders (live mode)
    - Closes all open positions at current LTP
    - Marks all nodes as Inactive
    - Ends strategy execution
    """

    def __init__(self, node_id: str, data: Dict[str, Any]):
        super().__init__(node_id, 'SquareOffNode', data.get('label', 'Square off'))
        self.data = data
        self.end_condition_manager = EndConditionManager()
        self.square_off_executed = False  # Track if square-off already executed

    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute square-off logic based on configured exit conditions.
        
        Exit Conditions (evaluated in order):
        1. Immediate Exit - Triggered by parent condition node becoming Active
        2. Performance-based Exit - Daily profit target or loss limit reached
        3. Time-based Exit - Market close or specific time reached
        
        Flow:
        1. Check if square-off already executed (prevent duplicate execution)
        2. Evaluate exit conditions
        3. If triggered: Cancel orders → Close positions → Deactivate all nodes
        4. If not triggered: Stay Active and monitor
        
        Returns:
            logic_completed=True: Square-off executed, node becomes Inactive
            logic_completed=False: Monitoring, stay Active for next tick
        """
        # Prevent duplicate execution
        if self.square_off_executed:
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Square-off already executed',
                'logic_completed': True
            }
        
        mode = context.get('mode', 'backtesting')
        current_timestamp = context.get('current_timestamp')
        
        # Get strategy configuration
        strategy_config = context.get('strategy_config', {})
        symbol = strategy_config.get('symbol', strategy_config.get('resolved_trading_instrument'))
        end_conditions = self.data.get('endConditions', {})
        
        # =====================================================================
        # STEP 1: Evaluate Exit Conditions (in priority order)
        # =====================================================================
        should_execute = False
        reason = None
        condition_type = None
        details = {}
        
        # Priority 1: Immediate Exit (triggered by parent condition node)
        immediate_exit_config = end_conditions.get('immediateExit', {})
        if immediate_exit_config.get('enabled', False):
            # Immediate exit means: Execute square-off when this node becomes Active
            # Parent condition node activates this node → square-off immediately
            should_execute = True
            reason = 'Immediate exit triggered by parent condition'
            condition_type = 'immediateExit'
            log_info(f"🚨 SquareOffNode {self.id}: Immediate exit triggered")
        
        # Priority 2: Performance-based Exit (daily P&L targets)
        if not should_execute:
            perf_exit_config = end_conditions.get('performanceBasedExit', {})
            if perf_exit_config.get('enabled', False):
                result, which_triggered = self.end_condition_manager.evaluate_performance_based_exit(
                    perf_exit_config,
                    context
                )
                
                if result and result.get('satisfied', False):
                    should_execute = True
                    condition_type = 'performanceBasedExit'
                    details = result
                    
                    if which_triggered == 'profit':
                        reason = f"Daily profit target reached (P&L: {result.get('current_pnl', 0):.2f})"
                        log_info(f"🎯 SquareOffNode {self.id}: {reason}")
                    elif which_triggered == 'loss':
                        reason = f"Daily loss limit reached (P&L: {result.get('current_pnl', 0):.2f})"
                        log_error(f"⛔ SquareOffNode {self.id}: {reason}")
        
        # Priority 3: Time-based Exit (market close or specific time)
        if not should_execute:
            time_exit_config = end_conditions.get('timeBasedExit', {})
            if time_exit_config.get('enabled', False):
                result = self.end_condition_manager.evaluate_time_based_exit(
                    time_exit_config,
                    current_timestamp,
                    symbol
                )
                
                if result and result.get('satisfied', False):
                    should_execute = True
                    condition_type = 'timeBasedExit'
                    reason = result.get('description', 'Time-based exit')
                    details = result
                    log_info(f"⏰ SquareOffNode {self.id}: {reason}")
        
        # =====================================================================
        # STEP 2: If conditions not met, stay Active and monitor
        # =====================================================================
        if not should_execute:
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Monitoring exit conditions',
                'logic_completed': False  # Stay Active, check again next tick
            }
        
        # =====================================================================
        # STEP 3: Execute Square-off
        # =====================================================================
        log_info(f"")
        log_info(f"{'='*80}")
        log_info(f"🧹 SQUARE-OFF TRIGGERED")
        log_info(f"{'='*80}")
        log_info(f"  Reason: {reason}")
        log_info(f"  Type: {condition_type}")
        log_info(f"  Time: {current_timestamp.strftime('%Y-%m-%d %H:%M:%S') if current_timestamp else 'N/A'}")
        if details:
            log_info(f"  Details: {details}")
        log_info(f"{'='*80}")
        
        # Step 1: Cancel pending orders (LIVE mode only)
        cancelled_count = 0
        if mode == 'live':
            cancelled_count = self._cancel_pending_orders(context)
        
        # Step 2: Close all open positions
        context_manager = context.get('context_manager')
        closed_count = 0
        if context_manager:
            gps = context_manager.get_gps()
            open_positions = gps.get_open_positions()
            ltp_store = context.get('ltp_store', {})

            for position_id in list(open_positions.keys()):
                position = open_positions[position_id]
                
                # Get exit price from ltp_store using position's actual symbol
                position_symbol = position.get('symbol', '')
                exit_price = 0
                
                # First try: Look up by exact symbol (for options)
                if position_symbol and position_symbol in ltp_store:
                    ltp_data = ltp_store.get(position_symbol, {})
                    if isinstance(ltp_data, dict):
                        exit_price = ltp_data.get('ltp') or ltp_data.get('price', 0)
                    else:
                        exit_price = ltp_data  # Direct value
                    log_info(f"[SquareOff] Found LTP for {position_symbol}: ₹{exit_price:.2f}")
                else:
                    # Fallback: Try underlying instrument or use last known price from position
                    instrument = position.get('instrument', '')
                    if instrument in ltp_store:
                        ltp_data = ltp_store.get(instrument, {})
                        if isinstance(ltp_data, dict):
                            exit_price = ltp_data.get('ltp') or ltp_data.get('price', 0)
                        else:
                            exit_price = ltp_data
                        log_info(f"[SquareOff] Using fallback LTP for {instrument}: ₹{exit_price:.2f}")
                    else:
                        # Last fallback: Use last known price from position (current_price)
                        exit_price = position.get('current_price', position.get('entry_price', 0))
                        log_warning(f"[SquareOff] No LTP found for {position_symbol}, using last known price: ₹{exit_price:.2f}")
                
                # Get NIFTY spot price at square-off
                nifty_spot_exit = 0
                if 'NIFTY' in ltp_store:
                    nifty_data = ltp_store['NIFTY']
                    if isinstance(nifty_data, dict):
                        nifty_spot_exit = nifty_data.get('ltp', 0)
                    else:
                        nifty_spot_exit = nifty_data
                
                exit_data = {
                    'reason': 'square_off',
                    'reason_detail': reason,  # Use the actual reason (time_based_exit, immediate_exit_enabled, etc.)
                    'price': exit_price,
                    'node_id': self.id,
                    'nifty_spot': nifty_spot_exit  # NIFTY spot price at exit
                }
                # Use BaseNode helper to ensure reEntryNum is attached
                self.close_position(context, position_id, exit_data)
                closed_count += 1

        # Step 3: Mark every node as Inactive
        node_states = context.get('node_states', {})
        for node_id, state in node_states.items():
            state['status'] = 'Inactive'
            # Optional: reset visited for cleanliness
            state['visited'] = False

        # Mark square-off as executed to prevent re-execution
        self.square_off_executed = True
        
        # Mark strategy as ended
        context['strategy_ended'] = True
        
        log_info(f"")
        log_info(f"✅ SQUARE-OFF COMPLETE")
        log_info(f"  Orders cancelled: {cancelled_count}")
        log_info(f"  Positions closed: {closed_count}")
        log_info(f"  All nodes deactivated: Yes")
        log_info(f"  Strategy ended: Yes")
        log_info(f"{'='*80}")
        log_info(f"")

        # Do not activate children; base will run children but they are inactive
        return {
            'node_id': self.id,
            'executed': True,
            'reason': reason,
            'condition_type': condition_type,
            'orders_cancelled': cancelled_count,
            'positions_closed': closed_count,
            'details': details,
            'logic_completed': True  # Becomes Inactive, job complete
        }
    
    def _cancel_pending_orders(self, context: Dict[str, Any]) -> int:
        """
        Cancel all pending orders (LIVE mode only).
        
        Returns:
            Number of orders cancelled
        """
        order_manager = context.get('order_manager')
        if not order_manager:
            log_warning(f"⚠️ SquareOffNode {self.id}: No OrderManager in context (LIVE mode)")
            return 0
        
        try:
            # Get all pending orders
            pending_orders = order_manager.get_pending_orders()
            cancelled_count = 0
            
            for order in pending_orders:
                order_id = order.get('order_id')
                if not order_id:
                    continue
                
                try:
                    # Cancel order
                    result = order_manager.cancel_order(order_id)
                    if result.get('success'):
                        cancelled_count += 1
                        log_info(f"✅ Cancelled order: {order_id}")
                    else:
                        log_warning(f"⚠️ Failed to cancel order {order_id}: {result.get('reason')}")
                except Exception as e:
                    log_warning(f"⚠️ Error cancelling order {order_id}: {e}")
            
            return cancelled_count
            
        except Exception as e:
            log_warning(f"⚠️ Error getting pending orders: {e}")
            return 0



