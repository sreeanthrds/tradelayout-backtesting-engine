"""
Exit Node - Executes exit orders and closes positions
"""

from datetime import datetime
from typing import Dict, Any

from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical

from .base_node import BaseNode


class ExitNode(BaseNode):
    """
    Exit Node - Executes exit orders and closes positions.
    
    This node handles the actual execution of exit orders including:
    - Market orders for position closure
    - Stop loss orders
    - Take profit orders
    - Time-based exits
    - Force closure orders
    """

    def __init__(self, node_id: str, data: Dict[str, Any]):
        """
        Initialize Exit Node.
        
        Args:
            node_id: Unique identifier for the node
            data: Node configuration data containing exit configuration
        """
        super().__init__(node_id, 'ExitNode', data.get('label', 'Exit'))

        # Extract configuration from data
        self.data = data
        # Handle both old and new structure
        if 'exitNodeData' in data:
            # New structure
            self.exit_config = data.get('exitNodeData', {}).get('orderConfig', {})
            self.re_entry_config = data.get('exitNodeData', {}).get('reEntryConfig', {})
            self.post_execution_config = data.get('exitNodeData', {}).get('postExecutionConfig', {})
        else:
            # Old structure
            self.exit_config = data.get('exitConfig', {})
            self.re_entry_config = {}
            self.post_execution_config = {}

        self.instrument = data.get('instrument', 'RELIANCE')

        # Tracking
        self._orders_generated = 0
        self._positions_closed = 0

        # log_info(f"🚪 Exit Node {self.id} initialized for {self.instrument}")
    
    def reset(self, context):
        """
        Reset node state for new execution.
        Also resets order status to None to allow new order placement.
        """
        super().reset(context)
        
        # Reset order status in tracking dict
        if 'node_order_status' in context:
            context['node_order_status'][self.id] = None
        
        # Clear pending order ID
        self._set_node_state(context, {'pending_order_id': None})
        
        log_info(f"🔄 Exit Node {self.id}: Reset - order status cleared, ready for new order")

    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute exit node logic with postback-based fill verification.
        
        Flow:
        1. Check node order status in context tracking dict
        2. If status is None: Place new exit order
        3. If status is PENDING/PARTIALLY_FILLED: Wait for postback (don't place again)
        4. If status is COMPLETE: Mark position closed, deactivate self
        5. If status is REJECTED/CANCELLED: Log message, deactivate self (don't retry)
        
        Args:
            context: Execution context
            
        Returns:
            Dict containing execution results
        """
        current_timestamp = context.get('current_timestamp')
        mode = context.get('mode', 'backtesting')
        
        # Initialize node_order_status tracking dict if not exists
        if 'node_order_status' not in context:
            context['node_order_status'] = {}
        
        node_order_status = context['node_order_status']
        
        # Check if we have an order status for this node
        current_order_status = node_order_status.get(self.id)

        # Check if we have a pending exit order from previous tick
        node_state = self._get_node_state(context)
        pending_order_id = node_state.get('pending_order_id')
        
        if pending_order_id and current_order_status:
            # We have an exit order - check its status from postback updates
            log_info(f"🔍 Exit Node {self.id}: Checking order status for {pending_order_id}")
            log_info(f"   Current order status: {current_order_status}")
            
            fill_status = self._check_order_fill_status(context, pending_order_id)
            
            if fill_status['is_filled']:
                # Order is COMPLETE (fully filled) - close position in GPS
                log_info(f"✅ Exit Node {self.id}: Exit order {pending_order_id} is COMPLETE (fully filled)")
                
                order_data = fill_status.get('order_data', {})
                
                # Get target position ID from exit config
                target_position_id = self.exit_config.get('targetPositionVpi')
                
                if target_position_id:
                    # Store exit in GPS to close the position
                    store_res = self._store_exit_in_global_store(context, target_position_id, order_data)
                    
                    if store_res.get('success'):
                        log_info(f"✅ Exit Node {self.id}: Position {target_position_id} closed successfully")
                    else:
                        log_error(f"❌ Exit Node {self.id}: Failed to close position {target_position_id}")
                else:
                    log_warning(f"⚠️ Exit Node {self.id}: No target position ID found in exit config")
                
                # Clear order status and pending order
                node_order_status[self.id] = None
                self._set_node_state(context, {'pending_order_id': None})
                
                # Activate children and mark self inactive
                self._activate_children(context)
                
                return {
                    'node_id': self.id,
                    'executed': True,
                    'order_generated': True,
                    'positions_closed': 1,
                    'logic_completed': True  # Exit filled = deactivate self
                }
                
            elif fill_status['is_rejected']:
                # Order was REJECTED or CANCELLED - log and deactivate
                rejection_reason = fill_status.get('reason', 'Unknown reason')
                log_error(f"❌ Exit Node {self.id}: Exit order {pending_order_id} was REJECTED/CANCELLED")
                log_error(f"   Reason: {rejection_reason}")
                log_error(f"   ⚠️ This exit order will NOT be retried. Please check:")
                log_error(f"      - Order was cancelled externally (manual cancellation)")
                log_error(f"      - Insufficient margin/funds")
                log_error(f"      - Invalid order parameters")
                log_error(f"      - Market hours or circuit limits")
                log_error(f"   💡 IMPORTANT: You may have OPEN POSITIONS that need manual closure!")
                log_error(f"   🚨 Please check your broker account and close positions manually if needed.")
                
                # Clear order status and pending order (don't retry)
                node_order_status[self.id] = None
                self._set_node_state(context, {'pending_order_id': None})
                
                return {
                    'node_id': self.id,
                    'executed': False,
                    'reason': f"Exit order rejected/cancelled: {rejection_reason}",
                    'order_generated': False,
                    'logic_completed': True  # Rejected = deactivate self (don't retry)
                }
                
            else:
                # Order still PENDING or PARTIALLY_FILLED - keep waiting
                log_info(f"⏳ Exit Node {self.id}: Exit order {pending_order_id} status: {current_order_status}")
                log_info(f"   Waiting for postback to update status to COMPLETE...")
                
                return {
                    'node_id': self.id,
                    'executed': False,
                    'reason': f'Waiting for exit order fill (status: {current_order_status})',
                    'order_generated': True,
                    'logic_completed': False  # Keep active to check again next tick
                }

        # Same-tick guard: if entry happened on this tick, defer closing
        if context.get('_just_created_position_tick_ts') == current_timestamp:
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Deferred to next tick to avoid same-tick entry/exit',
                'order_generated': False,
                'logic_completed': False
            }

        # Determine target by VPI only
        target_position_id = self.exit_config.get('targetPositionVpi')

        closed_ids = []
        if target_position_id:
            # Close specific position by exact VPI
            pos = self.get_position(context, target_position_id)
            if not pos:
                log_warning(f"  ⚠️  Target position {target_position_id} not found in GPS")
                return {
                    'node_id': self.id,
                    'executed': True,
                    'reason': f'Target position {target_position_id} not found',
                    'order_generated': False,
                    'positions_closed': 0,
                    'logic_completed': True
                }
            # If already closed, return gracefully
            txns = pos.get('transactions', []) or []
            if txns and txns[-1].get('status') != 'open':
                return {
                    'node_id': self.id,
                    'executed': True,
                    'reason': f'No open positions to close for {target_position_id}',
                    'order_generated': False,
                    'positions_closed': 0,
                    'logic_completed': True
                }
            # For live mode: Place order through OrderManager
            if mode == 'live':
                order_manager = context.get('order_manager')
                if not order_manager:
                    log_error(f"❌ Exit Node {self.id}: No OrderManager in live mode")
                    return {
                        'node_id': self.id,
                        'executed': False,
                        'reason': 'No OrderManager available',
                        'order_generated': False,
                        'logic_completed': True
                    }
                
                # Get exit order details
                exit_order = self._create_exit_order(context, pos)
                
                # DEBUG: Show position contents
                log_info(f"🔍 [EXIT DEBUG] Position {target_position_id} contents:")
                log_info(f"   Keys: {list(pos.keys())}")
                log_info(f"   symbol: {pos.get('symbol')}")
                log_info(f"   exchange: {pos.get('exchange')}")
                log_info(f"   instrument: {pos.get('instrument')}")
                log_info(f"   quantity: {pos.get('quantity')}")
                log_info(f"   side: {pos.get('side')}")
                
                # Get symbol and exchange from the POSITION (not strategy config!)
                # The position contains the actual instrument that was traded (e.g., option contract)
                trading_symbol = pos.get('symbol')  # This is the actual traded symbol (e.g., NIFTY28OCT2525900CE)
                trading_exchange = pos.get('exchange', 'NFO')  # Options trade on NFO
                
                if not trading_symbol:
                    log_error(f"❌ Exit Node {self.id}: No symbol found in position {target_position_id}")
                    return {
                        'node_id': self.id,
                        'executed': False,
                        'reason': 'No symbol in position',
                        'order_generated': False,
                        'logic_completed': True
                    }
                
                # Get position config for product type
                position_config = pos.get('position_config', {})
                product_type = position_config.get('productType', 'INTRADAY')
                
                log_info(f"[ExitNode] Placing LIVE exit order: {exit_order['side']} {exit_order['quantity']} {trading_symbol} on {trading_exchange}")
                
                try:
                    # Place order through OrderManager
                    order_result = order_manager.place_order(
                        symbol=trading_symbol,
                        exchange=trading_exchange,
                        transaction_type=exit_order['side'],
                        quantity=exit_order['quantity'],
                        order_type=exit_order['order_type'],
                        product_type=product_type.upper(),
                        price=exit_order['price'] if exit_order['order_type'] != 'MARKET' else 0,
                        node_id=self.id
                    )
                    
                    if order_result and order_result.get('broker_order_id'):
                        order_id = order_result.get('order_id')
                        log_info(f"✅ Exit Node {self.id}: Exit order placed (ID: {order_id}), waiting for fill...")
                        log_info(f"   Broker Order ID: {order_result.get('broker_order_id')}")
                        
                        # Set order status to PENDING in tracking dict
                        node_order_status[self.id] = 'PENDING'
                        self._set_node_state(context, {'pending_order_id': order_id})
                        
                        # CRITICAL: Mark node as PENDING (waiting for async order fill)
                        self.mark_pending(context)
                        
                        log_info(f"   Order status set to: PENDING")
                        log_info(f"   Will wait for postback to update status to COMPLETE")
                        
                        return {
                            'node_id': self.id,
                            'executed': False,
                            'reason': 'Exit order placed, waiting for fill',
                            'order_generated': True,
                            'order_id': order_id,
                            'order_status': 'PENDING',
                            'logic_completed': False  # Keep active to check fill status next tick
                        }
                    else:
                        log_error(f"❌ Failed to place live exit order: {order_result}")
                        return {
                            'node_id': self.id,
                            'executed': False,
                            'reason': f"Exit order placement failed: {order_result.get('error_message') if order_result else 'Unknown error'}",
                            'order_generated': False,
                            'logic_completed': True
                        }
                        
                except Exception as e:
                    from src.utils.error_handler import handle_exception
                    log_error(f"❌ Error placing live exit order: {e}")
                    
                    handle_exception(e, "exit_node_place_order", {
                        'node_id': self.id,
                        'symbol': trading_symbol,
                        'transaction_type': exit_order['side'],
                        'quantity': exit_order['quantity']
                    }, is_critical=True, continue_execution=False)
                    
                    return {
                        'node_id': self.id,
                        'executed': False,
                        'reason': f"Exit order placement error: {e}",
                        'order_generated': False,
                        'logic_completed': True
                    }
            
            # Backtesting mode: Create local exit order
            exit_order = self._create_exit_order(context, pos)
            order_id = exit_order.get('order_id')
            
            # Backtesting mode: Immediate fill
            store_res = self._store_exit_in_global_store(context, target_position_id, exit_order)
            if store_res.get('success'):
                closed_ids.append(target_position_id)
                try:
                    log_info(f"ExitNode {self.id}: closed {target_position_id}")
                except Exception as e:
                    log_warning(f"ExitNode {self.id}: Failed to log position closure: {e}")
        else:
            # Close all open positions
            open_positions = self.get_open_positions(context)
            if not open_positions:
                return {
                    'node_id': self.id,
                    'executed': True,
                    'reason': 'No open positions to close',
                    'order_generated': False,
                    'positions_closed': 0,
                    'logic_completed': True
                }
            for pid, pos in open_positions.items():
                exit_order = self._create_exit_order(context, pos)
                store_res = self._store_exit_in_global_store(context, pid, exit_order)
                if store_res.get('success'):
                    closed_ids.append(pid)

        # Update counters and mark as executed
        self._orders_generated += len(closed_ids)
        self._positions_closed += len(closed_ids)

        # Activate children and mark self inactive
        self._activate_children(context)

        return {
            'node_id': self.id,
            'executed': True,
            'order_generated': len(closed_ids) > 0,
            'positions_closed': len(closed_ids),
            'closed_position_ids': closed_ids,
            'logic_completed': True
        }

    def _exit_specific_position(self, context: Dict[str, Any], target_position_id: str) -> Dict[str, Any]:
        """Exit a specific position by ID."""
        current_timestamp = context.get('current_timestamp')

        # Check if target position exists in GPS
        position = self.get_position(context, target_position_id)
        if not position:
            log_warning(f"  ⚠️  Target position {target_position_id} not found in GPS")
            return {
                'node_id': self.id,
                'executed': True,
                'reason': f'Target position {target_position_id} not found',
                'order_generated': False,
                'positions_closed': 0,
                'logic_completed': True
            }

        # Process exit order
        exit_result = self._process_exit_order(context, target_position_id)

        if exit_result.get('success', False):
            # log_info(f"✅ Exit Node {self.id}: Closed position {target_position_id} at {current_timestamp}")
            # Activate children and mark self inactive (ExitNode-specific activator)
            self._activate_children(context)
            return {
                'node_id': self.id,
                'executed': True,
                'order_generated': True,
                'positions_closed': 1,
                'closed_position_ids': [target_position_id],
                'logic_completed': True
            }
        else:
            log_error(f"❌ Exit Node {self.id}: Failed to close position {target_position_id}")
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Failed to close target position',
                'order_generated': False,
                'positions_closed': 0
            }

    def _exit_all_positions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Exit all active positions."""
        current_timestamp = context.get('current_timestamp')

        # If this is the same tick as just created entries, defer exit to avoid same-tick entry/exit
        if context.get('_just_created_position_tick_ts') == current_timestamp:
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Deferred to next tick to avoid same-tick entry/exit',
                'order_generated': False,
                'logic_completed': False
            }

        # Get all open positions from GPS
        open_positions = self.get_open_positions(context)

        if not open_positions:
            # log_info(f"  ℹ️  No open positions to close")
            return {
                'node_id': self.id,
                'executed': True,
                'reason': 'No open positions to close',
                'order_generated': False,
                'positions_closed': 0,
                'logic_completed': True
            }

        # Process exit orders for each open position
        closed_positions = []
        for position_id in open_positions:
            exit_result = self._process_exit_order(context, position_id)
            if exit_result.get('success', False):
                closed_positions.append(position_id)

        if closed_positions:
            # log_info(f"✅ Exit Node {self.id}: Closed {len(closed_positions)} positions")
            # Activate children and mark self inactive (ExitNode-specific activator)
            self._activate_children(context)
            return {
                'node_id': self.id,
                'executed': True,
                'order_generated': True,
                'positions_closed': len(closed_positions),
                'closed_position_ids': closed_positions,
                'logic_completed': True
            }
        else:
            log_error(f"❌ Exit Node {self.id}: Failed to close any positions")
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Failed to close positions',
                'order_generated': False,
                'positions_closed': 0
            }

    def _process_exit_order(self, context: Dict[str, Any], position_id: str) -> Dict[str, Any]:
        """
        Process exit order for a single position.
        
        Args:
            context: Execution context
            position_id: Position identifier
            
        Returns:
            Dict containing exit order result
        """
        # Deprecated in favor of _create_exit_order + _store_exit_in_global_store
        current_timestamp = context.get('current_timestamp')
        return {
            'success': False,
            'reason': f'Use _create_exit_order/_store_exit_in_global_store instead (at {current_timestamp})'
        }

    def _create_exit_order(self, context: Dict[str, Any], position: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an exit order description (no side effects).
        """
        current_timestamp = context.get('current_timestamp')
        
        try:
            position_id = position['position_id']
        except (KeyError, AttributeError, TypeError) as e:
            raise ValueError(
                f"ExitNode {self.id}: Invalid position structure "
                f"(type: {type(position).__name__}): {e}"
            ) from e

        # Get exit price from ltp_store based on position's actual symbol
        ltp_store = context.get('ltp_store', {})
        exit_price = 0
        
        # Get the actual traded symbol from position (e.g., NIFTY:2024-10-03:OPT:25900:CE)
        position_symbol = position.get('symbol', '')
        
        # First try: Look up by exact symbol (for options)
        if position_symbol and position_symbol in ltp_store:
            ltp_data = ltp_store.get(position_symbol, {})
            if isinstance(ltp_data, dict):
                exit_price = ltp_data.get('ltp') or ltp_data.get('price', 0)
            else:
                exit_price = ltp_data  # Direct value
            log_info(f"[ExitNode] Found LTP for {position_symbol}: ₹{exit_price:.2f}")
        else:
            # Fallback: Try underlying instrument
            instrument = position.get('instrument', '')
            if instrument in ltp_store:
                ltp_data = ltp_store.get(instrument, {})
                if isinstance(ltp_data, dict):
                    exit_price = ltp_data.get('ltp') or ltp_data.get('price', 0)
                else:
                    exit_price = ltp_data
                log_info(f"[ExitNode] Using fallback LTP for {instrument}: ₹{exit_price:.2f}")
            else:
                log_warning(f"[ExitNode] No LTP found for {position_symbol} or {instrument}")
                log_warning(f"[ExitNode] Available LTP keys: {list(ltp_store.keys())}")

        # Determine exit side based on position side
        # Position is stored with 'side' at top level (from entry_data)
        # Get the latest transaction to find the actual position side
        transactions = position.get('transactions', [])
        if transactions:
            # Get the last open transaction
            last_txn = transactions[-1]
            entry_data = last_txn.get('entry', {})
            position_side = entry_data.get('side', 'BUY').upper()
        else:
            # Fallback: check top-level side or entry.side
            position_side = position.get('side', position.get('entry', {}).get('side', 'BUY')).upper()
        
        # Exit side is opposite of position side
        # If position is BUY, exit is SELL
        # If position is SELL, exit is BUY
        exit_side = 'SELL' if position_side == 'BUY' else 'BUY'
        
        log_info(f"[ExitNode] Position side: {position_side}, Exit side: {exit_side}")
        
        return {
            'order_id': f"EXIT_{self.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'position_id': position_id,
            'node_id': self.id,
            'order_type': self.exit_config.get('orderType', 'MARKET').upper(),
            'side': exit_side,
            'quantity': position.get('quantity', 1),
            'price': exit_price,
            'timestamp': current_timestamp,
            'status': 'FILLED',
            'fill_time': current_timestamp,
            'fill_price': exit_price
        }

    def _check_order_fill_status(self, context: Dict[str, Any], order_id: str) -> Dict[str, Any]:
        """
        Check if an exit order has been filled using postback data (no API calls).
        Same logic as entry node.
        
        Args:
            context: Execution context
            order_id: Order ID to check
            
        Returns:
            Dict with fill status
        """
        order_manager = context.get('order_manager')
        
        if not order_manager:
            # No order manager - assume filled (backtesting)
            return {
                'is_filled': True,
                'is_rejected': False,
                'is_pending': False,
                'filled_quantity': 0,
                'order_data': {}
            }
        
        try:
            # Get order status from order manager
            # Since we don't have postback webhook, we need to refresh from broker
            # TODO: Set up postback webhook to avoid API calls
            order_status = order_manager.get_order_status(order_id, refresh_from_broker=True)
            
            if not order_status:
                log_warning(f"⚠️ Order {order_id} not found in local store")
                return {
                    'is_filled': False,
                    'is_rejected': False,
                    'is_pending': True,
                    'filled_quantity': 0,
                    'order_data': {}
                }
            
            # Check order status from postback-updated data
            status = order_status.get('status', '').lower()
            filled_qty = order_status.get('filled_quantity', 0)
            total_qty = order_status.get('quantity', 0)
            
            # Check if fully filled
            is_filled = (
                status in ['complete', 'filled'] or 
                (filled_qty > 0 and filled_qty >= total_qty)
            )
            
            # Check if rejected/cancelled
            is_rejected = status in ['rejected', 'cancelled', 'canceled']
            
            # Check if partially filled
            is_partially_filled = (filled_qty > 0 and filled_qty < total_qty)
            
            # Check if still pending
            is_pending = not is_filled and not is_rejected
            
            # Update node_order_status tracking dict based on order status
            node_order_status = context.get('node_order_status', {})
            if is_filled:
                node_order_status[self.id] = 'COMPLETE'
            elif is_rejected:
                node_order_status[self.id] = 'REJECTED'
            elif is_partially_filled:
                node_order_status[self.id] = 'PARTIALLY_FILLED'
            else:
                node_order_status[self.id] = 'PENDING'
            
            return {
                'is_filled': is_filled,
                'is_rejected': is_rejected,
                'is_pending': is_pending,
                'filled_quantity': filled_qty,
                'order_data': order_status,
                'reason': order_status.get('rejection_reason', order_status.get('message', ''))
            }
            
        except Exception as e:
            from src.utils.error_handler import handle_exception
            log_error(f"❌ Error checking order fill status: {e}")
            
            # Non-critical - can retry on next tick
            handle_exception(e, "exit_node_check_order_status", {
                'node_id': self.id,
                'order_id': order_id
            }, is_critical=False, continue_execution=True)
            
            # On error, assume pending to retry later
            return {
                'is_filled': False,
                'is_rejected': False,
                'is_pending': True,
                'order_data': None
            }
    def _store_exit_in_global_store(self, context: Dict[str, Any], position_id: str, exit_order: Dict[str, Any]) -> Dict[str, Any]:
        """
{{ ... }}
        """
        try:
            current_timestamp = context.get('current_timestamp')
            # Attach reEntryNum for auditing/reporting
            try:
                re_entry_num_raw = self._get_node_state(context).get('reEntryNum', 0) or 0
                re_entry_num = int(re_entry_num_raw)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"ExitNode {self.id}: Invalid reEntryNum '{re_entry_num_raw}' "
                    f"(type: {type(re_entry_num_raw).__name__}): {e}"
                ) from e

            # If an ExitSignalNode triggered this, capture its node_id/time/price
            trigger_node_id = None
            trigger_time = None
            trigger_price = None
            try:
                exit_signals = context.get('exit_signals') or []
                if exit_signals:
                    last_sig = exit_signals[-1]
                    trigger_node_id = last_sig.get('node_id')
                    trigger_time = last_sig.get('exit_signal_time')
                    trigger_price = last_sig.get('exit_signal_price')
            except Exception:
                pass

            # Extract fill price and time from order
            # For live trading: use average_price and completed_at
            # For backtesting: use fill_price and fill_time
            mode = context.get('mode', 'backtesting')
            
            if mode == 'live':
                fill_price = exit_order.get('average_price', 0)
                fill_time = exit_order.get('completed_at')
                exit_time = exit_order.get('completed_at')
            else:
                fill_price = exit_order.get('fill_price', 0)
                fill_time = exit_order.get('fill_time')
                exit_time = current_timestamp
            
            # Get NIFTY spot price at exit
            ltp_store = context.get('ltp_store', {})
            nifty_spot_exit = 0
            if 'NIFTY' in ltp_store:
                nifty_data = ltp_store['NIFTY']
                if isinstance(nifty_data, dict):
                    nifty_spot_exit = nifty_data.get('ltp', 0)
                else:
                    nifty_spot_exit = nifty_data
            
            exit_data = {
                'node_id': self.id,
                'price': fill_price,  # Actual average fill price
                'reason': 'exit_condition_met',
                'reason_detail': self.exit_config.get('reason', 'condition_met'),
                'trigger_node_id': trigger_node_id,
                'trigger_time': trigger_time,
                'trigger_price': trigger_price,
                'order_id': exit_order.get('order_id'),
                'order_type': exit_order.get('order_type', 'MARKET'),
                'exit_time': exit_time.isoformat() if exit_time and hasattr(exit_time, 'isoformat') else str(exit_time),
                'fill_time': fill_time.isoformat() if fill_time and hasattr(fill_time, 'isoformat') else str(fill_time),
                'fill_price': fill_price,  # Actual average fill price
                'reEntryNum': re_entry_num,
                'nifty_spot': nifty_spot_exit  # NIFTY spot price at exit
            }

            # Close position in GPS (with tick time)
            self.close_position(context, position_id, exit_data)

            return {
                'success': True,
                'position_id': position_id,
                'exit_data': exit_data
            }

        except Exception as e:
            from src.utils.error_handler import handle_exception
            log_error(f"  ❌ Error storing exit in GPS for {position_id}: {e}", exc_info=True)
            
            # Critical - position tracking failed
            handle_exception(e, "exit_node_store_exit", {
                'node_id': self.id,
                'position_id': position_id
            }, is_critical=True, continue_execution=False)
            
            return {
                'success': False,
                'error': str(e)
            }

    def _activate_children(self, context: Dict[str, Any]):
        """
        ExitNode-specific activation matching EntryNode semantics:
        - Mark self inactive
        - Activate children
        - Mark children visited to defer execution to the next tick
        """
        node_instances = context.get('node_instances', {})
        self.mark_inactive(context)

        # Parent re-entry number from this node's state
        parent_re = int(self._get_node_state(context).get('reEntryNum', 0) or 0)

        for child_id in self.children:
            child_node = node_instances.get(child_id)
            if not child_node:
                log_warning(f"   ⚠️  Child node {child_id} not found in node instances")
                continue
            child_node.mark_active(context)
            # Update child's reEntryNum per shared policy
            try:
                child_node._update_child_reentry_num(context, child_node, parent_re)
            except Exception as e:
                log_warning(f"ExitNode {self.id}: Failed to update reEntryNum for child {child_id}: {e}")
            # Forcibly allow child to run by resetting visited
            try:
                child_node.reset_visited(context)
            except Exception as e:
                log_warning(f"ExitNode {self.id}: Failed to reset visited flag for child {child_id}: {e}")
