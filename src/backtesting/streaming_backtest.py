"""
Streaming Backtest - Run backtest with real-time SSE event emission.

This module provides a streaming interface for backtesting that emits
tick timestamps and progress updates via async generators for SSE.

Author: UniTrader Team
Created: 2024-12-27
"""

import asyncio
import time
from datetime import datetime, date
from typing import Dict, List, Any, Optional, AsyncGenerator
import logging

logger = logging.getLogger(__name__)


def build_flow_chain(events_history: dict, exec_id: str, max_depth: int = 10) -> list:
    """
    Build execution chain from an execution ID back to root (Start node).
    Returns list of execution IDs in CHRONOLOGICAL order (oldest to newest).
    """
    chain = [exec_id]  # Include the current node
    current_id = exec_id
    depth = 0
    
    while current_id and current_id in events_history and depth < max_depth:
        event = events_history[current_id]
        parent_id = event.get('parent_execution_id')
        
        if parent_id and parent_id in events_history:
            parent_event = events_history[parent_id]
            node_type = parent_event.get('node_type', '')
            
            # Add ALL parent nodes (signals, conditions, start)
            if any(keyword in node_type for keyword in ['Signal', 'Condition', 'Start', 'Entry', 'Exit']):
                chain.append(parent_id)
            
            current_id = parent_id
            depth += 1
        else:
            break
    
    # Return in chronological order (oldest first)
    return list(reversed(chain))


def extract_flow_ids_from_events(events_history: dict, node_id: str, timestamp: str) -> list:
    """
    Extract execution_ids (flow_ids) for a specific node execution.
    Matches by node_id and timestamp to find the correct execution.
    """
    if not events_history or not node_id:
        return []
    
    for exec_id, event in events_history.items():
        if event.get('node_id') == node_id:
            # Check if timestamp matches (compare HH:MM:SS)
            event_time = event.get('timestamp', '')
            if timestamp and event_time:
                # Extract time portion from diagnostic timestamp
                # Diagnostic format: "2024-10-28 09:18:00+05:30"
                # Position format: "09:18:00" or "2024-10-28T09:18:00"
                if len(event_time) >= 19:
                    diagnostic_time = event_time[11:19]  # "09:18:00"
                    
                    # Extract HH:MM:SS from position timestamp
                    pos_time = timestamp
                    if 'T' in timestamp:
                        pos_time = timestamp.split('T')[1][:8]
                    elif len(timestamp) >= 8:
                        pos_time = timestamp[:8]
                    
                    # Compare HH:MM:SS
                    if diagnostic_time == pos_time:
                        # Found the node execution - build full chain
                        return build_flow_chain(events_history, exec_id)
    
    return []


