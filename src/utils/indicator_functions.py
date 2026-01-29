from typing import Dict

import numpy as np
import pandas as pd
import talib


class TechnicalIndicators:
    def __init__(self, df: pd.DataFrame):
        """
        Initialize with a pandas DataFrame containing OHLCV&OI data.
        
        Args:
            df (pd.DataFrame): DataFrame with columns ['open', 'high', 'low', 'close', 'volume', 'oi']
        """
        self.df = df.copy()
        required_columns = ['open', 'high', 'low', 'close', 'volume', 'oi']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"DataFrame must contain columns: {required_columns}")

        # Convert column names to lowercase for consistency
        self.df.columns = self.df.columns.str.lower()

    def sma(self, timeperiod: int = 20) -> pd.Series:
        """Calculate Simple Moving Average."""
        return pd.Series(talib.SMA(self.df['close'], timeperiod=timeperiod), name='SMA')

    def ema(self, timeperiod: int = 21) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return pd.Series(talib.EMA(self.df['close'], timeperiod=timeperiod), name='EMA')

    def macd(self, fastperiod: int = 12, slowperiod: int = 26, signalperiod: int = 9) -> pd.DataFrame:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        macd, signal, hist = talib.MACD(
            self.df['close'],
            fastperiod=fastperiod,
            slowperiod=slowperiod,
            signalperiod=signalperiod
        )
        return pd.DataFrame({
            'MACD': macd,
            'Signal': signal,
            'Histogram': hist
        })

    def rsi(self, timeperiod: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        return pd.Series(talib.RSI(self.df['close'], timeperiod=timeperiod), name='RSI')

    def bbands(self, timeperiod: int = 20, nbdevup: float = 2.0, nbdevdn: float = 2.0) -> pd.DataFrame:
        """Calculate Bollinger Bands."""
        if nbdevup <= 0 or nbdevdn <= 0:
            raise ValueError("Deviation values must be positive")
        upper, middle, lower = talib.BBANDS(self.df['close'], timeperiod=timeperiod, nbdevup=nbdevup, nbdevdn=nbdevdn)
        return pd.DataFrame({
            'UpperBand': upper,
            'MiddleBand': middle,
            'LowerBand': lower
        }, index=self.df.index)

    def stoch(self, fastk_period: int = 5, slowk_period: int = 3, slowd_period: int = 3) -> pd.DataFrame:
        """Calculate Stochastic Oscillator."""
        slowk, slowd = talib.STOCH(self.df['high'], self.df['low'], self.df['close'],
                                   fastk_period=fastk_period, slowk_period=slowk_period, slowd_period=slowd_period)
        # Clamp values to [0, 100]
        slowk = slowk.clip(lower=0, upper=100)
        slowd = slowd.clip(lower=0, upper=100)
        return pd.DataFrame({'SlowK': slowk, 'SlowD': slowd}, index=self.df.index)

    def adx(self, timeperiod: int = 14) -> pd.DataFrame:
        """Calculate Average Directional Index."""
        adx = talib.ADX(self.df['high'], self.df['low'], self.df['close'], timeperiod=timeperiod)
        plus_di = talib.PLUS_DI(self.df['high'], self.df['low'], self.df['close'], timeperiod=timeperiod)
        minus_di = talib.MINUS_DI(self.df['high'], self.df['low'], self.df['close'], timeperiod=timeperiod)
        return pd.DataFrame({
            'ADX': adx,
            'PlusDI': plus_di,
            'MinusDI': minus_di
        })

    def ichimoku(self, conversion_period: int = 9, base_period: int = 26, span_period: int = 52,
                 displacement: int = 26) -> pd.DataFrame:
        """Calculate Ichimoku Cloud."""

        # Conversion Line (Tenkan-sen)
        high_9 = self.df['high'].rolling(window=conversion_period).max()
        low_9 = self.df['low'].rolling(window=conversion_period).min()
        tenkan_sen = (high_9 + low_9) / 2

        # Base Line (Kijun-sen)
        high_26 = self.df['high'].rolling(window=base_period).max()
        low_26 = self.df['low'].rolling(window=base_period).min()
        kijun_sen = (high_26 + low_26) / 2

        # Leading Span A (Senkou Span A)
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(displacement)

        # Leading Span B (Senkou Span B)
        high_52 = self.df['high'].rolling(window=span_period).max()
        low_52 = self.df['low'].rolling(window=span_period).min()
        senkou_span_b = ((high_52 + low_52) / 2).shift(displacement)

        # Lagging Span (Chikou Span)
        chikou_span = self.df['close'].shift(-displacement)

        return pd.DataFrame({
            'Tenkan': tenkan_sen,
            'Kijun': kijun_sen,
            'SenkouA': senkou_span_a,
            'SenkouB': senkou_span_b,
            'Chikou': chikou_span
        })

    def fibonacci(self, high_price: float, low_price: float) -> pd.DataFrame:
        """Calculate Fibonacci Retracement Levels."""
        diff = high_price - low_price
        levels = {
            'Level_0': high_price,
            'Level_23.6': high_price - (diff * 0.236),
            'Level_38.2': high_price - (diff * 0.382),
            'Level_50': high_price - (diff * 0.500),
            'Level_61.8': high_price - (diff * 0.618),
            'Level_78.6': high_price - (diff * 0.786),
            'Level_100': low_price
        }
        return pd.DataFrame(levels, index=[0])

    def vwap(self, timeperiod: int = 14) -> pd.Series:
        """Calculate Volume Weighted Average Price."""
        typical_price = (self.df['high'] + self.df['low'] + self.df['close']) / 3
        vwap = (typical_price * self.df['volume']).rolling(window=timeperiod).sum() / self.df['volume'].rolling(
            window=timeperiod).sum()
        return pd.Series(vwap, name='VWAP')

    def obv(self) -> pd.Series:
        """Calculate On-Balance Volume."""
        return pd.Series(talib.OBV(self.df['close'], self.df['volume']), name='OBV')

    def cci(self, timeperiod: int = 20) -> pd.Series:
        """Calculate Commodity Channel Index."""
        return pd.Series(talib.CCI(self.df['high'], self.df['low'], self.df['close'], timeperiod=timeperiod),
                         name='CCI')

    def atr(self, timeperiod: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        return pd.Series(talib.ATR(self.df['high'], self.df['low'], self.df['close'], timeperiod=timeperiod),
                         name='ATR')

    def sar(self, acceleration: float = 0.02, maximum: float = 0.2) -> pd.Series:
        """Calculate Parabolic SAR."""
        return pd.Series(talib.SAR(self.df['high'], self.df['low'], acceleration=acceleration, maximum=maximum),
                         name='SAR')

    def aroon(self, timeperiod: int = 14) -> pd.DataFrame:
        """Calculate Aroon Oscillator."""
        aroon_down, aroon_up = talib.AROON(self.df['high'], self.df['low'], timeperiod=timeperiod)
        oscillator = aroon_up - aroon_down
        return pd.DataFrame({
            'AroonUp': aroon_up,
            'AroonDown': aroon_down,
            'Oscillator': oscillator
        })

    def mfi(self, timeperiod: int = 14) -> pd.Series:
        """Calculate Money Flow Index."""
        return pd.Series(
            talib.MFI(self.df['high'], self.df['low'], self.df['close'], self.df['volume'], timeperiod=timeperiod),
            name='MFI')

    def cmf(self, timeperiod: int = 20) -> pd.Series:
        """Calculate Chaikin Money Flow."""
        mfv = ((self.df['close'] - self.df['low']) - (self.df['high'] - self.df['close'])) / (
                    self.df['high'] - self.df['low'])
        mfv = mfv.fillna(0.0)
        mfv *= self.df['volume']
        cmf = mfv.rolling(window=timeperiod).sum() / self.df['volume'].rolling(window=timeperiod).sum()
        return pd.Series(cmf, name='CMF')

    def willr(self, timeperiod: int = 14) -> pd.Series:
        """Calculate Williams %R."""
        result = talib.WILLR(self.df['high'], self.df['low'], self.df['close'], timeperiod=timeperiod)
        # Clamp values to [-100, 0]
        result = result.clip(lower=-100, upper=0)
        return pd.Series(result, name='WILLR')

    def roc(self, timeperiod: int = 10) -> pd.Series:
        """Calculate Rate of Change."""
        return pd.Series(talib.ROC(self.df['close'], timeperiod=timeperiod), name='ROC')

    def donchian(self, timeperiod: int = 20) -> pd.DataFrame:
        """Calculate Donchian Channels."""
        upper = self.df['high'].rolling(window=timeperiod).max()
        lower = self.df['low'].rolling(window=timeperiod).min()
        middle = (upper + lower) / 2
        return pd.DataFrame({
            'UpperChannel': upper,
            'MiddleChannel': middle,
            'LowerChannel': lower
        })

    def keltner(self, timeperiod: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> pd.DataFrame:
        """Calculate Keltner Channels."""
        middle = talib.EMA(self.df['close'], timeperiod=timeperiod)
        atr = talib.ATR(self.df['high'], self.df['low'], self.df['close'], timeperiod=atr_period)
        upper = middle + (multiplier * atr)
        lower = middle - (multiplier * atr)
        return pd.DataFrame({
            'UpperBand': upper,
            'MiddleLine': middle,
            'LowerBand': lower
        })

    def hma(self, timeperiod: int = 16) -> pd.Series:
        """Calculate Hull Moving Average."""
        half_length = int(timeperiod / 2)
        sqrt_length = int(np.sqrt(timeperiod))

        wma1 = talib.WMA(self.df['close'], timeperiod=half_length)
        wma2 = talib.WMA(self.df['close'], timeperiod=timeperiod)
        hma = talib.WMA(2 * wma1 - wma2, timeperiod=sqrt_length)
        return pd.Series(hma, name='HMA')

    def tema(self, timeperiod: int = 20) -> pd.Series:
        """Calculate Triple Exponential Moving Average."""
        return pd.Series(talib.TEMA(self.df['close'], timeperiod=timeperiod), name='TEMA')

    def trix(self, timeperiod: int = 15) -> pd.Series:
        """Calculate TRIX."""
        return pd.Series(talib.TRIX(self.df['close'], timeperiod=timeperiod), name='TRIX')

    def ppo(self, fastperiod: int = 12, slowperiod: int = 26, matype: str = 'EMA') -> pd.Series:
        """Calculate Percentage Price Oscillator."""
        if matype not in ['SMA', 'EMA', 'WMA', 'DEMA', 'TEMA', 'TRIMA', 'KAMA', 'MAMA', 'T3']:
            raise KeyError(f"Invalid MA type: {matype}")
        return pd.Series(
            talib.PPO(self.df['close'], fastperiod=fastperiod, slowperiod=slowperiod, matype=self._get_matype(matype)),
            name='PPO')

    def cmo(self, timeperiod: int = 14) -> pd.Series:
        """Calculate Chande Momentum Oscillator."""
        return pd.Series(talib.CMO(self.df['close'], timeperiod=timeperiod), name='CMO')

    def dpo(self, timeperiod: int = 20) -> pd.Series:
        """Calculate Detrended Price Oscillator."""
        # Since DPO is not available in TA-Lib, we'll implement it manually
        ma = self.df['close'].rolling(window=timeperiod).mean()
        dpo = self.df['close'] - ma.shift(timeperiod // 2 + 1)
        return pd.Series(dpo, name='DPO')

    def vosc(self, short_period: int = 5, long_period: int = 10) -> pd.Series:
        """Calculate Volume Oscillator."""
        short_ma = talib.SMA(self.df['volume'], timeperiod=short_period)
        long_ma = talib.SMA(self.df['volume'], timeperiod=long_period)
        volosc = ((short_ma - long_ma) / long_ma) * 100
        return pd.Series(volosc, name='VolumeOscillator')

    def linearreg(self, timeperiod: int = 14) -> pd.Series:
        """Calculate Linear Regression."""
        return pd.Series(talib.LINEARREG(self.df['close'], timeperiod=timeperiod), name='LinearReg')

    def pivot(self, method: str = 'Traditional') -> pd.DataFrame:
        """Calculate Pivot Points."""
        if method not in ['Traditional', 'Fibonacci']:
            raise ValueError(f"Invalid method: {method}")

        high = self.df['high'].iloc[-1]
        low = self.df['low'].iloc[-1]
        close = self.df['close'].iloc[-1]

        if method == 'Traditional':
            pivot = (high + low + close) / 3
            r1 = 2 * pivot - low
            r2 = pivot + (high - low)
            r3 = high + 2 * (pivot - low)
            s1 = 2 * pivot - high
            s2 = pivot - (high - low)
            s3 = low - 2 * (high - pivot)
        else:  # Fibonacci
            pivot = (high + low + close) / 3
            r1 = pivot + 0.382 * (high - low)
            r2 = pivot + 0.618 * (high - low)
            r3 = pivot + 1.000 * (high - low)
            s1 = pivot - 0.382 * (high - low)
            s2 = pivot - 0.618 * (high - low)
            s3 = pivot - 1.000 * (high - low)

        return pd.DataFrame({
            'Pivot': [pivot],
            'R1': [r1],
            'R2': [r2],
            'R3': [r3],
            'S1': [s1],
            'S2': [s2],
            'S3': [s3]
        }, index=[self.df.index[-1]])

    def stddev(self, timeperiod: int = 10) -> pd.Series:
        """Calculate Standard Deviation."""
        return pd.Series(talib.STDDEV(self.df['close'], timeperiod=timeperiod), name='StdDev')

    def vortex(self, timeperiod: int = 14) -> pd.DataFrame:
        """Calculate Vortex Indicator."""
        plus_vm = abs(self.df['high'] - self.df['low'].shift(1))
        minus_vm = abs(self.df['low'] - self.df['high'].shift(1))
        plus_dm = abs(self.df['high'] - self.df['high'].shift(1))
        minus_dm = abs(self.df['low'] - self.df['low'].shift(1))

        plus_vi = plus_vm.rolling(window=timeperiod).sum() / plus_dm.rolling(window=timeperiod).sum()
        minus_vi = minus_vm.rolling(window=timeperiod).sum() / minus_dm.rolling(window=timeperiod).sum()

        return pd.DataFrame({
            'VIPlus': plus_vi,
            'VIMinus': minus_vi
        })

    def efi(self, timeperiod: int = 13) -> pd.Series:
        """Calculate Elder's Force Index."""
        force = (self.df['close'] - self.df['close'].shift(1)) * self.df['volume']
        efi = force.rolling(window=timeperiod).mean()
        return pd.Series(efi, name='EFI')

    def kama(self, timeperiod: int = 10, fast_ema: int = 2, slow_ema: int = 30) -> pd.Series:
        """Calculate Kaufman's Adaptive Moving Average."""
        return pd.Series(talib.KAMA(self.df['close'], timeperiod=timeperiod), name='KAMA')

    def dmi(self, timeperiod: int = 14) -> pd.DataFrame:
        """Calculate Directional Movement Index."""
        plus_di = talib.PLUS_DI(self.df['high'], self.df['low'], self.df['close'], timeperiod=timeperiod)
        minus_di = talib.MINUS_DI(self.df['high'], self.df['low'], self.df['close'], timeperiod=timeperiod)
        adx = talib.ADX(self.df['high'], self.df['low'], self.df['close'], timeperiod=timeperiod)
        return pd.DataFrame({
            'DIPlus': plus_di,
            'DIMinus': minus_di,
            'ADX': adx
        })

    def maenvelope(self, timeperiod: int = 20, percentage: float = 2.5) -> pd.DataFrame:
        """Calculate Moving Average Envelope."""
        middle = talib.SMA(self.df['close'], timeperiod=timeperiod)
        upper = middle * (1 + percentage / 100)
        lower = middle * (1 - percentage / 100)
        return pd.DataFrame({
            'Upper': upper,
            'Middle': middle,
            'Lower': lower
        })

    def coppock(self, roc1: int = 14, roc2: int = 11, wma: int = 10) -> pd.Series:
        """Calculate Coppock Curve."""
        roc1_series = talib.ROC(self.df['close'], timeperiod=roc1)
        roc2_series = talib.ROC(self.df['close'], timeperiod=roc2)
        coppock = talib.WMA(roc1_series + roc2_series, timeperiod=wma)
        return pd.Series(coppock, name='Coppock')

    def supertrend(self, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
        """Calculate SuperTrend indicator."""
        atr = self.atr(timeperiod=period)
        basic_upper = (self.df['high'] + self.df['low']) / 2 + multiplier * atr
        basic_lower = (self.df['high'] + self.df['low']) / 2 - multiplier * atr
        final_upper = pd.Series(np.nan, index=self.df.index)
        final_lower = pd.Series(np.nan, index=self.df.index)
        supertrend = pd.Series(np.nan, index=self.df.index)
        direction = pd.Series(np.nan, index=self.df.index)

        # Initialize first value after warmup
        final_upper.iloc[period - 1] = basic_upper.iloc[period - 1]
        final_lower.iloc[period - 1] = basic_lower.iloc[period - 1]
        supertrend.iloc[period - 1] = final_upper.iloc[period - 1]
        direction.iloc[period - 1] = -1

        for i in range(period, len(self.df)):
            # Final upper band
            if np.isnan(final_upper.iloc[i - 1]):
                final_upper.iloc[i - 1] = basic_upper.iloc[i - 1]
            if np.isnan(final_lower.iloc[i - 1]):
                final_lower.iloc[i - 1] = basic_lower.iloc[i - 1]
            if basic_upper.iloc[i] < final_upper.iloc[i - 1] or self.df['close'].iloc[i - 1] > final_upper.iloc[i - 1]:
                final_upper.iloc[i] = basic_upper.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i - 1]
            if basic_lower.iloc[i] > final_lower.iloc[i - 1] or self.df['close'].iloc[i - 1] < final_lower.iloc[i - 1]:
                final_lower.iloc[i] = basic_lower.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i - 1]
            # Supertrend and direction
            if np.isnan(supertrend.iloc[i - 1]):
                supertrend.iloc[i - 1] = final_upper.iloc[i - 1]
                direction.iloc[i - 1] = -1
            if supertrend.iloc[i - 1] == final_upper.iloc[i - 1] and self.df['close'].iloc[i] <= final_upper.iloc[i]:
                supertrend.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = -1
            elif supertrend.iloc[i - 1] == final_upper.iloc[i - 1] and self.df['close'].iloc[i] > final_upper.iloc[i]:
                supertrend.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = 1
            elif supertrend.iloc[i - 1] == final_lower.iloc[i - 1] and self.df['close'].iloc[i] >= final_lower.iloc[i]:
                supertrend.iloc[i] = final_lower.iloc[i]
                direction.iloc[i] = 1
            elif supertrend.iloc[i - 1] == final_lower.iloc[i - 1] and self.df['close'].iloc[i] < final_lower.iloc[i]:
                supertrend.iloc[i] = final_upper.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = supertrend.iloc[i - 1]
                direction.iloc[i] = direction.iloc[i - 1]
        # Fill initial period with NaN
        supertrend.iloc[:period - 1] = np.nan
        direction.iloc[:period - 1] = np.nan
        return pd.DataFrame({'Supertrend': supertrend, 'Direction': direction}, index=self.df.index)

    def tsi(self, long: int = 25, short: int = 13, signal: int = 7) -> pd.DataFrame:
        """Calculate True Strength Index."""
        diff = self.df['close'] - self.df['close'].shift(1)
        abs_diff = abs(diff)

        smoothed_diff = talib.EMA(talib.EMA(diff, timeperiod=short), timeperiod=long)
        smoothed_abs_diff = talib.EMA(talib.EMA(abs_diff, timeperiod=short), timeperiod=long)

        tsi = 100 * (smoothed_diff / smoothed_abs_diff)
        signal_line = talib.EMA(tsi, timeperiod=signal)

        return pd.DataFrame({
            'TSI': tsi,
            'Signal': signal_line
        })

    def stochrsi(self, rsi_period: int = 14, stoch_period: int = 14) -> pd.Series:
        """Calculate Stochastic RSI."""
        rsi = talib.RSI(self.df['close'], timeperiod=rsi_period)
        stoch_rsi = (rsi - rsi.rolling(window=stoch_period).min()) / (
                    rsi.rolling(window=stoch_period).max() - rsi.rolling(window=stoch_period).min())
        return pd.Series(stoch_rsi, name='StochRSI')

    def ao(self, fast_period: int = 5, slow_period: int = 34) -> pd.Series:
        """Calculate Awesome Oscillator."""
        median_price = (self.df['high'] + self.df['low']) / 2
        ao = talib.SMA(median_price, timeperiod=fast_period) - talib.SMA(median_price, timeperiod=slow_period)
        return pd.Series(ao, name='AO')

    def bop(self, timeperiod: int = 14) -> pd.Series:
        """Calculate Balance of Power."""
        denom = self.df['high'] - self.df['low']
        denom = denom.replace(0, np.nan)
        bop = (self.df['close'] - self.df['open']) / denom
        bop = bop.rolling(window=timeperiod).mean()
        # Clamp values to [-1, 1]
        bop = bop.clip(lower=-1, upper=1)
        return pd.Series(bop, name='BOP')

    def hv(self, timeperiod: int = 20, bars_back: int = 252) -> pd.Series:
        """Calculate Historical Volatility."""
        returns = np.log(self.df['close'] / self.df['close'].shift(1))
        hv = returns.rolling(window=timeperiod).std() * np.sqrt(bars_back)
        return pd.Series(hv, name='HV')

    def ad(self) -> pd.Series:
        """Calculate Accumulation/Distribution Line."""
        return pd.Series(talib.AD(self.df['high'], self.df['low'], self.df['close'], self.df['volume']), name='AD')

    def eom(self, timeperiod: int = 14) -> pd.Series:
        """Calculate Ease of Movement."""
        distance = ((self.df['high'] + self.df['low']) / 2) - ((self.df['high'].shift(1) + self.df['low'].shift(1)) / 2)
        box_ratio = (self.df['volume'] / 100000000) / (self.df['high'] - self.df['low'])
        eom = distance / box_ratio
        return pd.Series(talib.SMA(eom, timeperiod=timeperiod), name='EOM')

    def mass(self, timeperiod: int = 25) -> pd.Series:
        """Calculate Mass Index."""
        ema1 = talib.EMA(self.df['high'] - self.df['low'], timeperiod=9)
        ema2 = talib.EMA(ema1, timeperiod=9)
        ema_diff = ema1 - ema2
        ema_diff_sum = ema_diff.rolling(window=timeperiod).sum()
        return pd.Series(ema_diff_sum, name='MASS')

    def macdfix(self, fastperiod: int = 12, slowperiod: int = 26, signalperiod: int = 9) -> pd.Series:
        """Calculate MACD Histogram."""
        macd, signal, hist = talib.MACD(
            self.df['close'],
            fastperiod=fastperiod,
            slowperiod=slowperiod,
            signalperiod=signalperiod
        )
        return pd.Series(hist, name='MACDHist')

    def zigzag(self, percentage: float = 5.0) -> pd.Series:
        """Calculate ZigZag."""
        high = self.df['high']
        low = self.df['low']
        close = self.df['close']

        # Initialize variables
        zigzag = pd.Series(index=self.df.index, dtype=float)
        last_high = high.iloc[0]
        last_low = low.iloc[0]
        last_zigzag = close.iloc[0]
        direction = 1  # 1 for up, -1 for down

        for i in range(1, len(self.df)):
            if direction == 1:
                if high.iloc[i] > last_high:
                    last_high = high.iloc[i]
                elif low.iloc[i] < last_high * (1 - percentage / 100):
                    zigzag.iloc[i] = last_high
                    last_low = low.iloc[i]
                    direction = -1
            else:
                if low.iloc[i] < last_low:
                    last_low = low.iloc[i]
                elif high.iloc[i] > last_low * (1 + percentage / 100):
                    zigzag.iloc[i] = last_low
                    last_high = high.iloc[i]
                    direction = 1

        return pd.Series(zigzag, name='ZigZag')

    def gmma(self, short_periods: str = "3,5,8,10,12,15", long_periods: str = "30,35,40,45,50,60") -> pd.DataFrame:
        """Calculate Guppy Multiple Moving Average."""
        short_periods = [int(x) for x in short_periods.split(',')]
        long_periods = [int(x) for x in long_periods.split(',')]
        max_period = max(max(short_periods), max(long_periods))

        short_mas = {}
        long_mas = {}

        for period in short_periods:
            short_mas[f'ShortMA_{period}'] = talib.EMA(self.df['close'], timeperiod=period)

        for period in long_periods:
            long_mas[f'LongMA_{period}'] = talib.EMA(self.df['close'], timeperiod=period)

        return pd.DataFrame({**short_mas, **long_mas})

    def elderray(self, timeperiod: int = 13) -> pd.DataFrame:
        """Calculate Elder Ray Index."""
        ema = talib.EMA(self.df['close'], timeperiod=timeperiod)
        bull_power = self.df['high'] - ema
        bear_power = self.df['low'] - ema
        return pd.DataFrame({
            'BullPower': bull_power,
            'BearPower': bear_power
        })

    def hlscan(self, start_time: str = "09:15", end_time: str = "10:30", process_date=None, timeframe: str = "5m") -> pd.DataFrame:
        """
        High-Low Scanner (HLSCAN):
        For each trading day, compute the high/low in [start_time, end_time), and from end_time onward
        fill the day's rows with those values; before end_time, leave NaN.
        Returns a DataFrame indexed identically to input with columns 'RangeHigh' and 'RangeLow'.
        """
        from datetime import datetime, date
        df = self.df
        if df.empty or 'high' not in df.columns or 'low' not in df.columns:
            return pd.DataFrame({"RangeHigh": pd.Series(index=df.index, dtype=float),
                                 "RangeLow": pd.Series(index=df.index, dtype=float)})

        start_t = datetime.strptime(start_time, "%H:%M").time()
        end_t = datetime.strptime(end_time, "%H:%M").time()
        # timeframe delta in seconds (support Xm or Xh)
        if isinstance(timeframe, str) and timeframe.endswith('m'):
            tf_delta = pd.Timedelta(minutes=int(timeframe[:-1]))
        elif isinstance(timeframe, str) and timeframe.endswith('h'):
            tf_delta = pd.Timedelta(hours=int(timeframe[:-1]))
        else:
            tf_delta = pd.Timedelta(minutes=5)

        range_high_series = pd.Series(index=df.index, dtype=float)
        range_low_series = pd.Series(index=df.index, dtype=float)

        # Group by date and compute per-day scan; optionally restrict to process_date
        dates = pd.to_datetime(df.index).date
        all_days = pd.Series(dates, index=df.index).groupby(level=0).first().index.normalize().unique()
        if process_date is not None:
            try:
                if isinstance(process_date, datetime):
                    target_day = process_date.date()
                elif isinstance(process_date, date):
                    target_day = process_date
                else:
                    # attempt to parse from string
                    target_day = pd.to_datetime(process_date).date()
                unique_days = pd.Index([pd.Timestamp(target_day)])
            except Exception as e:
                from src.utils.error_handler import handle_exception
                handle_exception(e, "indicator_functions_date_processing", {
                    "process_date": process_date,
                    "all_days": all_days
                }, is_critical=False, continue_execution=True)
                unique_days = all_days
        else:
            unique_days = all_days

        for day in unique_days:
            day_mask = (df.index.normalize() == day)
            if not day_mask.any():
                continue
            day_df = df[day_mask]
            # Build absolute datetimes for the process day
            start_dt = pd.Timestamp.combine(pd.Timestamp(day).date(), start_t)
            end_dt = pd.Timestamp.combine(pd.Timestamp(day).date(), end_t)
            # Adjust end_dt by -1s per spec to avoid including next candle when exactly on boundary
            end_dt = end_dt - pd.Timedelta(seconds=1)
            # Compute candle-aligned boundaries based on available candle starts (index)
            # start_candle: max index <= start_dt
            eligible_starts = day_df.index[day_df.index <= start_dt]
            if len(eligible_starts) == 0:
                start_candle = day_df.index.min()
            else:
                start_candle = eligible_starts.max()
            # end_candle: max index <= end_dt
            eligible_ends = day_df.index[day_df.index <= end_dt]
            if len(eligible_ends) == 0:
                continue
            end_candle = eligible_ends.max()
            # Select candle rows fully within [start_candle, end_candle]
            window_df = day_df.loc[(day_df.index >= start_candle) & (day_df.index <= end_candle)]
            if window_df.empty:
                continue
            day_range_high = float(window_df['high'].max())
            day_range_low = float(window_df['low'].min())
            # Fill from end boundary (end_candle + tf_delta) onward within the same day
            post_start = end_candle + tf_delta
            idx_to_fill = day_df.index[day_df.index >= post_start]
            if len(idx_to_fill) > 0:
                range_high_series.loc[idx_to_fill] = day_range_high
                range_low_series.loc[idx_to_fill] = day_range_low

        return pd.DataFrame({"RangeHigh": range_high_series, "RangeLow": range_low_series}, index=df.index)

    def _get_matype(self, matype: str) -> int:
        """Map MA type string to TA-Lib integer code."""
        matype_map = {
            'SMA': 0, 'EMA': 1, 'WMA': 2, 'DEMA': 3, 'TEMA': 4, 'TRIMA': 5, 'KAMA': 6, 'MAMA': 7, 'T3': 8
        }
        return matype_map[matype]


class IndicatorFunctions:
    @staticmethod
    def apply_indicator(indicator_name: str, data: pd.DataFrame, params: dict) -> pd.Series:
        """
        Dynamically apply a technical indicator using its name from JSON.
        
        Args:
            indicator_name (str): Name of the indicator (e.g., 'EMA', 'SMA', 'RSI')
            data (pd.DataFrame): DataFrame containing price data
            params (dict): Dictionary of parameters for the indicator
            
        Returns:
            pd.Series: Calculated indicator values
        """
        try:
            # Get the indicator function from talib using getattr
            indicator_func = getattr(talib, indicator_name)

            # For indicators that use close price
            if indicator_name in ['EMA', 'SMA', 'RSI', 'MACD', 'BBANDS']:
                return indicator_func(data['close'], **params)

            # For indicators that use high/low/close
            elif indicator_name in ['ADX', 'CCI', 'STOCH']:
                return indicator_func(data['high'], data['low'], data['close'], **params)

            # For indicators that use open/high/low/close
            elif indicator_name in ['CDLDOJI', 'CDLHAMMER']:
                return indicator_func(data['open'], data['high'], data['low'], data['close'], **params)

            # Add more indicator groups as needed

            else:
                raise ValueError(f"Unsupported indicator: {indicator_name}")

        except AttributeError:
            raise ValueError(f"Indicator {indicator_name} not found in TA-Lib")
        except Exception as e:
            raise Exception(f"Error calculating {indicator_name}: {str(e)}")

    @staticmethod
    def get_required_params(indicator_name: str) -> list:
        """
        Get the list of required parameters for a given indicator.
        
        Args:
            indicator_name (str): Name of the indicator
            
        Returns:
            list: List of required parameter names
        """
        # Define required parameters for each indicator
        param_map = {
            'EMA': ['timeperiod'],
            'SMA': ['timeperiod'],
            'RSI': ['timeperiod'],
            'MACD': ['fastperiod', 'slowperiod', 'signalperiod'],
            'BBANDS': ['timeperiod', 'nbdevup', 'nbdevdn'],
            'ADX': ['timeperiod'],
            'CCI': ['timeperiod'],
            'STOCH': ['fastk_period', 'slowk_period', 'slowd_period'],
            # Add more indicators and their required parameters
        }

        return param_map.get(indicator_name, [])


def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average.
    
    Args:
        data (pd.Series): Price data series
        period (int): EMA period
        
    Returns:
        pd.Series: EMA values
    """
    if period >= len(data):
        raise ValueError(f"Period {period} is greater than or equal to data length {len(data)}")

    return pd.Series(talib.EMA(data, timeperiod=period), index=data.index)


def calculate_macd(data: pd.Series, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[
    str, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    
    Args:
        data (pd.Series): Price data series
        fast_period (int): Fast EMA period
        slow_period (int): Slow EMA period
        signal_period (int): Signal line period
        
    Returns:
        Dict[str, pd.Series]: Dictionary with 'macd', 'signal', and 'histogram' keys
    """
    max_period = max(fast_period, slow_period, signal_period)
    if max_period >= len(data):
        raise ValueError(f"Period {max_period} is greater than or equal to data length {len(data)}")

    macd, signal, hist = talib.MACD(
        data,
        fastperiod=fast_period,
        slowperiod=slow_period,
        signalperiod=signal_period
    )

    return {
        'macd': pd.Series(macd, index=data.index),
        'signal': pd.Series(signal, index=data.index),
        'histogram': pd.Series(hist, index=data.index)
    }
