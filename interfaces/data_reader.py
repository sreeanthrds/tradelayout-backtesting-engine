"""
DataReader Interface - Zero Dependency on Old Context

This interface defines how to read data from Cache/DB.
NO dependency on old context_manager, candle_df_dict, ltp_store, etc.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime


class DataReaderInterface(ABC):
    """
    Interface for reading data from Cache/DB.
    
    Implementations:
    - RedisClickHouseDataReader: Reads from Redis cache → ClickHouse fallback
    - BacktestingDataReader: Reads from in-memory DataFrames for backtesting
    - ReplayDataReader: Reads from ClickHouse for replay mode
    """
    
    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        n: int = 100
    ) -> pd.DataFrame:
        """
        Get last N closed candles for symbol-timeframe.
        
        Args:
            symbol: Trading symbol (e.g., 'NIFTY', 'BANKNIFTY')
            timeframe: Timeframe (e.g., '1m', '5m', '15m', '30m', '1h', '1d')
            n: Number of candles to fetch (default 100)
        
        Returns:
            DataFrame with columns: ts (index), open, high, low, close, volume
            Empty DataFrame if no data available
        
        Example:
            df = await data_reader.get_candles('NIFTY', '5m', 100)
            # Returns last 100 5-minute candles for NIFTY
        """
        pass
    
    @abstractmethod
    async def get_indicators(
        self,
        symbol: str,
        timeframe: str
    ) -> Dict[str, float]:
        """
        Get latest indicator values for symbol-timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            Dictionary of indicator_name -> value
            {
                'EMA_20': 25900.5,
                'RSI_14': 65.3,
                'MACD': 12.5,
                'MACD_signal': 10.2,
                'MACD_histogram': 2.3,
                'BB_upper': 26000.0,
                'BB_middle': 25900.0,
                'BB_lower': 25800.0
            }
        
        Example:
            indicators = await data_reader.get_indicators('NIFTY', '5m')
            ema_20 = indicators.get('EMA_20', 0)
        """
        pass
    
    @abstractmethod
    async def get_ltp(self, symbol: str) -> Dict[str, Any]:
        """
        Get latest LTP (Last Traded Price) for symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Dictionary with tick data:
            {
                'ltp': 25900.0,
                'timestamp': datetime(2025, 11, 6, 10, 30, 0),
                'volume': 1000000,
                'oi': 50000,
                'bid': 25899.5,
                'ask': 25900.5,
                'bid_qty': 100,
                'ask_qty': 150
            }
        
        Example:
            ltp_data = await data_reader.get_ltp('NIFTY')
            current_price = ltp_data.get('ltp', 0)
        """
        pass
    
    @abstractmethod
    async def get_positions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get open positions for user.
        
        Args:
            user_id: User ID
        
        Returns:
            List of position dictionaries:
            [
                {
                    'position_id': 'entry-3-pos1',
                    'symbol': 'NIFTY28NOV2525900CE',
                    'exchange': 'NFO',
                    'transaction_type': 'BUY',
                    'quantity': 75,
                    'entry_price': 150.0,
                    'current_price': 155.0,
                    'pnl': 375.0,
                    'entry_time': datetime(2025, 11, 6, 10, 15, 0),
                    'status': 'OPEN'
                }
            ]
        
        Example:
            positions = await data_reader.get_positions('user123')
            for pos in positions:
                print(f"Position: {pos['symbol']}, PNL: {pos['pnl']}")
        """
        pass
    
    @abstractmethod
    async def get_node_variable(
        self,
        user_id: str,
        strategy_id: str,
        node_id: str,
        variable_name: str
    ) -> Optional[float]:
        """
        Get node variable value.
        
        Args:
            user_id: User ID
            strategy_id: Strategy ID
            node_id: Node ID
            variable_name: Variable name
        
        Returns:
            Variable value (float) or None if not found
        
        Example:
            entry_price = await data_reader.get_node_variable(
                'user123', 'strategy456', 'entry-3', 'entry_price'
            )
        """
        pass
    
    @abstractmethod
    async def get_node_state(
        self,
        user_id: str,
        strategy_id: str,
        node_id: str
    ) -> Dict[str, Any]:
        """
        Get node state.
        
        Args:
            user_id: User ID
            strategy_id: Strategy ID
            node_id: Node ID
        
        Returns:
            Node state dictionary:
            {
                'status': 'Active',  # 'Active', 'Inactive', 'Pending'
                'visited': False,
                're_entry_num': 0
            }
        
        Example:
            state = await data_reader.get_node_state('user123', 'strategy456', 'entry-3')
            is_active = state.get('status') == 'Active'
        """
        pass
    
    @abstractmethod
    async def get_all_node_states(
        self,
        user_id: str,
        strategy_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get all node states for a strategy.
        
        Args:
            user_id: User ID
            strategy_id: Strategy ID
        
        Returns:
            Dictionary of node_id -> state:
            {
                'start-1': {'status': 'Active', 'visited': False, 're_entry_num': 0},
                'entry-3': {'status': 'Inactive', 'visited': False, 're_entry_num': 0},
                'exit-5': {'status': 'Inactive', 'visited': False, 're_entry_num': 0}
            }
        
        Example:
            states = await data_reader.get_all_node_states('user123', 'strategy456')
            for node_id, state in states.items():
                print(f"{node_id}: {state['status']}")
        """
        pass
    
    @abstractmethod
    async def get_position_by_id(
        self,
        user_id: str,
        position_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific position by ID.
        
        Args:
            user_id: User ID
            position_id: Position ID
        
        Returns:
            Position dictionary or None if not found
        
        Example:
            position = await data_reader.get_position_by_id('user123', 'entry-3-pos1')
            if position:
                print(f"PNL: {position['pnl']}")
        """
        pass
