#!/usr/bin/env python3
"""
Generate complete dashboard data for backtest results
Captures all entry/exit details for UI display
"""
import os
import sys
import json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['SUPABASE_URL'] = 'https://oonepfqgzpdssfzvokgk.supabase.co'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MDE5OTkxNCwiZXhwIjoyMDY1Nzc1OTE0fQ.qmUNhAh3oVhPW2lcAkw7E2Z19MenEIoWCBXCR9Hq6Kg'

from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
from src.backtesting.backtest_config import BacktestConfig
from datetime import date
from src.core.gps import GlobalPositionStore

# Dashboard data structure
dashboard_data = {
    'strategy_id': '4a7a1a31-e209-4b23-891a-3899fb8e4c28',
    'backtest_date': '2024-10-01',
    'positions': [],
    'summary': {}
}

# Track all operations
orig_add = GlobalPositionStore.add_position
orig_close = GlobalPositionStore.close_position

def track_add(self, pos_id, entry_data, tick_time=None):
    """Track position entry with all details"""
    symbol = entry_data.get('symbol', 'N/A')
    
    # Extract strike and option type
    strike, opt_type, expiry = 'N/A', 'N/A', 'N/A'
    if ':OPT:' in symbol:
        parts = symbol.split(':')
        if len(parts) >= 5:
            expiry = parts[1]
            strike = parts[3]
            opt_type = parts[4]
    
    # Get NIFTY spot price
    ltp_store = entry_data.get('ltp_store', {})
    nifty_spot = 0
    if 'NIFTY' in ltp_store:
        nifty_data = ltp_store['NIFTY']
        if isinstance(nifty_data, dict):
            nifty_spot = nifty_data.get('ltp', 0)
        else:
            nifty_spot = nifty_data
    
    # Create position entry
    position_entry = {
        'position_id': pos_id,
        'strategy_id': entry_data.get('strategy_id', 'N/A'),  # MULTI-STRATEGY: Track which strategy owns this position
        'entry_node_id': entry_data.get('node_id', 'N/A'),
        'entry_time': tick_time.isoformat() if hasattr(tick_time, 'isoformat') else str(tick_time),
        'entry_timestamp': tick_time.strftime('%H:%M:%S') if hasattr(tick_time, 'strftime') else str(tick_time),
        'instrument': entry_data.get('instrument', 'N/A'),
        'symbol': symbol,
        'strike': strike,
        'option_type': opt_type,
        'expiry': expiry,
        'entry_price': entry_data.get('price', 0),
        'quantity': entry_data.get('quantity', 0),
        'lot_size': entry_data.get('lot_size', 1),
        'lots': entry_data.get('lots', 1),
        'side': entry_data.get('side', 'BUY'),
        'order_type': entry_data.get('order_type', 'MARKET'),
        'order_id': entry_data.get('order_id', 'N/A'),
        're_entry_num': entry_data.get('reEntryNum', 0),
        'nifty_spot_at_entry': nifty_spot,
        'exchange': entry_data.get('exchange', 'NSE'),
        'product_type': entry_data.get('product_type', 'INTRADAY'),
        'status': 'OPEN',
        'exit_node_id': None,
        'exit_time': None,
        'exit_timestamp': None,
        'exit_price': None,
        'exit_reason': None,
        'duration_seconds': None,
        'duration_minutes': None,
        'pnl': None,
        'pnl_percentage': None
    }
    
    dashboard_data['positions'].append(position_entry)
    
    return orig_add(self, pos_id, entry_data, tick_time)

