#!/usr/bin/env python3
"""
Demonstration: Current vs New Data Context Structure
"""
import json

print("="*80)
print("CURRENT DATA CONTEXT STRUCTURE (Single Strategy)")
print("="*80)

current_context = {
    "mode": "backtesting",
    
    # ===== CANDLES =====
    # Format: {timeframe_instrumentType: DataFrame}
    "candle_df_dict": {
        "1m_TI": "DataFrame[20 rows × columns: timestamp, open, high, low, close, volume, EMA_21, RSI_14, ...]",
        "3m_TI": "DataFrame[20 rows × columns: timestamp, open, high, low, close, volume, RSI_14, ...]",
        "5m_TI": "DataFrame[20 rows × columns: timestamp, open, high, low, close, volume, ...]"
    },
    
    # ===== LTP STORE =====
    # Format: {ltp_role: value}
    "ltp_store": {
        "ltp_TI": 24350.50,           # Trading Instrument (underlying)
        "ltp_SI": 24350.50,           # Strategy Instrument
        "ltp_pos_123": 125.50,        # Position-specific LTP (for options)
        "ltp_pos_124": 98.25
    },
    
    # ===== GPS (Global Position Store) =====
    "gps": "GlobalPositionStore instance",
    
    # ===== NODE PERSISTENCE =====
    "node_variables": {
        "entry-node-1": {"last_signal": "BUY", "signal_time": "09:16:00"},
        "exit-node-1": {"exit_triggered": False}
    },
    "node_order_status": {
        "entry-node-1": {"order_id": "ORD123", "status": "COMPLETE"}
    },
    "node_states": {
        "entry-node-1": "ACTIVE",
        "exit-node-1": "INACTIVE"
    },
    "node_instances": "Dict[node_id: NodeInstance]",
    
    # ===== OTHER =====
    "position_manager": "PositionManagerAdapter instance",
    "clickhouse_client": "ClickHouse client for F&O resolution",
    "current_tick": {"symbol": "NIFTY", "ltp": 24350.50, "timestamp": "2024-10-01 09:16:54"},
    "current_timestamp": "2024-10-01 09:16:54"
}

print("\n📊 Current Structure Keys:")
for key in current_context.keys():
    print(f"  - {key}")

print("\n📋 Current candle_df_dict keys:")
for key in current_context["candle_df_dict"].keys():
    print(f"  - {key}")

print("\n💾 Current ltp_store keys:")
for key in current_context["ltp_store"].keys():
    print(f"  - {key}")

print("\n" + "="*80)
print("NEW DATA CONTEXT STRUCTURE (Multi-Strategy)")
print("="*80)

