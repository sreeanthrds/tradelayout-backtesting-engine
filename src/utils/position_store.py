from typing import Dict, List, Any, Optional

from src.utils.recursive_processor import process_recursive, deep_copy


class PositionStore:
    """
    Central position store for tracking all positions and trades.
    - Unified JSON schema for STOCKS, futures, and options.
    - Supports multi-leg trades and re-entries.
    - Stores detailed fields for future extensibility.
    """

    def __init__(self):
        self.positions = {}  # position_id -> position_data
        self.trades = []  # List of all trades
        self.entries = []  # List of all entries
        self.exits = []  # List of all exits
        self.next_position_id = 1
        self.next_order_id = 1

    def add_entry(self, entry_data: Dict[str, Any]):
        """
        Add an entry to the position store.
        
        Args:
            entry_data: Entry data with all required fields
        """
        # Process entry data using recursive processor
        processed_entry = process_recursive(entry_data)

        # Validate required fields
        required_fields = ['nodeId', 'positionId', 'instrument', 'quantity', 'entryPrice', 'entryTime']
        for field in required_fields:
            if field not in processed_entry:
                raise ValueError(f"Missing required field: {field}")

        # Create position if it doesn't exist
        position_id = processed_entry['positionId']
        if position_id not in self.positions:
            self.positions[position_id] = {
                'positionId': position_id,
                'instrument': processed_entry['instrument'],
                'quantity': processed_entry['quantity'],
                'positionType': processed_entry.get('positionType', 'buy'),
                'productType': processed_entry.get('productType', 'intraday'),
                'entries': [],
                'exits': [],
                'status': 'open',
                'currentQuantity': 0,
                'averageEntryPrice': 0,
                'totalEntryValue': 0,
                'pnl': 0,
                'realizedPnl': 0,
                'unrealizedPnl': 0
            }

        # Add entry to position
        position = self.positions[position_id]
        position['entries'].append(processed_entry)

        # Update position metrics
        self._update_position_metrics(position_id)

        # Add to entries list
        self.entries.append(processed_entry)

        # Create trade record
        trade_record = deep_copy(processed_entry)
        trade_record['tradeType'] = 'entry'
        trade_record['timestamp'] = processed_entry['entryTime']
        self.trades.append(trade_record)

    def add_exit(self, positionId: str, trade_pair_index: str, exit_data: dict):
        """
        Add an exit leg to an existing trade.
        """
        # Process exit data using recursive processor
        processed_exit = process_recursive(exit_data)

        # Find the trade and trade pair
        trade = next((t for t in self.trades if t["positionId"] == positionId), None)
        if not trade:
            raise ValueError(f"Trade with positionId {positionId} not found")

        trade_pair = next((tp for tp in trade["tradePairs"] if tp["index"] == trade_pair_index), None)
        if not trade_pair:
            raise ValueError(f"Trade pair {trade_pair_index} not found in trade {positionId}")

        # Add exit data
        trade_pair["exit"] = processed_exit

        # Update trade status
        trade["exitDate"] = processed_exit["timestamp"][:10]
        trade["exitTime"] = processed_exit["timestamp"][11:19]
        trade["status"] = "Closed"

        # Calculate P&L
        entry_price = trade_pair["entry"]["entryPrice"]
        exit_price = processed_exit["exitPrice"]
        quantity = trade_pair["entry"]["quantity"]

        if trade_pair["entry"]["positionType"] == "buy":
            profit_loss = (exit_price - entry_price) * quantity
        else:
            profit_loss = (entry_price - exit_price) * quantity

        trade["profitLoss"] = profit_loss

        # Add to exits list
        self.exits.append(processed_exit)

        # Update position metrics
        if positionId in self.positions:
            self._update_position_metrics(positionId)

    def get_trade(self, positionId: str) -> dict:
        for t in self.trades:
            if t["positionId"] == positionId:
                return t
        return None

    def get_all_trades(self) -> List[Dict[str, Any]]:
        """
        Get all trades in the store.
        
        Returns:
            List of all trades
        """
        return deep_copy(self.trades)

    def update_status(self, positionId: str, status: str):
        for t in self.trades:
            if t["positionId"] == positionId:
                t["status"] = status

    def to_json(self) -> dict:
        return {"trades": self.trades}

    def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific position by ID.
        
        Args:
            position_id: Position ID to retrieve
            
        Returns:
            Position data or None if not found
        """
        return deep_copy(self.positions.get(position_id))

    def get_all_positions(self) -> Dict[str, Any]:
        """
        Get all positions.
        
        Returns:
            Dictionary of all positions
        """
        return deep_copy(self.positions)

    def _update_position_metrics(self, position_id: str):
        """
        Update position metrics after entry/exit.
        
        Args:
            position_id: Position ID to update
        """
        position = self.positions[position_id]

        # Calculate current quantity and average entry price
        total_quantity = 0
        total_value = 0

        for entry in position['entries']:
            quantity = entry['quantity']
            price = entry['entryPrice']
            total_quantity += quantity
            total_value += quantity * price

        position['currentQuantity'] = total_quantity
        position['totalEntryValue'] = total_value
        position['averageEntryPrice'] = total_value / total_quantity if total_quantity > 0 else 0

        # Update status
        if total_quantity == 0:
            position['status'] = 'closed'
        else:
            position['status'] = 'open'

    def reset_for_new_day(self):
        """
        Reset position store for a new trading day.
        This ensures daily isolation and prevents carry-over issues.
        """
        # Clear all positions and trades for the new day
        self.positions = {}
        self.trades = []
        self.next_position_id = 1
        self.next_order_id = 1

        # log_info("🔄 Position store reset for new day")

    def export_json(self):
        # Implementation of export_json method
        pass

    def get_positions_snapshot(self):
        """
        Return a snapshot of all positions (shallow copy).
        This is for compatibility with code expecting this method.
        """
        return self.get_all_positions()
