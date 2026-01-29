"""
Backtest Orchestrator

Main orchestrator for running backtests.
Initializes all components, loads historical data, replays ticks, and returns results.
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import clickhouse_connect

from .dataframe_writer import DataFrameWriter
from .dict_cache import DictCache
from .in_memory_persistence import InMemoryPersistence
from .historical_loader import HistoricalLoader
from .backtest_candle_builder import BacktestCandleBuilder
from .backtest_indicator_engine import BacktestIndicatorEngine


logger = logging.getLogger(__name__)


class BacktestOrchestrator:
    """
    Orchestrates the entire backtesting process.
    
    Responsibilities:
    1. Load historical OHLCV data
    2. Initialize indicators from historical data
    3. Set up in-memory components (DataFrame writer, cache, persistence)
    4. Replay ticks for the backtest date
    5. Execute strategy logic
    6. Return consolidated results as JSON
    """
    
    def __init__(
        self,
        clickhouse_client,
        strategy_config: Dict,
        backtest_date: datetime,
        symbols: List[str] = None,
        timeframes: List[str] = None
    ):
        """
        Initialize backtest orchestrator.
        
        Args:
            clickhouse_client: ClickHouse client (clickhouse_connect)
            strategy_config: Strategy configuration
            backtest_date: Date to backtest
            symbols: List of symbols to backtest (default: from strategy config)
            timeframes: List of timeframes (default: from strategy config)
        """
        self.client = clickhouse_client
        self.strategy_config = strategy_config
        self.backtest_date = backtest_date
        
        # Extract symbols and timeframes from strategy if not provided
        self.symbols = symbols or self._extract_symbols_from_strategy()
        self.timeframes = timeframes or self._extract_timeframes_from_strategy()
        
        # Initialize components
        self.data_writer = DataFrameWriter()
        self.cache = DictCache(max_candles=10)
        self.persistence = InMemoryPersistence()
        self.historical_loader = HistoricalLoader(clickhouse_client)
        
        # Initialize indicator engine first
        self.indicator_engine = BacktestIndicatorEngine(
            data_writer=self.data_writer,
            cache=self.cache
        )
        
        # Initialize candle builders (one per timeframe)
        # Connect indicator engine as callback
        self.candle_builders = {}
        for timeframe in self.timeframes:
            interval_minutes = self._parse_timeframe_to_minutes(timeframe)
            self.candle_builders[timeframe] = BacktestCandleBuilder(
                data_writer=self.data_writer,
                cache=self.cache,
                interval_minutes=interval_minutes,
                timeframe=timeframe,
                on_candle_complete=self.indicator_engine.on_candle_complete
            )
        
        logger.info(f"🎯 Backtest Orchestrator initialized for {backtest_date.date()}")
        logger.info(f"   Symbols: {self.symbols}")
        logger.info(f"   Timeframes: {self.timeframes}")
    
    def _extract_symbols_from_strategy(self) -> List[str]:
        """Extract symbols from strategy configuration."""
        # Default to NIFTY if not found
        symbols = set(['NIFTY'])
        
        # Look for symbols in strategy config
        if 'symbols' in self.strategy_config:
            symbols.update(self.strategy_config['symbols'])
        
        # Look in nodes
        for node in self.strategy_config.get('nodes', []):
            config = node.get('config', {})
            if 'instrument' in config:
                instrument = config['instrument']
                if isinstance(instrument, str):
                    symbols.add(instrument)
        
        return list(symbols)
    
    def _extract_timeframes_from_strategy(self) -> List[str]:
        """Extract timeframes from strategy configuration."""
        # Default timeframes
        timeframes = set(['1m', '5m'])
        
        # Look for timeframes in strategy config
        if 'timeframes' in self.strategy_config:
            timeframes.update(self.strategy_config['timeframes'])
        
        # Look in nodes for indicator timeframes
        for node in self.strategy_config.get('nodes', []):
            config = node.get('config', {})
            
            # Check conditions for timeframe references
            if 'conditions' in config:
                for condition in config['conditions']:
                    # Parse condition for timeframe patterns like "5m.EMA"
                    if isinstance(condition, str):
                        for tf in ['1m', '3m', '5m', '15m', '30m', '1h', '1d']:
                            if tf in condition:
                                timeframes.add(tf)
        
        return sorted(list(timeframes))
    
    def load_historical_data(self, lookback_candles: int = 200):
        """
        Load historical OHLCV data for all symbols and timeframes.
        
        Args:
            lookback_candles: Number of candles to load before backtest date
        """
        logger.info(f"📥 Loading historical data ({lookback_candles} candles lookback)")
        
        # Calculate end date (day before backtest)
        end_date = self.backtest_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                # Load historical candles
                df = self.historical_loader.load_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    end_date=end_date,
                    lookback_candles=lookback_candles
                )
                
                if len(df) > 0:
                    # Initialize DataFrame writer with historical data
                    self.data_writer.initialize_from_historical(symbol, timeframe, df)
                    
                    # Initialize cache with last 10 candles
                    last_10 = df.tail(10).to_dict('records')
                    self.cache.set_candles(symbol, timeframe, last_10)
                    
                    logger.info(f"✅ Loaded {len(df)} candles for {symbol} {timeframe}")
                else:
                    logger.warning(f"⚠️  No historical data for {symbol} {timeframe}")
    
    def initialize_indicators(self):
        """
        Calculate indicators on historical data.
        
        This should be called after load_historical_data().
        Calculates all indicators defined in the strategy on historical candles.
        """
        logger.info("📊 Initializing indicators from historical data")
        
        # Extract indicators from strategy config
        indicators = self._extract_indicators_from_strategy()
        
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                df = self.data_writer.get_dataframe(symbol, timeframe)
                
                if df is None or len(df) == 0:
                    continue
                
                # Calculate each indicator
                for indicator_config in indicators:
                    indicator_name = indicator_config['name']
                    indicator_type = indicator_config['type']
                    params = indicator_config.get('params', {})
                    
                    logger.info(f"   Calculating {indicator_name} for {symbol} {timeframe}")
                    
                    # Calculate indicator (placeholder - will be replaced with actual indicator engine)
                    # For now, just add placeholder columns
                    if indicator_type == 'EMA':
                        period = params.get('period', 20)
                        df[indicator_name] = df['close'].ewm(span=period, adjust=False).mean()
                    elif indicator_type == 'RSI':
                        period = params.get('period', 14)
                        # Simple RSI calculation
                        delta = df['close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                        rs = gain / loss
                        df[indicator_name] = 100 - (100 / (1 + rs))
                    
                    # Write indicator values to cache (last value)
                    if len(df) > 0 and indicator_name in df.columns:
                        last_value = df[indicator_name].iloc[-1]
                        if pd.notna(last_value):
                            self.cache.set_indicator(
                                symbol=symbol,
                                timeframe=timeframe,
                                indicator_name=indicator_name,
                                value=float(last_value)
                            )
        
        logger.info("✅ Indicators initialized")
        
        # Register indicators with engine
        for symbol in self.symbols:
            for timeframe in self.timeframes:
                for indicator_config in indicators:
                    self.indicator_engine.register_indicator(
                        symbol=symbol,
                        timeframe=timeframe,
                        indicator_name=indicator_config['name'],
                        indicator_type=indicator_config['type'],
                        params=indicator_config.get('params', {})
                    )
    
    def process_tick(self, tick: Dict):
        """
        Process a single tick through candle builders.
        
        Args:
            tick: Tick data dictionary
        """
        # Process through all candle builders
        for timeframe, builder in self.candle_builders.items():
            builder.process_tick(tick)
    
    def finalize(self):
        """
        Finalize backtesting (complete all candles, calculate final indicators).
        """
        logger.info("🏁 Finalizing backtest...")
        
        # Complete all pending candles
        for timeframe, builder in self.candle_builders.items():
            builder.force_complete_all()
        
        logger.info("✅ Backtest finalized")
    
    def _extract_indicators_from_strategy(self) -> List[Dict]:
        """Extract indicator definitions from strategy configuration."""
        indicators = []
        
        # Look for indicators in strategy config
        if 'indicators' in self.strategy_config:
            indicators.extend(self.strategy_config['indicators'])
        
        # Parse conditions to find indicator references
        for node in self.strategy_config.get('nodes', []):
            config = node.get('config', {})
            
            if 'conditions' in config:
                for condition in config['conditions']:
                    # Parse condition for indicator patterns
                    # Example: "5m.EMA_20 > 5m.close"
                    if isinstance(condition, str):
                        # Simple parsing (can be enhanced)
                        if 'EMA' in condition:
                            # Extract EMA period
                            import re
                            match = re.search(r'EMA_(\d+)', condition)
                            if match:
                                period = int(match.group(1))
                                indicators.append({
                                    'name': f'EMA_{period}',
                                    'type': 'EMA',
                                    'params': {'period': period}
                                })
                        
                        if 'RSI' in condition:
                            match = re.search(r'RSI_(\d+)', condition)
                            if match:
                                period = int(match.group(1))
                                indicators.append({
                                    'name': f'RSI_{period}',
                                    'type': 'RSI',
                                    'params': {'period': period}
                                })
        
        # Remove duplicates
        unique_indicators = []
        seen = set()
        for ind in indicators:
            key = f"{ind['name']}_{ind['type']}"
            if key not in seen:
                seen.add(key)
                unique_indicators.append(ind)
        
        return unique_indicators
    
    def _parse_timeframe_to_minutes(self, timeframe: str) -> int:
        """
        Parse timeframe string to minutes.
        
        Args:
            timeframe: Timeframe string (e.g., '1m', '5m', '1h')
        
        Returns:
            Number of minutes
        """
        timeframe = timeframe.lower()
        
        if timeframe.endswith('m'):
            return int(timeframe[:-1])
        elif timeframe.endswith('h'):
            return int(timeframe[:-1]) * 60
        elif timeframe.endswith('d'):
            return int(timeframe[:-1]) * 60 * 24
        else:
            logger.warning(f"⚠️  Unknown timeframe format: {timeframe}, defaulting to 1 minute")
            return 1
    
    def get_components(self) -> Dict:
        """
        Get initialized components for strategy executor.
        
        Returns:
            Dictionary with data_writer, cache, persistence
        """
        return {
            'data_writer': self.data_writer,
            'cache': self.cache,
            'persistence': self.persistence
        }
    
    def get_results(self) -> Dict:
        """
        Get backtest results.
        
        Returns:
            Consolidated results as JSON
        """
        results = self.persistence.get_results()
        
        # Add metadata
        results['metadata'] = {
            'backtest_date': self.backtest_date.isoformat(),
            'symbols': self.symbols,
            'timeframes': self.timeframes,
            'strategy_id': self.strategy_config.get('strategy_id'),
            'strategy_name': self.strategy_config.get('name')
        }
        
        # Add DataFrame stats
        results['data_stats'] = self.data_writer.get_stats()
        results['cache_stats'] = self.cache.get_stats()
        
        return results
