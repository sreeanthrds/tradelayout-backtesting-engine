"""
Incremental Indicators Module
==============================

O(1) incremental indicator calculations for live trading.

All indicators:
- Update in constant time O(1) or O(N) where N is small
- Work with any timeframe
- Support state persistence
- Compatible with TA-Lib formulas

Available Indicators (20 total):

Trend Indicators:
- EMA: Exponential Moving Average
- SMA: Simple Moving Average
- MACD: Moving Average Convergence Divergence
- ADX: Average Directional Index
- Parabolic SAR: Stop and Reverse
- Aroon: Trend identification

Momentum Indicators:
- RSI: Relative Strength Index
- Stochastic: Momentum oscillator
- CCI: Commodity Channel Index
- Williams %R: Momentum indicator
- ROC: Rate of Change
- Stochastic RSI: Sensitive overbought/oversold

Volatility Indicators:
- Bollinger Bands: Volatility bands
- ATR: Average True Range
- Donchian Channels: Breakout bands
- Keltner Channels: Volatility-based bands

Volume Indicators:
- MFI: Money Flow Index
- OBV: On-Balance Volume
- VWAP: Volume Weighted Average Price

Trend Following:
- SuperTrend: Dynamic support/resistance
"""

from .base import BaseIndicator
from .ema import EMAIndicator
from .sma import SMAIndicator
from .rsi import RSIIndicator
from .macd import MACDIndicator
from .bollinger_bands import BollingerBandsIndicator
from .stochastic import StochasticIndicator
from .atr import ATRIndicator
from .adx import ADXIndicator
from .cci import CCIIndicator
from .williams_r import WilliamsRIndicator
from .sar import SARIndicator
from .aroon import AroonIndicator
from .mfi import MFIIndicator
from .obv import OBVIndicator
from .roc import ROCIndicator
from .donchian import DonchianIndicator
from .keltner import KeltnerIndicator
from .vwap import VWAPIndicator
from .stochrsi import StochRSIIndicator
from .supertrend import SuperTrendIndicator

__all__ = [
    'BaseIndicator',
    'EMAIndicator',
    'SMAIndicator',
    'RSIIndicator',
    'MACDIndicator',
    'BollingerBandsIndicator',
    'StochasticIndicator',
    'ATRIndicator',
    'ADXIndicator',
    'CCIIndicator',
    'WilliamsRIndicator',
    'SARIndicator',
    'AroonIndicator',
    'MFIIndicator',
    'OBVIndicator',
    'ROCIndicator',
    'DonchianIndicator',
    'KeltnerIndicator',
    'VWAPIndicator',
    'StochRSIIndicator',
    'SuperTrendIndicator',
]

__version__ = '1.0.0'
