"""
Backtest Indicator Engine

Calculates indicators incrementally (O(1) updates) during backtesting.
Supports EMA, RSI, and other common indicators.
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class BacktestIndicatorEngine:
    """
    Incremental indicator calculator for backtesting.
    
    Calculates indicators in O(1) time using state from cache.
    Integrates with DataFrameWriter and DictCache.
    """
    
    def __init__(self, data_writer, cache):
        """
        Initialize indicator engine.
        
        Args:
            data_writer: DataFrameWriter instance
            cache: DictCache instance
        """
        self.data_writer = data_writer
        self.cache = cache
        
        # Indicator configurations
        self.indicators = {}  # {symbol:timeframe:indicator_name: config}
        
        logger.info("📊 Backtest Indicator Engine initialized")
    
    def register_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator_name: str,
        indicator_type: str,
        params: Dict
    ):
        """
        Register an indicator for calculation.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Indicator name (e.g., 'EMA_20')
            indicator_type: Type (e.g., 'EMA', 'RSI')
            params: Parameters (e.g., {'period': 20})
        """
        key = f"{symbol}:{timeframe}:{indicator_name}"
        self.indicators[key] = {
            'symbol': symbol,
            'timeframe': timeframe,
            'name': indicator_name,
            'type': indicator_type,
            'params': params
        }
        
        logger.info(f"📈 Registered {indicator_name} for {symbol} {timeframe}")
    
    def on_candle_complete(self, candle: Dict):
        """
        Calculate indicators when a candle completes.
        
        Args:
            candle: Completed candle dictionary
        """
        symbol = candle['symbol']
        timeframe = candle['timeframe']
        timestamp = candle['timestamp']
        close = candle['close']
        
        # Calculate all registered indicators for this symbol+timeframe
        for key, config in self.indicators.items():
            if config['symbol'] == symbol and config['timeframe'] == timeframe:
                indicator_name = config['name']
                indicator_type = config['type']
                params = config['params']
                
                # Calculate indicator
                value = self._calculate_indicator(
                    symbol=symbol,
                    timeframe=timeframe,
                    indicator_name=indicator_name,
                    indicator_type=indicator_type,
                    params=params,
                    close=close
                )
                
                if value is not None:
                    # Write to DataFrame
                    self.data_writer.write_indicator({
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'timestamp': timestamp,
                        'indicator_name': indicator_name,
                        'value': value
                    })
                    
                    # Update cache (for next calculation)
                    # Cache stores both value and state for incremental updates
    
    def _calculate_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator_name: str,
        indicator_type: str,
        params: Dict,
        close: float
    ) -> Optional[float]:
        """
        Calculate indicator value incrementally.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Indicator name
            indicator_type: Indicator type
            params: Parameters
            close: Current close price
        
        Returns:
            Indicator value or None
        """
        if indicator_type == 'EMA':
            return self._calculate_ema(symbol, timeframe, indicator_name, params, close)
        elif indicator_type == 'RSI':
            return self._calculate_rsi(symbol, timeframe, indicator_name, params, close)
        elif indicator_type == 'SMA':
            return self._calculate_sma(symbol, timeframe, indicator_name, params, close)
        else:
            logger.warning(f"⚠️  Unknown indicator type: {indicator_type}")
            return None
    
    def _calculate_ema(
        self,
        symbol: str,
        timeframe: str,
        indicator_name: str,
        params: Dict,
        close: float
    ) -> Optional[float]:
        """
        Calculate EMA incrementally.
        
        EMA formula: EMA = (Close - PrevEMA) * multiplier + PrevEMA
        where multiplier = 2 / (period + 1)
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Indicator name
            params: {'period': int}
            close: Current close price
        
        Returns:
            EMA value or None
        """
        period = params.get('period', 20)
        multiplier = 2 / (period + 1)
        
        # Get previous EMA from cache
        cached = self.cache.get_indicator(symbol, timeframe, indicator_name)
        
        if cached:
            # Incremental update (O(1))
            prev_ema = cached['value']
            ema = (close - prev_ema) * multiplier + prev_ema
        else:
            # First calculation - use SMA of last N candles
            candles = self.cache.get_candles(symbol, timeframe, count=period)
            
            if len(candles) < period:
                # Not enough data yet
                return None
            
            # Calculate SMA as initial EMA
            closes = [c['close'] for c in candles[-period:]]
            ema = sum(closes) / period
        
        # Store in cache for next calculation
        self.cache.set_indicator(symbol, timeframe, indicator_name, ema)
        
        return ema
    
    def _calculate_rsi(
        self,
        symbol: str,
        timeframe: str,
        indicator_name: str,
        params: Dict,
        close: float
    ) -> Optional[float]:
        """
        Calculate RSI incrementally.
        
        RSI formula: RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Indicator name
            params: {'period': int}
            close: Current close price
        
        Returns:
            RSI value or None
        """
        period = params.get('period', 14)
        
        # Get previous state from cache
        cached = self.cache.get_indicator(symbol, timeframe, indicator_name)
        
        # Get previous close
        candles = self.cache.get_candles(symbol, timeframe, count=2)
        if len(candles) < 2:
            return None
        
        prev_close = candles[-2]['close']
        change = close - prev_close
        
        if cached and 'state' in cached:
            # Incremental update (O(1))
            state = cached['state']
            avg_gain = state.get('avg_gain', 0)
            avg_loss = state.get('avg_loss', 0)
            
            # Update averages
            gain = max(change, 0)
            loss = abs(min(change, 0))
            
            avg_gain = ((avg_gain * (period - 1)) + gain) / period
            avg_loss = ((avg_loss * (period - 1)) + loss) / period
        else:
            # First calculation - need N candles
            if len(candles) < period + 1:
                return None
            
            # Calculate initial averages
            gains = []
            losses = []
            
            for i in range(len(candles) - period, len(candles)):
                change = candles[i]['close'] - candles[i-1]['close']
                gains.append(max(change, 0))
                losses.append(abs(min(change, 0)))
            
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
        
        # Calculate RSI
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Store in cache with state
        self.cache.set_indicator(
            symbol, timeframe, indicator_name, rsi,
            state={'avg_gain': avg_gain, 'avg_loss': avg_loss}
        )
        
        return rsi
    
    def _calculate_sma(
        self,
        symbol: str,
        timeframe: str,
        indicator_name: str,
        params: Dict,
        close: float
    ) -> Optional[float]:
        """
        Calculate SMA.
        
        SMA = Average of last N closes
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicator_name: Indicator name
            params: {'period': int}
            close: Current close price
        
        Returns:
            SMA value or None
        """
        period = params.get('period', 20)
        
        # Get last N candles
        candles = self.cache.get_candles(symbol, timeframe, count=period)
        
        if len(candles) < period:
            return None
        
        # Calculate average
        closes = [c['close'] for c in candles[-period:]]
        sma = sum(closes) / period
        
        # Store in cache
        self.cache.set_indicator(symbol, timeframe, indicator_name, sma)
        
        return sma
    
    def get_stats(self) -> Dict:
        """
        Get engine statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            'registered_indicators': len(self.indicators),
            'indicators': list(self.indicators.keys())
        }
