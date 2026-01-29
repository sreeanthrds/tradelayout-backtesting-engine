{
    "indicators": [
        {
            "name": "SMA",
            "function_name": "SMA",
            "display_name": "Simple Moving Average",
            "description": "Calculates the average price over a specified period",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 20,
                    "description": "Number of periods to average"
                }
            ],
            "outputs": ["SMA"]
        },
        {
            "name": "EMA",
            "function_name": "EMA",
            "display_name": "Exponential Moving Average",
            "description": "Weighted moving average that gives more importance to recent prices",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 21,
                    "description": "Number of periods for the calculation"
                }
            ],
            "outputs": ["EMA"]
        },
        {
            "name": "MACD",
            "function_name": "MACD",
            "display_name": "Moving Average Convergence Divergence",
            "description": "Trend-following momentum indicator showing relationship between two moving averages",
            "parameters": [
                {
                    "name": "fastperiod",
                    "type": "number",
                    "label": "Fast Period",
                    "default": 12,
                    "description": "Number of periods for the fast moving average"
                },
                {
                    "name": "slowperiod",
                    "type": "number",
                    "label": "Slow Period",
                    "default": 26,
                    "description": "Number of periods for the slow moving average"
                },
                {
                    "name": "signalperiod",
                    "type": "number",
                    "label": "Signal Period",
                    "default": 9,
                    "description": "Number of periods for the signal line"
                }
            ],
            "outputs": ["MACD", "Signal", "Histogram"]
        },
        {
            "name": "RSI",
            "function_name": "RSI",
            "display_name": "Relative Strength Index",
            "description": "Momentum oscillator measuring speed and change of price movements",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods used to calculate the RSI"
                }
            ],
            "outputs": ["RSI"]
        },
        {
            "name": "BollingerBands",
            "function_name": "BBANDS",
            "display_name": "Bollinger Bands",
            "description": "Volatility bands placed above and below a moving average",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 20,
                    "description": "Number of periods used to calculate Bollinger Bands"
                },
                {
                    "name": "nbdevup",
                    "type": "number",
                    "label": "Standard Deviation Up",
                    "default": 2,
                    "description": "Number of standard deviations above the middle band"
                },
                {
                    "name": "nbdevdn",
                    "type": "number",
                    "label": "Standard Deviation Down",
                    "default": 2,
                    "description": "Number of standard deviations below the middle band"
                },
                {
                    "name": "matype",
                    "type": "dropdown",
                    "label": "Moving Average Type",
                    "options": ["SMA", "EMA", "WMA"],
                    "default": "SMA",
                    "description": "Type of moving average used for the middle band"
                }
            ],
            "outputs": ["UpperBand", "MiddleBand", "LowerBand"]
        },
        {
            "name": "Stochastic",
            "function_name": "STOCH",
            "display_name": "Stochastic Oscillator",
            "description": "Momentum indicator comparing a particular closing price to a range of prices over time",
            "parameters": [
                {
                    "name": "fastk_period",
                    "type": "number",
                    "label": "FastK Period",
                    "default": 5,
                    "description": "Time period for %K line"
                },
                {
                    "name": "slowk_period",
                    "type": "number",
                    "label": "SlowK Period",
                    "default": 3,
                    "description": "Smoothing for %K line"
                },
                {
                    "name": "slowd_period",
                    "type": "number",
                    "label": "SlowD Period",
                    "default": 3,
                    "description": "Smoothing for %D line"
                }
            ],
            "outputs": ["SlowK", "SlowD"]
        },
        {
            "name": "ADX",
            "function_name": "ADX",
            "display_name": "Average Directional Index",
            "description": "Measures strength of a trend regardless of direction",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods for ADX calculation"
                }
            ],
            "outputs": ["ADX", "PlusDI", "MinusDI"]
        },
        {
            "name": "Ichimoku",
            "function_name": "ICHIMOKU",
            "display_name": "Ichimoku Cloud",
            "description": "Comprehensive indicator showing support and resistance, momentum, and trend direction",
            "parameters": [
                {
                    "name": "conversionPeriod",
                    "type": "number",
                    "label": "Conversion Period",
                    "default": 9,
                    "description": "Period for Tenkan-sen (Conversion Line)"
                },
                {
                    "name": "basePeriod",
                    "type": "number",
                    "label": "Base Period",
                    "default": 26,
                    "description": "Period for Kijun-sen (Base Line)"
                },
                {
                    "name": "spanPeriod",
                    "type": "number",
                    "label": "Span Period",
                    "default": 52,
                    "description": "Period for Senkou Span B"
                },
                {
                    "name": "displacement",
                    "type": "number",
                    "label": "Displacement",
                    "default": 26,
                    "description": "Displacement period for Senkou Span A and B"
                }
            ],
            "outputs": ["Tenkan", "Kijun", "SenkouA", "SenkouB", "Chikou"]
        },
        {
            "name": "Fibonacci",
            "function_name": "FIBONACCI",
            "display_name": "Fibonacci Retracement",
            "description": "Identifies potential support and resistance levels based on Fibonacci sequence",
            "parameters": [
                {
                    "name": "highPrice",
                    "type": "number",
                    "label": "High Price",
                    "default": 0,
                    "description": "Highest price in the period"
                },
                {
                    "name": "lowPrice",
                    "type": "number",
                    "label": "Low Price",
                    "default": 0,
                    "description": "Lowest price in the period"
                }
            ],
            "outputs": ["Level_0", "Level_23.6", "Level_38.2", "Level_50", "Level_61.8", "Level_78.6", "Level_100"]
        },
        {
            "name": "VWAP",
            "function_name": "VWAP",
            "display_name": "Volume Weighted Average Price",
            "description": "Average price weighted by volume",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Calculation period"
                }
            ],
            "outputs": ["VWAP"]
        },
        {
            "name": "OBV",
            "function_name": "OBV",
            "display_name": "On-Balance Volume",
            "description": "Cumulative indicator using volume flow to predict price changes",
            "parameters": [],
            "outputs": ["OBV"]
        },
        {
            "name": "CCI",
            "function_name": "CCI",
            "display_name": "Commodity Channel Index",
            "description": "Measures current price level relative to average price level over a period",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 20,
                    "description": "Number of periods for CCI calculation"
                }
            ],
            "outputs": ["CCI"]
        },
        {
            "name": "ATR",
            "function_name": "ATR",
            "display_name": "Average True Range",
            "description": "Measures market volatility by decomposing the entire range of an asset",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods for ATR calculation"
                }
            ],
            "outputs": ["ATR"]
        },
        {
            "name": "ParabolicSAR",
            "function_name": "SAR",
            "display_name": "Parabolic SAR",
            "description": "Stop and Reverse indicator to identify potential reversals in price direction",
            "parameters": [
                {
                    "name": "acceleration",
                    "type": "number",
                    "label": "Acceleration",
                    "default": 0.02,
                    "description": "Acceleration factor"
                },
                {
                    "name": "maximum",
                    "type": "number",
                    "label": "Maximum",
                    "default": 0.2,
                    "description": "Maximum acceleration factor"
                }
            ],
            "outputs": ["SAR"]
        },
        {
            "name": "Aroon",
            "function_name": "AROON",
            "display_name": "Aroon Oscillator",
            "description": "Identifies when a trend is about to begin",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods for Aroon calculation"
                }
            ],
            "outputs": ["AroonUp", "AroonDown", "Oscillator"]
        },
        {
            "name": "MFI",
            "function_name": "MFI",
            "display_name": "Money Flow Index",
            "description": "Oscillator that uses price and volume to identify overbought or oversold conditions",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods for MFI calculation"
                }
            ],
            "outputs": ["MFI"]
        },
        {
            "name": "CMF",
            "function_name": "CMF",
            "display_name": "Chaikin Money Flow",
            "description": "Measures the amount of Money Flow Volume over a specific period",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 20,
                    "description": "Number of periods for CMF calculation"
                }
            ],
            "outputs": ["CMF"]
        },
        {
            "name": "WilliamsR",
            "function_name": "WILLR",
            "display_name": "Williams %R",
            "description": "Momentum indicator measuring overbought/oversold levels",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods for %R calculation"
                }
            ],
            "outputs": ["WilliamsR"]
        },
        {
            "name": "ROC",
            "function_name": "ROC",
            "display_name": "Rate of Change",
            "description": "Shows the percentage change in price between current and previous periods",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 10,
                    "description": "Number of periods to compare"
                }
            ],
            "outputs": ["ROC"]
        },
        {
            "name": "DonchianChannels",
            "function_name": "DONCHIAN",
            "display_name": "Donchian Channels",
            "description": "Price bands based on highest high and lowest low for a period",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 20,
                    "description": "Number of periods for channel calculation"
                }
            ],
            "outputs": ["UpperChannel", "MiddleChannel", "LowerChannel"]
        },
        {
            "name": "KeltnerChannels",
            "function_name": "KELTNER",
            "display_name": "Keltner Channels",
            "description": "Volatility-based bands with ATR around EMA",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 20,
                    "description": "EMA period"
                },
                {
                    "name": "atrPeriod",
                    "type": "number",
                    "label": "ATR Period",
                    "default": 10,
                    "description": "ATR calculation period"
                },
                {
                    "name": "multiplier",
                    "type": "number",
                    "label": "ATR Multiplier",
                    "default": 2,
                    "description": "Multiplier for ATR"
                }
            ],
            "outputs": ["UpperBand", "MiddleLine", "LowerBand"]
        },
        {
            "name": "HMA",
            "function_name": "HMA",
            "display_name": "Hull Moving Average",
            "description": "Improved moving average reducing lag while maintaining smoothness",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 16,
                    "description": "Number of periods for HMA calculation"
                }
            ],
            "outputs": ["HMA"]
        },
        {
            "name": "TEMA",
            "function_name": "TEMA",
            "display_name": "Triple Exponential Moving Average",
            "description": "Moving average with reduced lag",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 20,
                    "description": "Number of periods for TEMA calculation"
                }
            ],
            "outputs": ["TEMA"]
        },
        {
            "name": "TRIX",
            "function_name": "TRIX",
            "display_name": "TRIX",
            "description": "Triple exponential moving average oscillator",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 15,
                    "description": "Number of periods for TRIX calculation"
                }
            ],
            "outputs": ["TRIX"]
        },
        {
            "name": "PPO",
            "function_name": "PPO",
            "display_name": "Percentage Price Oscillator",
            "description": "Shows the difference between two moving averages as a percentage",
            "parameters": [
                {
                    "name": "fastperiod",
                    "type": "number",
                    "label": "Fast Period",
                    "default": 12,
                    "description": "Fast EMA period"
                },
                {
                    "name": "slowperiod",
                    "type": "number",
                    "label": "Slow Period",
                    "default": 26,
                    "description": "Slow EMA period"
                },
                {
                    "name": "matype",
                    "type": "dropdown",
                    "label": "Moving Average Type",
                    "options": ["SMA", "EMA", "WMA"],
                    "default": "EMA",
                    "description": "Type of moving average to use"
                }
            ],
            "outputs": ["PPO"]
        },
        {
            "name": "CMO",
            "function_name": "CMO",
            "display_name": "Chande Momentum Oscillator",
            "description": "Momentum oscillator calculating relative strength of up and down days",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods for CMO calculation"
                }
            ],
            "outputs": ["CMO"]
        },
        {
            "name": "DPO",
            "function_name": "DPO",
            "display_name": "Detrended Price Oscillator",
            "description": "Eliminates trend from price to identify cycles",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 20,
                    "description": "Cycle period"
                }
            ],
            "outputs": ["DPO"]
        },
        {
            "name": "VolumeOscillator",
            "function_name": "VOSC",
            "display_name": "Volume Oscillator",
            "description": "Measures the difference between two volume moving averages",
            "parameters": [
                {
                    "name": "shortPeriod",
                    "type": "number",
                    "label": "Short Period",
                    "default": 5,
                    "description": "Short MA period"
                },
                {
                    "name": "longPeriod",
                    "type": "number",
                    "label": "Long Period",
                    "default": 10,
                    "description": "Long MA period"
                }
            ],
            "outputs": ["VolumeOscillator"]
        },
        {
            "name": "LinearRegression",
            "function_name": "LINEARREG",
            "display_name": "Linear Regression",
            "description": "Linear regression trendline for the given period",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods for linear regression"
                }
            ],
            "outputs": ["LinearReg"]
        },
        {
            "name": "PivotPoints",
            "function_name": "PIVOT",
            "display_name": "Pivot Points",
            "description": "Support and resistance levels based on previous period data",
            "parameters": [
                {
                    "name": "method",
                    "type": "dropdown",
                    "label": "Calculation Method",
                    "options": ["Traditional", "Fibonacci", "Camarilla", "Woodie"],
                    "default": "Traditional",
                    "description": "Method used to calculate pivot points"
                }
            ],
            "outputs": ["Pivot", "R1", "R2", "R3", "S1", "S2", "S3"]
        },
        {
            "name": "StandardDeviation",
            "function_name": "STDDEV",
            "display_name": "Standard Deviation",
            "description": "Measures dispersion of price from its average",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 10,
                    "description": "Number of periods for standard deviation"
                }
            ],
            "outputs": ["StdDev"]
        },
        {
            "name": "Vortex",
            "function_name": "VORTEX",
            "display_name": "Vortex Indicator",
            "description": "Identifies the start of a new trend or continuation of a trend",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods for vortex indicator"
                }
            ],
            "outputs": ["VIPlus", "VIMinus"]
        },
        {
            "name": "EFI",
            "function_name": "EFI",
            "display_name": "Elder's Force Index",
            "description": "Measures the power behind price movements using price and volume",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 13,
                    "description": "Number of periods for EFI"
                }
            ],
            "outputs": ["EFI"]
        },
        {
            "name": "KAMA",
            "function_name": "KAMA",
            "display_name": "Kaufman's Adaptive Moving Average",
            "description": "Moving average that adapts to market volatility",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 10,
                    "description": "Number of periods for KAMA"
                },
                {
                    "name": "fastEMA",
                    "type": "number",
                    "label": "Fast EMA Period",
                    "default": 2,
                    "description": "Fast efficiency factor"
                },
                {
                    "name": "slowEMA",
                    "type": "number",
                    "label": "Slow EMA Period",
                    "default": 30,
                    "description": "Slow efficiency factor"
                }
            ],
            "outputs": ["KAMA"]
        },
        {
            "name": "DMI",
            "function_name": "DMI",
            "display_name": "Directional Movement Index",
            "description": "Identifies the direction of price movement",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Number of periods for DMI"
                }
            ],
            "outputs": ["DIPlus", "DIMinus", "ADX"]
        },
        {
            "name": "MAEnvelope",
            "function_name": "MAENVELOPE",
            "display_name": "Moving Average Envelope",
            "description": "Creates bands around a moving average at a fixed percentage",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "MA Period",
                    "default": 20,
                    "description": "Moving average period"
                },
                {
                    "name": "percentage",
                    "type": "number",
                    "label": "Envelope Percentage",
                    "default": 2.5,
                    "description": "Percentage for envelope width"
                }
            ],
            "outputs": ["Upper", "Middle", "Lower"]
        },
        {
            "name": "Coppock",
            "function_name": "COPPOCK",
            "display_name": "Coppock Curve",
            "description": "Long-term momentum indicator used to identify market bottoms",
            "parameters": [
                {
                    "name": "roc1",
                    "type": "number",
                    "label": "ROC 1 Period",
                    "default": 14,
                    "description": "First ROC period"
                },
                {
                    "name": "roc2",
                    "type": "number",
                    "label": "ROC 2 Period",
                    "default": 11,
                    "description": "Second ROC period"
                },
                {
                    "name": "wma",
                    "type": "number",
                    "label": "WMA Period",
                    "default": 10,
                    "description": "WMA period"
                }
            ],
            "outputs": ["Coppock"]
        },
        {
            "name": "SuperTrend",
            "function_name": "SUPERTREND",
            "display_name": "SuperTrend",
            "description": "Trend-following indicator based on ATR",
            "parameters": [
                {
                    "name": "period",
                    "type": "number",
                    "label": "ATR Period",
                    "default": 10,
                    "description": "ATR calculation period"
                },
                {
                    "name": "multiplier",
                    "type": "number",
                    "label": "ATR Multiplier",
                    "default": 3,
                    "description": "Multiplier for ATR"
                }
            ],
            "outputs": ["SuperTrend", "Direction"]
        },
        {
            "name": "TSI",
            "function_name": "TSI",
            "display_name": "True Strength Index",
            "description": "Momentum oscillator based on double smoothing of price changes",
            "parameters": [
                {
                    "name": "long",
                    "type": "number",
                    "label": "Long Period",
                    "default": 25,
                    "description": "Long smoothing period"
                },
                {
                    "name": "short",
                    "type": "number",
                    "label": "Short Period",
                    "default": 13,
                    "description": "Short smoothing period"
                },
                {
                    "name": "signal",
                    "type": "number",
                    "label": "Signal Period",
                    "default": 7,
                    "description": "Signal line period"
                }
            ],
            "outputs": ["TSI", "Signal"]
        },
        {
            "name": "StochRSI",
            "function_name": "STOCHRSI",
            "display_name": "Stochastic RSI",
            "description": "Applies stochastic oscillator formula to RSI values",
            "parameters": [
                {
                    "name": "rsiPeriod",
                    "type": "number",
                    "label": "RSI Period",
                    "default": 14,
                    "description": "Period for RSI calculation"
                },
                {
                    "name": "stochPeriod",
                    "type": "number",
                    "label": "Stoch Period",
                    "default": 14,
                    "description": "Period for stochastic calculation"
                }
            ],
            "outputs": ["StochRSI"]
        },
        {
            "name": "AO",
            "function_name": "AO",
            "display_name": "Awesome Oscillator",
            "description": "Measures market momentum using simple moving averages",
            "parameters": [
                {
                    "name": "fastPeriod",
                    "type": "number",
                    "label": "Fast Period",
                    "default": 5,
                    "description": "Fast SMA period"
                },
                {
                    "name": "slowPeriod",
                    "type": "number",
                    "label": "Slow Period",
                    "default": 34,
                    "description": "Slow SMA period"
                }
            ],
            "outputs": ["AO"]
        },
        {
            "name": "BOP",
            "function_name": "BOP",
            "display_name": "Balance of Power",
            "description": "Measures the strength of buyers versus sellers",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Smoothing period"
                }
            ],
            "outputs": ["BOP"]
        },
        {
            "name": "HistoricalVolatility",
            "function_name": "HV",
            "display_name": "Historical Volatility",
            "description": "Measures the dispersion of returns for a given security over time",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 20,
                    "description": "Number of periods for volatility calculation"
                },
                {
                    "name": "barsBack",
                    "type": "number",
                    "label": "Historical Reference",
                    "default": 252,
                    "description": "Annual trading days for annualization"
                }
            ],
            "outputs": ["HV"]
        },
        {
            "name": "AccumulationDistribution",
            "function_name": "AD",
            "display_name": "Accumulation/Distribution Line",
            "description": "Volume-based indicator designed to measure cumulative flow of money",
            "parameters": [],
            "outputs": ["AD"]
        },
        {
            "name": "EOM",
            "function_name": "EOM",
            "display_name": "Ease of Movement",
            "description": "Relates price change to volume to identify the strength of a trend",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 14,
                    "description": "Moving average period"
                }
            ],
            "outputs": ["EOM"]
        },
        {
            "name": "MassIndex",
            "function_name": "MASS",
            "display_name": "Mass Index",
            "description": "Identifies trend reversals by measuring the narrowing and widening of trading ranges",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "Time Period",
                    "default": 25,
                    "description": "EMA period"
                }
            ],
            "outputs": ["MASS"]
        },
        {
            "name": "MACDHistogram",
            "function_name": "MACDFIX",
            "display_name": "MACD Histogram",
            "description": "Shows the difference between MACD and its signal line",
            "parameters": [
                {
                    "name": "fastperiod",
                    "type": "number",
                    "label": "Fast Period",
                    "default": 12,
                    "description": "Fast EMA period"
                },
                {
                    "name": "slowperiod",
                    "type": "number",
                    "label": "Slow Period",
                    "default": 26,
                    "description": "Slow EMA period"
                },
                {
                    "name": "signalperiod",
                    "type": "number",
                    "label": "Signal Period",
                    "default": 9,
                    "description": "Signal EMA period"
                }
            ],
            "outputs": ["MACDHist"]
        },
        {
            "name": "ZigZag",
            "function_name": "ZIGZAG",
            "display_name": "ZigZag",
            "description": "Filters out small price movements by highlighting significant trends",
            "parameters": [
                {
                    "name": "percentage",
                    "type": "number",
                    "label": "Reversal Percentage",
                    "default": 5,
                    "description": "Percentage threshold for a reversal"
                }
            ],
            "outputs": ["ZigZag"]
        },
        {
            "name": "GMMA",
            "function_name": "GMMA",
            "display_name": "Guppy Multiple Moving Average",
            "description": "System of multiple moving averages to identify trend changes",
            "parameters": [
                {
                    "name": "shortPeriods",
                    "type": "dropdown",
                    "label": "Short-term Periods",
                    "options": ["3,5,8,10,12,15", "3,5,7,9,11,13"],
                    "default": "3,5,8,10,12,15",
                    "description": "Short-term moving average periods"
                },
                {
                    "name": "longPeriods",
                    "type": "dropdown",
                    "label": "Long-term Periods",
                    "options": ["30,35,40,45,50,60", "24,30,36,42,48,54"],
                    "default": "30,35,40,45,50,60",
                    "description": "Long-term moving average periods"
                }
            ],
            "outputs": ["ShortMAs", "LongMAs"]
        },
        {
            "name": "ElderRay",
            "function_name": "ELDERRAY",
            "display_name": "Elder Ray Index",
            "description": "Measures buying and selling pressure with Bull Power and Bear Power",
            "parameters": [
                {
                    "name": "timeperiod",
                    "type": "number",
                    "label": "EMA Period",
                    "default": 13,
                    "description": "EMA calculation period"
                }
            ],
            "outputs": ["BullPower", "BearPower"]
        }
    ]
}