def track_close(self, pos_id, exit_data, tick_time=None):
    """Track position exit with all details"""
    pos = self.get_position(pos_id)
    if pos:
        # Find the position entry in dashboard data
        position_entry = None
        for p in dashboard_data['positions']:
            if p['position_id'] == pos_id and p['status'] == 'OPEN':
                # Check if strikes match (for re-entries)
                symbol = pos.get('symbol', '')
                strike = 'N/A'
                if ':OPT:' in symbol:
                    parts = symbol.split(':')
                    if len(parts) >= 5:
                        strike = parts[3]
                
                if p['strike'] == strike:
                    position_entry = p
                    break
        
        if position_entry:
            ep = pos.get('entry_price', 0)
            xp = exit_data.get('price', 0)
            qty = pos.get('quantity', 0)
            side = pos.get('side', 'BUY')
            
            # Calculate P&L
            if side.upper() == 'BUY':
                pnl = (xp - ep) * qty
            else:
                pnl = (ep - xp) * qty
            
            # Calculate P&L percentage
            pnl_pct = (pnl / (ep * qty) * 100) if (ep * qty) != 0 else 0
            
            # Calculate duration
            entry_time = datetime.fromisoformat(position_entry['entry_time']) if isinstance(position_entry['entry_time'], str) else position_entry['entry_time']
            if hasattr(tick_time, 'total_seconds'):
                exit_time = tick_time
            elif isinstance(tick_time, str):
                exit_time = datetime.fromisoformat(tick_time)
            else:
                exit_time = tick_time
            
            duration_seconds = (exit_time - entry_time).total_seconds()
            duration_minutes = duration_seconds / 60
            
            # Update position entry with exit details
            position_entry['status'] = 'CLOSED'
            position_entry['exit_node_id'] = exit_data.get('node_id', 'N/A')
            position_entry['exit_time'] = exit_time.isoformat() if hasattr(exit_time, 'isoformat') else str(exit_time)
            position_entry['exit_timestamp'] = exit_time.strftime('%H:%M:%S') if hasattr(exit_time, 'strftime') else str(exit_time)
            position_entry['exit_price'] = xp
            position_entry['exit_reason'] = exit_data.get('reason', 'exit_signal')
            position_entry['duration_seconds'] = round(duration_seconds, 2)
            position_entry['duration_minutes'] = round(duration_minutes, 2)
            position_entry['pnl'] = round(pnl, 2)
            position_entry['pnl_percentage'] = round(pnl_pct, 2)
    
    return orig_close(self, pos_id, exit_data, tick_time)

GlobalPositionStore.add_position = track_add
GlobalPositionStore.close_position = track_close