new_context = {
    "mode": "backtesting",
    
    # ===== METADATA (NEW!) =====
    "strategies_agg": {
        "instruments": ["NIFTY", "BANKNIFTY"],
        "timeframes": ["NIFTY:1m", "NIFTY:3m", "BANKNIFTY:3m", "BANKNIFTY:5m"],
        "indicators": {
            "NIFTY": {
                "1m": [{"name": "EMA", "params": {"length": 21}}],
                "3m": [{"name": "RSI", "params": {"length": 14}}]
            },
            "BANKNIFTY": {
                "3m": [
                    {"name": "RSI", "params": {"length": 14}},
                    {"name": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9}}
                ],
                "5m": [{"name": "EMA", "params": {"length": 21}}]
            }
        },
        "options": {
            "NIFTY": ["TI:W0:ATM:CE", "TI:W0:ATM:PE"],
            "BANKNIFTY": ["TI:M0:ITM2:CE", "TI:M0:OTM2:PE"]
        },
        "strategies": [
            ("user_2yfjTGEKjL7XkklQyBaMP6SN2Lc", "9da37830-158a-46c2-97bd-968817f6b130"),
            ("user_2yfjTGEKjL7XkklQyBaMP6SN2Lc", "4a7a1a31-e209-4b23-891a-3899fb8e4c28")
        ]
    },
    
    "strategies": {
        "9da37830-158a-46c2-97bd-968817f6b130": {
            "user_id": "user_2yfjTGEKjL7XkklQyBaMP6SN2Lc",
            "name": "My New Strategy14",
            "instruments": ["BANKNIFTY"],
            "timeframes": ["BANKNIFTY:3m", "BANKNIFTY:5m"],
            "indicators": {"BANKNIFTY": {"3m": [...], "5m": [...]}},
            "options": {"BANKNIFTY": ["TI:M0:ITM2:CE", "TI:M0:OTM2:PE"]}
        },
        "4a7a1a31-e209-4b23-891a-3899fb8e4c28": {
            "user_id": "user_2yfjTGEKjL7XkklQyBaMP6SN2Lc",
            "name": "My New Strategy13",
            "instruments": ["NIFTY"],
            "timeframes": ["NIFTY:1m", "NIFTY:3m"],
            "indicators": {"NIFTY": {"1m": [...], "3m": [...]}},
            "options": {"NIFTY": ["TI:W0:ATM:CE", "TI:W0:ATM:PE"]}
        }
    },
    
    # ===== CANDLES (UPDATED FORMAT!) =====
    # NEW: Store by SYMBOL:TIMEFRAME (not timeframe_instrumentType)
    "candles": {
        "NIFTY:1m": [
            # List of 20 dicts (candles), with indicators as fields
            {"timestamp": "09:15", "open": 24340, "high": 24355, "low": 24338, "close": 24350, "volume": 1000, "EMA_21": 24345.5},
            {"timestamp": "09:16", "open": 24350, "high": 24365, "low": 24348, "close": 24360, "volume": 1200, "EMA_21": 24346.8},
            "... 18 more candles ..."
        ],
        "NIFTY:3m": [
            {"timestamp": "09:15", "open": 24340, "high": 24365, "low": 24338, "close": 24355, "volume": 3500, "RSI_14": 62.5},
            "... 19 more candles ..."
        ],
        "BANKNIFTY:3m": [
            {"timestamp": "09:15", "open": 53200, "high": 53250, "low": 53180, "close": 53220, "volume": 2000, "RSI_14": 58.3, "MACD_macd": 15.5},
            "... 19 more candles ..."
        ],
        "BANKNIFTY:5m": [
            {"timestamp": "09:15", "open": 53200, "high": 53280, "low": 53180, "close": 53250, "volume": 4500, "EMA_21": 53210.2},
            "... 19 more candles ..."
        ]
    },
    
    # ===== INDICATORS (LATEST VALUES) =====
    # NEW: Quick access to latest indicator values per symbol/timeframe
    "indicators": {
        "NIFTY": {
            "1m": {"EMA_21": 24346.8},
            "3m": {"RSI_14": 62.5}
        },
        "BANKNIFTY": {
            "3m": {"RSI_14": 58.3, "MACD_macd": 15.5, "MACD_signal": 12.3, "MACD_hist": 3.2},
            "5m": {"EMA_21": 53210.2}
        }
    },
    
    # ===== LTP (UPDATED!) =====
    # NEW: Include both instruments AND option contracts
    "ltp": {
        # Underlying instruments
        "NIFTY": 24350.50,
        "BANKNIFTY": 53250.25,
        
        # Option contracts (dynamically subscribed based on strategies_agg.options)
        "NIFTY:2024-11-28:OPT:24350:CE": 125.50,    # TI:W0:ATM:CE
        "NIFTY:2024-11-28:OPT:24350:PE": 98.25,     # TI:W0:ATM:PE
        "BANKNIFTY:2024-11-27:OPT:53300:CE": 185.0, # TI:M0:ITM2:CE
        "BANKNIFTY:2024-11-27:OPT:53100:PE": 142.5  # TI:M0:OTM2:PE
    },
    
    # ===== GPS (Same) =====
    "gps": "GlobalPositionStore instance",
    
    # ===== NODE PERSISTENCE (Same) =====
    "node_variables": "...",
    "node_order_status": "...",
    "node_states": "...",
    "node_instances": "...",
    
    # ===== OTHER (Same) =====
    "position_manager": "...",
    "clickhouse_client": "...",
    "current_tick": "...",
    "current_timestamp": "..."
}

