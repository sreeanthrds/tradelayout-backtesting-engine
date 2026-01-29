"""
DataFrame Writer - Backtesting Implementation

Stores candles and indicators in-memory using Pandas DataFrames.
No database writes - pure in-memory for maximum speed.
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class DataFrameWriter:
    """
    In-memory DataFrame-based data writer for backtesting.
    
    Stores:
    - OHLCV candles in DataFrames (one per symbol+timeframe)
    - Indicators as additional columns in the same DataFrames
    
    Structure:
    {
        'NIFTY:1m': DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'EMA_20', 'RSI_14', ...]),
        'NIFTY:5m': DataFrame(...),
        'BANKNIFTY:1m': DataFrame(...),
    }
    """
    
    def __init__(self):
        """Initialize DataFrame writer."""
        # Store DataFrames by symbol:timeframe key
        self.dataframes: Dict[str, pd.DataFrame] = {}
        
        # Track which indicators exist for each symbol:timeframe
        self.indicators: Dict[str, set] = defaultdict(set)
        
        logger.info("📊 DataFrame Writer initialized (in-memory)")
    
    def _get_key(self, symbol: str, timeframe: str) -> str:
        """Get storage key for symbol+timeframe."""
        return f"{symbol}:{timeframe}"
    
    def initialize_from_historical(self, symbol: str, timeframe: str, historical_df: pd.DataFrame):
        """
        Initialize DataFrame with historical data.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            historical_df: Historical OHLCV DataFrame with columns:
                ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        key = self._get_key(symbol, timeframe)
        
        # Ensure timestamp is datetime
        if 'timestamp' in historical_df.columns:
            historical_df['timestamp'] = pd.to_datetime(historical_df['timestamp'])
        
        # Sort by timestamp
        historical_df = historical_df.sort_values('timestamp').reset_index(drop=True)
        
        self.dataframes[key] = historical_df.copy()
        
        logger.info(f"✅ Initialized {key} with {len(historical_df)} historical candles")
    
    def write_candle(self, candle: Dict) -> bool:
        """
        Write a single candle to DataFrame.
        
        Args:
            candle: Candle data
        
        Returns:
            True if successful
        """
        try:
            symbol = candle['symbol']
            timeframe = candle['timeframe']
            key = self._get_key(symbol, timeframe)
            
            # Create DataFrame if doesn't exist
            if key not in self.dataframes:
                self.dataframes[key] = pd.DataFrame(columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume'
                ])
            
            df = self.dataframes[key]
            
            # Check if candle already exists (update) or new (append)
            timestamp = pd.to_datetime(candle['timestamp'])
            existing = df[df['timestamp'] == timestamp]
            
            if len(existing) > 0:
                # Update existing candle
                idx = existing.index[0]
                df.loc[idx, 'open'] = candle.get('open', df.loc[idx, 'open'])
                df.loc[idx, 'high'] = max(candle.get('high', 0), df.loc[idx, 'high'])
                df.loc[idx, 'low'] = min(candle.get('low', float('inf')), df.loc[idx, 'low'])
                df.loc[idx, 'close'] = candle.get('close', df.loc[idx, 'close'])
                df.loc[idx, 'volume'] = candle.get('volume', 0) + df.loc[idx, 'volume']
            else:
                # Append new candle
                new_row = pd.DataFrame([{
                    'timestamp': timestamp,
                    'open': candle.get('open'),
                    'high': candle.get('high'),
                    'low': candle.get('low'),
                    'close': candle.get('close'),
                    'volume': candle.get('volume', 0)
                }])
                
                self.dataframes[key] = pd.concat([df, new_row], ignore_index=True)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error writing candle: {e}")
            return False
    
    def write_indicator(self, indicator: Dict) -> bool:
        """
        Write indicator value to DataFrame.
        
        Adds indicator as a new column if doesn't exist.
        
        Args:
            indicator: Indicator data
        
        Returns:
            True if successful
        """
        try:
            symbol = indicator['symbol']
            timeframe = indicator['timeframe']
            indicator_name = indicator['indicator_name']
            value = indicator['value']
            timestamp = pd.to_datetime(indicator['timestamp'])
            
            key = self._get_key(symbol, timeframe)
            
            # Ensure DataFrame exists
            if key not in self.dataframes:
                logger.warning(f"⚠️  DataFrame for {key} doesn't exist, creating empty")
                self.dataframes[key] = pd.DataFrame(columns=['timestamp'])
            
            df = self.dataframes[key]
            
            # Add indicator column if doesn't exist
            if indicator_name not in df.columns:
                df[indicator_name] = None
                self.indicators[key].add(indicator_name)
            
            # Find row with matching timestamp
            mask = df['timestamp'] == timestamp
            
            if mask.any():
                df.loc[mask, indicator_name] = value
            else:
                logger.warning(f"⚠️  No candle found for timestamp {timestamp} in {key}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error writing indicator: {e}")
            return False
    
    def get_latest_candles(self, symbol: str, timeframe: str, count: int = 10) -> List[Dict]:
        """
        Get latest N candles.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            count: Number of candles
        
        Returns:
            List of candle dictionaries
        """
        try:
            key = self._get_key(symbol, timeframe)
            
            if key not in self.dataframes:
                return []
            
            df = self.dataframes[key]
            
            # Get last N rows
            latest = df.tail(count)
            
            # Convert to list of dicts
            candles = latest.to_dict('records')
            
            return candles
            
        except Exception as e:
            logger.error(f"❌ Error getting latest candles: {e}")
            return []
    
    def get_indicator_value(self, symbol: str, timeframe: str, indicator_name: str) -> Optional[float]:
        """
        Get latest indicator value.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Indicator name
        
        Returns:
            Latest indicator value or None
        """
        try:
            key = self._get_key(symbol, timeframe)
            
            if key not in self.dataframes:
                return None
            
            df = self.dataframes[key]
            
            if indicator_name not in df.columns:
                return None
            
            # Get last non-null value
            values = df[indicator_name].dropna()
            
            if len(values) == 0:
                return None
            
            return float(values.iloc[-1])
            
        except Exception as e:
            logger.error(f"❌ Error getting indicator value: {e}")
            return None
    
    def get_dataframe(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get raw DataFrame for symbol+timeframe.
        
        Useful for debugging and analysis.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            DataFrame or None
        """
        key = self._get_key(symbol, timeframe)
        return self.dataframes.get(key)
    
    def get_all_dataframes(self) -> Dict[str, pd.DataFrame]:
        """
        Get all DataFrames.
        
        Returns:
            Dictionary of symbol:timeframe -> DataFrame
        """
        return self.dataframes.copy()
    
    def get_stats(self) -> Dict:
        """
        Get statistics about stored data.
        
        Returns:
            Dictionary with stats
        """
        stats = {
            'total_dataframes': len(self.dataframes),
            'dataframes': {}
        }
        
        for key, df in self.dataframes.items():
            stats['dataframes'][key] = {
                'rows': len(df),
                'columns': list(df.columns),
                'indicators': list(self.indicators.get(key, []))
            }
        
        return stats