def run_dashboard_backtest(strategy_id: str, backtest_date):
    """
    Run a backtest for a specific strategy and date, returning dashboard data.
    
    Args:
        strategy_id: UUID string of the strategy
        backtest_date: date object for the backtest
        
    Returns:
        Dictionary with strategy_id, positions, and summary
    """
    # Reset dashboard_data for this run
    dashboard_data['positions'] = []
    dashboard_data['strategy_id'] = strategy_id
    dashboard_data['backtest_date'] = backtest_date.strftime('%Y-%m-%d') if hasattr(backtest_date, 'strftime') else str(backtest_date)
    
    # Run the backtest
    config = BacktestConfig(
        strategy_ids=[strategy_id],
        backtest_date=backtest_date if isinstance(backtest_date, date) else date.fromisoformat(str(backtest_date)),
        debug_mode=None
    )
    
    engine = CentralizedBacktestEngine(config)
    engine.run()
    
    # Extract diagnostics from engine
    diagnostics_export = {}
    if hasattr(engine, 'centralized_processor'):
        # Get diagnostics from strategy_state (centralized processor)
        active_strategies = engine.centralized_processor.strategy_manager.active_strategies
        
        # For single-strategy backtests, get first strategy
        if active_strategies:
            strategy_state = list(active_strategies.values())[0]
            diagnostics = strategy_state.get('diagnostics')
            
            if diagnostics:
                # NOTE: current_state is NOT included for backtesting.
                # It's only relevant for live simulation where we need real-time state tracking.
                # For backtesting, we only need the events_history for UI diagnostics.
                diagnostics_export = {
                    'events_history': diagnostics.get_all_events({
                        'node_events_history': strategy_state.get('node_events_history', {})
                    })
                }
    elif hasattr(engine, 'context_adapter'):
        # Fallback: Old engine using context_adapter
        # NOTE: current_state is NOT included for backtesting (only for live simulation)
        diagnostics = engine.context_adapter.diagnostics
        diagnostics_export = {
            'events_history': diagnostics.get_all_events({'node_events_history': engine.context_adapter.node_events_history})
        }
    
    dashboard_data['diagnostics'] = diagnostics_export
    
    # Calculate summary statistics
    positions = dashboard_data['positions']
    closed_positions = [p for p in positions if p['status'] == 'CLOSED']
    open_positions = [p for p in positions if p['status'] == 'OPEN']
    
    total_pnl = sum(p['pnl'] for p in closed_positions if p['pnl'] is not None)
    winning_trades = [p for p in closed_positions if p['pnl'] and p['pnl'] > 0]
    losing_trades = [p for p in closed_positions if p['pnl'] and p['pnl'] < 0]
    breakeven_trades = [p for p in closed_positions if p['pnl'] == 0]
    
    avg_win = sum(p['pnl'] for p in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(p['pnl'] for p in losing_trades) / len(losing_trades) if losing_trades else 0
    avg_duration = sum(p['duration_minutes'] for p in closed_positions if p['duration_minutes']) / len(closed_positions) if closed_positions else 0
    
    dashboard_data['summary'] = {
        'total_positions': len(positions),
        'closed_positions': len(closed_positions),
        'open_positions': len(open_positions),
        'total_pnl': round(total_pnl, 2),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'breakeven_trades': len(breakeven_trades),
        'win_rate': round(len(winning_trades) / len(closed_positions) * 100, 2) if closed_positions else 0,
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'avg_duration_minutes': round(avg_duration, 2),
        'largest_win': round(max((p['pnl'] for p in closed_positions if p['pnl']), default=0), 2),
        'largest_loss': round(min((p['pnl'] for p in closed_positions if p['pnl']), default=0), 2),
        're_entries': len([p for p in positions if p['re_entry_num'] > 0])
    }
    
    return dict(dashboard_data)


def _build_flow_chain(events_history: dict, exec_id: str, max_depth: int = 50) -> list:
    """Build flow chain from current node back to start/trigger."""
    chain = [exec_id]
    current_id = exec_id
    depth = 0
    
    while current_id and current_id in events_history and depth < max_depth:
        event = events_history[current_id]
        parent_id = event.get('parent_execution_id')
        
        if parent_id and parent_id in events_history:
            parent_event = events_history[parent_id]
            node_type = parent_event.get('node_type', '')
            
            if any(keyword in node_type for keyword in ['Signal', 'Condition', 'Start', 'Entry', 'Exit']):
                chain.append(parent_id)
            
            current_id = parent_id
            depth += 1
        else:
            break
    
    return list(reversed(chain))

def _extract_flow_ids(events_history: dict, node_id: str, timestamp: str) -> list:
    """Extract execution_ids (flow_ids) for a specific node execution"""
    if not events_history or not node_id:
        return []
    
    # Try to find matching node execution
    for exec_id, event in events_history.items():
        if event.get('node_id') == node_id:
            event_time = event.get('timestamp', '')
            if timestamp and event_time:
                # Extract HH:MM:SS from diagnostic timestamp
                # Event time format: "2024-10-28 09:18:00+05:30" or similar
                # Position timestamp format: "09:18:41"
                diagnostic_time = ''
                if len(event_time) >= 19:
                    diagnostic_time = event_time[11:19]  # "09:18:00"
                elif 'T' in event_time:
                    # ISO format: "2024-10-01T09:18:41"
                    diagnostic_time = event_time.split('T')[1][:8]
                
                # Compare HH:MM (first 5 chars) for more lenient matching
                if diagnostic_time[:5] == timestamp[:5]:
                    return _build_flow_chain(events_history, exec_id)
    
    # Fallback: just find by node_id without timestamp
    for exec_id, event in events_history.items():
        if event.get('node_id') == node_id:
            return _build_flow_chain(events_history, exec_id)
    
    return []

def run_multi_strategy_backtest(strategy_ids: list, backtest_date, scales: dict = None):
    """
    MULTI-STRATEGY: Run backtest for multiple strategies simultaneously.
    
    Args:
        strategy_ids: List of strategy UUID strings
        backtest_date: date object for the backtest
        scales: Optional dict of strategy_id -> scale multiplier
        
    Returns:
        Dictionary with:
        - strategies: Dict[strategy_id] -> {positions, summary, diagnostics}
        - combined_summary: Aggregated summary across all strategies
    """
    from typing import List
    
    # Reset dashboard_data for this run
    dashboard_data['positions'] = []
    dashboard_data['backtest_date'] = backtest_date.strftime('%Y-%m-%d') if hasattr(backtest_date, 'strftime') else str(backtest_date)
    
    # Run the backtest with ALL strategies
    config = BacktestConfig(
        strategy_ids=strategy_ids,
        backtest_date=backtest_date if isinstance(backtest_date, date) else date.fromisoformat(str(backtest_date)),
        debug_mode=None,
        scales=scales  # Pass scales to engine config
    )
    
    engine = CentralizedBacktestEngine(config)
    engine.run()
    
    # Build per-strategy results
    results = {
        'backtest_date': dashboard_data['backtest_date'],
        'strategies': {},
        'combined_summary': {}
    }
    
    # Group positions by strategy_id
    positions_by_strategy = {}
    positions_without_strategy = []
    
    print(f"[DEBUG] Total positions in dashboard_data: {len(dashboard_data['positions'])}")
    
    for pos in dashboard_data['positions']:
        sid = pos.get('strategy_id', 'unknown')
        if sid == 'unknown' or not sid:
            positions_without_strategy.append(pos)
            print(f"[DEBUG] Position without strategy_id: {pos.get('position_id', 'N/A')} - strategy: {pos.get('strategy', 'N/A')}")
        else:
            if sid not in positions_by_strategy:
                positions_by_strategy[sid] = []
            positions_by_strategy[sid].append(pos)
    
    print(f"[DEBUG] Positions without strategy_id: {len(positions_without_strategy)}")
    print(f"[DEBUG] Positions by strategy: {[(sid, len(positions)) for sid, positions in positions_by_strategy.items()]}")
    
    # TEMPORARY: Include positions without strategy_id in the first strategy for debugging
    if positions_without_strategy and strategy_ids:
        first_strategy = strategy_ids[0]
        if first_strategy not in positions_by_strategy:
            positions_by_strategy[first_strategy] = []
        positions_by_strategy[first_strategy].extend(positions_without_strategy)
        print(f"[DEBUG] Added {len(positions_without_strategy)} positions without strategy_id to {first_strategy}")
    
    # Extract diagnostics per strategy - use the strategy_ids from the request as keys
    diagnostics_by_strategy = {}
    all_events_history = {}  # Collect all events
    
    if hasattr(engine, 'centralized_processor'):
        active_strategies = engine.centralized_processor.strategy_manager.active_strategies
        print(f"[DEBUG] Found {len(active_strategies)} active strategies")
        print(f"[DEBUG] Requested strategy_ids: {strategy_ids}")
        
        for instance_id, strategy_state in active_strategies.items():
            print(f"[DEBUG] Processing instance: {instance_id}")
            
            # The strategy_id is stored directly in strategy_state
            sid = strategy_state.get('strategy_id', '')
            print(f"[DEBUG] Strategy ID from state: '{sid}'")
            
            diagnostics = strategy_state.get('diagnostics')
            if diagnostics:
                events = diagnostics.get_all_events({
                    'node_events_history': strategy_state.get('node_events_history', {})
                })
                print(f"[DEBUG] Found {len(events)} diagnostic events")
                
                # Store by the actual strategy_id from state
                if sid:
                    diagnostics_by_strategy[sid] = {
                        'events_history': events
                    }
                
                # Also collect all events
                all_events_history.update(events)
            else:
                print(f"[DEBUG] No diagnostics found for instance {instance_id}")
    
    # If we have strategy_ids in request but no matching diagnostics, use all events for all strategies
    if all_events_history and not diagnostics_by_strategy:
        print(f"[DEBUG] Using all events ({len(all_events_history)}) for all strategies")
        for sid in strategy_ids:
            diagnostics_by_strategy[sid] = {
                'events_history': all_events_history
            }
    
    print(f"[DEBUG] Final diagnostics_by_strategy keys: {list(diagnostics_by_strategy.keys())}")
    
    # Calculate per-strategy summaries
    all_positions = []
    for sid in strategy_ids:
        positions = positions_by_strategy.get(sid, [])
        all_positions.extend(positions)
        
        closed_positions = [p for p in positions if p['status'] == 'CLOSED']
        open_positions = [p for p in positions if p['status'] == 'OPEN']
        
        total_pnl = sum(p['pnl'] for p in closed_positions if p['pnl'] is not None)
        winning_trades = [p for p in closed_positions if p['pnl'] and p['pnl'] > 0]
        losing_trades = [p for p in closed_positions if p['pnl'] and p['pnl'] < 0]
        breakeven_trades = [p for p in closed_positions if p['pnl'] == 0]
        
        avg_win = sum(p['pnl'] for p in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(p['pnl'] for p in losing_trades) / len(losing_trades) if losing_trades else 0
        avg_duration = sum(p['duration_minutes'] for p in closed_positions if p['duration_minutes']) / len(closed_positions) if closed_positions else 0
        
        # Add flow_ids to each position for UI flow diagrams
        diagnostics = diagnostics_by_strategy.get(sid, {})
        events_history = diagnostics.get('events_history', {})
        
        print(f"[DEBUG] Strategy {sid}: {len(events_history)} events in diagnostics")
        print(f"[DEBUG] Available strategy IDs in diagnostics: {list(diagnostics_by_strategy.keys())}")
        
        for pos in positions:
            entry_node = pos.get('entry_node_id')
            entry_ts = pos.get('entry_timestamp')
            
            # Extract entry flow_ids
            entry_flow_ids = _extract_flow_ids(events_history, entry_node, entry_ts)
            pos['entry_flow_ids'] = entry_flow_ids
            
            # Extract exit flow_ids
            exit_flow_ids = []
            if pos.get('status') == 'CLOSED':
                exit_node = pos.get('exit_node_id')
                exit_ts = pos.get('exit_timestamp')
                exit_flow_ids = _extract_flow_ids(events_history, exit_node, exit_ts)
            pos['exit_flow_ids'] = exit_flow_ids
            
            print(f"[DEBUG] Position {pos.get('position_id')}: entry_node={entry_node}, entry_ts={entry_ts}, entry_flows={len(entry_flow_ids)}, exit_flows={len(exit_flow_ids)}")
        
        results['strategies'][sid] = {
            'strategy_id': sid,
            'positions': positions,
            'diagnostics': diagnostics,
            'summary': {
                'total_positions': len(positions),
                'closed_positions': len(closed_positions),
                'open_positions': len(open_positions),
                'total_pnl': round(total_pnl, 2),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'breakeven_trades': len(breakeven_trades),
                'win_rate': round(len(winning_trades) / len(closed_positions) * 100, 2) if closed_positions else 0,
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'avg_duration_minutes': round(avg_duration, 2),
                'largest_win': round(max((p['pnl'] for p in closed_positions if p['pnl']), default=0), 2),
                'largest_loss': round(min((p['pnl'] for p in closed_positions if p['pnl']), default=0), 2),
                're_entries': len([p for p in positions if p['re_entry_num'] > 0])
            }
        }
    
    # Calculate combined summary across all strategies
    all_closed = [p for p in all_positions if p['status'] == 'CLOSED']
    all_open = [p for p in all_positions if p['status'] == 'OPEN']
    
    combined_pnl = sum(p['pnl'] for p in all_closed if p['pnl'] is not None)
    combined_winners = [p for p in all_closed if p['pnl'] and p['pnl'] > 0]
    combined_losers = [p for p in all_closed if p['pnl'] and p['pnl'] < 0]
    
    results['combined_summary'] = {
        'strategy_count': len(strategy_ids),
        'total_positions': len(all_positions),
        'closed_positions': len(all_closed),
        'open_positions': len(all_open),
        'combined_pnl': round(combined_pnl, 2),
        'winning_trades': len(combined_winners),
        'losing_trades': len(combined_losers),
        'win_rate': round(len(combined_winners) / len(all_closed) * 100, 2) if all_closed else 0
    }
    
    return results


def format_value_for_display(value, expr_str):
    """
    Format a value for display in diagnostics.
    
    Args:
        value: The value to format
        expr_str: String representation of the expression
        
    Returns:
        Formatted string
    """
    if value is None:
        return "None"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return f"{value:.2f}" if isinstance(value, float) else str(value)
    return str(value)

def substitute_condition_values(preview_str, diagnostic_data):
    """
    Substitute variable names with their actual values in a condition preview string.
    
    Args:
        preview_str: The condition preview string
        diagnostic_data: Dictionary containing condition evaluation data
        
    Returns:
        String with substituted values
    """
    if not diagnostic_data or 'conditions' not in diagnostic_data:
        return preview_str
    
    result = preview_str
    for cond in diagnostic_data.get('conditions', []):
        if 'lhs_expr' in cond and 'lhs_value' in cond:
            lhs_expr = str(cond['lhs_expr'])
            lhs_val = format_value_for_display(cond['lhs_value'], lhs_expr)
            result = result.replace(lhs_expr, lhs_val)
        
        if 'rhs_expr' in cond and 'rhs_value' in cond:
            rhs_expr = str(cond['rhs_expr'])
            rhs_val = format_value_for_display(cond['rhs_value'], rhs_expr)
            result = result.replace(rhs_expr, rhs_val)
    
    return result

if __name__ == "__main__":
    print('='*80)
    print('GENERATING DASHBOARD DATA')
    print('='*80)

    config = BacktestConfig(
        strategy_ids=['4a7a1a31-e209-4b23-891a-3899fb8e4c28'],
        backtest_date=date(2024, 10, 1),
        debug_mode=None
    )

    engine = CentralizedBacktestEngine(config)
    engine.run()

    # Calculate summary statistics
    positions = dashboard_data['positions']
    closed_positions = [p for p in positions if p['status'] == 'CLOSED']
    open_positions = [p for p in positions if p['status'] == 'OPEN']

    total_pnl = sum(p['pnl'] for p in closed_positions if p['pnl'] is not None)
    winning_trades = [p for p in closed_positions if p['pnl'] and p['pnl'] > 0]
    losing_trades = [p for p in closed_positions if p['pnl'] and p['pnl'] < 0]
    breakeven_trades = [p for p in closed_positions if p['pnl'] == 0]

    avg_win = sum(p['pnl'] for p in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(p['pnl'] for p in losing_trades) / len(losing_trades) if losing_trades else 0
    avg_duration = sum(p['duration_minutes'] for p in closed_positions if p['duration_minutes']) / len(closed_positions) if closed_positions else 0

    dashboard_data['summary'] = {
        'total_positions': len(positions),
        'closed_positions': len(closed_positions),
        'open_positions': len(open_positions),
        'total_pnl': round(total_pnl, 2),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'breakeven_trades': len(breakeven_trades),
        'win_rate': round(len(winning_trades) / len(closed_positions) * 100, 2) if closed_positions else 0,
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'avg_duration_minutes': round(avg_duration, 2),
        'largest_win': round(max((p['pnl'] for p in closed_positions if p['pnl']), default=0), 2),
        'largest_loss': round(min((p['pnl'] for p in closed_positions if p['pnl']), default=0), 2),
        're_entries': len([p for p in positions if p['re_entry_num'] > 0])
    }

    # Display formatted results
    print('\n' + '='*80)
    print('📊 DASHBOARD DATA')
    print('='*80)

    print(f"\n{'='*80}")
    print('📝 ALL POSITIONS')
    print(f"{'='*80}")

    for i, pos in enumerate(positions, 1):
        re_entry_label = f" (RE-ENTRY {pos['re_entry_num']})" if pos['re_entry_num'] > 0 else ""
        status_icon = '✅' if pos['status'] == 'CLOSED' else '⏳'
        
        print(f"\n{i}. {status_icon} Position {pos['position_id']}{re_entry_label}")
        print(f"   Contract: {pos['symbol']}")
        print(f"   Strike: {pos['strike']} {pos['option_type']}")
        print(f"   Entry Node: {pos['entry_node_id']} @ {pos['entry_timestamp']}")
        print(f"   Entry Price: ₹{pos['entry_price']:.2f}")
        print(f"   Quantity: {pos['quantity']} ({pos['lots']} lots × {pos['lot_size']})")
        print(f"   NIFTY Spot: ₹{pos['nifty_spot_at_entry']:.2f}")
        
        if pos['status'] == 'CLOSED':
            pnl_icon = '🟢' if pos['pnl'] >= 0 else '🔴'
            print(f"   Exit Node: {pos['exit_node_id']} @ {pos['exit_timestamp']}")
            print(f"   Exit Price: ₹{pos['exit_price']:.2f}")
            print(f"   Duration: {pos['duration_minutes']:.1f} minutes")
            print(f"   P&L: {pnl_icon} ₹{pos['pnl']:.2f} ({pos['pnl_percentage']:.2f}%)")
            print(f"   Exit Reason: {pos['exit_reason']}")

    print(f"\n{'='*80}")
    print('📊 SUMMARY STATISTICS')
    print(f"{'='*80}")

    summary = dashboard_data['summary']
    print(f"\nTotal Positions: {summary['total_positions']}")
    print(f"  Closed: {summary['closed_positions']}")
    print(f"  Open: {summary['open_positions']}")
    print(f"  Re-entries: {summary['re_entries']}")

    print(f"\nP&L Summary:")
    pnl_icon = '🟢' if summary['total_pnl'] >= 0 else '🔴'
    print(f"  Total P&L: {pnl_icon} ₹{summary['total_pnl']:.2f}")
    print(f"  Largest Win: 🟢 ₹{summary['largest_win']:.2f}")
    print(f"  Largest Loss: 🔴 ₹{summary['largest_loss']:.2f}")
    print(f"  Average Win: ₹{summary['avg_win']:.2f}")
    print(f"  Average Loss: ₹{summary['avg_loss']:.2f}")

    print(f"\nTrade Statistics:")
    print(f"  Winning Trades: {summary['winning_trades']}")
    print(f"  Losing Trades: {summary['losing_trades']}")
    print(f"  Breakeven Trades: {summary['breakeven_trades']}")
    print(f"  Win Rate: {summary['win_rate']:.2f}%")
    print(f"  Avg Duration: {summary['avg_duration_minutes']:.1f} minutes")

    # Save to JSON file
    output_file = 'backtest_dashboard_data.json'
    with open(output_file, 'w') as f:
        json.dump(dashboard_data, f, indent=2)

    print(f"\n{'='*80}")
    print(f'✅ Dashboard data saved to: {output_file}')
    print(f"{'='*80}")

    # Display JSON structure preview
    print(f"\n{'='*80}")
    print('📋 JSON STRUCTURE PREVIEW')
    print(f"{'='*80}")
    print(json.dumps({
        'strategy_id': dashboard_data['strategy_id'],
        'backtest_date': dashboard_data['backtest_date'],
        'positions': [
            'Array of position objects with:',
            '  - position_id, entry_node_id, exit_node_id',
            '  - entry_time, exit_time, timestamps',
            '  - instrument, strike, option_type, expiry',
            '  - entry_price, exit_price, quantity',
            '  - pnl, pnl_percentage, duration',
            '  - status, exit_reason, re_entry_num',
            '  - nifty_spot_at_entry, etc.'
        ],
        'summary': dashboard_data['summary']
    }, indent=2))

    print(f"\n{'='*80}")
