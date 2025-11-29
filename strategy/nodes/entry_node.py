from datetime import datetime
from typing import Dict, Any

from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical

from .base_node import BaseNode


class EntryNode(BaseNode):
    """
    Entry Node for placing entry orders based on strategy configuration.
    - Reads position configuration from strategy JSON
    - Places entry order based on configuration
    - Stores position details in global position store
    - Implements standardized post-execution logic
    """

    def __init__(self, node_id: str, data: Dict[str, Any]):
        """
        Initialize Entry Node.
        
        Args:
            node_id: Unique identifier for the node
            data: Node configuration data containing positions
        """
        super().__init__(node_id, 'EntryNode', data.get('label', 'Entry'))

        # Extract configuration from data
        self.data = data
        self.positions = data.get('positions', [])
        # NOTE: instrument will be set from strategy config in execute(), not from node data
        self.instrument = None  # Will be set from context during execution
        self.action_type = data.get('actionType', 'entry')

        # Tracking (optional)
        self._orders_generated = 0
        self._positions_created = 0

        # log_info(f"🎯 Entry Node {self.id} initialized for {self.instrument}")
    
    def reset(self, context):
        """
        Reset node state for new execution.
        Also resets order status to None to allow new order placement.
        """
        super().reset(context)
        
        # Reset order status in node_states dict (correct location)
        node_states = context.get('node_states', {})
        node_state = node_states.get(self.id, {})
        if 'node_order_status' in node_state:
            node_state['node_order_status'][self.id] = None
        
        # Clear pending order ID
        self._set_node_state(context, {'pending_order_id': None})
        
        log_info(f"🔄 Entry Node {self.id}: Reset - order status cleared, ready for new order")

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the entry node following the BaseNode template pattern.
        
        Args:
            context: Execution context containing current state, data, etc.
            
        Returns:
            Dict containing execution results
        """
        # Call the parent's execute method to follow the standardized template
        return super().execute(context)

    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute entry node logic: place orders and track fill status.
        
        CRITICAL Node State Management:
        ================================
        This node places ONE order per activation. To prevent duplicate orders:
        - Node becomes INACTIVE after order completion
        - Parent can activate it again, but BaseNode.execute() skips INACTIVE nodes
        - Re-entry is handled by ReEntrySignalNode calling reset() + mark_active()
        
        Flow:
        1. Check if we have pending order → check fill status
        2. If order complete → store position, activate children, mark INACTIVE
        3. If no order/None status → place new order, mark PENDING (live) or INACTIVE (backtest)
        4. If order rejected → mark INACTIVE (don't retry)
        
        Args:
            context: Execution context containing current state, data, etc.
            
        Returns:
            Dict containing execution results with 'logic_completed' flag
        """
        # Get trading instrument from strategy config (not from node data!)
        if self.instrument is None:
            strategy_config = context.get('strategy_config', {})
            self.instrument = strategy_config.get('symbol', strategy_config.get('resolved_trading_instrument'))
            if not self.instrument:
                raise ValueError("❌ Trading instrument not found in strategy config!")
            log_info(f"✅ Entry Node {self.id}: Using trading instrument from strategy: {self.instrument}")
        
        current_timestamp = context.get('current_timestamp')
        mode = context.get('mode', 'backtesting')

        # Get node order status tracking
        node_states = context.get('node_states', {})
        node_state = node_states.get(self.id, {})
        
        # Initialize node_order_status dict if it doesn't exist
        if 'node_order_status' not in node_state:
            node_state['node_order_status'] = {}
        node_order_status = node_state['node_order_status']
        
        # Check if we have an order status for this node
        current_order_status = node_order_status.get(self.id)
        
        # Get pending order ID from node state (for backward compatibility)
        node_state = self._get_node_state(context)
        pending_order_id = node_state.get('pending_order_id')
        
        if pending_order_id and current_order_status:
            # We have an order - check its status from postback updates
            log_info(f"🔍 Entry Node {self.id}: Checking order status for {pending_order_id}")
            log_info(f"   Current order status: {current_order_status}")
            
            fill_status = self._check_order_fill_status(context, pending_order_id)
            
            if fill_status['is_filled']:
                # Order is COMPLETE (fully filled) - proceed with position storage
                log_info(f"✅ Entry Node {self.id}: Order {pending_order_id} is COMPLETE (fully filled)")
                
                order_data = fill_status.get('order_data', {})
                
                # Store position in global position store
                position_result = self._store_position_in_global_store(context, order_data)
                
                # Activate children (parent responsibility)
                self._activate_children(context)
                
                # Clear order tracking (node becomes INACTIVE, no re-ordering possible)
                node_order_status[self.id] = None
                self._set_node_state(context, {'pending_order_id': None})
                
                return {
                    'node_id': self.id,
                    'executed': True,
                    'order_generated': True,
                    'order': order_data,
                    'position_stored': position_result.get('success', False),
                    'position': position_result.get('position'),
                    'order_count': 1,
                    'logic_completed': True  # Order filled = deactivate self
                }
                
            elif fill_status['is_rejected']:
                # Order was REJECTED or CANCELLED - log and deactivate
                rejection_reason = fill_status.get('reason', 'Unknown reason')
                log_error(f"❌ Entry Node {self.id}: Order {pending_order_id} was REJECTED/CANCELLED")
                log_error(f"   Reason: {rejection_reason}")
                log_error(f"   ⚠️ This order will NOT be retried. Please check:")
                log_error(f"      - Insufficient funds")
                log_error(f"      - Invalid order parameters")
                log_error(f"      - Market hours")
                log_error(f"      - Broker restrictions")
                log_error(f"   💡 If you have open positions, please close them manually.")
                
                # Clear order tracking (node becomes INACTIVE, won't retry)
                node_order_status[self.id] = None
                self._set_node_state(context, {'pending_order_id': None})
                
                return {
                    'node_id': self.id,
                    'executed': False,
                    'reason': f"Order rejected/cancelled: {rejection_reason}",
                    'order_generated': False,
                    'logic_completed': True  # Rejected = deactivate self (don't retry)
                }
                
            else:
                # Order still PENDING or PARTIALLY_FILLED - keep waiting, stay active
                log_info(f"⏳ Entry Node {self.id}: Order {pending_order_id} status: {current_order_status}")
                log_info(f"   Waiting for postback to update status to COMPLETE...")
                
                return {
                    'node_id': self.id,
                    'executed': False,
                    'reason': f'Waiting for order fill (status: {current_order_status})',
                    'order_generated': True,
                    'pending_order_id': pending_order_id,
                    'logic_completed': False  # Keep node active to check again next tick
                }
        
        # NOTE: This check is now redundant because:
        # - After order completion, node becomes INACTIVE
        # - BaseNode.execute() skips logic for INACTIVE nodes
        # - This code only runs if node is ACTIVE
        # But keeping it as a safety fallback for edge cases
        if current_order_status == 'COMPLETE':
            # Safety check: order completed but node still active somehow
            log_warning(f"Entry Node {self.id}: Order COMPLETE but node still ACTIVE (unexpected state)")
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Order already completed',
                'order_generated': False,
                'logic_completed': True  # Force deactivation
            }
        
        # No order or order status is None - place new entry order
        log_info(f"📝 Entry Node {self.id}: Placing NEW entry order at {current_timestamp}")
        log_info(f"   Order status: {current_order_status} (None = ready to place)")
        log_info(f"   Mode: {mode}")
        
        order_result = self._place_entry_order(context)

        if order_result.get('success', False):
            order_data = order_result.get('order', {})
            order_id = order_data.get('order_id')
            
            print(f"✅ Order placed successfully. order_id={order_id}, mode={mode}")
            
            # For live mode: Store order_id and set status to PENDING
            if mode == 'live' and order_id:
                print(f"🔴 LIVE MODE DETECTED - Setting to PENDING")
                log_info(f"✅ Entry Node {self.id}: Order placed (ID: {order_id}), waiting for fill...")
                
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
                    'reason': 'Order placed, waiting for fill',
                    'order_generated': True,
                    'order_id': order_id,
                    'order_status': 'PENDING',
                    'logic_completed': False  # Keep active to check fill status next tick
                }
            else:
                # Backtesting mode: Immediate fill
                print(f"🟢 BACKTESTING MODE DETECTED - Filling immediately")
                position_result = self._store_position_in_global_store(context, order_data)
                self._activate_children(context)
                
                # Clear order status (node will become INACTIVE via logic_completed=True)
                # No need to track COMPLETE status - node state (INACTIVE) is the guard
                node_order_status[self.id] = None
                
                return {
                    'node_id': self.id,
                    'executed': True,
                    'order_generated': True,
                    'order': order_data,
                    'position_stored': position_result.get('success', False),
                    'position': position_result.get('position'),
                    'order_count': 1,
                    'logic_completed': True  # Becomes INACTIVE - prevents re-execution
                }
        else:
            log_error(f"❌ Entry Node {self.id}: Failed to place entry order")
            return {
                'node_id': self.id,
                'executed': False,
                'reason': order_result.get('reason', 'Unknown error'),
                'order_generated': False,
                'logic_completed': True  # Failed = deactivate self
            }

    def _check_order_fill_status(self, context: Dict[str, Any], order_id: str) -> Dict[str, Any]:
        """
        Check if an order has been filled using postback data (no API calls).
        The broker pushes order status updates via postback webhook.
        
        Args:
            context: Execution context
            order_id: Order ID to check
            
        Returns:
            Dict with fill status: {
                'is_filled': bool,
                'is_rejected': bool,
                'is_pending': bool,
                'filled_quantity': int,
                'order_data': dict,
                'reason': str (if rejected)
            }
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
            # AngelOne postback statuses: 'complete', 'rejected', 'cancelled', 'open', 'pending'
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
            log_error(f"❌ Error checking order fill status: {e}")
            # On error, assume pending to retry later
            return {
                'is_filled': False,
                'is_rejected': False,
                'is_pending': True,
                'filled_quantity': 0,
                'order_data': {},
                'reason': str(e)
            }

    # Use BaseNode._activate_children

    def _place_entry_order(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place entry order based on strategy configuration.
        
        Args:
            context: Execution context
            
        Returns:
            Dict containing order placement result
        """
        current_timestamp = context.get('current_timestamp')

        # Get position configuration from strategy JSON
        if not self.positions:
            return {
                'success': False,
                'reason': 'No position configuration found'
            }

        position_config = self.positions[0]  # Use first position configuration
        # log_debug(f"[DEBUG] EntryNode {self.id} creating position with config: {self.positions}")

        # Extract order parameters from configuration
        quantity = position_config.get('quantity', 1)  # Number of lots
        lot_size = position_config.get('lotSize', 1)   # Lot size multiplier
        actual_qty = quantity * lot_size                # Actual quantity to trade
        position_type = position_config.get('positionType', 'sell')
        order_type = position_config.get('orderType', 'market')
        product_type = position_config.get('productType', 'intraday')

        # Check if this is an options position - construct dynamic F&O symbol
        option_details = position_config.get('optionDetails')
        trading_instrument = self.instrument
        
        if option_details:
            # Construct dynamic F&O symbol from optionDetails
            # Format: SYMBOL:EXPIRY:STRIKE:TYPE
            # Example: NIFTY:W0:OTM10:CE
            expiry = option_details.get('expiry', 'W0')
            strike_type = option_details.get('strikeType', 'ATM')
            option_type = option_details.get('optionType', 'CE')
            
            trading_instrument = f"{self.instrument}:{expiry}:{strike_type}:{option_type}"
            log_info(f"📊 Entry Node: Constructed F&O symbol from optionDetails")
            log_info(f"   Base: {self.instrument}")
            log_info(f"   Dynamic: {trading_instrument}")

        # Resolve instrument if it's a dynamic F&O symbol
        resolved_instrument = trading_instrument
        print(f"\n🔍 [F&O CHECK] Trading instrument: {trading_instrument}")
        print(f"   Is dynamic F&O? {self.is_dynamic_fo_symbol(trading_instrument)}")
        
        if self.is_dynamic_fo_symbol(trading_instrument):
            print(f"   ✅ Entering F&O resolution block...")
            # Ensure F&O resolver is initialized
            self._ensure_fo_resolver(context)
            
            spot_prices = self.get_spot_prices_from_context(context)
            reference_date = context.get('current_timestamp')
            
            resolved_instrument = self.resolve_fo_symbol(
                trading_instrument,
                spot_prices,
                reference_date
            )
            
            log_info(f"🎯 Entry Node: Resolved F&O Instrument")
            log_info(f"   Dynamic: {trading_instrument}")
            log_info(f"   Resolved: {resolved_instrument}")
            
            # Load option contract data into ltp_store
            data_manager = context.get('data_manager')
            print(f"\n🔍 [OPTION LOAD CHECK]")
            print(f"   data_manager exists? {data_manager is not None}")
            print(f"   ':OPT:' in resolved_instrument? {':OPT:' in resolved_instrument}")
            print(f"   resolved_instrument = {resolved_instrument}")
            
            if data_manager and ':OPT:' in resolved_instrument:
                print(f"\n🔄 Loading option contract: {resolved_instrument}")
                option_ltp = data_manager.load_option_contract(
                    contract_key=resolved_instrument,
                    current_timestamp=current_timestamp
                )
                if option_ltp:
                    print(f"   ✅ Option LTP loaded: ₹{option_ltp:.2f}")
                else:
                    print(f"   ⚠️  Could not load option LTP (will use fallback)")
        
        # Determine exchange based on instrument type
        if ':OPT:' in resolved_instrument or ':FUT:' in resolved_instrument:
            trading_exchange = 'NFO'
        else:
            strategy_config = context.get('strategy_config', {})
            trading_exchange = strategy_config.get('exchange', 'NSE')

        # log_info(f"  📋 Placing order: {position_type.upper()} {quantity} {resolved_instrument} ({order_type})")

        # Get price from ltp_store using resolved instrument
        ltp_store = context.get('ltp_store', {})
        price = 0
        
        # Debug: Show what's in ltp_store
        print(f"\n🔍 [ENTRY DEBUG] Checking LTP for resolved instrument: {resolved_instrument}")
        print(f"   Available keys in ltp_store: {list(ltp_store.keys())}")
        
        # Try to get LTP for the resolved instrument
        if resolved_instrument in ltp_store:
            ltp_data = ltp_store.get(resolved_instrument)
            if isinstance(ltp_data, dict):
                price = ltp_data.get('ltp') or ltp_data.get('price', 0)
            else:
                price = ltp_data
            print(f"   ✅ Found LTP for {resolved_instrument}: {price}")
        else:
            print(f"   ❌ No LTP found for {resolved_instrument}")
            print(f"   Trying base instrument: {self.instrument}")
            
            # Fallback: try base instrument (for index/equity)
            if self.instrument in ltp_store:
                ltp_data = ltp_store.get(self.instrument)
                if isinstance(ltp_data, dict):
                    price = ltp_data.get('ltp') or ltp_data.get('price', 0)
                else:
                    price = ltp_data
                print(f"   ✅ Found LTP for base {self.instrument}: {price}")
        
        # Check if we have OrderManager in context (live trading)
        order_manager = context.get('order_manager')
        mode = context.get('mode', 'backtesting')
        
        if mode == 'live' and order_manager:
            # Live trading: Place real order via broker
            # Get symbol and exchange from strategy config (for live trading with modified symbols)
            strategy_config = context.get('strategy_config', {})
            trading_symbol = resolved_instrument  # Use resolved instrument
            
            # Determine exchange based on instrument type
            # If resolved symbol contains :OPT: or :FUT:, it's F&O (use NFO)
            # Otherwise use exchange from config (default NSE for equity)
            if ':OPT:' in trading_symbol or ':FUT:' in trading_symbol:
                trading_exchange = 'NFO'  # F&O instruments trade on NFO
            else:
                trading_exchange = strategy_config.get('exchange', 'NSE')
            
            log_info(f"[EntryNode DEBUG] strategy_config keys: {list(strategy_config.keys()) if strategy_config else 'NONE'}")
            log_info(f"[EntryNode DEBUG] symbol from config: {trading_symbol}, exchange: {trading_exchange}")
            log_info(f"[EntryNode] Placing LIVE order: {position_type.upper()} {quantity} {trading_symbol} on {trading_exchange}")
            
            try:
                order_result = order_manager.place_order(
                    symbol=trading_symbol,
                    exchange=trading_exchange,
                    transaction_type=position_type.upper(),  # BUY or SELL
                    quantity=quantity,
                    order_type=order_type.upper(),  # MARKET or LIMIT
                    product_type=product_type.upper(),
                    price=price if order_type.lower() != 'market' else 0,
                    node_id=self.id
                )
                
                # OrderManager returns the order object, check if broker_order_id exists
                if order_result and order_result.get('broker_order_id'):
                    log_info(f"✅ Live order placed: {order_result.get('order_id')}")
                    log_info(f"   Broker Order ID: {order_result.get('broker_order_id')}")
                    
                    # Set order_status for live trading
                    order_status = 'PENDING'
                    
                    # Create entry order with broker details
                    entry_order = {
                        'order_id': order_result.get('order_id'),
                        'broker_order_id': order_result.get('broker_order_id'),
                        'node_id': self.id,
                        'symbol': trading_symbol,  # Use actual traded symbol (resolved option contract)
                        'exchange': trading_exchange,  # Store exchange for exit
                        'order_type': order_type.upper(),
                        'side': position_type.upper(),
                        'quantity': quantity,
                        'price': price,
                        'timestamp': current_timestamp,
                        'product_type': product_type,
                        'status': order_status,
                        'fill_time': None,
                        'fill_price': None
                    }
                else:
                    log_error(f"❌ Failed to place live order: {order_result}")
                    log_error(f"   Order status: {order_result.get('status') if order_result else 'None'}")
                    log_error(f"   Error: {order_result.get('error_message') if order_result else 'Unknown'}")
                    return {
                        'success': False,
                        'reason': f"Order placement failed: {order_result.get('error_message') if order_result else 'Unknown error'}"
                    }
                    
            except Exception as e:
                from src.utils.error_handler import handle_exception
                log_error(f"❌ Error placing live order: {e}")
                
                # Critical error - order placement failed
                handle_exception(e, "entry_node_place_order", {
                    'node_id': self.id,
                    'symbol': trading_symbol,
                    'transaction_type': position_type,
                    'quantity': quantity
                }, is_critical=True, continue_execution=False)
                
                return {
                    'success': False,
                    'reason': f"Order placement error: {e}"
                }
        else:
            # Backtesting: Simulate immediate fill
            if order_type.lower() == 'market':
                order_status = 'FILLED'
                fill_time = current_timestamp
                fill_price = price
            else:
                order_status = 'PENDING'
                fill_time = None
                fill_price = None

            # Create entry order (backtesting)
            entry_order = {
                'order_id': f"ENTRY_{self.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'node_id': self.id,
                'symbol': resolved_instrument,  # Use resolved symbol
                'exchange': trading_exchange if ':OPT:' in resolved_instrument or ':FUT:' in resolved_instrument else 'NSE',
                'order_type': order_type.upper(),
                'side': position_type.upper(),
                'quantity': actual_qty,  # Actual quantity (lots * lot_size)
                'price': price,
                'timestamp': current_timestamp,
                'product_type': product_type,
                'status': order_status,
                'fill_time': fill_time,
                'fill_price': fill_price
            }

        self._orders_generated += 1

        if order_status == 'FILLED':
            # log_info(f"  📋 Entry order FILLED: {entry_order['side']} {entry_order['quantity']} @ {fill_price}")

            # Display detailed entry information
            # log_info(f"  🎯 ENTRY DETAILS:")
            # log_info(f"     📅 Entry Time: {current_timestamp}")
            # log_info(f"     💰 Entry Price: {fill_price}")
            # log_info(f"     📊 Order ID: {entry_order['order_id']}")
            # log_info(f"     🏷️  Symbol: {self.instrument}")
            # log_info(f"     📈 Side: {position_type.upper()}")
            # log_info(f"     🔢 Quantity: {quantity}")
            # log_info(f"     📋 Product Type: {product_type}")

            # Display position store information
            # log_info(f"  📦 POSITION STORE DETAILS:")
            # log_info(f"     🆔 Position ID: {position_config.get('id', 'N/A')}")
            # log_info(f"     🎯 VPI: {position_config.get('vpi', 'N/A')}")
            # log_info(f"     📊 VPT: {position_config.get('vpt', 'N/A')}")
            # log_info(f"     ⭐ Priority: {position_config.get('priority', 'N/A')}")
            # log_info(f"     🔄 Last Updated: {position_config.get('_lastUpdated', 'N/A')}")

            # Display context information
            # log_info(f"  📋 CONTEXT INFORMATION:")
            # log_info(f"     🕐 Current Tick Time: {current_timestamp}")
            # log_info(f"     💹 Current LTP: {current_tick.get('ltp', 'N/A')}")
            # log_info(f"     📊 Current Volume: {current_tick.get('volume', 'N/A')}")
            # log_info(f"     🏢 Instrument: {current_tick.get('instrument', 'N/A')}")

            # Show candles information if available
            candles_df = context.get('candles_df')
            if candles_df is not None and len(candles_df) > 0:
                latest_candle = candles_df.iloc[-1]
                # log_info(f"     🕯️  Latest Candle:")
                # log_info(f"        📈 OHLC: O={latest_candle.get('open', 'N/A')}, H={latest_candle.get('high', 'N/A')}, L={latest_candle.get('low', 'N/A')}, C={latest_candle.get('close', 'N/A')}")
                # log_info(f"        📊 Volume: {latest_candle.get('volume', 'N/A')}")

            # log_info(f"  {'='*60}")
        # else:
        # log_info(f"  📋 Entry order PENDING: {entry_order['side']} {entry_order['quantity']} @ {entry_order['price']}")

        return {
            'success': True,
            'order': entry_order
        }

    def _store_position_in_global_store(self, context: Dict[str, Any], order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store position details in the GPS (Global Position Store).
        
        Args:
            context: Execution context
            order: Order details
            
        Returns:
            Dict containing position storage result
        """
        try:
            # Get position configuration
            position_config = self.positions[0] if self.positions else {}

            # Get current tick time for GPS operations
            current_timestamp = context.get('current_timestamp')

            # Use stable position ID from JSON config (maps to Entry node). Re-entries stored as transactions.
            try:
                re_entry_num_raw = self._get_node_state(context).get('reEntryNum', 0) or 0
                re_entry_num = int(re_entry_num_raw)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"EntryNode {self.id}: Invalid reEntryNum '{re_entry_num_raw}' "
                    f"(type: {type(re_entry_num_raw).__name__}): {e}"
                ) from e
            # Prefer VPI as the stable position identifier; fallback to explicit id; finally to node-based id
            # Normalize date-dependent fields only for timestamps, not for identifiers
            position_id = position_config.get('vpi') or position_config.get('id') or f"pos_{self.id}"

            # Create entry data for GPS
            strategy_config = context.get('strategy_config', {})
            strategy_name = strategy_config.get('strategy_name', 'Unknown Strategy')

            # Extract fill price and time from order
            # Position is created only when node status is SUCCESS (order COMPLETE)
            # For live trading: use average_price (actual fill price) and completed_at
            # For backtesting: use fill_price and fill_time
            mode = context.get('mode', 'backtesting')
            
            if mode == 'live':
                # Live trading: order is COMPLETE, use actual fill data
                fill_price = order.get('average_price', 0)
                fill_time = order.get('completed_at')
                entry_time = order.get('completed_at')  # Use completed_at as entry time
            else:
                # Backtesting: use simulated fill data
                fill_price = order.get('fill_price') or order.get('price', 0)
                fill_time = order.get('fill_time')
                entry_time = order.get('timestamp')
            
            # Get lot size and calculate lots
            # order['quantity'] is the actual traded quantity (lots × lot_size)
            # lot_size comes from position config
            actual_quantity = order['quantity']
            lot_size = position_config.get('lotSize', 1)  # From config!
            lots = position_config.get('quantity', 1)  # Number of lots from config
            
            # Get underlying price at entry
            ltp_store = context.get('ltp_store', {})
            ltp_ti = ltp_store.get('ltp_TI', {})
            if isinstance(ltp_ti, dict):
                underlying_price_on_entry = ltp_ti.get('ltp') or ltp_ti.get('price', 0)
            else:
                underlying_price_on_entry = 0
            
            # Get node variables snapshot (from GPS)
            context_manager = context.get('context_manager')
            node_variables_snapshot = {}
            if context_manager:
                # Get all node variables at this moment
                node_variables_snapshot = dict(context_manager.gps.node_variables)
            
            entry_data = {
                'node_id': self.id,
                'instrument': self.instrument,  # Keep underlying for reference
                'symbol': order.get('symbol', self.instrument),  # Actual traded symbol (option contract)
                'exchange': order.get('exchange', 'NSE'),  # Exchange for exit orders
                'quantity': actual_quantity,  # MANDATORY: Actual traded quantity (lots × lot_size) for PNL calculation
                'lot_size': lot_size,  # Lot size multiplier (e.g., 50 for NIFTY)
                'lots': lots,  # Number of lots traded (e.g., 1, 2, 3)
                'price': fill_price,  # Actual average fill price (entry price)
                'entry_price': fill_price,  # Entry price for PNL calculation
                'underlying_price_on_entry': underlying_price_on_entry,  # Underlying price when position opened
                'side': position_config.get('positionType', 'buy'),
                'strategy': strategy_name,
                'order_id': order['order_id'],
                'broker_order_id': order.get('broker_order_id'),  # Add broker order ID
                'order_type': order.get('order_type', 'MARKET'),
                'product_type': position_config.get('productType', 'intraday'),
                'entry_time': entry_time.isoformat() if entry_time and hasattr(entry_time, 'isoformat') else str(entry_time),
                'fill_time': fill_time.isoformat() if fill_time and hasattr(fill_time, 'isoformat') else str(fill_time),
                'fill_price': fill_price,  # Actual average fill price
                'reEntryNum': re_entry_num,
                'node_variables': node_variables_snapshot,  # Snapshot of all node variables at entry
                'position_config': position_config  # Store full config for reference
            }

            # Add position to GPS using BaseNode method with tick time
            self.add_position(context, position_id, entry_data)
            
            print(f"✅ POSITION STORED: {position_id}")
            print(f"   Symbol: {entry_data['symbol']}")
            print(f"   Quantity: {entry_data['quantity']}")
            print(f"   Entry Price: {entry_data['entry_price']:.2f}")

            # Debug: confirm transactions count after add
            try:
                gps_pos = self.get_position(context, position_id)
                txns_cnt = len(gps_pos.get('transactions', []) or []) if gps_pos else 0
                log_info(f"EntryNode {self.id}: stored position {position_id}, reEntryNum={re_entry_num}, txns_count={txns_cnt}")
            except Exception as e:
                log_warning(f"EntryNode {self.id}: Failed to log position creation: {e}")

            self._positions_created += 1

            # log_info(f"  📦 Position stored in GPS:")
            # log_info(f"     🆔 Position ID: {position_id}")
            # log_info(f"     🏷️  Instrument: {entry_data['instrument']}")
            # log_info(f"     📊 Quantity: {entry_data['quantity']}")
            # log_info(f"     💰 Entry Price: {entry_data['price']}")
            # log_info(f"     📅 Entry Time: {entry_data['entry_time']}")
            # log_info(f"     📈 Side: {entry_data['side']}")

            return {
                'success': True,
                'position': entry_data,
                'position_id': position_id
            }

        except Exception as e:
            log_error(f"  ❌ Error storing position in GPS: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get Entry Node statistics."""
        return {
            'node_id': self.id,
            'orders_generated': self._orders_generated,
            'positions_created': self._positions_created,
            'instrument': self.instrument,
            'action_type': self.action_type
        }
