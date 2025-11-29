"""
P&L Debug Logger Utility
=========================

Utility for debug-only P&L logging.

Features:
- P&L snapshot at specific timestamp (one-time log)
- Per-tick P&L streaming for active positions (continuous until closed)

Only active when debug mode is enabled.
"""

from datetime import datetime
from typing import Dict, Any, Set, List, Optional

from src.utils.logger import log_info, log_critical


class PnLDebugLogger:
    """
    Utility for debug-only P&L logging.
    
    Features:
    - P&L snapshot at specific timestamp
    - Per-tick P&L streaming for active positions
    
    Only active when debug mode is enabled.
    """
    
    def __init__(self, snapshot_timestamp: str = "2024-12-04T11:45:16"):
        """
        Initialize P&L debug logger.
        
        Args:
            snapshot_timestamp: ISO timestamp for snapshot/streaming start
        """
        self.snapshot_timestamp = snapshot_timestamp
        self._pnl_snapshot_logged = False
        self._pnl_stream_started = False
        self._pnl_stream_targets: Optional[List[Dict]] = None
        self._pnl_stream_completed_keys: Set = set()
    
    def log_pnl_snapshot_if_due(self, context: Dict[str, Any]):
        """
        Log realized and unrealized P&L per position at snapshot timestamp.
        
        This method emits debug logs once per day when the current timestamp
        crosses the configured snapshot time.
        
        Args:
            context: Execution context
        """
        try:
            current_timestamp = context.get('current_timestamp')
            if current_timestamp is None or self._pnl_snapshot_logged:
                return
            
            # Parse snapshot threshold
            try:
                snapshot_ts = datetime.strptime(self.snapshot_timestamp, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                return
            
            # Only log once when we reach or cross the snapshot moment
            if not hasattr(current_timestamp, 'isoformat'):
                return
            if current_timestamp < snapshot_ts:
                return
            
            context_manager = context.get('context_manager')
            if not context_manager:
                return
            gps = context_manager.get_gps()
            if not gps:
                return
            
            last_tick = context.get('current_tick') or {}
            current_px = last_tick.get('ltp') or last_tick.get('price') or last_tick.get('close')
            
            rows = []
            realized_total = 0.0
            unrealized_total = 0.0
            
            positions = gps.get_all_positions() if hasattr(gps, 'get_all_positions') else {}
            for position_id, pos in (positions or {}).items():
                txns = pos.get('transactions') or []
                for txn in txns:
                    try:
                        entry = txn.get('entry') or {}
                        exit_ = txn.get('exit') or {}
                        entry_time_str = txn.get('entry_time') or entry.get('entry_time')
                        exit_time_str = txn.get('exit_time') or exit_.get('exit_time')
                        
                        entry_time = None
                        exit_time = None
                        try:
                            if entry_time_str:
                                entry_time = datetime.fromisoformat(entry_time_str)
                        except Exception:
                            entry_time = None
                        try:
                            if exit_time_str:
                                exit_time = datetime.fromisoformat(exit_time_str)
                        except Exception:
                            exit_time = None
                        
                        # Skip transactions that start after snapshot
                        if entry_time and entry_time > snapshot_ts:
                            continue
                        
                        qty = (entry.get('quantity')
                              if entry.get('quantity') is not None else pos.get('quantity') or 0)
                        try:
                            qty = int(qty)
                        except (ValueError, TypeError):
                            try:
                                qty = float(qty)
                                if qty <= 0:
                                    log_warning(f"[PnL Debug] Position {position_id}: Quantity {qty} is not positive, using 0")
                                    qty = 0
                            except (ValueError, TypeError) as e:
                                log_warning(
                                    f"[PnL Debug] Position {position_id}: Invalid quantity '{qty}' "
                                    f"(type: {type(qty).__name__}): {e}, using 0"
                                )
                                qty = 0
                        side = (entry.get('side') or 'buy').lower()
                        entry_px = entry.get('price') or pos.get('entry_price')
                        exit_px = (exit_.get('price') or exit_.get('fill_price')
                                  or pos.get('exit_price'))
                        
                        realized = None
                        unrealized = None
                        
                        # Realized if closed on or before snapshot
                        if (txn.get('status') == 'closed') and exit_time and exit_time <= snapshot_ts:
                            # Use stored txn pnl if available; otherwise compute
                            if txn.get('pnl') is not None:
                                try:
                                    realized = float(txn.get('pnl'))
                                except Exception:
                                    realized = None
                            if realized is None and entry_px is not None and exit_px is not None and qty:
                                try:
                                    realized = (exit_px - entry_px) * qty if side == 'buy' else (entry_px - exit_px) * qty
                                except Exception:
                                    realized = None
                        else:
                            # Unrealized if open at snapshot or closed after snapshot
                            if (entry_px is not None) and (current_px is not None) and qty:
                                try:
                                    unrealized = (current_px - entry_px) * qty if side == 'buy' else (entry_px - current_px) * qty
                                except Exception:
                                    unrealized = None
                        
                        if realized is not None:
                            realized_total += float(realized)
                            rows.append({
                                'position_id': position_id,
                                'reEntryNum': txn.get('reEntryNum'),
                                'pnl_type': 'realized',
                                'pnl_value': float(realized),
                                'entry_time': entry_time_str,
                                'exit_time': exit_time_str,
                                'entry_price': entry_px,
                                'exit_price': exit_px,
                                'qty': qty,
                                'side': side,
                            })
                        if unrealized is not None:
                            unrealized_total += float(unrealized)
                            rows.append({
                                'position_id': position_id,
                                'reEntryNum': txn.get('reEntryNum'),
                                'pnl_type': 'unrealized',
                                'pnl_value': float(unrealized),
                                'entry_time': entry_time_str,
                                'current_price': current_px,
                                'entry_price': entry_px,
                                'qty': qty,
                                'side': side,
                            })
                    except Exception:
                        # Debug only: ignore per-txn errors
                        continue
            
            overall_total = realized_total + unrealized_total
            try:
                log_critical(
                    f"[PnL SNAPSHOT @ {self.snapshot_timestamp}] totals: realized={realized_total:.2f}, "
                    f"unrealized={unrealized_total:.2f}, overall={overall_total:.2f}. Rows={rows}"
                )
            except Exception:
                # Always avoid breaking runtime due to debug log
                pass
            
            self._pnl_snapshot_logged = True
        except Exception:
            # Never raise from debug-only helper
            pass
    
    def log_pnl_stream_if_due(self, context: Dict[str, Any]):
        """
        Stream per-tick P&L for positions active at snapshot time.
        
        - Emits unrealized P&L for open transactions every tick.
        - Emits realized P&L once when the transaction closes, then stops logging for that transaction.
        - Stops entirely when all tracked transactions have closed.
        
        Args:
            context: Execution context
        """
        try:
            current_timestamp = context.get('current_timestamp')
            if current_timestamp is None:
                return
            
            try:
                snapshot_ts = datetime.strptime(self.snapshot_timestamp, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                return
            
            if current_timestamp < snapshot_ts:
                return
            
            context_manager = context.get('context_manager')
            if not context_manager:
                return
            gps = context_manager.get_gps()
            if not gps:
                return
            
            # Initialize targets on the first eligible tick
            if not self._pnl_stream_started:
                self._pnl_stream_started = True
                self._pnl_stream_targets = []
                self._pnl_stream_completed_keys = set()
                positions = gps.get_all_positions() if hasattr(gps, 'get_all_positions') else {}
                for position_id, pos in (positions or {}).items():
                    txns = pos.get('transactions') or []
                    for txn in txns:
                        entry_time_str = txn.get('entry_time') or (txn.get('entry') or {}).get('entry_time')
                        if not entry_time_str:
                            continue
                        try:
                            entry_time = datetime.fromisoformat(entry_time_str)
                        except Exception:
                            continue
                        # Track if the txn is already active by snapshot or starts exactly at snapshot
                        if entry_time <= snapshot_ts:
                            self._pnl_stream_targets.append({
                                'position_id': position_id,
                                'reEntryNum': txn.get('reEntryNum'),
                                'entry_time': entry_time_str,
                            })
                # If nothing to stream, return silently
                if not self._pnl_stream_targets:
                    return
            
            # If all targets completed, stop streaming
            if self._pnl_stream_targets and len(self._pnl_stream_completed_keys) >= len(self._pnl_stream_targets):
                return
            
            # Current price from tick
            last_tick = context.get('current_tick') or {}
            current_px = last_tick.get('ltp') or last_tick.get('price') or last_tick.get('close')
            
            # Trace specific timestamp if needed
            if hasattr(current_timestamp, 'strftime') and current_timestamp.strftime('%d-%m-%Y %H:%M:%S') == '12-12-2024 09:26:01':
                log_info("[TRACE_TICK] matched 12-12-2024 09:26:01 IST")
            
            # For each target txn, log unrealized if open, realized once if closed
            positions = gps.get_all_positions() if hasattr(gps, 'get_all_positions') else {}
            for target in (self._pnl_stream_targets or []):
                position_id = target.get('position_id')
                re_entry_num = target.get('reEntryNum')
                entry_time_str = target.get('entry_time')
                key = (position_id, re_entry_num, entry_time_str)
                if key in self._pnl_stream_completed_keys:
                    continue
                
                pos = positions.get(position_id) or {}
                txns = pos.get('transactions') or []
                # Find matching txn by reEntryNum and entry_time
                matched = None
                for t in txns:
                    if (t.get('reEntryNum') == re_entry_num) and ((t.get('entry_time') or (t.get('entry') or {}).get('entry_time')) == entry_time_str):
                        matched = t
                        break
                if not matched:
                    continue
                
                entry = matched.get('entry') or {}
                exit_ = matched.get('exit') or {}
                status = matched.get('status')
                side = (entry.get('side') or 'buy').lower()
                qty = entry.get('quantity') or pos.get('quantity') or 0
                entry_px = entry.get('price') or pos.get('entry_price')
                exit_px = exit_.get('price') or exit_.get('fill_price') or pos.get('exit_price')
                
                # If closed by now, emit realized once and mark complete
                if status == 'closed':
                    realized = None
                    if matched.get('pnl') is not None:
                        try:
                            realized = float(matched.get('pnl'))
                        except Exception:
                            realized = None
                    if realized is None and entry_px is not None and exit_px is not None and qty:
                        try:
                            realized = (exit_px - entry_px) * qty if side == 'buy' else (entry_px - exit_px) * qty
                        except Exception:
                            realized = None
                    try:
                        log_info(
                            f"[PnL STREAM] position_id={position_id} reEntryNum={re_entry_num} type=realized "
                            f"pnl={realized} entry={entry_px} exit={exit_px} qty={qty} side={side}"
                        )
                    except Exception:
                        pass
                    self._pnl_stream_completed_keys.add(key)
                    continue
                
                # Else if still open, emit unrealized this tick
                if (entry_px is not None) and (current_px is not None) and qty:
                    try:
                        unrealized = (current_px - entry_px) * qty if side == 'buy' else (entry_px - current_px) * qty
                    except Exception:
                        unrealized = None
                    try:
                        log_info(
                            f"[PnL STREAM] position_id={position_id} reEntryNum={re_entry_num} type=unrealized "
                            f"pnl={unrealized} entry={entry_px} current={current_px} qty={qty} side={side}"
                        )
                    except Exception:
                        pass
        except Exception:
            # Debug-only safety
            pass