print("\n📊 New Structure Keys:")
for key in new_context.keys():
    print(f"  - {key}")

print("\n🆕 NEW: strategies_agg structure:")
print(f"  - instruments: {new_context['strategies_agg']['instruments']}")
print(f"  - timeframes: {new_context['strategies_agg']['timeframes']}")
print(f"  - Total strategies: {len(new_context['strategies_agg']['strategies'])}")

print("\n🆕 NEW: strategies (per-strategy metadata):")
for strategy_id in new_context['strategies'].keys():
    name = new_context['strategies'][strategy_id]['name']
    print(f"  - {strategy_id[:12]}... ({name})")

print("\n🆕 NEW: candles structure (SYMBOL:TF format):")
for key in new_context["candles"].keys():
    print(f"  - {key}: 20 candles with indicators")

print("\n🆕 NEW: indicators (latest values):")
for symbol, tfs in new_context["indicators"].items():
    for tf, inds in tfs.items():
        print(f"  - {symbol}:{tf}: {list(inds.keys())}")

print("\n🆕 NEW: ltp (instruments + options):")
print(f"  - Underlying: NIFTY, BANKNIFTY")
print(f"  - Options: 4 contracts (based on strategies_agg.options)")

print("\n" + "="*80)
print("KEY DIFFERENCES")
print("="*80)
print("""
1. ✅ METADATA ADDED:
   - strategies_agg: Aggregated requirements across all strategies
   - strategies: Per-strategy metadata for isolation

2. ✅ CANDLES FORMAT CHANGED:
   OLD: {'1m_TI': DataFrame, '3m_TI': DataFrame}
   NEW: {'NIFTY:1m': List[20 dicts], 'NIFTY:3m': List[20 dicts], ...}
   
   Benefits:
   - Symbol-specific data (support multiple symbols)
   - List format (faster access, no DataFrame overhead)
   - Indicators included in each candle dict

3. ✅ INDICATORS QUICK ACCESS:
   NEW: Latest indicator values per symbol/timeframe
   Example: context['indicators']['NIFTY']['1m']['EMA_21'] → 24346.8

4. ✅ LTP EXPANDED:
   OLD: Only 'ltp_TI', 'ltp_SI', 'ltp_pos_123'
   NEW: Direct symbol keys: 'NIFTY', 'BANKNIFTY', option contracts

5. ✅ SAME: GPS, node persistence, position_manager (unchanged)
""")

print("\n" + "="*80)
print("USAGE EXAMPLES")
print("="*80)

print("""
# Get latest 20 candles for NIFTY 1m:
candles = context['candles']['NIFTY:1m']
latest_candle = candles[-1]  # Current/latest candle
previous_candle = candles[-2]  # Previous completed candle

# Get latest indicator value:
ema_value = context['indicators']['NIFTY']['1m']['EMA_21']

# Get LTP:
nifty_ltp = context['ltp']['NIFTY']
option_ltp = context['ltp']['NIFTY:2024-11-28:OPT:24350:CE']

# Check which strategies are active:
active_strategies = context['strategies_agg']['strategies']
for user_id, strategy_id in active_strategies:
    strategy_meta = context['strategies'][strategy_id]
    print(f"Strategy: {strategy_meta['name']}")
""")

print("\n" + "="*80)
print("✅ SUMMARY")
print("="*80)
print("""
Current: Single strategy, DataFrame-based, instrument-type keys
New: Multi-strategy, List-based, symbol:timeframe keys, with metadata

Next: We'll wire this new structure into ContextAdapter and test!
""")
