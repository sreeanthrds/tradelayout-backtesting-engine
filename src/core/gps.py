"""
Global Position Store (GPS) for managing position data across all nodes.
"""

import json
from datetime import datetime
from typing import Dict, Optional, Any
from src.utils.logger import log_info, log_error


class GlobalPositionStore:
    """
    Global Position Store to manage position data across all nodes.
    Stores comprehensive position information including entry/exit details.
    """

    def __init__(self):
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.node_variables: Dict[str, Any] = {}
        self.strategy_start_time: Optional[datetime] = None
        self.day_start_time: Optional[datetime] = None
        self.current_tick_time: Optional[datetime] = None
        # Overall PNL tracking
        self.overall_realized_pnl: float = 0.0
        self.overall_unrealized_pnl: float = 0.0
        self.overall_pnl: float = 0.0
        # Position number tracking (auto-increment per position_id)
        self.position_counters: Dict[str, int] = {}  # {position_id: next_position_num}

    def set_current_tick_time(self, tick_time: datetime):
        """Set the current tick time for all timestamp operations."""
        self.current_tick_time = tick_time

    def reset_strategy(self, tick_time: Optional[datetime] = None):
        """Reset all data when strategy starts."""
        self.positions = {}
        self.node_variables = {}
        self.position_counters = {}  # Reset position counters
        self.strategy_start_time = tick_time or self.current_tick_time
        self.day_start_time = None

    def reset_day(self, tick_time: Optional[datetime] = None):
        """Reset day-specific data."""
        self.day_start_time = tick_time or self.current_tick_time
        # Reset position counters for new day
        self.position_counters = {}
        # Keep positions and node_variables across days

    def add_position(self, position_id: str, entry_data: Dict[str, Any], tick_time: Optional[datetime] = None):
        """
        Add a new entry for a position. Position IDs are stable and map to Entry node IDs.
        Maintains a transactions list per position. At most one open transaction at a time.
        """
        entry_timestamp = tick_time or self.current_tick_time
        if entry_timestamp is None:
            raise ValueError("No tick time available for position entry")

        # Convert timestamp to datetime if needed
        from datetime import datetime
        if isinstance(entry_timestamp, (int, float)):
            # Unix timestamp (seconds or milliseconds)
            if entry_timestamp > 1e10:  # Milliseconds
                entry_timestamp = datetime.fromtimestamp(entry_timestamp / 1000)
            else:  # Seconds
                entry_timestamp = datetime.fromtimestamp(entry_timestamp)
        elif isinstance(entry_timestamp, str):
            # ISO format string
            entry_timestamp = datetime.fromisoformat(entry_timestamp.replace('Z', '+00:00'))

        # Get or initialize position_num counter for this position_id
        if position_id not in self.position_counters:
            self.position_counters[position_id] = 1
        
        position_num = self.position_counters[position_id]
        
        # Check if there's already an open position (CRITICAL: only one open at a time)
        if self.has_open_position(position_id):
            raise ValueError(
                f"Position {position_id} already has an open transaction. "
                f"Cannot create position_num {position_num} until previous position closes."
            )
        
        # Add position_num to entry_data
        entry_data['position_num'] = position_num

        # Initialize container if new position
        if position_id not in self.positions:
            self.positions[position_id] = {
                "position_id": position_id,  # MANDATORY: Position ID for tracking
                "status": "open",
                "entry_time": entry_timestamp.isoformat() if hasattr(entry_timestamp, 'isoformat') else str(entry_timestamp),  # MANDATORY: Updated on entry
                "exit_time": None,  # MANDATORY: Updated on exit
                "close_reason": None,  # MANDATORY: Updated on exit
                "pnl": None,  # MANDATORY: Updated on exit (realized + unrealized)
                "quantity": entry_data.get("quantity", 0),  # MANDATORY: Actual traded quantity (lots × lot_size) for PNL calculation
                "lot_size": entry_data.get("lot_size", 1),  # Lot size multiplier (e.g., 50 for NIFTY)
                "lots": entry_data.get("lots", 1),  # Number of lots traded
                "entry_price": entry_data.get("price", 0),
                "exit_price": None,  # MANDATORY: Updated on exit
                "current_price": None,  # MANDATORY: Updated every tick
                "unrealized_pnl": None,  # MANDATORY: Updated every tick
                "realized_pnl": None,  # MANDATORY: Updated on exit
                "instrument": entry_data.get("instrument", ""),
                "symbol": entry_data.get("symbol", ""),  # Actual traded symbol (option contract)
                "exchange": entry_data.get("exchange", "NSE"),  # Exchange for exit orders
                "side": entry_data.get("side", "buy"),  # Position side (buy/sell)
                "strategy": entry_data.get("strategy", ""),
                "node_id": entry_data.get("node_id", ""),
                "reEntryNum": entry_data.get("reEntryNum", 0),
                "position_num": position_num,  # Sequential position number (starts at 1)
                "underlying_price_on_entry": entry_data.get("underlying_price_on_entry"),  # Underlying price at entry
                "node_variables": entry_data.get("node_variables", {}),  # Node variables snapshot at entry
                "transactions": []  # MANDATORY: Captures each order with order_id, position_id, node_id, and all order details
            }

        position = self.positions[position_id]

        # Enforce single open transaction at any time
        if position.get("transactions"):
            last_txn = position["transactions"][-1]
            if last_txn.get("status") == "open":
                # Do not allow a new open before closing the previous one
                raise ValueError(f"Position {position_id} already has an open transaction")

        # Append new transaction with complete order details
        txn = {
            "position_id": position_id,  # Position ID for tracking
            "order_id": entry_data.get("order_id"),  # Order ID from broker
            "broker_order_id": entry_data.get("broker_order_id"),  # Broker's order ID
            "node_id": entry_data.get("node_id"),  # Node that created this order
            "reEntryNum": entry_data.get("reEntryNum", 0),
            "position_num": position_num,  # Sequential position number
            "symbol": entry_data.get("symbol", ""),  # Traded symbol
            "exchange": entry_data.get("exchange", "NSE"),  # Exchange
            "side": entry_data.get("side", "buy"),  # BUY/SELL
            "quantity": entry_data.get("quantity", 0),  # Quantity
            "order_type": entry_data.get("order_type", "MARKET"),  # MARKET/LIMIT
            "product_type": entry_data.get("product_type", "INTRADAY"),  # INTRADAY/DELIVERY
            "entry_price": entry_data.get("price", 0),  # Entry price
            "entry": entry_data,  # Full entry data
            "exit": None,
            "status": "open",  # Order completion status
            "entry_time": entry_timestamp.isoformat() if hasattr(entry_timestamp, 'isoformat') else str(entry_timestamp),
            "exit_time": None,
            "pnl": None
        }
        position["transactions"].append(txn)
        
        # Increment counter for next position
        self.position_counters[position_id] += 1
        
        
        try:
            log_info(f"GPS: add_position {position_id} reEntryNum={txn.get('reEntryNum')} txns_count={len(position['transactions'])}")
        except Exception as e:
            from src.utils.error_handler import handle_exception
            handle_exception(e, "gps_add_position_logging", {
                "position_id": position_id,
                "reEntryNum": txn.get('reEntryNum'),
                "txns_count": len(position['transactions'])
            }, is_critical=False, continue_execution=True)

        # Mirror latest transaction to top-level for backward compatibility
        position["position_id"] = position_id  # MANDATORY: Position ID
        position["status"] = "open"
        position["entry_time"] = entry_timestamp.isoformat() if hasattr(entry_timestamp, 'isoformat') else str(entry_timestamp)  # MANDATORY: Updated
        position["exit_time"] = None  # MANDATORY: Will be updated on exit
        position["close_reason"] = None  # MANDATORY: Will be updated on exit
        position["pnl"] = None  # MANDATORY: Will be updated (realized + unrealized)
        position["quantity"] = entry_data.get("quantity", 0)  # MANDATORY: Actual traded quantity (lots × lot_size)
        position["lot_size"] = entry_data.get("lot_size", 1)  # Lot size multiplier
        position["lots"] = entry_data.get("lots", 1)  # Number of lots
        position["entry_price"] = entry_data.get("price", 0)
        position["exit_price"] = None  # MANDATORY: Will be updated on exit
        position["current_price"] = entry_data.get("price", 0)  # MANDATORY: Initialize with entry price, update every tick
        position["unrealized_pnl"] = 0.0  # MANDATORY: Initialize to 0, update every tick
        position["realized_pnl"] = None  # MANDATORY: Will be updated on exit
        position["instrument"] = entry_data.get("instrument", position.get("instrument", ""))
        position["symbol"] = entry_data.get("symbol", position.get("symbol", ""))  # Actual traded symbol
        position["exchange"] = entry_data.get("exchange", position.get("exchange", "NSE"))  # Exchange
        position["underlying_price_on_entry"] = entry_data.get("underlying_price_on_entry")  # Underlying price at entry
        position["node_variables"] = entry_data.get("node_variables", {})  # Node variables snapshot at entry
        position["side"] = entry_data.get("side", position.get("side", "buy"))  # Position side
        position["strategy"] = entry_data.get("strategy", position.get("strategy", ""))
        position["node_id"] = entry_data.get("node_id", position.get("node_id", ""))
        position["reEntryNum"] = entry_data.get("reEntryNum", 0)
        position["position_num"] = position_num  # Update position_num

    def close_position(self, position_id: str, exit_data: Dict[str, Any], tick_time: Optional[datetime] = None):
        """
        Close the last open transaction for a position. If none open, no-op with graceful status.
        """
        if position_id not in self.positions:
            return  # Nothing to close

        exit_timestamp = tick_time or self.current_tick_time
        if exit_timestamp is None:
            raise ValueError("No tick time available for position exit")

        # Convert timestamp to datetime if needed
        from datetime import datetime
        if isinstance(exit_timestamp, (int, float)):
            # Unix timestamp (seconds or milliseconds)
            if exit_timestamp > 1e10:  # Milliseconds
                exit_timestamp = datetime.fromtimestamp(exit_timestamp / 1000)
            else:  # Seconds
                exit_timestamp = datetime.fromtimestamp(exit_timestamp)
        elif isinstance(exit_timestamp, str):
            # ISO format string
            exit_timestamp = datetime.fromisoformat(exit_timestamp.replace('Z', '+00:00'))

        position = self.positions[position_id]
        if not position.get("transactions"):
            return

        last_txn = position["transactions"][-1]
        if last_txn.get("status") != "open":
            return  # Already closed

        # Close transaction
        last_txn["exit"] = exit_data
        last_txn["status"] = "closed"
        last_txn["exit_time"] = exit_timestamp.isoformat() if hasattr(exit_timestamp, 'isoformat') else str(exit_timestamp)
        try:
            log_info(f"GPS: close_position {position_id} reEntryNum={last_txn.get('reEntryNum')} txns_count={len(position['transactions'])}")
        except Exception as e:
            from src.utils.error_handler import handle_exception
            handle_exception(e, "gps_close_position_logging", {
                "position_id": position_id,
                "reEntryNum": last_txn.get('reEntryNum'),
                "txns_count": len(position['transactions'])
            }, is_critical=False, continue_execution=True)

        # Calculate PnL based on entry/exit
        entry_price = position.get("entry_price") or last_txn.get("entry", {}).get("price")
        exit_price = exit_data.get("price", 0)
        quantity = position.get("quantity") or last_txn.get("entry", {}).get("quantity", 0)
        side = last_txn.get("entry", {}).get("side", "buy").lower()
        if entry_price and exit_price and quantity:
            if side == "buy":
                last_txn["pnl"] = (exit_price - entry_price) * quantity
            else:
                last_txn["pnl"] = (entry_price - exit_price) * quantity

        # Debug-only: emit a detailed close summary for verification
        try:
            log_info(
                f"GPS close summary | position_id={position_id} reEntryNum={last_txn.get('reEntryNum')} "
                f"side={side} qty={quantity} entry_time={last_txn.get('entry_time')} entry_price={entry_price} "
                f"exit_time={last_txn.get('exit_time')} exit_price={exit_price} txn_pnl={last_txn.get('pnl')}"
            )
        except Exception as e:
            from src.utils.error_handler import handle_exception
            handle_exception(e, "gps_close_summary_logging", {
                "position_id": position_id,
                "reEntryNum": last_txn.get('reEntryNum'),
                "side": side,
                "quantity": quantity
            }, is_critical=False, continue_execution=True)

        # Mirror latest transaction to top-level
        position["status"] = "closed"
        position["exit_time"] = exit_timestamp.isoformat()  # MANDATORY: Updated on exit
        position["close_reason"] = exit_data.get("reason", "unknown")  # MANDATORY: Updated on exit
        position["exit_price"] = exit_price  # MANDATORY: Updated on exit
        # Calculate TOTAL realized P&L from ALL transactions (not just last one)
        try:
            transactions = position.get("transactions", [])
            total_pnl = 0.0
            for txn in transactions:
                txn_pnl = txn.get("pnl")
                if txn_pnl is not None:
                    total_pnl += float(txn_pnl)
            position["pnl"] = total_pnl
            position["realized_pnl"] = total_pnl
            log_info(f"✅ Position {position_id} total PNL: {total_pnl} (from {len(transactions)} transactions)")
        except Exception as e:
            log_error(f"❌ Error calculating position PNL: {e}")
            import traceback
            log_error(traceback.format_exc())
            from src.utils.error_handler import handle_exception
            handle_exception(e, "gps_pnl_conversion", {
                "position_id": position_id,
                "transactions_count": len(position.get("transactions", []))
            }, is_critical=False, continue_execution=True)
        if "reEntryNum" in exit_data:
            position["reEntryNum"] = exit_data.get("reEntryNum")
        
        # Update overall GPS PNL after closing position
        self._update_overall_pnl()

    def update_position_prices(self, current_ltp_store: Dict[str, Any]):
        """
        MANDATORY: Update current_price and unrealized_pnl for all open positions every tick.
        
        Args:
            current_ltp_store: Dictionary with current LTP values
        """
        for position_id, position in self.positions.items():
            # Only update open positions
            if position.get("status") != "open":
                continue
                
            # Get position details
            entry_price = position.get("entry_price")
            quantity = position.get("quantity", 0)
            side = position.get("side", "buy").lower()
            instrument = position.get("instrument", "")
            
            # Get current LTP - try to match by instrument
            current_ltp = None
            for ltp_key, ltp_data in current_ltp_store.items():
                if isinstance(ltp_data, dict):
                    if ltp_data.get("symbol") == instrument or ltp_key == "ltp_TI":
                        current_ltp = ltp_data.get("ltp") or ltp_data.get("price")
                        break
            
            # Update current_price (MANDATORY: every tick)
            if current_ltp:
                position["current_price"] = current_ltp
                
                # Calculate and update unrealized_pnl (MANDATORY: every tick)
                if entry_price and quantity:
                    if side == "buy":
                        position["unrealized_pnl"] = (current_ltp - entry_price) * quantity
                    else:
                        position["unrealized_pnl"] = (entry_price - current_ltp) * quantity
                    
                    # Update total pnl (realized + unrealized)
                    realized = position.get("realized_pnl") or 0.0
                    position["pnl"] = realized + position["unrealized_pnl"]

    def _update_overall_pnl(self, current_ltp_store: Optional[Dict[str, Any]] = None):
        """Update overall PNL by summing all positions."""
        pnl_data = self.get_total_pnl(current_ltp_store)
        self.overall_realized_pnl = pnl_data['realized']
        self.overall_unrealized_pnl = pnl_data['unrealized']
        self.overall_pnl = pnl_data['overall']

    def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get position data by ID."""
        return self.positions.get(position_id)

    def get_open_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all positions whose last transaction is open."""
        result: Dict[str, Dict[str, Any]] = {}
        for pid, pos in self.positions.items():
            txns = pos.get("transactions", [])
            if txns and txns[-1].get("status") == "open":
                result[pid] = pos
        return result

    def get_closed_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all positions whose last transaction is closed."""
        result: Dict[str, Dict[str, Any]] = {}
        for pid, pos in self.positions.items():
            txns = pos.get("transactions", [])
            if txns and txns[-1].get("status") == "closed":
                result[pid] = pos
        return result

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all positions (open and closed)."""
        return self.positions.copy()

    def set_node_variable(self, node_id: str, variable_name: str, value: Any):
        """Set a variable for a specific node."""
        if node_id not in self.node_variables:
            self.node_variables[node_id] = {}
        self.node_variables[node_id][variable_name] = value

    def get_node_variable(self, node_id: str, variable_name: str) -> Optional[Any]:
        """Get a variable for a specific node."""
        return self.node_variables.get(node_id, {}).get(variable_name)

    def get_node_variables(self, node_id: str) -> Dict[str, Any]:
        """Get all variables for a specific node."""
        return self.node_variables.get(node_id, {}).copy()

    def get_all_node_variables(self) -> Dict[str, Dict[str, Any]]:
        """Get all node variables."""
        return self.node_variables.copy()

    def get_total_pnl(self, current_ltp_store: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Calculate total P&L across all positions.
        
        Args:
            current_ltp_store: Optional dict with current LTP values for unrealized P&L calculation
            
        Returns:
            Dict with 'realized', 'unrealized', and 'overall' P&L values
        """
        total_realized = 0.0
        total_unrealized = 0.0
        
        for position_id, position in self.positions.items():
            transactions = position.get("transactions", [])
            if not transactions:
                continue
                
            last_txn = transactions[-1]
            
            # Add realized P&L from ALL closed transactions in this position
            if last_txn.get("status") == "closed":
                # Sum ALL transactions for this position
                for txn in transactions:
                    if txn.get("status") == "closed" and txn.get("pnl") is not None:
                        total_realized += float(txn.get("pnl"))
            
            # Calculate unrealized P&L for open transactions
            elif last_txn.get("status") == "open" and current_ltp_store:
                entry_price = position.get("entry_price")
                quantity = position.get("quantity", 0)
                side = last_txn.get("entry", {}).get("side", "buy").lower()
                
                # Get current LTP - try to match by instrument
                instrument = position.get("instrument", "")
                current_ltp = None
                
                # Try to find matching LTP from store
                for ltp_key, ltp_data in current_ltp_store.items():
                    if isinstance(ltp_data, dict):
                        if ltp_data.get("symbol") == instrument or ltp_key == "ltp_TI":
                            current_ltp = ltp_data.get("ltp") or ltp_data.get("price")
                            break
                
                # Calculate unrealized P&L if we have all required data
                if entry_price and current_ltp and quantity:
                    if side == "buy":
                        unrealized_pnl = (current_ltp - entry_price) * quantity
                    else:
                        unrealized_pnl = (entry_price - current_ltp) * quantity
                    total_unrealized += unrealized_pnl
        
        return {
            "realized": total_realized,
            "unrealized": total_unrealized,
            "overall": total_realized + total_unrealized
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert GPS to dictionary for JSON serialization."""
        return {
            "positions": self.positions,
            "node_variables": self.node_variables,
            "strategy_start_time": self.strategy_start_time.isoformat() if self.strategy_start_time else None,
            "day_start_time": self.day_start_time.isoformat() if self.day_start_time else None,
            "overall_realized_pnl": self.overall_realized_pnl,
            "overall_unrealized_pnl": self.overall_unrealized_pnl,
            "overall_pnl": self.overall_pnl
        }

    def from_dict(self, data: Dict[str, Any]):
        """Load GPS from dictionary."""
        self.positions = data.get("positions", {})
        self.node_variables = data.get("node_variables", {})

        strategy_start = data.get("strategy_start_time")
        if strategy_start:
            self.strategy_start_time = datetime.fromisoformat(strategy_start)

        day_start = data.get("day_start_time")
        if day_start:
            self.day_start_time = datetime.fromisoformat(day_start)

    def to_json(self) -> str:
        """Convert GPS to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    def from_json(self, json_str: str):
        """Load GPS from JSON string."""
        data = json.loads(json_str)
        self.from_dict(data)
    
    # Helper methods for re-entry logic
    
    def has_open_position(self, position_id: str) -> bool:
        """
        Check if position_id has any open transaction.
        Returns True if there's an open position, False otherwise.
        """
        if position_id not in self.positions:
            return False
        
        position = self.positions[position_id]
        transactions = position.get("transactions", [])
        
        if not transactions:
            return False
        
        # Check if last transaction is open
        last_txn = transactions[-1]
        return last_txn.get("status") == "open"
    
    def get_latest_position_num(self, position_id: str) -> int:
        """
        Get the latest (highest) position_num for this position_id.
        Returns 0 if no positions exist yet.
        """
        if position_id not in self.position_counters:
            return 0
        
        # Counter is already incremented, so subtract 1 to get latest
        return self.position_counters[position_id] - 1
    
    def get_open_position_for_id(self, position_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the currently open position for this position_id.
        Returns None if no open position exists.
        """
        if not self.has_open_position(position_id):
            return None
        
        return self.positions.get(position_id)
