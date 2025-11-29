"""
Tick Processor for Backtesting
================================

Pure strategy execution - NO data management!

Data management (candle building, indicator updates, LTP store) 
is handled by DataManager BEFORE onTick() is called.

This module ONLY handles:
1. Reset visited flags
2. Process start node (node propagation)
3. Check termination conditions
"""

from typing import Dict, Any


def onTick(context: Dict[str, Any], tick_data: dict) -> None:
    """
    Pure strategy execution function.
    
    Called AFTER DataManager has prepared all data:
    - LTP store updated
    - Candles built
    - Indicators calculated
    - Cache updated
    
    This function ONLY handles node propagation.
    
    Args:
        context: Execution context with prepared data
            - candle_df_dict: DataFrame dict with candles + indicators
            - ltp_store: Updated LTP store
            - cache: Updated cache
            - node_instances: Node instances
            - node_states: Node states
            - gps: Global Position Store
            - current_tick: Current tick data
            - current_timestamp: Current timestamp
        tick_data: Current tick (for reference)
    """
    # ========================================================================
    # 1. RESET VISITED FLAGS
    # ========================================================================
    # Reset visited flags for all nodes (allows nodes to execute on this tick)
    node_states = context.get('node_states', {})
    for node_id in node_states:
        node_states[node_id]['visited'] = False
    
    # ========================================================================
    # 2. PROCESS START NODE (entire strategy executes here)
    # ========================================================================
    _process_start_node(context)
    
    # ========================================================================
    # 3. UPDATE GPS (after strategy execution)
    # ========================================================================
    context_manager = context.get('context_manager')
    ltp_store = context.get('ltp_store', {})
    if context_manager:
        context_manager.gps.update_position_prices(ltp_store)


def _process_start_node(context: Dict[str, Any]) -> None:
    """
    Process the Start node for the current tick.
    Mirrors live_trading_engine _process_start_node_optimized() logic.
    
    Args:
        context: Execution context
    """
    # ========================================================================
    # 1. GET/CREATE NODE INSTANCES
    # ========================================================================
    node_instances = context.get('node_instances', {})
    
    if not node_instances:
        # No nodes to process
        print("❌ No node instances found in context")
        return
    
    # ========================================================================
    # 2. FIND START NODE (with caching)
    # ========================================================================
    # Cache Start Node for performance (avoid repeated lookups)
    if '_cached_start_node' not in context:
        start_node = None
        for node_id, node in node_instances.items():
            if hasattr(node, 'type') and node.type == 'StartNode':
                start_node = node
                break
        
        if start_node is None:
            print("❌ No StartNode found in node instances")
            return
        
        context['_cached_start_node'] = start_node
    
    start_node = context['_cached_start_node']
    
    # ========================================================================
    # 3. INITIALIZE NODE STATES (First tick only)
    # ========================================================================
    if 'node_states' not in context:
        context['node_states'] = {}
        
        # Set StartNode as Active, others as Inactive
        for node_id, node in node_instances.items():
            if hasattr(node, 'type') and node.type == 'StartNode':
                context['node_states'][node_id] = {'status': 'Active', 'visited': False}
            else:
                context['node_states'][node_id] = {'status': 'Inactive', 'visited': False}
    
    # ========================================================================
    # 4. CHECK TERMINATION CONDITIONS
    # ========================================================================
    # Check if any node is NOT Inactive (Active or Pending)
    has_non_inactive_nodes = _check_any_non_inactive_nodes(node_instances, context)
    
    # Check if there are any open positions
    has_open_positions = _check_any_open_positions(context)
    
    # TERMINATE if all nodes are Inactive (regardless of positions)
    # Force square-off any open positions before terminating
    if not has_non_inactive_nodes:
        if has_open_positions:
            print("🏁 All nodes Inactive - Force closing all open positions")
            try:
                # Force square-off all positions using start_node's exit logic
                start_node._trigger_exit_node(context, reason='All nodes inactive - forced square-off')
                print(f"✅ Forced square-off completed")
            except Exception as e:
                print(f"❌ Error during forced square-off: {e}")
                import traceback
                traceback.print_exc()
        
        print("🏁 Strategy terminated - all nodes Inactive")
        context['strategy_terminated'] = True
        return
    
    # ========================================================================
    # 5. EXECUTE START NODE (Normal execution)
    # ========================================================================
    try:
        result = start_node.execute(context)
        
        # Handle end conditions
        if result and result.get('end_condition_result', {}).get('should_end', False):
            print(f"🏁 End condition met: {result['end_condition_result']['reason']}")
            context['strategy_terminated'] = True
    except Exception as e:
        print(f"❌ Error executing StartNode: {e}")
        import traceback
        traceback.print_exc()


def _check_any_non_inactive_nodes(node_instances: dict, context: dict) -> bool:
    """
    Check if there are any nodes that are NOT Inactive (i.e., Active or Pending).
    
    Args:
        node_instances: Dictionary of node instances
        context: Execution context
        
    Returns:
        True if any node is Active or Pending, False if all are Inactive
    """
    non_inactive_count = 0
    
    for node_id, node in node_instances.items():
        node_state = context.get('node_states', {}).get(node_id, {})
        status = node_state.get('status', 'Inactive')
        
        if status != 'Inactive':  # Active or Pending
            non_inactive_count += 1
    
    return non_inactive_count > 0


def _check_any_open_positions(context: Dict[str, Any]) -> bool:
    """
    Check if there are any open positions in GPS.
    
    Args:
        context: Execution context
        
    Returns:
        True if there are open positions, False otherwise
    """
    try:
        gps = context.get('gps')
        if gps:
            open_positions = gps.get_open_positions()
            return len(open_positions) > 0
        return False
    except Exception as e:
        print(f"⚠️ Error checking open positions: {e}")
        return False
