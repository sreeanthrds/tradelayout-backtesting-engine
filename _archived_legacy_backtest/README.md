# Archived Legacy Backtest Files

**Date Archived:** 2025-11-25

## Why Archived?

These files implement a **simple/legacy strategy executor** that:

❌ Uses hardcoded 1-minute candles only  
❌ Only processes spot/underlying, not multi-symbol  
❌ Doesn't use the node framework (`start_node.execute()`)  
❌ Missing `context['node_states']` and `context['node_variables']`  
❌ Different behavior from production live trading engine  

## Files Archived:

- `strategy_executor.py` - Legacy executor with hardcoded logic
- `backtest_engine.py` - Engine that uses legacy executor
- `run_backtest.py` - Entry point for legacy system
- `fetch_and_test_strategy.py` - Helper for legacy system
- `backtest_config.py` - Config for legacy system

## Production System:

The **correct** backtest system uses:

✅ `run_with_centralized_processor.py` - Matches live trading  
✅ `src/core/centralized_tick_processor.py` - Node framework  
✅ `src/backtesting/centralized_backtest_engine.py` - Proper engine  
✅ Full node framework with `start_node.execute()`  
✅ Multi-timeframe, multi-symbol candle building  
✅ Complete `context` with node states and variables  

## Migration:

Use `run_with_centralized_processor.py` for all backtests going forward.

It provides:
- Exact same logic as live trading engine
- Full node variable tracking
- Multi-timeframe support from strategy config
- Proper position management via GPS
- Complete context structure