async def run_streaming_backtest(
    strategy_ids: List[str],
    backtest_date: date,
    scales: Dict[str, float] = None,
    queue_entries: Dict[str, Dict] = None,
    speed_multiplier: float = 50.0,
    emit_interval: int = 10
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Run backtest with streaming events.
    
    Args:
        strategy_ids: List of strategy/queue IDs
        backtest_date: Date to run backtest
        scales: Dict of strategy_id -> scale multiplier
        queue_entries: Dict of queue_id -> {actual_strategy_id, broker_connection_id, user_id}
        speed_multiplier: Speed multiplier (50 = 50x real-time)
        emit_interval: Emit SSE event every N simulated seconds
    
    Yields:
        Dict with 'type' and 'data' keys for SSE events
    """
    from src.backtesting.backtest_config import BacktestConfig
    from src.backtesting.centralized_backtest_engine import CentralizedBacktestEngine
    from show_dashboard_data import dashboard_data
    
    # Reset dashboard_data
    dashboard_data['positions'] = []
    dashboard_data['backtest_date'] = backtest_date.strftime('%Y-%m-%d')
    
    # Create config
    config = BacktestConfig(
        strategy_ids=strategy_ids,
        backtest_date=backtest_date,
        debug_mode=None,
        scales=scales,
        queue_entries=queue_entries
    )
    
    # Create engine
    engine = CentralizedBacktestEngine(config)
    
    # Initialize engine components (normally done in run())
    print("=" * 80)
    print("🚀 STREAMING BACKTEST")
    print(f"   Speed: {speed_multiplier}x | Emit interval: {emit_interval}s")
    print("=" * 80)
    
    # Step 1: Load strategies
    strategies = []
    for strategy_id in config.strategy_ids:
        queue_entry = None
        actual_strategy_id = strategy_id
        broker_connection_id = None
        
        if config.queue_entries and strategy_id in config.queue_entries:
            queue_entry = config.queue_entries[strategy_id]
            actual_strategy_id = queue_entry.get('actual_strategy_id', strategy_id)
            broker_connection_id = queue_entry.get('broker_connection_id')
        
        strategy = engine.strategy_manager.load_strategy(
            strategy_id=actual_strategy_id,
            broker_connection_id=broker_connection_id
        )
        
        if queue_entry:
            strategy.strategy_id = strategy_id
            strategy.actual_strategy_id = actual_strategy_id
            strategy.broker_connection_id = broker_connection_id
            if queue_entry.get('user_id'):
                strategy.user_id = queue_entry['user_id']
        
        strategies.append(strategy)
    
    engine.strategies = strategies
    strategy = strategies[0]
    
    # Step 2: Build metadata
    engine.strategies_agg = engine._build_metadata(strategies)
    
    # Step 3: Initialize data components
    engine._initialize_data_components(strategy)
    engine.data_manager.initialize(
        strategy=strategy,
        backtest_date=config.backtest_date,
        strategies_agg=engine.strategies_agg
    )
    engine.context_adapter.clickhouse_client = engine.data_manager.clickhouse_client
    
    # Step 4: Initialize centralized components
    engine._initialize_centralized_components()
    
    # Step 5: Subscribe strategies
    for strat in strategies:
        engine._subscribe_strategy_to_cache(strat)
    
    # Step 5.5: Build strategy metadata dict for each strategy
    # Key: strategy_id (queue_id), Value: {symbols: set, name: str, user_id: str}
    strategy_metadata = {}
    for strat in strategies:
        strat_symbols = set(strat.get_symbols())
        actual_strat_id = getattr(strat, 'actual_strategy_id', None) or strat.strategy_id
        strategy_metadata[strat.strategy_id] = {
            'symbols': strat_symbols,
            'name': strat.strategy_name,
            'user_id': strat.user_id,
            'actual_strategy_id': actual_strat_id,
            'broker_connection_id': getattr(strat, 'broker_connection_id', None)
        }
        print(f"\n📊 Strategy Metadata Stored:")
        print(f"   Strategy ID (Key): {strat.strategy_id}")
        print(f"   Actual Strategy ID: {actual_strat_id}")
        print(f"   Name: {strat.strategy_name}")
        print(f"   Symbols: {strat_symbols}")
        print(f"   ⚠️ Data will be sent with key: {actual_strat_id}")
    
    # Step 6: Load ticks
    all_symbols = set()
    for strat in strategies:
        all_symbols.update(strat.get_symbols())
    
    ticks = engine.data_manager.load_ticks(
        date=config.backtest_date,
        symbols=list(all_symbols)
    )
    
    yield {
        "type": "init",
        "data": {
            "total_ticks": len(ticks),
            "symbols": list(all_symbols),
            "strategies": len(strategies)
        }
    }
    
    # Group ticks by second
    from collections import defaultdict
    ticks_by_second = defaultdict(list)
    for tick in ticks:
        tick_timestamp = tick['timestamp']
        second_key = tick_timestamp.replace(microsecond=0)
        ticks_by_second[second_key].append(tick)
    
    sorted_seconds = sorted(ticks_by_second.keys())
    total_seconds = len(sorted_seconds)
    
    if total_seconds == 0:
        yield {"type": "error", "data": {"error": "No ticks to process"}}
        return
    
    start_time = sorted_seconds[0]
    end_time = sorted_seconds[-1]
    
    yield {
        "type": "ready",
        "data": {
            "total_seconds": total_seconds,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "ticks_per_second_avg": len(ticks) / total_seconds
        }
    }
    
    # Calculate sleep duration per simulated second
    sleep_duration = 1.0 / speed_multiplier if speed_multiplier > 0 else 0
    
    # Process ticks with streaming
    processed_tick_count = 0
    last_emit_second = 0
    positions_emitted = set()
    
    # Track node events for diagnostics streaming
    last_event_counts = {}  # {strategy_id: last_event_count} to detect new events
    emitted_events = set()  # Track emitted event execution_ids
    
    # Store events_history per strategy (persists after strategies terminate)
    # Use queue_id (strat_id) as key - unique per broker account
    stored_events_history = {}  # {queue_id: events_history}
    
    # Track trades for trades_daily streaming
    trades_list = {}  # {strategy_id: [trades]} built incrementally
    
    real_start = time.time()
    
    for second_idx, second_timestamp in enumerate(sorted_seconds):
        tick_batch = ticks_by_second[second_timestamp]
        
        # Process ticks
        last_processed_tick = None
        for tick in tick_batch:
            try:
                last_processed_tick = engine.data_manager.process_tick(tick)
                processed_tick_count += 1
            except Exception as e:
                continue
        
        # Process option ticks
        option_ticks = engine.data_manager.get_option_ticks_for_timestamp(second_timestamp)
        for option_tick in option_ticks:
            try:
                engine.data_manager.process_tick(option_tick)
                processed_tick_count += 1
            except:
                continue
        
        # Execute strategy
        if last_processed_tick:
            tick_data = {
                'symbol': last_processed_tick.get('symbol'),
                'ltp': last_processed_tick.get('ltp'),
                'timestamp': second_timestamp,
                'volume': last_processed_tick.get('volume', 0),
                'batch_size': len(tick_batch)
            }
            
            engine.centralized_processor.on_tick(tick_data)
        
        # ============================================================
        # PRINT: Per-second data for each strategy (GPS + LTP)
        # ============================================================
        # Get global LTP store from data_manager context
        global_ltp_store = {}
        try:
            # Primary: Get from data_manager context (has full LTP data)
            if engine.data_manager:
                data_context = engine.data_manager.get_context()
                global_ltp_store = data_context.get('ltp_store', {})
            
            # Fallback: Get from centralized_processor.ltp_store (UnifiedLTPStore)
            if not global_ltp_store and hasattr(engine.centralized_processor, 'ltp_store'):
                ltp_store_obj = engine.centralized_processor.ltp_store
                if hasattr(ltp_store_obj, 'get_all'):
                    global_ltp_store = ltp_store_obj.get_all()
        except Exception as e:
            pass
        
        # Print for each strategy
        for strat_id, meta in strategy_metadata.items():
            # A) Get GPS positions for this strategy
            gps_positions = {}
            try:
                # Access active_strategies to get context_manager with GPS
                for instance_id, strategy_state in engine.centralized_processor.strategy_manager.active_strategies.items():
                    if strategy_state.get('strategy_id') == strat_id:
                        context_mgr = strategy_state.get('context_manager')
                        if context_mgr and hasattr(context_mgr, 'gps'):
                            gps_positions = context_mgr.gps.positions
                        break
            except Exception:
                pass
            
            # B) Filter LTP store by this strategy's symbols (include options that match underlying)
            strat_symbols = meta.get('symbols', set())
            filtered_ltp = {}
            for sym in strat_symbols:
                # Direct match
                if sym in global_ltp_store:
                    filtered_ltp[sym] = global_ltp_store[sym]
                # Also include option symbols that start with this underlying (e.g., NIFTY:2024-10-10:OPT:...)
                for ltp_sym, ltp_price in global_ltp_store.items():
                    if ltp_sym.startswith(f"{sym}:"):
                        filtered_ltp[ltp_sym] = ltp_price
            
            # Print in expected format (only every emit_interval seconds to reduce noise)
            if second_idx % emit_interval == 0:
                print(f"\n{'='*60}", flush=True)
                print(f"⏱️  TIMESTAMP: {second_timestamp}", flush=True)
                print(f"📌 STRATEGY: {meta.get('name')} (ID: {strat_id})", flush=True)
                print(f"{'='*60}", flush=True)
                print(f"\n🎯 GPS POSITIONS (strategy_id={strat_id}):", flush=True)
                if gps_positions:
                    for pos_id, pos_data in gps_positions.items():
                        print(f"   {pos_id}: {pos_data}", flush=True)
                else:
                    print(f"   (No positions)", flush=True)
                print(f"\n📈 LTP STORE (filtered by strategy symbols):", flush=True)
                if filtered_ltp:
                    for sym, ltp in filtered_ltp.items():
                        print(f"   {sym}: {ltp}", flush=True)
                else:
                    print(f"   (No LTP data for strategy symbols)", flush=True)
                print(f"{'='*60}\n", flush=True)
        
        # Emit tick event at intervals
        if second_idx - last_emit_second >= emit_interval or second_idx == 0:
            last_emit_second = second_idx
            progress_pct = (second_idx + 1) / total_seconds * 100
            
            # Get active nodes
            active_nodes = []
            for instance_id, strategy_state in engine.centralized_processor.strategy_manager.active_strategies.items():
                for node_id, state in strategy_state.get('node_states', {}).items():
                    if state.get('status') in ['Active', 'Pending']:
                        active_nodes.append(node_id)
            
            # Get current positions
            current_positions = dashboard_data.get('positions', [])
            positions_count = len(current_positions)
            
            # Get LTP store from cache manager
            ltp_store = {}
            try:
                cache_mgr = engine.centralized_processor.cache_manager
                if hasattr(cache_mgr, 'ltp_cache'):
                    ltp_store = dict(cache_mgr.ltp_cache)
                elif hasattr(cache_mgr, 'ltp_store'):
                    ltp_store = dict(cache_mgr.ltp_store)
            except Exception:
                pass
            
            # Build per-strategy data: P&L, positions, and filtered LTP
            strategy_data = {}
            
            # Debug: Log active_strategies info
            active_strats = engine.centralized_processor.strategy_manager.active_strategies
            print(f"\n🔍 [DEBUG] active_strategies count: {len(active_strats)}")
            for inst_id, st in active_strats.items():
                print(f"   Instance: {inst_id[:30]}... | strategy_id: {st.get('strategy_id', 'N/A')[:30]}...")
            print(f"   strategy_metadata keys: {list(strategy_metadata.keys())}")
            
            for strat_id, meta in strategy_metadata.items():
                print(f"\n🔍 [DEBUG] Processing strategy: {strat_id[:30]}...")
                
                # Get GPS positions for this strategy
                gps_positions = {}
                try:
                    found_strategy = False
                    for instance_id, strategy_state in engine.centralized_processor.strategy_manager.active_strategies.items():
                        state_strat_id = strategy_state.get('strategy_id')
                        if state_strat_id == strat_id:
                            found_strategy = True
                            print(f"   ✅ Found strategy in active_strategies: {instance_id[:30]}...")
                            context_mgr = strategy_state.get('context_manager')
                            if context_mgr and hasattr(context_mgr, 'gps'):
                                # Include ALL transactions as separate positions for UI
                                for pos_id, pos_data in context_mgr.gps.positions.items():
                                    symbol = pos_data.get('symbol', '')
                                    transactions = pos_data.get('transactions', [])
                                    
                                    # Get current LTP for this position's symbol
                                    current_ltp = None
                                    if symbol in global_ltp_store:
                                        ltp_data = global_ltp_store[symbol]
                                        current_ltp = ltp_data.get('ltp') if isinstance(ltp_data, dict) else ltp_data
                                    
                                    # Process each transaction as a separate position entry
                                    for txn in transactions:
                                        position_num = txn.get('position_num', 1)
                                        txn_key = f"{pos_id}_{position_num}"
                                        txn_status = txn.get('status', 'open')
                                        exit_data = txn.get('exit', {}) or {}
                                        entry_data = txn.get('entry', {}) or {}
                                        
                                        # Get events_history for this strategy to extract flow IDs
                                        strat_events_history = strategy_state.get('node_events_history', {})
                                        
                                        # Extract flow IDs using events_history (matches node_id + timestamp)
                                        entry_node_id = txn.get('node_id')
                                        entry_time = txn.get('entry_time', '')
                                        entry_flow_ids = extract_flow_ids_from_events(strat_events_history, entry_node_id, entry_time)
                                        
                                        # For exit, use exit node_id and exit_time
                                        exit_node_id = exit_data.get('node_id')
                                        exit_time_str = txn.get('exit_time', '')
                                        exit_flow_ids = []
                                        if exit_node_id and exit_time_str:
                                            exit_flow_ids = extract_flow_ids_from_events(strat_events_history, exit_node_id, exit_time_str)
                                        
                                        gps_positions[txn_key] = {
                                            'position_id': pos_id,
                                            'position_num': position_num,
                                            're_entry_num': position_num - 1,  # 0 for initial, 1+ for re-entries
                                            'status': txn_status,
                                            'symbol': txn.get('symbol', symbol),
                                            'side': txn.get('side'),
                                            'quantity': txn.get('quantity'),
                                            'entry_price': txn.get('entry_price'),
                                            'current_price': current_ltp,
                                            'current_ltp': current_ltp,
                                            'unrealized_pnl': 0 if txn_status == 'closed' else pos_data.get('unrealized_pnl', 0),
                                            'realized_pnl': txn.get('pnl'),
                                            'pnl': txn.get('pnl'),
                                            'entry_time': txn.get('entry_time'),
                                            'exit_time': txn.get('exit_time'),
                                            'exit_price': exit_data.get('price'),
                                            'close_reason': exit_data.get('reason') or pos_data.get('close_reason'),
                                            'entry_flow_ids': entry_flow_ids,
                                            'exit_flow_ids': exit_flow_ids,
                                        }
                            break
                    if not found_strategy:
                        print(f"   ❌ Strategy NOT found in active_strategies! Looking for: {strat_id[:30]}...")
                except Exception as e:
                    print(f"   ❌ Exception getting GPS positions: {e}")
                
                # Debug: Log GPS positions count and global LTP store
                print(f"   GPS positions found: {len(gps_positions)}")
                print(f"   Global LTP store size: {len(global_ltp_store)}")
                
                # Filter LTP store by this strategy's symbols
                strat_symbols = meta.get('symbols', set())
                filtered_ltp = {}
                for sym in strat_symbols:
                    if sym in global_ltp_store:
                        ltp_data = global_ltp_store[sym]
                        filtered_ltp[sym] = ltp_data.get('ltp') if isinstance(ltp_data, dict) else ltp_data
                    for ltp_sym, ltp_data in global_ltp_store.items():
                        if ltp_sym.startswith(f"{sym}:"):
                            filtered_ltp[ltp_sym] = ltp_data.get('ltp') if isinstance(ltp_data, dict) else ltp_data
                
                # Calculate P&L from GPS positions
                realized_pnl = 0
                unrealized_pnl = 0
                open_count = 0
                closed_count = 0
                
                for pos_id, pos in gps_positions.items():
                    if pos.get('status') == 'open':
                        open_count += 1
                        # Calculate unrealized P&L using filtered LTP
                        symbol = pos.get('symbol')
                        entry_price_raw = pos.get('entry_price', 0)
                        # Handle case where entry_price might be a dict or string
                        entry_price = float(entry_price_raw) if not isinstance(entry_price_raw, dict) else 0
                        qty = float(pos.get('quantity', 0) or 0)
                        side = pos.get('side', 'buy').lower()
                        current_ltp_raw = filtered_ltp.get(symbol, entry_price)
                        # Handle case where LTP might be a dict
                        current_ltp = float(current_ltp_raw) if not isinstance(current_ltp_raw, dict) else entry_price
                        
                        if side == 'buy':
                            unrealized_pnl += (current_ltp - entry_price) * qty
                        else:
                            unrealized_pnl += (entry_price - current_ltp) * qty
                    else:
                        closed_count += 1
                        realized_pnl += pos.get('realized_pnl') or 0
                
                # Use queue_id (strat_id) as key - unique per broker account
                actual_strat_id = meta.get('actual_strategy_id') or strat_id
                
                # Get trades for this strategy - use queue_id
                strat_trades = list(trades_list.get(strat_id, {}).values())
                
                # Calculate realized P&L from trades (more accurate than GPS positions)
                trades_realized_pnl = sum(
                    float(t.get('pnl', 0) or 0) 
                    for t in strat_trades 
                    if t.get('status') == 'CLOSED'
                )
                
                # Calculate unrealized P&L from trades
                trades_unrealized_pnl = sum(
                    float(t.get('unrealized_pnl', 0) or 0) 
                    for t in strat_trades 
                    if t.get('status') == 'OPEN'
                )
                
                # Use trades-based P&L if available, otherwise fall back to GPS calculation
                final_realized = trades_realized_pnl if trades_realized_pnl != 0 else realized_pnl
                final_unrealized = trades_unrealized_pnl if trades_unrealized_pnl != 0 else unrealized_pnl
                
                # Calculate trade statistics
                winning_trades = sum(1 for t in strat_trades if float(t.get('pnl', 0) or 0) > 0 and t.get('status') == 'CLOSED')
                losing_trades = sum(1 for t in strat_trades if float(t.get('pnl', 0) or 0) <= 0 and t.get('status') == 'CLOSED')
                
                # Use queue_id (strat_id) as key - unique per broker account
                strategy_data[strat_id] = {
                    "name": meta.get('name'),
                    "actual_strategy_id": actual_strat_id,
                    "positions": gps_positions,
                    "ltp_store": filtered_ltp,
                    "pnl_summary": {
                        "realized_pnl": round(final_realized, 2),
                        "unrealized_pnl": round(final_unrealized, 2),
                        "total_pnl": round(final_realized + final_unrealized, 2),
                        "open_positions": open_count,
                        "closed_positions": closed_count,
                        "winning_trades": winning_trades,
                        "losing_trades": losing_trades
                    },
                    "trades": strat_trades
                }
            
            # Debug: Log what we're about to send
            print(f"\n🔥 [STREAM EMIT] Progress: {progress_pct:.1f}%")
            print(f"   strategy_data keys: {list(strategy_data.keys())}")
            for sid, sdata in strategy_data.items():
                print(f"   Strategy {sid[:20]}...: LTP={len(sdata.get('ltp_store', {}))}, Positions={len(sdata.get('positions', {}))}, Trades={len(sdata.get('trades', []))}")
                print(f"      P&L Summary: {sdata.get('pnl_summary', {})}")
            
            yield {
                "type": "tick",
                "data": {
                    "timestamp": second_timestamp.isoformat(),
                    "progress_pct": round(progress_pct, 2),
                    "second_idx": second_idx + 1,
                    "total_seconds": total_seconds,
                    "ticks_processed": processed_tick_count,
                    "active_nodes": active_nodes,
                    "positions_count": positions_count,
                    "strategy_data": strategy_data
                }
            }
        
        # Check for new positions and emit
        current_positions = dashboard_data.get('positions', [])
        for pos in current_positions:
            pos_id = pos.get('position_id')
            if pos_id and pos_id not in positions_emitted:
                positions_emitted.add(pos_id)
                yield {
                    "type": "position",
                    "data": {
                        "position_id": pos_id,
                        "symbol": pos.get('symbol'),
                        "side": pos.get('side'),
                        "entry_price": pos.get('entry_price'),
                        "entry_time": pos.get('entry_timestamp'),
                        "status": pos.get('status')
                    }
                }
        
        # ============================================================
        # EMIT: New node events (diagnostics) when they happen
        # ============================================================
        for instance_id, strategy_state in engine.centralized_processor.strategy_manager.active_strategies.items():
            strat_id = strategy_state.get('strategy_id')
            actual_strat_id = strategy_metadata.get(strat_id, {}).get('actual_strategy_id') or strat_id
            
            # Get node_events_history from strategy context
            events_history = strategy_state.get('node_events_history', {})
            
            # Store a copy of events_history (so it persists after strategy terminates)
            # Use queue_id (strat_id) as key - unique per broker account
            if events_history:
                stored_events_history[strat_id] = dict(events_history)
            
            # Check for new events
            for exec_id, event_data in events_history.items():
                if exec_id not in emitted_events:
                    emitted_events.add(exec_id)
                    
                    # Emit node event for action nodes (entry, exit, square-off)
                    node_type = event_data.get('node_type', '')
                    if node_type in ['EntryNode', 'ExitNode', 'SquareOffNode']:
                        yield {
                            "type": "node_event",
                            "data": {
                                "strategy_id": actual_strat_id,
                                "execution_id": exec_id,
                                "node_id": event_data.get('node_id'),
                                "node_name": event_data.get('node_name'),
                                "node_type": node_type,
                                "event_type": event_data.get('event_type'),
                                "timestamp": event_data.get('timestamp'),
                                "action": event_data.get('action'),
                                "position": event_data.get('position'),
                                "exit_result": event_data.get('exit_result'),
                                "square_off": event_data.get('square_off')
                            }
                        }
            
            # Build trades_daily incrementally from GPS positions
            context_mgr = strategy_state.get('context_manager')
            if context_mgr and hasattr(context_mgr, 'gps'):
                gps = context_mgr.gps
                
                if strat_id not in trades_list:
                    trades_list[strat_id] = {}
                
                # Convert GPS positions to trades format
                # GPS stores transactions within each position - iterate over ALL transactions
                for pos_id, pos_data in gps.positions.items():
                    transactions = pos_data.get('transactions', [])
                    symbol = pos_data.get('symbol', '')
                    
                    # Process each transaction (each entry/re-entry is a separate trade)
                    for txn in transactions:
                        position_num = txn.get('position_num', 1)
                        trade_key = f"{pos_id}_{position_num}"
                        
                        # Get transaction status
                        txn_status = txn.get('status', 'open').upper()
                        
                        # Check if this trade already exists and is CLOSED - preserve closed trades
                        existing_trade = trades_list[strat_id].get(trade_key)
                        if existing_trade and existing_trade.get('status') == 'CLOSED':
                            continue
                        
                        # Calculate unrealized P&L for open positions
                        trade_unrealized_pnl = 0
                        if txn_status == 'OPEN':
                            entry_price_raw = txn.get('entry_price', 0)
                            entry_price = float(entry_price_raw) if not isinstance(entry_price_raw, dict) else 0
                            qty = float(txn.get('quantity', 0) or 0)
                            side = txn.get('side', 'buy').lower()
                            # Get current LTP
                            current_ltp_raw = filtered_ltp.get(symbol) or global_ltp_store.get(symbol, {})
                            if isinstance(current_ltp_raw, dict):
                                current_ltp = float(current_ltp_raw.get('ltp', entry_price))
                            else:
                                current_ltp = float(current_ltp_raw) if current_ltp_raw else entry_price
                            if side == 'buy':
                                trade_unrealized_pnl = (current_ltp - entry_price) * qty
                            else:
                                trade_unrealized_pnl = (entry_price - current_ltp) * qty
                        
                        # Get exit data from transaction
                        exit_data = txn.get('exit', {}) or {}
                        entry_data = txn.get('entry', {}) or {}
                        
                        # Get events_history for this strategy to extract flow IDs
                        strat_events_history = {}
                        for instance_id, strategy_state in engine.centralized_processor.strategy_manager.active_strategies.items():
                            if strategy_state.get('strategy_id') == strat_id:
                                strat_events_history = strategy_state.get('node_events_history', {})
                                break
                        
                        # Extract flow IDs using events_history (matches node_id + timestamp)
                        entry_node_id = txn.get('node_id')
                        entry_time = txn.get('entry_time', '')
                        entry_flow_ids = extract_flow_ids_from_events(strat_events_history, entry_node_id, entry_time)
                        
                        # For exit, use exit node_id and exit_time
                        exit_node_id = exit_data.get('node_id')
                        exit_time = txn.get('exit_time', '')
                        exit_flow_ids = []
                        if exit_node_id and exit_time:
                            exit_flow_ids = extract_flow_ids_from_events(strat_events_history, exit_node_id, exit_time)
                        
                        # Build trade record from transaction data
                        # position_num: 1 = initial entry, 2+ = re-entries
                        # re_entry_num: 0 = initial entry, 1+ = re-entries (for UI display)
                        trade = {
                            "trade_id": trade_key,
                            "position_id": pos_id,
                            "re_entry_num": position_num - 1,
                            "symbol": txn.get('symbol', symbol),
                            "side": txn.get('side', ''),
                            "quantity": txn.get('quantity', 0),
                            "entry_price": str(txn.get('entry_price', 0)),
                            "entry_time": txn.get('entry_time', ''),
                            "exit_price": str(exit_data.get('price', '')) if exit_data.get('price') else None,
                            "exit_time": txn.get('exit_time'),
                            "pnl": str(txn.get('pnl', 0) or 0),
                            "unrealized_pnl": str(round(trade_unrealized_pnl, 2)),
                            "status": txn_status,
                            "exit_reason": exit_data.get('reason') or pos_data.get('close_reason'),
                            "entry_trigger": entry_data.get('trigger', ''),
                            "entry_flow_ids": entry_flow_ids,
                            "exit_flow_ids": exit_flow_ids,
                        }
                        
                        trades_list[strat_id][trade_key] = trade
        
        # Check termination
        active_strategies = engine.centralized_processor.strategy_manager.active_strategies
        if not active_strategies:
            break
        
        # Sleep for speed control
        if sleep_duration > 0:
            await asyncio.sleep(sleep_duration)
    
    # Finalize
    engine._finalize()
    
    real_duration = time.time() - real_start
    
    # Build summary
    positions = dashboard_data.get('positions', [])
    total_pnl = sum(p.get('realized_pnl', 0) or 0 for p in positions)
    
    # Build final trades_daily and diagnostics per strategy
    # Use strategy_metadata (always populated) instead of active_strategies (may be empty)
    final_strategy_data = {}
    for strat_id, meta in strategy_metadata.items():
        actual_strat_id = meta.get('actual_strategy_id') or strat_id
        
        # Get final diagnostics from stored_events_history (persisted during tick loop)
        # Use queue_id (strat_id) as key since that's how it was stored
        events_history = stored_events_history.get(strat_id, {})
        
        # Get final trades - use queue_id (strat_id) as key
        strat_trades = list(trades_list.get(strat_id, {}).values())
        
        # Calculate final statistics
        winning_trades = sum(1 for t in strat_trades if float(t.get('pnl', 0)) > 0 and t.get('status') == 'CLOSED')
        losing_trades = sum(1 for t in strat_trades if float(t.get('pnl', 0)) <= 0 and t.get('status') == 'CLOSED')
        total_trades = len([t for t in strat_trades if t.get('status') == 'CLOSED'])
        strat_pnl = sum(float(t.get('pnl', 0)) for t in strat_trades if t.get('status') == 'CLOSED')
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        print(f"[Stream Complete] Strategy queue_id={strat_id}, actual={actual_strat_id}: {len(strat_trades)} trades, {len(events_history)} events")
        
        # Use queue_id (strat_id) as key - unique per broker account
        final_strategy_data[strat_id] = {
            "trades_daily": {
                "date": backtest_date.isoformat(),
                "summary": {
                    "total_trades": total_trades,
                    "total_pnl": f"{strat_pnl:.2f}",
                    "winning_trades": winning_trades,
                    "losing_trades": losing_trades,
                    "win_rate": f"{win_rate:.2f}"
                },
                "trades": strat_trades
            },
            "diagnostics_export": {
                "events_history": events_history
            }
        }
    
    yield {
        "type": "complete",
        "data": {
            "backtest_date": backtest_date.isoformat(),
            "total_ticks": processed_tick_count,
            "total_seconds": total_seconds,
            "positions_count": len(positions),
            "total_pnl": round(total_pnl, 2),
            "real_duration_seconds": round(real_duration, 2),
            "effective_speed": round(total_seconds / real_duration, 1) if real_duration > 0 else 0,
            "strategy_results": final_strategy_data
        }
    }
