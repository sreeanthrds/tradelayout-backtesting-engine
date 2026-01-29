from datetime import datetime
from typing import Dict, List, Any, Optional

from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical, is_node_exec_log_enabled
from src.data.fo_dynamic_resolver import FODynamicResolver
import os


class BaseNode:
    """Base class for all nodes with Active/Visited flag management using ContextManager."""

    def __init__(self, node_id: str, node_type: str, name: str):
        """
        Initialize the base node.
        
        Args:
            node_id: Unique identifier for the node
            node_type: Type of the node (startNode, entrySignalNode, etc.)
            name: Display name of the node
        """
        self.id = node_id
        self.type = node_type
        self.name = name

        # Node relations (parent/child relationships) - set from JSON strategy
        self.parents = []
        self.children = []
        
        # F&O Dynamic Resolution (will be initialized with instrument_store from context)
        self.fo_resolver = None
        self.resolved_symbols = {}  # Cache for resolved symbols

    def set_relations(self, parents: List[str], children: List[str]):
        """
        Set parent-child relationships for this node.
        
        Args:
            parents: List of parent node IDs
            children: List of child node IDs
        """
        self.parents = parents
        self.children = children

    def _get_node_state(self, context) -> Dict[str, Any]:
        """Get node state from context."""
        node_states = context.get('node_states', {})
        if self.id not in node_states:
            # Initialize node state if not exists (simplified)
            node_states[self.id] = {
                'status': 'Inactive',
                'visited': False,
                'reEntryNum': 0
            }
        return node_states[self.id]

    def _set_node_state(self, context, state_updates: Dict[str, Any]):
        """Update node state in context."""
        node_states = context.get('node_states', {})
        if self.id not in node_states:
            node_states[self.id] = {
                'status': 'Inactive',
                'visited': False,
                'reEntryNum': 0
            }
        # Ensure reEntryNum key always exists
        if 'reEntryNum' not in node_states[self.id]:
            node_states[self.id]['reEntryNum'] = 0
        node_states[self.id].update(state_updates)
        context['node_states'] = node_states

    def set_status(self, context, status: str):
        """Set the node status in context."""
        self._set_node_state(context, {'status': status})

    def is_active(self, context) -> bool:
        """Check if node is active."""
        state = self._get_node_state(context)
        return state.get('status') == 'Active'

    def is_visited(self, context) -> bool:
        """Check if node has been visited in current candle."""
        state = self._get_node_state(context)
        return state.get('visited', False)

    def mark_visited(self, context):
        """Mark node as visited for current candle."""
        self._set_node_state(context, {'visited': True})

    def reset_visited(self, context):
        """Reset visited flag for new candle."""
        self._set_node_state(context, {'visited': False})

    def mark_active(self, context):
        """Mark node as active."""
        self.set_status(context, 'Active')

    def mark_inactive(self, context):
        """Mark node as inactive."""
        self.set_status(context, 'Inactive')
    
    def mark_pending(self, context):
        """Mark node as pending (logic executing)."""
        self.set_status(context, 'Pending')
    
    def is_pending(self, context) -> bool:
        """Check if node is pending."""
        state = self._get_node_state(context)
        return state.get('status') == 'Pending'

    def _update_child_reentry_num(self, context: Dict[str, Any], child_node: Any, parent_reentry_num: int) -> int:
        """
        Update child's reEntryNum based on parent policy (per-node state).
        - For normal nodes: copy parent's reEntryNum as-is.
        - For ReEntrySignalNode: set child's reEntryNum = parent_reentry_num + 1.

        Returns: child's resulting reEntryNum (int)
        """
        base_val = int(parent_reentry_num or 0)

        # Identify ReEntry node by its type flag on the instance
        if getattr(child_node, 'type', None) == 'ReEntrySignalNode':
            new_val = base_val + 1
        else:
            new_val = base_val

        child_node._set_node_state(context, {'reEntryNum': new_val})
        return new_val

    def activate_children(self, context, node_instances: Dict[str, Any]):
        """Activate all child nodes."""
        for child_id in self.children:
            if child_id in node_instances:
                child_node = node_instances[child_id]
                child_node.mark_active(context)

    def get_children(self):
        """Get all child nodes."""
        return self.children

    def get_parents(self):
        """Get all parent nodes."""
        return self.parents

    def _ensure_fo_resolver(self, context: Dict[str, Any]):
        """
        Ensure F&O resolver is initialized with instrument_store from context.
        Lazy initialization on first use.
        """
        if self.fo_resolver is None:
            instrument_store = context.get('instrument_store')
            clickhouse_client = context.get('clickhouse_client')
            mode = context.get('mode', 'live')
            
            if mode == 'backtesting':
                # Backtesting mode: use clickhouse_client
                if clickhouse_client:
                    log_info(f"✅ Initializing FODynamicResolver in backtesting mode")
                    self.fo_resolver = FODynamicResolver(
                        instrument_store=None,
                        clickhouse_client=clickhouse_client,
                        mode='backtesting'
                    )
                else:
                    log_warning("⚠️ clickhouse_client not found in context! F&O resolution will fail in backtesting.")
                    self.fo_resolver = None
            else:
                # Live mode: use instrument_store
                if instrument_store is None:
                    log_warning("⚠️ instrument_store not found in context! F&O resolution will fail.")
                    log_warning(f"   Context keys: {list(context.keys())}")
                    self.fo_resolver = None
                else:
                    # DEBUG: Check if instrument_store has data
                    total_instruments = len(instrument_store.instruments) if hasattr(instrument_store, 'instruments') else 0
                    log_info(f"✅ Initializing FODynamicResolver with instrument_store ({total_instruments} instruments)")
                    if total_instruments == 0:
                        log_warning(f"⚠️ WARNING: instrument_store has 0 instruments!")
                    self.fo_resolver = FODynamicResolver(instrument_store, mode='live')
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Template method that implements the common node execution flow.
        
        Flow:
        1. Check if already visited → Skip everything (no logic, no children)
        2. Mark as visited
        3. If ACTIVE → Change to PENDING → Execute logic
        4. If logic_completed=True → Activate children → Mark INACTIVE
        5. If logic_completed=False → Mark ACTIVE (retry next tick)
        6. Execute children (only if not visited initially)
        
        Args:
            context: Execution context containing current state, data, etc.
            
        Returns:
            Dict containing execution results
        """
        # Ensure F&O resolver is initialized
        self._ensure_fo_resolver(context)
        
        # Optional tick-specific trace
        trace_tick = os.environ.get('TRACE_TICK')
        ts = context.get('current_timestamp')
        ts_str = ts.strftime('%H:%M:%S') if hasattr(ts, 'strftime') else None

        # ====================================================================
        # CRITICAL: Check visited status first
        # If visited=True, this is the END of this sub-tree
        # No logic execution, no children execution
        # ====================================================================
        if self.is_visited(context):
            return {
                'node_id': self.id,
                'executed': False,
                'reason': 'Node already visited - subtree terminated',
                'signal_emitted': False,
                'child_results': []
            }

        # Mark as visited to prevent infinite loops
        self.mark_visited(context)
        
        # Show node identification on first tick (for ALL nodes, active or not)
        if context.get('tick_count') == 1:
            node_type_emoji = {
                'StartNode': '🟢',
                'EntrySignalNode': '🔵',
                'EntryNode': '🟡',
                'ExitSignalNode': '🟠',
                'ExitNode': '🔴'
            }
            emoji = node_type_emoji.get(self.type, '⚪')
            print(f"{emoji} I am from {self.type} (id={self.id})")

        # ====================================================================
        # STEP 1: Execute node-specific logic (ONLY if active)
        # ====================================================================
        is_active_result = self.is_active(context)
        
        # TEMP DEBUG - Check node state for first few ticks
        if hasattr(self, 'type') and self.type == 'StartNode':
            node_states = context.get('node_states', {})
            my_state = node_states.get(self.id, {})
            print(f"[DEBUG BaseNode] StartNode.execute: is_active={is_active_result}, state={my_state}")
        
        if is_active_result:
            # CRITICAL: Mark PENDING as FIRST statement before any logic execution
            self.mark_pending(context)
            
            try:
                if trace_tick and ts_str == trace_tick:
                    pass
            except Exception:
                pass
            
            # Execute node logic
            if hasattr(self, 'type') and self.type == 'StartNode':
                print(f"[DEBUG BaseNode] About to call StartNode._execute_node_logic()")
            
            node_result = self._execute_node_logic(context)
            
            if hasattr(self, 'type') and self.type == 'StartNode':
                print(f"[DEBUG BaseNode] StartNode._execute_node_logic() returned: {node_result}")
            
            try:
                if trace_tick and ts_str == trace_tick:
                    pass
            except Exception:
                pass

            # ================================================================
            # CRITICAL: Update status based on logic result
            # ================================================================
            if node_result.get('logic_completed', False):
                # SUCCESS: Activate children FIRST, then mark self INACTIVE
                # Order is critical to avoid edge cases
                
                # TEMP DEBUG
                if hasattr(self, 'type') and self.type == 'StartNode':
                    print(f"[DEBUG BaseNode] StartNode logic_completed=True, activating {len(self.children)} children: {self.children}")
                
                self._activate_children(context)
                self.mark_inactive(context)
                node_result['node_deactivated'] = True
            else:
                # FAILURE: Revert to ACTIVE for retry on next tick
                self.mark_active(context)
                node_result['node_deactivated'] = False
        else:
            # Node not active - skip logic execution but still process children
            node_result = {
                'node_id': self.id,
                'executed': False,
                'reason': 'Node not active',
                'signal_emitted': False
            }

        # ====================================================================
        # STEP 2: Execute children REGARDLESS of parent's active status
        # Children will check their own active status and execute accordingly
        # This ensures the entire tree is traversed every tick
        # ====================================================================
        try:
            if trace_tick and ts_str == trace_tick:
                pass
        except Exception:
            pass

        child_results = self._execute_children(context)

        try:
            if trace_tick and ts_str == trace_tick:
                pass
        except Exception:
            pass
        node_result['child_results'] = child_results

        return node_result

    def _execute_node_logic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Abstract method - subclasses must implement their specific logic.
        
        Args:
            context: Execution context
            
        Returns:
            Dict containing execution results with 'logic_completed' flag
        """
        raise NotImplementedError("Subclasses must implement _execute_node_logic")

    def _execute_children(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute all children nodes recursively.
        
        IMPORTANT: This method should NOT be overridden by subclasses.
        It implements the core recursive execution pattern where:
        - Children are executed regardless of their active status
        - Each child handles its own visited/active logic internally
        - This creates a natural flow through the entire node tree
        
        Args:
            context: Execution context
            
        Returns:
            List of child execution results
        """
        # Track recursion depth for monitoring and safety
        depth = context.get('_exec_depth', 0)
        context['_exec_depth'] = depth + 1
        
        # Track maximum depth seen (for post-backtest analysis)
        max_depth = context.get('_max_exec_depth', 0)
        if depth + 1 > max_depth:
            context['_max_exec_depth'] = depth + 1
            # Warn if getting unusually deep
            if depth + 1 > 100 and (depth + 1) % 50 == 0:
                log_warning(f"⚠️ Deep recursion detected: {depth + 1} levels at node {self.id}")
        
        results = []
        node_instances = context.get('node_instances', {})

        # if is_node_exec_log_enabled():
        #     log_debug(f"  🔍 {self.id} ({self.type}): Executing {len(self.children)} children")

        for child_id in self.children:
            if child_id in node_instances:
                child_node = node_instances[child_id]

                # if is_node_exec_log_enabled():
                # log_debug(f"    📋 Child {child_id} ({child_node.type}): Active={child_node.is_active(context)}, Visited={child_node.is_visited(context)}")

                # Execute child regardless of active status
                # The child's execute() method will handle visited/active logic internally
                child_result = child_node.execute(context)
                results.append(child_result)

                # if is_node_exec_log_enabled():
                # log_debug(f"    📊 Child {child_id} result: {child_result.get('executed', False)} - {child_result.get('reason', 'No reason')}")

                # TODO: Handle recursive child execution if needed
                # if child_result.get('signal_emitted', False):
                #     # Implement recursive child execution
                #     pass
            else:
                if is_node_exec_log_enabled():
                    log_warning(f"  ⚠️  Child node {child_id} not found in node instances")

        # Reset depth after executing children
        context['_exec_depth'] = depth
        
        return results

    def _execute_standardized_post_execution_logic(self, context: Dict[str, Any], node_result: Dict[str, Any],
                                                   **kwargs) -> Dict[str, Any]:
        """
        Execute standardized post-execution logic that all nodes can use.
        
        Args:
            context: Execution context
            node_result: Node execution result
            **kwargs: Additional parameters for specific node types
            
        Returns:
            Dict containing post-execution results
        """
        post_execution_results = {}

        # 1. Activate children (if any)
        if self.children:
            # if is_node_exec_log_enabled():
            # log_info(f"  📋 Activating {len(self.children)} children after {self.type} execution")
            self._activate_children(context)
            post_execution_results['children_activated'] = len(self.children)

        # 2. Trigger alert if configured
        alert_triggered = self._trigger_standardized_alert(node_result, **kwargs)
        post_execution_results['alert_triggered'] = alert_triggered

        # 3. Update node variables (if any)
        variables_updated = self._update_standardized_node_variables(context, node_result, **kwargs)
        post_execution_results['variables_updated'] = variables_updated

        # 4. Log execution event
        self._log_standardized_execution_event(context, node_result, **kwargs)
        post_execution_results['event_logged'] = True

        return post_execution_results

    def _activate_children(self, context: Dict[str, Any]):
        """
        Activate all child nodes after node execution and propagate this node's re-entry number
        to children. If reEntryNum > 0, reset children's visited to allow immediate execution.
        
        CRITICAL: This method ONLY activates children. 
        The parent's status change (PENDING → INACTIVE) is handled in execute().
        Order in execute(): _activate_children() FIRST, then mark_inactive() SECOND.
        """
        node_instances = context.get('node_instances', {})

        # Current node's re-entry number (defaults to 0)
        current_reentry_num = int(self._get_node_state(context).get('reEntryNum', 0) or 0)

        # Activate all children
        for child_id in self.children:
            if child_id in node_instances:
                child_node = node_instances[child_id]
                # TEMP DEBUG
                if hasattr(self, 'type') and self.type == 'StartNode':
                    print(f"[DEBUG] Activating child: {child_id} (type: {getattr(child_node, 'type', 'Unknown')})")
                child_node.mark_active(context)
                # Update child's reEntryNum using shared policy
                child_re = self._update_child_reentry_num(context, child_node, current_reentry_num)
                try:
                    log_info(f"{self.type} {self.id}: set child {child_id} reEntryNum={child_re} (parent={current_reentry_num})")
                except Exception:
                    pass
                # Always reset visited on activation (parent can forcibly unvisit children)
                try:
                    child_node.reset_visited(context)
                    try:
                        log_info(f"{self.type} {self.id}: child {child_id} visited_reset=True")
                    except Exception:
                        pass
                except Exception:
                    pass

    def _trigger_standardized_alert(self, node_result: Dict[str, Any], **kwargs) -> bool:
        """
        Trigger standardized alert notification.
        
        Args:
            node_result: Node execution result
            **kwargs: Additional parameters for specific node types
            
        Returns:
            True if alert was triggered, False otherwise
        """
        # TODO: Implement standardized alert notification logic
        # This could send emails, webhooks, etc.
        # if is_node_exec_log_enabled():
        # log_info(f"�� Standardized alert triggered for {self.id}: {self.type} executed successfully")
        return True

    def _update_standardized_node_variables(self, context: Dict[str, Any], node_result: Dict[str, Any],
                                            **kwargs) -> bool:
        """
        Update standardized node variables after execution.
        
        Args:
            context: Execution context
            node_result: Node execution result
            **kwargs: Additional parameters for specific node types
            
        Returns:
            True if variables were updated, False otherwise
        """
        # TODO: Implement standardized node variable updates
        # This could update context with execution details for other nodes to use
        # if is_node_exec_log_enabled():
        # log_info(f"📊 Standardized node variables updated for {self.id}")
        return True

    def _log_standardized_execution_event(self, context: Dict[str, Any], node_result: Dict[str, Any], **kwargs):
        """
        Log standardized execution event for tracking and analysis.
        
        Args:
            context: Execution context
            node_result: Node execution result
            **kwargs: Additional parameters for specific node types
        """
        # Get context manager if available
        context_manager = context.get('context_manager')
        if context_manager and hasattr(context_manager, 'log_event'):
            event = {
                'type': f'{self.type.lower()}_executed',
                'node_id': self.id,
                'node_type': self.type,
                'timestamp': datetime.now().isoformat(),
                'success': node_result.get('executed', False),
                'logic_completed': node_result.get('logic_completed', False),
                'node_result': node_result
            }
            context_manager.log_event(event)
            # if is_node_exec_log_enabled():
            # log_info(f"📝 {self.type} execution event logged")

    def reset(self, context):
        """Reset node state for new execution."""
        self.reset_visited(context)

    def get_status_info(self, context) -> Dict[str, Any]:
        """Get comprehensive status information for this node."""
        state = self._get_node_state(context)
        return {
            'node_id': self.id,
            'node_type': self.type,
            'name': self.name,
            'status': state.get('status', 'Unknown'),
            'visited': state.get('visited', False),
            'parents': self.parents,
            'children': self.children
        }

    # GPS Access Methods
    def get_gps(self, context) -> Any:
        """Get GPS instance from context manager."""
        context_manager = context.get('context_manager')
        if context_manager:
            return context_manager.get_gps()
        return None

    def add_position(self, context, position_id: str, entry_data: Dict[str, Any]):
        """Add a position to GPS."""
        context_manager = context.get('context_manager')
        if context_manager:
            # Get current tick time from context
            current_timestamp = context.get('current_timestamp')
            # Attach this node's reEntryNum to entry_data for GPS tracking
            node_reentry = int(self._get_node_state(context).get('reEntryNum', 0) or 0)
            if isinstance(entry_data, dict):
                entry_data.setdefault('reEntryNum', node_reentry)
            context_manager.add_position(position_id, entry_data, current_timestamp)
            # Mark the tick timestamp to allow downstream nodes to avoid same-tick exit
            context['_just_created_position_tick_ts'] = current_timestamp

    def close_position(self, context, position_id: str, exit_data: Dict[str, Any]):
        """Close a position in GPS."""
        context_manager = context.get('context_manager')
        if context_manager:
            # Get current tick time from context
            current_timestamp = context.get('current_timestamp')
            # Attach this node's reEntryNum to exit_data for GPS tracking
            node_reentry = int(self._get_node_state(context).get('reEntryNum', 0) or 0)
            if isinstance(exit_data, dict):
                exit_data.setdefault('reEntryNum', node_reentry)
            context_manager.close_position(position_id, exit_data, current_timestamp)

    def get_position(self, context, position_id: str) -> Optional[Dict[str, Any]]:
        """Get position data from GPS."""
        context_manager = context.get('context_manager')
        if context_manager:
            return context_manager.get_position(position_id)
        return None

    def get_open_positions(self, context) -> Dict[str, Dict[str, Any]]:
        """Get all open positions from GPS."""
        context_manager = context.get('context_manager')
        if context_manager:
            return context_manager.get_open_positions()
        return {}

    def get_closed_positions(self, context) -> Dict[str, Dict[str, Any]]:
        """Get all closed positions from GPS."""
        context_manager = context.get('context_manager')
        if context_manager:
            return context_manager.get_closed_positions()
        return {}

    def set_node_variable(self, context, variable_name: str, value: Any):
        """Set a node variable in GPS."""
        context_manager = context.get('context_manager')
        if context_manager:
            context_manager.set_node_variable(self.id, variable_name, value)

    def get_node_variable(self, context, variable_name: str) -> Optional[Any]:
        """Get a node variable from GPS."""
        context_manager = context.get('context_manager')
        if context_manager:
            return context_manager.get_node_variable(self.id, variable_name)
        return None

    def get_node_variables(self, context) -> Dict[str, Any]:
        """Get all variables for this node from GPS."""
        context_manager = context.get('context_manager')
        if context_manager:
            return context_manager.get_node_variables(self.id)
        return {}
    
    # F&O Dynamic Resolution Methods
    
    def is_dynamic_fo_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is a dynamic F&O format.
        
        Args:
            symbol: Symbol to check
        
        Returns:
            True if dynamic F&O symbol, False otherwise
        
        Examples:
            is_dynamic_fo_symbol('NIFTY:M0:FUT') → True
            is_dynamic_fo_symbol('NIFTY:W0:ATM:CE') → True
            is_dynamic_fo_symbol('RELIANCE') → False
        """
        if not symbol or ':' not in symbol:
            return False
        
        # Check for expiry codes (W0-W4, M0-M2, Q0-Q1, Y0-Y1)
        expiry_codes = ['W0', 'W1', 'W2', 'W3', 'W4', 
                       'M0', 'M1', 'M2', 
                       'Q0', 'Q1', 
                       'Y0', 'Y1']
        
        return any(code in symbol for code in expiry_codes)
    
    def resolve_fo_symbol(
        self,
        dynamic_symbol: str,
        spot_prices: Dict[str, float],
        reference_date: Any = None
    ) -> str:
        """
        Resolve dynamic F&O symbol to universal format.
        
        Args:
            dynamic_symbol: Dynamic symbol (e.g., NIFTY:M0:FUT, GOLD:M0:ATM:CE)
            spot_prices: Dictionary of spot prices {symbol: price}
            reference_date: Reference date for resolution (default: today)
        
        Returns:
            Universal symbol format
        
        Examples:
            resolve_fo_symbol('NIFTY:M0:FUT', {}) 
            → 'NIFTY:2024-11-21:FUT'
            
            resolve_fo_symbol('NIFTY:W0:ATM:CE', {'NIFTY': 19547})
            → 'NIFTY:2024-11-21:OPT:19550:CE'
        """
        # Check if already resolved (cached)
        cache_key = f"{dynamic_symbol}_{reference_date}"
        if cache_key in self.resolved_symbols:
            return self.resolved_symbols[cache_key]
        
        # Check if it's a dynamic symbol
        if not self.is_dynamic_fo_symbol(dynamic_symbol):
            return dynamic_symbol
        
        # Resolve using F&O resolver
        try:
            if self.fo_resolver is None:
                raise ValueError("FODynamicResolver not initialized! instrument_store missing from context.")
            
            resolved = self.fo_resolver.resolve(
                dynamic_symbol,
                spot_prices,
                reference_date
            )
            
            # Cache the result
            self.resolved_symbols[cache_key] = resolved
            
            log_info(f"📊 F&O Resolution: {dynamic_symbol} → {resolved}")
            
            return resolved
        except Exception as e:
            log_error(f"❌ F&O Resolution failed for {dynamic_symbol}: {e}")
            log_error(f"   Spot prices: {spot_prices}")
            log_error(f"   Reference date: {reference_date}")
            log_error(f"   ⚠️ CRITICAL: Returning unresolved symbol - ORDER WILL LIKELY FAIL!")
            raise ValueError(f"F&O resolution failed for {dynamic_symbol}: {e}") from e
    
    def resolve_fo_symbols_batch(
        self,
        dynamic_symbols: List[str],
        spot_prices: Dict[str, float],
        reference_date: Any = None
    ) -> Dict[str, str]:
        """
        Resolve multiple dynamic F&O symbols in batch.
        
        Args:
            dynamic_symbols: List of dynamic symbols
            spot_prices: Dictionary of spot prices
            reference_date: Reference date for resolution
        
        Returns:
            Dictionary mapping dynamic symbols to universal symbols
        """
        results = {}
        
        for symbol in dynamic_symbols:
            results[symbol] = self.resolve_fo_symbol(
                symbol,
                spot_prices,
                reference_date
            )
        
        return results
    
    def get_spot_prices_from_context(self, context: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract spot prices from context for F&O resolution.
        
        Args:
            context: Execution context
        
        Returns:
            Dictionary of spot prices {symbol: price}
        """
        spot_prices = {}
        
        # Try to get from current tick
        current_tick = context.get('current_tick', {})
        
        # Get trading instrument from strategy config
        strategy_config = context.get('strategy_config', {})
        trading_instrument = strategy_config.get('trading_instrument', {})
        
        # Extract symbol and price
        symbol = strategy_config.get('symbol')
        if symbol and current_tick:
            price = current_tick.get('ltp') or current_tick.get('close') or current_tick.get('price')
            if price:
                spot_prices[symbol] = float(price)
        
        # If not found in current_tick, try ltp_store (for live mode)
        if symbol and symbol not in spot_prices:
            ltp_store = context.get('ltp_store', {})
            ltp_ti = ltp_store.get('ltp_TI', {})
            if isinstance(ltp_ti, dict):
                price = ltp_ti.get('ltp') or ltp_ti.get('price')
                if price:
                    spot_prices[symbol] = float(price)
        
        # Also check for spot prices explicitly stored in context
        context_spot_prices = context.get('spot_prices', {})
        spot_prices.update(context_spot_prices)
        
        return spot_prices
