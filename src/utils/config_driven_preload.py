#!/usr/bin/env python3
"""
Config-Driven Preload System

Loads historical data based on strategy configuration:
- Only timeframes mentioned in strategy
- Only symbols mentioned in strategy
- Respects lookback days per timeframe
- Skips unavailable data gracefully
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigDrivenPreload:
    """
    Preload historical data based on strategy configuration
    """
    
    # Lookback days specification per timeframe
    LOOKBACK_SPECS = {
        "1m": 5,
        "3m": 7,
        "5m": 10,
        "10m": 20,
        "15m": 30,
        "30m": 60,
        "60m": 120,  # 1h
        "1h": 120,   # Alias for 60m
        "1d": 750
    }
    
    # Symbol mapping for yfinance
    SYMBOL_MAP = {
        'NIFTY': '^NSEI',
        'BANKNIFTY': '^NSEBANK',
        'FINNIFTY': '^CNXFIN',
        'SENSEX': '^BSESN',
    }
    
    # Timeframe mapping: strategy format → yfinance format
    TIMEFRAME_MAP = {
        '1m': '1m',
        '3m': '5m',   # yfinance doesn't have 3m, use 5m and resample
        '5m': '5m',
        '10m': '15m', # yfinance doesn't have 10m, use 15m and resample
        '15m': '15m',
        '30m': '30m',
        '60m': '1h',
        '1h': '1h',
        '1d': '1d'
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_required_symbols(self, strategy_config: dict) -> List[str]:
        """
        Extract all symbols mentioned in strategy config
        
        Args:
            strategy_config: Strategy configuration
        
        Returns:
            List of unique symbols
        """
        symbols = set()
        
        # Main symbol
        main_symbol = strategy_config.get('symbol')
        if main_symbol:
            symbols.add(main_symbol)
        
        # Symbols from trading instruments
        trading_instruments = strategy_config.get('tradingInstruments', [])
        for instrument in trading_instruments:
            symbol = instrument.get('symbol')
            if symbol:
                symbols.add(symbol)
        
        # Symbols from conditions (if any reference other symbols)
        # This can be extended based on your strategy structure
        
        return list(symbols)
    
    def extract_required_timeframes(self, strategy_config: dict) -> List[str]:
        """
        Extract all timeframes mentioned in strategy config
        
        Args:
            strategy_config: Strategy configuration
        
        Returns:
            List of unique timeframes
        """
        timeframes = set()
        
        # Main timeframe
        main_tf = strategy_config.get('timeframe')
        if main_tf:
            timeframes.add(main_tf)
        
        # Timeframes from trading instruments
        trading_instruments = strategy_config.get('tradingInstruments', [])
        for instrument in trading_instruments:
            tf = instrument.get('timeframe')
            if tf:
                timeframes.add(tf)
        
        # Timeframes from indicators (if they specify different timeframes)
        # This can be extended based on your strategy structure
        
        return list(timeframes)
    
    def get_yfinance_symbol(self, symbol: str, exchange: str = 'NSE') -> Optional[str]:
        """Convert internal symbol to yfinance symbol"""
        if symbol in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[symbol]
        
        # For stocks
        if exchange == 'NSE':
            return f"{symbol}.NS"
        elif exchange == 'BSE':
            return f"{symbol}.BO"
        
        return None
    
    def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str,
        lookback_days: int,
        exchange: str = 'NSE'
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol and timeframe
        
        Args:
            symbol: Symbol name
            timeframe: Timeframe (1m, 5m, etc.)
            lookback_days: Number of days to look back
            exchange: Exchange (NSE, BSE)
        
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            # Get yfinance symbol
            yf_symbol = self.get_yfinance_symbol(symbol, exchange)
            if not yf_symbol:
                self.logger.warning(f"Could not map symbol: {symbol}")
                return None
            
            # Get yfinance interval
            yf_interval = self.TIMEFRAME_MAP.get(timeframe)
            if not yf_interval:
                self.logger.warning(f"Unsupported timeframe: {timeframe}")
                return None
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            
            self.logger.info(f"Fetching {symbol} ({yf_symbol}) {timeframe} for {lookback_days} days...")
            
            # Fetch data
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(start=start_date, end=end_date, interval=yf_interval)
            
            if data.empty:
                self.logger.warning(f"No data for {symbol} {timeframe}")
                return None
            
            # Standardize columns
            data = data.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Keep only OHLCV
            data = data[['open', 'high', 'low', 'close', 'volume']]
            
            # Reset index
            data = data.reset_index()
            data = data.rename(columns={'Datetime': 'timestamp', 'Date': 'timestamp'})
            
            # Convert timezone-aware to naive
            if hasattr(data['timestamp'].iloc[0], 'tz_localize'):
                data['timestamp'] = data['timestamp'].dt.tz_localize(None)
            
            # Resample if needed (for 3m, 10m which yfinance doesn't have)
            if timeframe == '3m' and yf_interval == '5m':
                data = self._resample_to_3m(data)
            elif timeframe == '10m' and yf_interval == '15m':
                data = self._resample_to_10m(data)
            
            self.logger.info(f"✅ Fetched {len(data)} candles for {symbol} {timeframe}")
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching {symbol} {timeframe}: {e}")
            return None
    
    def _resample_to_3m(self, data: pd.DataFrame) -> pd.DataFrame:
        """Resample 5m data to 3m (approximate)"""
        # For simplicity, just return 5m data
        # True 3m resampling would require 1m data
        self.logger.warning("3m not natively supported, using 5m data")
        return data
    
    def _resample_to_10m(self, data: pd.DataFrame) -> pd.DataFrame:
        """Resample 15m data to 10m (approximate)"""
        # For simplicity, just return 15m data
        self.logger.warning("10m not natively supported, using 15m data")
        return data
    
    def preload_for_strategy(
        self,
        strategy_config: dict
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Preload all required data based on strategy configuration
        
        Args:
            strategy_config: Strategy configuration from Supabase
        
        Returns:
            Dict: {symbol: {timeframe: DataFrame}}
        """
        self.logger.info("=" * 70)
        self.logger.info("📥 PRELOADING DATA (Config-Driven)")
        self.logger.info("=" * 70)
        
        # Extract requirements from config
        symbols = self.extract_required_symbols(strategy_config)
        timeframes = self.extract_required_timeframes(strategy_config)
        
        self.logger.info(f"Symbols: {symbols}")
        self.logger.info(f"Timeframes: {timeframes}")
        self.logger.info("")
        
        # Preload data
        preloaded_data = {}
        
        for symbol in symbols:
            preloaded_data[symbol] = {}
            
            self.logger.info(f"📊 Preloading {symbol}")
            self.logger.info("-" * 70)
            
            for timeframe in timeframes:
                # Get lookback days for this timeframe
                lookback_days = self.LOOKBACK_SPECS.get(timeframe)
                
                if lookback_days is None:
                    self.logger.warning(f"   ⚠️  {timeframe}: No lookback spec, skipping")
                    continue
                
                # Fetch data
                data = self.fetch_historical_data(symbol, timeframe, lookback_days)
                
                if data is not None:
                    preloaded_data[symbol][timeframe] = data
                    first = data['timestamp'].iloc[0].strftime('%Y-%m-%d %H:%M')
                    last = data['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M')
                    self.logger.info(f"   ✅ {timeframe}: {len(data)} candles ({first} to {last})")
                else:
                    self.logger.warning(f"   ❌ {timeframe}: Failed to fetch, skipping")
            
            self.logger.info("")
        
        # Summary
        self.logger.info("=" * 70)
        self.logger.info("✅ PRELOAD COMPLETE")
        self.logger.info("=" * 70)
        
        total_candles = 0
        for symbol, tfs in preloaded_data.items():
            for tf, df in tfs.items():
                total_candles += len(df)
        
        self.logger.info(f"Total: {total_candles} candles across {len(symbols)} symbols")
        self.logger.info("")
        
        return preloaded_data
    
    def show_preloaded_data(self, preloaded_data: Dict[str, Dict[str, pd.DataFrame]]):
        """Display preloaded data structure"""
        print()
        print("📋 PRELOADED DATA STRUCTURE")
        print("=" * 70)
        print()
        
        for symbol, timeframes in preloaded_data.items():
            print(f"   📈 {symbol}:")
            for tf, df in timeframes.items():
                if not df.empty:
                    first = df['timestamp'].iloc[0].strftime('%Y-%m-%d %H:%M')
                    last = df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M')
                    print(f"      {tf:>5}: {len(df):>5} candles  |  {first} to {last}")
            print()
