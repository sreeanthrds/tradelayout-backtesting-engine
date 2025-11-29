"""
Data Management Layer
=====================

Orchestrates all data preparation for strategy execution:
1. Symbol mapping (broker format → unified format)
2. LTP store updates (all symbols)
3. Candle building (per timeframe)
4. Indicator calculation (incremental)
5. Cache management (20 candles + indicator state)

This layer is SEPARATE from strategy execution (onTick).
Same code works for both backtesting and live trading.
"""

import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import pandas as pd

from src.symbol_mapping.symbol_cache_manager import get_symbol_cache_manager

logger = logging.getLogger(__name__)


class DataManager:
    """
    Central data management for backtesting and live trading.
    
    Responsibilities:
    - Convert symbols to unified format
    - Update LTP store
    - Build candles
    - Calculate indicators incrementally
    - Maintain cache (20 candles + indicator state)
    
    Does NOT handle strategy execution - that's onTick()'s job!
    """
    
    def __init__(self, cache: Any, broker_name: str = 'clickhouse', shared_cache: Any = None):
        """
        Initialize data manager.
        
        Args:
            cache: Cache instance (DictCache for backtest, Redis for live)
            broker_name: Broker name ('angelone', 'zerodha', 'aliceblue', 'clickhouse')
            shared_cache: Optional SharedDataCache for multi-strategy optimization
        """
        self.cache = cache
        self.broker_name = broker_name
        self.symbol_cache = get_symbol_cache_manager()
        self.shared_cache = shared_cache  # NEW: Shared cache across strategies
        
        # LTP store (all symbols including options) - now uses universal format
        self.ltp: Dict[str, float] = {}  # {symbol: ltp} for both spot and options
        
        # Legacy LTP store for backward compatibility
        self.ltp_store: Dict[str, Dict[str, Any]] = {}
        
        # Candle builders per timeframe
        self.candle_builders: Dict[str, Any] = {}
        
        # Indicator instances: {symbol:timeframe: {indicator_key: indicator_instance}}
        # All indicators are HybridIndicator instances with calculate_bulk() and update_incremental()
        self.indicators: Dict[str, Dict[str, Any]] = {}

        # Track which symbol:timeframe pairs have been initialized from historical data.
        # Key format matches self.indicators ("SYMBOL:TF").
        # This is a light-weight registry used by higher-level components (e.g.,
        # StrategySubscriptionManager) to know which pairs already have a 500-candle
        # history and indicator state.
        self._initialized_symbol_timeframes: Dict[str, bool] = {}
        
        # Pattern resolver (initialized during initialize())
        self.pattern_resolver = None
        
        # Clickhouse client (will be initialized during initialize())
        self.clickhouse_client = None
        
        # Option tick buffers for on-demand loading
        # Format: {contract_key: {'ticks': deque, 'current_index': int}}
        self.option_tick_buffers = {}
        
        # Track loaded options for logging
        self.loaded_option_contracts = set()
        
        logger.info("📊 Data Manager initialized")
    
    def register_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator: Any
    ) -> str:
        """
        Register an indicator for calculation.
        
        Args:
            symbol: Unified symbol (e.g., 'NIFTY')
            timeframe: Timeframe (e.g., '1m', '5m')
            indicator: Indicator object with name and params attributes
        
        Returns:
            indicator_key: Generated key (e.g., 'RSI(14)', 'BBAND(14,2)')
        """
        key = f"{symbol}:{timeframe}"
        
        if key not in self.indicators:
            self.indicators[key] = {}
        
        # Generate indicator key (function-like format)
        indicator_key = self._generate_indicator_key(indicator.name, indicator.params)
        
        # Store indicator instance
        self.indicators[key][indicator_key] = indicator
        
        logger.info(f"📈 Registered {indicator_key} for {symbol}:{timeframe}")
        
        return indicator_key
    
    def _generate_indicator_key(self, name: str, params: Dict[str, Any]) -> str:
        """
        Generate function-like indicator key.
        
        Examples:
            RSI, {period: 14} → 'RSI(14)'
            BBAND, {period: 14, std_dev: 2} → 'BBAND(14,2)'
            MACD, {fast: 12, slow: 26, signal: 9} → 'MACD(12,26,9)'
        
        Args:
            name: Indicator name
            params: Parameters dict
        
        Returns:
            Indicator key in function format
        """
        param_values = ','.join(str(v) for v in params.values())
        return f"{name}({param_values})"
    
    def initialize_from_historical_data(
        self,
        symbol: str,
        timeframe: str,
        candles: pd.DataFrame
    ):
        """
        Initialize indicators with historical data using ta_hybrid bulk calculation.
        
        This is called ONCE before trading starts to:
        1. Load 500 historical candles from ClickHouse
        2. Calculate indicators on all 500 candles (bulk - fast vectorized) if indicators exist
        3. Initialize indicator state for incremental updates
        4. Store last 20 candles with indicator values in cache
        
        IMPORTANT: Always stores last 20 candles even if no indicators registered,
        because condition nodes may reference historical candles.
        
        Args:
            symbol: Unified symbol
            timeframe: Timeframe
            candles: DataFrame with 500 candles (OHLCV)
        """
        key = f"{symbol}:{timeframe}"
        
        has_indicators = key in self.indicators and self.indicators[key]
        
        if has_indicators:
            logger.info(f"🔄 Initializing {len(self.indicators[key])} indicators for {key} with {len(candles)} candles")
        else:
            logger.info(f"📊 Loading {len(candles)} historical candles for {key} (no indicators)")
        
        # Initialize each ta_hybrid indicator instance (only if indicators registered)
        if has_indicators:
            for indicator_key, indicator in self.indicators[key].items():
                try:
                    # Step 1: Bulk calculation on full historical data (fast vectorized)
                    result = indicator.calculate_bulk(candles)
                    
                    # Step 2: Initialize indicator state from bulk result
                    indicator.initialize_from_dataframe(candles)
                    
                    # Step 3: Add indicator values to DataFrame
                    col_name = indicator_key.replace('(', '_').replace(')', '').replace(',', '_')
                    
                    if result is not None:
                        if isinstance(result, pd.Series):
                            candles[col_name] = result
                        elif isinstance(result, pd.DataFrame):
                            # Multi-column result (e.g., MACD, Bollinger Bands)
                            for col in result.columns:
                                candles[f"{col_name}_{col}"] = result[col]
                        
                        logger.info(f"✅ {indicator_key} initialized with bulk calculation + state")
                    else:
                        logger.warning(f"⚠️  {indicator_key} returned None from bulk calculation")

                    # Optional debug verification: replay candles incrementally and compare
                    try:
                        test_indicator_class = type(indicator)
                        test_indicator = test_indicator_class(**getattr(indicator, 'params', {}))

                        # Prepare bulk reference values
                        reference_columns = []
                        if isinstance(result, pd.Series):
                            reference_columns = [col_name]
                        elif isinstance(result, pd.DataFrame):
                            reference_columns = [f"{col_name}_{c}" for c in result.columns]

                        incremental_values = {col: [] for col in reference_columns}

                        # Replay each candle through update()
                        for _, row in candles.iterrows():
                            candle_dict = {
                                'timestamp': row['timestamp'],
                                'open': row['open'],
                                'high': row['high'],
                                'low': row['low'],
                                'close': row['close'],
                                'volume': row['volume'],
                            }

                            new_value = test_indicator.update(candle_dict)

                            if isinstance(new_value, dict):
                                for ref_col in reference_columns:
                                    base = ref_col.replace(f"{col_name}_", "")
                                    if base in new_value:
                                        incremental_values[ref_col].append(new_value[base])
                                    else:
                                        incremental_values[ref_col].append(None)
                            else:
                                # Single-column indicator
                                if reference_columns:
                                    incremental_values[reference_columns[0]].append(new_value)

                        # Compare last value of each column (500th candle) with bulk result
                        for ref_col in reference_columns:
                            bulk_series = candles[ref_col].tolist()
                            inc_series = incremental_values.get(ref_col, [])
                            if not bulk_series or not inc_series:
                                continue

                            bulk_last = bulk_series[-1]
                            inc_last = inc_series[-1]

                            # Only compare when both are numeric and not NaN
                            if pd.notna(bulk_last) and pd.notna(inc_last):
                                try:
                                    diff = abs(float(bulk_last) - float(inc_last))
                                    if diff > 1e-6:
                                        logger.warning(
                                            f"⚠️  Bulk vs incremental mismatch for {indicator_key} on {key} "
                                            f"column {ref_col}: bulk={bulk_last}, incremental={inc_last}, diff={diff}"
                                        )
                                except Exception:
                                    # Fallback: string comparison if casting fails
                                    if str(bulk_last) != str(inc_last):
                                        logger.warning(
                                            f"⚠️  Bulk vs incremental string mismatch for {indicator_key} on {key} "
                                            f"column {ref_col}: bulk={bulk_last}, incremental={inc_last}"
                                        )

                    except Exception as debug_e:
                        # Debug path must never break core flow
                        logger.debug(f"Bulk/incremental verification skipped for {indicator_key}: {debug_e}")
                
                except Exception as e:
                    import traceback
                    logger.error(f"❌ CRITICAL: Error initializing {indicator_key}: {e}")
                    logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                    # Re-raise - indicator initialization failure is critical
                    raise RuntimeError(f"Indicator initialization failed for {indicator_key}: {e}") from e
        
        # CRITICAL: ALWAYS store last 20 candles, even if no indicators registered
        # Reason: Condition nodes may reference historical candles (e.g., candles[-2]['high'])
        # This runs for all timeframes, regardless of indicator registration
        if self._is_index_or_future(symbol):
            last_20 = candles.tail(20).copy()
            
            # Convert to list of dicts for cache (includes indicator columns!)
            candles_list = last_20.to_dict('records')
            self.cache.set_candles(symbol, timeframe, candles_list)
            
            # Mark this symbol:timeframe as initialized from historical data
            self._initialized_symbol_timeframes[key] = True
            
            if has_indicators:
                logger.info(f"💾 Stored last 20 candles with {len(self.indicators[key])} indicators for {key}")
                logger.info(f"🧠 Indicator states ready for incremental updates")
            else:
                logger.info(f"💾 Stored last 20 candles for {key} (no indicators registered)")
    
    def process_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single tick.
        
        Steps:
        1. Convert symbol to unified format
        2. Update LTP store
        3. Build candles (per timeframe)
        4. If candle completes:
           - Update indicators incrementally
           - Add to 20-candle buffer
        
        Args:
            tick: Tick data with keys:
                - symbol: Broker-specific symbol
                - ltp: Last traded price
                - timestamp: Timestamp
                - volume: Volume
                - oi: Open interest
        
        Returns:
            Processed tick with unified symbol
        """
        # Step 1: Convert symbol to unified format
        broker_symbol = tick['symbol']
        
        # Check if symbol is already in universal format (has colons like NIFTY:2024-10-03:OPT:25950:CE)
        # This happens when tick source already converted it
        if ':' in broker_symbol:
            # Already in universal format - use as-is
            unified_symbol = broker_symbol
        elif self.broker_name == 'clickhouse':
            # For backtesting: Convert ClickHouse compact ticker format to universal format
            # if needed (e.g., NIFTY03OCT2425950CE -> NIFTY:2024-10-03:OPT:25950:CE)
            from src.symbol_mapping.clickhouse_ticker_converter import is_clickhouse_format, to_universal
            
            if is_clickhouse_format(broker_symbol):
                try:
                    # Convert ClickHouse format to universal format directly
                    unified_symbol = to_universal(broker_symbol)
                except ValueError as e:
                    import traceback
                    logger.error(f"❌ CRITICAL: Failed to convert ClickHouse ticker: {broker_symbol}")
                    logger.error(f"   Error: {e}")
                    logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                    raise RuntimeError(f"ClickHouse ticker conversion failed: {e}") from e
            else:
                # Not ClickHouse format and not universal (probably index symbol like NIFTY)
                # Use symbol cache for lookup
                unified_symbol = self.symbol_cache.to_unified(self.broker_name, broker_symbol)
        else:
            # For live trading: Use symbol cache lookup (handles AngelOne, AliceBlue, etc.)
            unified_symbol = self.symbol_cache.to_unified(self.broker_name, broker_symbol)
        
        tick['symbol'] = unified_symbol
        
        # Step 2: Update LTP stores (all symbols)
        # Update new unified LTP dict (simple: symbol -> ltp)
        self.ltp[unified_symbol] = tick['ltp']
        
        # Also update legacy LTP store for backward compatibility
        self.ltp_store[unified_symbol] = {
            'ltp': tick['ltp'],
            'timestamp': self._format_timestamp_microseconds(tick['timestamp']),
            'volume': tick.get('volume', 0),
            'oi': tick.get('oi', 0)
        }
        
        # Update shared cache LTP store if available
        if self.shared_cache:
            self.shared_cache.update_ltp(
                symbol=unified_symbol,
                price=tick['ltp'],
                timestamp=tick['timestamp']
            )
        
        # Step 3: Build candles (per timeframe) - ONLY for indices/futures, NOT options
        completed_candles = []
        
        # Debug: Track tick processing
        tick_count = getattr(self, '_tick_count', 0)
        self._tick_count = tick_count + 1
        
        if self._tick_count <= 5:
            print(f"[DEBUG DataManager] Processing tick {self._tick_count}: {unified_symbol} @ {tick['ltp']}, builders: {len(self.candle_builders)}")
        
        # Only build candles for indices and futures (not options)
        # Options only need LTP tracking, no candle building
        if self._is_index_or_future(unified_symbol):
            for timeframe, builder in self.candle_builders.items():
                candle = builder.process_tick(tick)
                
                if candle:  # Candle completed
                    completed_candles.append((timeframe, candle))
                    if self._tick_count <= 300:  # Show first 300 completed candles
                        print(f"[DEBUG DataManager] ✅ Candle completed: {unified_symbol} {timeframe} at {candle['timestamp']}")
        
        # Step 4: Update indicators and cache for completed candles
        for timeframe, candle in completed_candles:
            # Add to candle buffer with incremental indicator updates
            if self._tick_count <= 300:
                print(f"[DEBUG DataManager] Adding candle to buffer: {unified_symbol}:{timeframe}")
            self._add_to_candle_buffer(unified_symbol, timeframe, candle)
        
        return tick
    
    # NOTE: _update_indicators method removed - functionality merged into _add_to_candle_buffer
    # Old method was redundant and caused duplicate calls to _add_to_candle_buffer
    # New approach: _add_to_candle_buffer handles both buffer management AND incremental indicator updates
    
    def _add_to_candle_buffer(self, symbol: str, timeframe: str, candle: Dict[str, Any]):
        """
        Add completed candle to 20-candle buffer with incremental indicator updates.
        
        Uses pure list operations (no DataFrame conversions) for optimal performance.
        
        Args:
            symbol: Unified symbol
            timeframe: Timeframe
            candle: Completed candle
        """
        key = f"{symbol}:{timeframe}"
        
        # Get current buffer as list of dicts (no conversion needed!)
        buffer = self.cache.get_candles(symbol, timeframe, count=20)
        if not buffer:
            buffer = []
        
        # Create new candle dict (OHLCV only initially)
        new_candle_data = {
            'timestamp': candle['timestamp'],
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle['volume']
        }
        
        # Update indicators incrementally (O(1) - super fast!)
        if key in self.indicators and self.indicators[key]:
            for indicator_key, indicator in self.indicators[key].items():
                try:
                    # ✅ Incremental update (1 calculation, not 20!)
                    new_value = indicator.update(candle)
                    
                    # Add indicator value to new candle
                    col_name = indicator_key.replace('(', '_').replace(')', '').replace(',', '_')
                    
                    if new_value is not None:
                        if isinstance(new_value, dict):
                            # Multi-column result (e.g., MACD)
                            for col, val in new_value.items():
                                new_candle_data[f"{col_name}_{col}"] = val
                        else:
                            # Single value result
                            new_candle_data[col_name] = new_value
                
                except Exception as e:
                    import traceback
                    logger.error(f"❌ CRITICAL: Error updating {indicator_key} incrementally: {e}")
                    logger.error(f"   Candle: {candle}")
                    logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                    # Re-raise - incremental indicator update failure is critical
                    raise RuntimeError(f"Incremental update failed for {indicator_key}: {e}") from e
        
        # Append new candle and keep last 20 (pure list operations - no DataFrame!)
        buffer.append(new_candle_data)
        buffer = buffer[-20:]  # Keep last 20 (FIFO)
        
        # Store back in cache (no conversion needed!)
        self.cache.set_candles(symbol, timeframe, buffer)
        
        logger.debug(f"📊 Updated {symbol}:{timeframe} buffer with incremental indicators")
    
    # NOTE: _add_indicator_columns method removed - replaced with incremental updates
    # Old method recalculated ALL indicators on ALL candles (20x slower + wrong history)
    # New method uses indicator.update() for O(1) incremental calculation
    
    def get_context(self) -> Dict[str, Any]:
        """
        Get simplified context for strategy execution.
        
        SIMPLIFIED CONTEXT (only what strategies actually need):
        - Market data: candles, LTP
        - Service interfaces: data_manager (for loading options), pattern_resolver
        
        Returns:
            Context dict with:
                - candle_df_dict: {symbol:timeframe: [list of candle dicts]}
                - ltp: {symbol: price} - Unified LTP store
                - data_manager: Reference to DataManager for service calls
                - pattern_resolver: For resolving option patterns
        """
        # Build candle_df_dict from cache
        # Include ALL symbols with candles, not just those with indicators
        candle_df_dict = {}
        
        # Get all unique symbol:timeframe combinations from cache
        # First, try from indicators (if any)
        keys_to_check = set(self.indicators.keys())
        
        # Also check cache directly for any stored candles
        # DictCache stores candles with keys like "NIFTY:1m"
        if hasattr(self.cache, 'candles'):
            keys_to_check.update(self.cache.candles.keys())
        
        # Get candles for all keys
        for key in keys_to_check:
            if ':' in key:
                symbol, timeframe = key.split(':', 1)
                candles = self.cache.get_candles(symbol, timeframe, count=20)
                if candles is not None and len(candles) > 0:
                    candle_df_dict[key] = candles
        
        # SIMPLIFIED: Only expose what strategies actually need
        return {
            # Market data
            'candle_df_dict': candle_df_dict,  # All candles with indicators
            'ltp': self.ltp,                   # Current prices {symbol: price}
            'ltp_store': self.ltp_store,       # Full LTP store with metadata
            
            # Service interfaces (clean APIs, not internal objects)
            'data_manager': self,              # For load_option_contract(), etc.
            'pattern_resolver': self.pattern_resolver,  # For TI:W0:ATM:CE resolution
            'clickhouse_client': self.clickhouse_client,  # For option loading
            'mode': 'backtesting',             # Explicitly set mode for backtesting
        }
    
    def _is_index_or_future(self, symbol: str) -> bool:
        """
        Check if symbol is an index or future (not option).
        
        Only indices and futures get 20-candle buffer.
        Options only get LTP tracking.
        
        Args:
            symbol: Unified symbol (uses colon separator)
        
        Returns:
            True if index or future, False if option
        
        Examples:
            - NIFTY → True (index)
            - NIFTY:2024-10-03:FUT → True (future)
            - NIFTY:2024-10-03:OPT:25950:CE → False (option)
        """
        # Universal format uses colons, not underscores
        # Options have :OPT: in the symbol
        if ':OPT:' in symbol:
            return False
        
        # Indices and futures don't have :OPT:
        return True
    
    def _format_timestamp_microseconds(self, timestamp: Any) -> str:
        """
        Format timestamp to microseconds string.
        
        Args:
            timestamp: Timestamp (datetime, string, or int)
        
        Returns:
            Formatted timestamp string with microseconds
        """
        if isinstance(timestamp, datetime):
            return timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')
        elif isinstance(timestamp, str):
            return timestamp
        elif isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        return str(timestamp)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get data manager statistics.
        
        Returns:
            Statistics dict
        """
        total_indicators = sum(len(inds) for inds in self.indicators.values())
        initialized_indicators = sum(
            1 for inds in self.indicators.values()
            for ind in inds.values()
            if ind.is_initialized
        )
        
        return {
            'symbols_tracked': len(set(k.split(':')[0] for k in self.indicators.keys())),
            'timeframes': len(set(k.split(':')[1] for k in self.indicators.keys())),
            'total_indicators': total_indicators,
            'initialized_indicators': initialized_indicators,
            'ltp_store_size': len(self.ltp_store),
            'candle_builders': len(self.candle_builders)
        }

    # ========================================================================
    # INTROSPECTION HELPERS FOR COLD SUBSCRIPTION
    # ========================================================================

    def has_initialized_history(self, symbol: str, timeframe: str) -> bool:
        """Return True if this symbol:timeframe has been bootstrapped from history.

        This simply checks whether initialize_from_historical_data() has run and
        stored last-20 candles for the given pair (for indices/futures). For
        options, this will always be False because we do not keep 20-candle
        buffers for them.
        """
        key = f"{symbol}:{timeframe}"
        return bool(self._initialized_symbol_timeframes.get(key))

    def get_indicator_keys_for(self, symbol: str, timeframe: str) -> Set[str]:
        """Return the set of indicator keys currently registered for symbol:timeframe.

        This reflects whatever has been registered via register_indicator()
        (typically from _register_indicators during backtest initialization).
        It does NOT guarantee that historical initialization has run; combine
        with has_initialized_history() if that distinction matters.
        """
        key = f"{symbol}:{timeframe}"
        if key not in self.indicators:
            return set()
        return set(self.indicators[key].keys())
    
    # ========================================================================
    # INITIALIZATION METHODS (for BacktestEngine)
    # ========================================================================
    
    def initialize(self, strategy: Any, backtest_date: Any, strategies_agg: Dict[str, Any] = None):
        """
        Initialize all data components for BACKTESTING.
        
        For live trading, use initialize_for_live() instead.
        
        Args:
            strategy: Strategy object with timeframes, indicators, symbols (legacy)
            backtest_date: Date to run backtest on
            strategies_agg: Optional aggregated metadata from multiple strategies (new multi-strategy path)
        """
        logger.info("🔧 Initializing DataManager for backtest...")
        
        # Store backtest date for option loader
        self.backtest_date = backtest_date
        
        # 1. Initialize symbol cache
        self._initialize_symbol_cache()
        
        # 2. Initialize ClickHouse
        self._initialize_clickhouse()
        
        # 3. Initialize option loader and pattern resolver
        self._initialize_option_components()
        
        # 4. Setup candle builders
        if strategies_agg:
            # New multi-strategy path: parse "SYMBOL:TF" format
            timeframes_set = set()
            for symbol_tf in strategies_agg.get('timeframes', []):
                # Extract TF from "NIFTY:1m" -> "1m"
                if ':' in symbol_tf:
                    tf = symbol_tf.split(':')[1]
                    timeframes_set.add(tf)
            timeframes = list(timeframes_set)
            logger.info(f"   Using aggregated timeframes: {timeframes}")
        else:
            # Legacy single-strategy path
            timeframes = strategy.get_timeframes()
        
        self._setup_candle_builders(timeframes)
        
        # 5. Register indicators
        if strategies_agg:
            self._register_indicators_from_agg(strategies_agg)
        else:
            self._register_indicators(strategy)
        
        # 6. Load historical candles
        if strategies_agg:
            self._load_historical_candles_from_agg(strategies_agg, backtest_date)
        else:
            self._load_historical_candles(strategy, backtest_date)
        
        logger.info("✅ DataManager initialized")
    
    def initialize_for_live(
        self, 
        strategies_agg: Dict[str, Any],
        websocket_client: Any = None,
        broker_adapter: Any = None
    ):
        """
        Initialize all data components for LIVE TRADING.
        
        Key differences from backtesting:
        - No ClickHouse (uses WebSocket for real-time data)
        - No historical candle loading (uses yfinance catchup or waits for live data)
        - Uses LiveOptionLoader instead of LazyOptionLoader
        - Subscribes to live WebSocket feeds
        
        Args:
            strategies_agg: Aggregated metadata from multiple strategies
            websocket_client: WebSocket client for live data (optional)
            broker_adapter: Broker adapter for live trading (optional)
        """
        logger.info("🔧 Initializing DataManager for LIVE trading...")
        
        # 1. Initialize symbol cache (same as backtest)
        self._initialize_symbol_cache()
        
        # 2. Store references for live trading
        self.websocket_client = websocket_client
        self.broker_adapter = broker_adapter
        
        # 3. Initialize option components for live (uses WebSocket, not ClickHouse)
        self._initialize_live_option_components()
        
        # 4. Setup candle builders (same as backtest)
        timeframes_set = set()
        for symbol_tf in strategies_agg.get('timeframes', []):
            if ':' in symbol_tf:
                tf = symbol_tf.split(':')[1]
                timeframes_set.add(tf)
        timeframes = list(timeframes_set)
        self._setup_candle_builders(timeframes)
        
        # 5. Register indicators (same as backtest)
        self._register_indicators_from_agg(strategies_agg)
        
        # 6. Load today's intraday data (catchup) using yfinance
        # This gives us initial 20 candles for each timeframe
        self._load_intraday_catchup(strategies_agg)
        
        # 7. Subscribe to live WebSocket feeds (if client provided)
        if websocket_client:
            self._subscribe_to_live_feeds(strategies_agg)
        
        logger.info("✅ DataManager initialized for live trading")
    
    def _initialize_live_option_components(self):
        """Initialize live option loader and pattern resolver."""
        logger.info("   Initializing live option components...")
        
        try:
            from src.core.option_pattern_resolver import OptionPatternResolver
            
            # Initialize pattern resolver (same as backtest)
            self.pattern_resolver = OptionPatternResolver()
            
            # For live: Option data comes from WebSocket, not pre-loaded
            # LiveOptionLoader subscribes to option contracts on-demand
            # We'll initialize it when first needed (lazy initialization)
            self.option_loader = None  # Will be created on first load_option_contract() call
            
            logger.info("   ✅ Live option components initialized")
        except Exception as e:
            logger.warning(f"   ⚠️  Option components initialization failed: {e}")
            self.option_loader = None
            self.pattern_resolver = None
    
    def _load_intraday_catchup(self, strategies_agg: Dict[str, Any]):
        """
        Load today's intraday data using yfinance for catchup.
        Gives us initial candles before live WebSocket data starts flowing.
        """
        logger.info("   Loading intraday catchup data (yfinance)...")
        
        try:
            from src.utils.yfinance_catchup import YFinanceCatchup
            from datetime import datetime
            
            # Parse symbols from timeframes
            symbols = set()
            for symbol_tf in strategies_agg.get('timeframes', []):
                if ':' in symbol_tf:
                    symbol = symbol_tf.split(':')[0]
                    symbols.add(symbol)
            
            # Load today's data for each symbol
            catchup = YFinanceCatchup()
            for symbol in symbols:
                candles_dict = catchup.fetch_today_data(symbol)
                
                # Initialize indicators with this data for each timeframe
                for timeframe, candles_df in candles_dict.items():
                    if not candles_df.empty:
                        self.initialize_from_historical_data(symbol, timeframe, candles_df)
                        logger.info(f"   ✅ {symbol}:{timeframe} - Loaded {len(candles_df)} catchup candles")
            
            logger.info("   ✅ Intraday catchup complete")
        except Exception as e:
            logger.warning(f"   ⚠️  Catchup failed (will build from live ticks): {e}")
    
    def _subscribe_to_live_feeds(self, strategies_agg: Dict[str, Any]):
        """Subscribe to live WebSocket feeds for all required symbols."""
        logger.info("   Subscribing to live WebSocket feeds...")
        
        if not self.websocket_client:
            logger.warning("   ⚠️  No WebSocket client provided, skipping subscriptions")
            return
        
        # Parse symbols to subscribe
        symbols_to_subscribe = set()
        for symbol_tf in strategies_agg.get('timeframes', []):
            if ':' in symbol_tf:
                symbol = symbol_tf.split(':')[0]
                symbols_to_subscribe.add(symbol)
        
        # Subscribe to each symbol
        for symbol in symbols_to_subscribe:
            try:
                self.websocket_client.subscribe(symbol)
                logger.info(f"   ✅ Subscribed to {symbol}")
            except Exception as e:
                logger.error(f"   ❌ Failed to subscribe to {symbol}: {e}")
        
        logger.info(f"   ✅ Subscribed to {len(symbols_to_subscribe)} symbols")
    
    def _initialize_symbol_cache(self):
        """Initialize symbol cache for symbol mapping."""
        logger.info("   Initializing symbol cache...")
        
        try:
            from src.backtesting.initialize_symbol_cache import initialize_symbol_cache
            initialize_symbol_cache(async_load=False)
            logger.info("   ✅ Symbol cache loaded")
        except Exception as e:
            import traceback
            logger.error(f"   ❌ CRITICAL: Symbol cache loading failed: {e}")
            logger.error(f"   Full traceback:\n{traceback.format_exc()}")
            # Re-raise - symbol cache is critical for trading
            raise RuntimeError(f"Symbol cache initialization failed: {e}") from e
    
    def _initialize_clickhouse(self):
        """Initialize ClickHouse client for historical data."""
        logger.info("   Initializing ClickHouse...")
        
        import clickhouse_connect
        from src.config.clickhouse_config import ClickHouseConfig
        
        self.clickhouse_client = clickhouse_connect.get_client(
            host=ClickHouseConfig.HOST,
            user=ClickHouseConfig.USER,
            password=ClickHouseConfig.PASSWORD,
            secure=ClickHouseConfig.SECURE,
            database=ClickHouseConfig.DATABASE
        )
        
        logger.info("   ✅ ClickHouse client initialized")
    
    def _initialize_option_components(self):
        """Initialize lazy option loader and pattern resolver."""
        logger.info("   Initializing option components...")
        
        try:
            from src.backtesting.lazy_option_loader import LazyOptionLoader
            from src.core.option_pattern_resolver import OptionPatternResolver
            
            # Initialize lazy option loader
            self.option_loader = LazyOptionLoader(
                clickhouse_client=self.clickhouse_client,
                backtest_date=self.backtest_date
            )
            
            # Initialize pattern resolver
            self.pattern_resolver = OptionPatternResolver()
            
            logger.info("   ✅ Option components initialized")
        except Exception as e:
            logger.warning(f"   ⚠️  Option components initialization failed: {e}")
            # Non-critical - strategies without options will work fine
            self.option_loader = None
            self.pattern_resolver = None
    
    def load_option_contract(self, contract_key: str, current_timestamp: Any) -> Optional[float]:
        """
        Load ALL option ticks for the day and buffer them for tick-by-tick processing.
        
        This simulates live trading websocket behavior:
        - In live: Subscribe to option → Get ticks from next tick onwards
        - In backtest: Load all ticks → Process from current_timestamp onwards
        
        Workflow:
        1. Entry node resolves: NIFTY:W0:ATM:CE → NIFTY:2024-10-03:OPT:25900:CE
        2. Entry node calls: data_manager.load_option_contract(contract_key, timestamp)
        3. Load ALL option ticks for the day from ClickHouse
        4. Store in buffer starting from current_timestamp
        5. Return first LTP for immediate order placement
        6. Subsequent ticks processed in main loop via get_option_ticks_for_timestamp()
        
        Args:
            contract_key: Universal format "NIFTY:2024-10-03:OPT:25900:CE"
            current_timestamp: Timestamp to start from (datetime object)
        
        Returns:
            First option LTP at/after current_timestamp, or None if unavailable
        """
        from collections import deque
        from datetime import datetime
        
        # Check if already loaded
        if contract_key in self.option_tick_buffers:
            print(f"   ℹ️  Option contract already loaded: {contract_key}")
            return self.ltp.get(contract_key)
        
        if not self.clickhouse_client:
            error_msg = f"⚠️  ClickHouse client not initialized, cannot load {contract_key}"
            logger.warning(error_msg)
            print(f"\n{error_msg}")
            print(f"   System will use fallback pricing (underlying spot price)")
            return None
        
        try:
            # Convert universal format to ClickHouse format
            # NIFTY:2024-10-03:OPT:25900:CE → NIFTY03OCT2425900CE
            from src.symbol_mapping.clickhouse_ticker_converter import from_universal
            ch_symbol = from_universal(contract_key)
            
            # Add .NFO suffix as ClickHouse stores tickers with exchange suffix
            ch_symbol_with_nfo = f"{ch_symbol}.NFO"
            
            # Ensure current_timestamp is datetime
            if isinstance(current_timestamp, str):
                current_timestamp = datetime.fromisoformat(current_timestamp)
            
            # Get trading day
            trading_day = current_timestamp.strftime('%Y-%m-%d')
            timestamp_str = current_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"\n🔄 Loading option ticks from ClickHouse...")
            print(f"   Contract: {contract_key}")
            print(f"   ClickHouse symbol: {ch_symbol}")
            print(f"   With NFO suffix: {ch_symbol_with_nfo}")
            print(f"   From: {timestamp_str}")
            
            # Load ALL option ticks from current_timestamp onwards
            # Note: ticker column includes .NFO suffix
            query = f"""
                SELECT 
                    ticker,
                    timestamp,
                    ltp,
                    ltq,
                    oi
                FROM nse_ticks_options
                WHERE trading_day = '{trading_day}'
                  AND ticker = '{ch_symbol_with_nfo}'
                  AND timestamp >= '{timestamp_str}'
                ORDER BY timestamp ASC
            """
            
            result = self.clickhouse_client.query(query)
            
            # Convert to tick dictionaries with universal symbol format
            option_ticks = []
            for row in result.result_rows:
                tick = {
                    'symbol': contract_key,  # Use universal format
                    'timestamp': row[1],
                    'ltp': row[2],
                    'ltq': row[3],
                    'oi': row[4],
                }
                option_ticks.append(tick)
            
            if not option_ticks:
                error_msg = f"⚠️  No option ticks found for {contract_key} from {timestamp_str}"
                logger.warning(error_msg)
                print(f"\n{error_msg}")
                print(f"   Possible reasons:")
                print(f"   1. Option data not loaded in ClickHouse for this date")
                print(f"   2. Contract not traded after {timestamp_str}")
                print(f"   3. Wrong symbol format or data quality issue")
                print(f"   System will use fallback pricing (underlying spot price)")
                return None
            
            # Store in buffer for tick-by-tick processing
            self.option_tick_buffers[contract_key] = {
                'ticks': deque(option_ticks),
                'current_index': 0
            }
            
            # Track loaded contract
            self.loaded_option_contracts.add(contract_key)
            
            # Get first LTP for immediate order placement
            first_tick = option_ticks[0]
            first_ltp = first_tick['ltp']
            
            # Update LTP stores with first tick
            self.ltp[contract_key] = first_ltp
            self.ltp_store[contract_key] = {
                'ltp': first_ltp,
                'timestamp': first_tick['timestamp'],
                'volume': 0,
                'oi': first_tick['oi']
            }
            
            print(f"   ✅ Loaded {len(option_ticks):,} option ticks")
            print(f"   First LTP: ₹{first_ltp:.2f} at {first_tick['timestamp']}")
            logger.info(f"✅ Loaded option contract: {contract_key} - {len(option_ticks):,} ticks from {timestamp_str}")
            
            return first_ltp
                
        except Exception as e:
            error_msg = f"❌ Error loading option contract {contract_key}: {e}"
            logger.error(error_msg)
            print(f"\n{error_msg}")
            print(f"   Exception type: {type(e).__name__}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            print(f"   System will use fallback pricing (underlying spot price)")
            return None
    
    def get_option_ticks_for_timestamp(self, current_timestamp: Any) -> List[Dict[str, Any]]:
        """
        Get all option ticks that match the current timestamp.
        
        This is called in the main tick processing loop to get option ticks
        that should be processed alongside the spot tick at current_timestamp.
        
        Args:
            current_timestamp: Current tick timestamp (datetime object)
        
        Returns:
            List of option ticks at current_timestamp (can be empty)
        """
        from datetime import datetime
        
        option_ticks = []
        
        # Ensure timestamp is datetime
        if isinstance(current_timestamp, str):
            current_timestamp = datetime.fromisoformat(current_timestamp)
        
        # Check each loaded option contract
        for contract_key, buffer_data in self.option_tick_buffers.items():
            ticks_deque = buffer_data['ticks']
            
            # Peek at ticks without removing them
            # Get all ticks at current_timestamp
            while ticks_deque:
                # Peek at first tick
                next_tick = ticks_deque[0]
                tick_timestamp = next_tick['timestamp']
                
                # Ensure tick_timestamp is datetime
                if isinstance(tick_timestamp, str):
                    tick_timestamp = datetime.fromisoformat(tick_timestamp)
                
                if tick_timestamp < current_timestamp:
                    # This tick is in the past, remove it (should not happen if loaded correctly)
                    ticks_deque.popleft()
                elif tick_timestamp == current_timestamp:
                    # This tick matches current timestamp, add to results and remove
                    option_ticks.append(ticks_deque.popleft())
                else:
                    # Future tick, stop checking this contract
                    break
        
        return option_ticks
    
    def _setup_candle_builders(self, timeframes: List[str]):
        """
        Setup candle builders for all timeframes.
        
        Args:
            timeframes: List of timeframes (e.g., ['1m', '5m'])
        """
        logger.info(f"   Setting up candle builders for {timeframes}...")
        
        from src.backtesting.candle_builder import CandleBuilder
        
        for timeframe in timeframes:
            self.candle_builders[timeframe] = CandleBuilder(timeframe=timeframe)
            print(f"[DEBUG] Created candle builder for {timeframe}")
        
        logger.info(f"   ✅ {len(timeframes)} candle builders created")
        print(f"[DEBUG] Total candle builders: {len(self.candle_builders)}, timeframes: {list(self.candle_builders.keys())}")
    
    def _register_indicators(self, strategy: Any):
        """
        Register all indicators from strategy using ta_hybrid instances.
        
        Args:
            strategy: StrategyMetadata object
        """
        import ta_hybrid as ta
        
        registered_count = 0
        total_configs = len(strategy.instrument_configs)
        
        logger.info(f"   Registering indicators from {total_configs} instrument configs...")
        
        # Process each instrument config (symbol-timeframe-indicators binding)
        for inst_config in strategy.instrument_configs.values():
            symbol = inst_config.symbol
            timeframe = inst_config.timeframe
            indicators = inst_config.indicators
            
            logger.info(f"      {inst_config.get_key()} - {len(indicators)} indicators")
            
            for indicator_metadata in indicators:
                try:
                    # Get indicator class from ta_hybrid registry
                    indicator_name = indicator_metadata.name.lower()
                    indicator_class = ta._INDICATOR_REGISTRY.get(indicator_name)
                    
                    if indicator_class is None:
                        logger.warning(f"⚠️  Indicator '{indicator_name}' not found in ta_hybrid")
                        continue
                    
                    # Create ta_hybrid indicator instance
                    indicator = indicator_class(**indicator_metadata.params)
                    
                    # Register with data manager
                    indicator_key = self.register_indicator(
                        symbol=symbol,
                        timeframe=timeframe,
                        indicator=indicator
                    )
                    
                    if indicator_key:
                        registered_count += 1
                        logger.info(f"         ✅ {indicator_metadata.key} -> {indicator_class.__name__}")
                
                except Exception as e:
                    import traceback
                    logger.error(f"❌ CRITICAL: Failed to create {indicator_metadata.name}: {e}")
                    logger.error(f"   Symbol: {symbol}, Timeframe: {timeframe}")
                    logger.error(f"   Key: {indicator_metadata.key}")
                    logger.error(f"   Params: {indicator_metadata.params}")
                    logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                    # Re-raise - indicator creation failure is critical
                    raise RuntimeError(f"Indicator creation failed for {indicator_metadata.name}: {e}") from e
        
        if registered_count > 0:
            logger.info(f"   ✅ Registered {registered_count} ta_hybrid indicator instances")
        else:
            logger.info(f"   ℹ️  No indicators found in strategy config")
    
    def _load_historical_candles(self, strategy: Any, backtest_date: Any):
        """
        Load historical candles from ClickHouse.
        
        Args:
            strategy: StrategyMetadata object
            backtest_date: Date to run backtest on
        """
        logger.info("   Loading historical candles from ClickHouse...")
        
        for timeframe in strategy.get_timeframes():
            query = f"""
                SELECT 
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    symbol,
                    timeframe
                FROM nse_ohlcv_indices
                WHERE symbol IN ({','.join(f"'{s}'" for s in strategy.get_symbols())})
                  AND timeframe = '{timeframe}'
                  AND timestamp < '{backtest_date.strftime('%Y-%m-%d')} 09:15:00'
                ORDER BY timestamp DESC
                LIMIT 500
            """
            
            # Direct to DataFrame (10-15x faster than manual iteration)
            df = self.clickhouse_client.query_df(query)
            
            if not df.empty:
                # Reverse to chronological order (query was DESC to get most recent)
                df = df.sort_values('timestamp', ascending=True)
                
                # Debug: Show date range of historical data
                logger.info(f"   📅 Historical data range: {df['timestamp'].min()} to {df['timestamp'].max()}")
                
                # Load into DataManager for each symbol
                for symbol in strategy.get_symbols():
                    symbol_df = df[df['symbol'] == symbol]
                    if not symbol_df.empty:
                        self.initialize_from_historical_data(symbol, timeframe, symbol_df)
                        logger.info(f"   ✅ {timeframe}: Loaded {len(symbol_df)} candles for {symbol}")
            else:
                logger.info(f"   ℹ️  {timeframe}: No historical candles (will build from ticks)")
    
    def _register_indicators_from_agg(self, strategies_agg: Dict[str, Any]):
        """
        Register all indicators from aggregated strategy metadata.
        
        Args:
            strategies_agg: Aggregated metadata with indicators per symbol/timeframe
        """
        import ta_hybrid as ta
        
        registered_count = 0
        indicators_dict = strategies_agg.get('indicators', {})
        
        logger.info(f"   Registering indicators from aggregated metadata...")
        
        # Process each symbol
        for symbol, timeframes_dict in indicators_dict.items():
            for timeframe, indicator_list in timeframes_dict.items():
                logger.info(f"      {symbol}:{timeframe} - {len(indicator_list)} indicators")
                
                for ind_meta in indicator_list:
                    try:
                        # Get indicator class from ta_hybrid registry
                        indicator_name = ind_meta.get('name', '').lower()
                        indicator_class = ta._INDICATOR_REGISTRY.get(indicator_name)
                        
                        if indicator_class is None:
                            logger.warning(f"⚠️  Indicator '{indicator_name}' not found in ta_hybrid")
                            continue
                        
                        # Create ta_hybrid indicator instance
                        params = ind_meta.get('params', {})
                        indicator = indicator_class(**params)
                        
                        # Register with data manager
                        indicator_key = self.register_indicator(
                            symbol=symbol,
                            timeframe=timeframe,
                            indicator=indicator
                        )
                        
                        if indicator_key:
                            registered_count += 1
                            logger.info(f"         ✅ {indicator_name} -> {indicator_class.__name__}")
                    
                    except Exception as e:
                        import traceback
                        logger.error(f"❌ CRITICAL: Failed to create {ind_meta.get('name')}: {e}")
                        logger.error(f"   Symbol: {symbol}, Timeframe: {timeframe}")
                        logger.error(f"   Params: {ind_meta.get('params')}")
                        logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                        raise RuntimeError(f"Indicator creation failed: {e}") from e
        
        if registered_count > 0:
            logger.info(f"   ✅ Registered {registered_count} ta_hybrid indicator instances")
        else:
            logger.info(f"   ℹ️  No indicators found in aggregated metadata")
    
    def _load_historical_candles_from_agg(self, strategies_agg: Dict[str, Any], backtest_date: Any):
        """
        Load historical candles using aggregated strategy metadata.
        Uses SharedDataCache if available to avoid duplicate loading across strategies.
        
        Args:
            strategies_agg: Aggregated metadata with timeframes list
            backtest_date: Date to run backtest on
        """
        logger.info("   Loading historical candles from ClickHouse (aggregated)...")
        
        # Parse timeframes to get unique symbol-timeframe pairs
        symbol_tf_pairs = {}  # {symbol: set(timeframes)}
        
        for symbol_tf in strategies_agg.get('timeframes', []):
            if ':' in symbol_tf:
                symbol, tf = symbol_tf.split(':', 1)
                if symbol not in symbol_tf_pairs:
                    symbol_tf_pairs[symbol] = set()
                symbol_tf_pairs[symbol].add(tf)
        
        # Load candles for each symbol-timeframe combination
        for symbol, timeframes in symbol_tf_pairs.items():
            for timeframe in timeframes:
                # Define loader function for SharedDataCache
                def load_candles(sym: str, tf: str) -> pd.DataFrame:
                    """Load candles from ClickHouse."""
                    query = f"""
                        SELECT 
                            timestamp,
                            open,
                            high,
                            low,
                            close,
                            volume,
                            symbol,
                            timeframe
                        FROM nse_ohlcv_indices
                        WHERE symbol = '{sym}'
                          AND timeframe = '{tf}'
                          AND timestamp < '{backtest_date.strftime('%Y-%m-%d')} 09:15:00'
                        ORDER BY timestamp DESC
                        LIMIT 500
                    """
                    
                    # Direct to DataFrame (10-15x faster than manual iteration)
                    df = self.clickhouse_client.query_df(query)
                    
                    if not df.empty:
                        # Reverse to chronological order (query was DESC to get most recent)
                        df = df.sort_values('timestamp', ascending=True)
                        logger.info(f"   📅 {sym}:{tf} - {len(df)} candles: {df['timestamp'].min()} to {df['timestamp'].max()}")
                    
                    return df
                
                # Use shared cache if available, otherwise load directly
                if self.shared_cache:
                    df = self.shared_cache.get_or_load_candles(symbol, timeframe, load_candles)
                else:
                    df = load_candles(symbol, timeframe)
                
                if not df.empty:
                    # Initialize indicators with this data (and store last 20 candles)
                    self.initialize_from_historical_data(symbol, timeframe, df)
                    logger.info(f"   ✅ {symbol}:{timeframe} - Loaded {len(df)} candles")
                else:
                    logger.info(f"   ℹ️  {symbol}:{timeframe} - No historical candles (will build from ticks)")
    
    def load_ticks(self, date: Any, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Load raw ticks from ClickHouse for backtesting.
        
        Args:
            date: Date to load ticks for
            symbols: List of symbols to load
        
        Returns:
            List of tick dictionaries
        """
        trading_day = date.strftime('%Y-%m-%d')
        logger.info(f"📥 Loading raw ticks from ClickHouse for {trading_day}...")

        symbol_list = ','.join(f"'{s}'" for s in symbols)

        query = f"""
            SELECT 
                symbol,
                timestamp,
                ltp,
                ltq,
                oi
            FROM nse_ticks_indices
            WHERE trading_day = '{trading_day}'
              AND timestamp >= '{trading_day} 09:15:00'
              AND timestamp <= '{trading_day} 15:30:00'
              AND symbol IN ({symbol_list})
            ORDER BY timestamp ASC
        """

        result = self.clickhouse_client.query(query)

        ticks: List[Dict[str, Any]] = []
        for row in result.result_rows:
            tick = {
                'symbol': row[0],
                'timestamp': row[1],
                'ltp': row[2],
                'ltq': row[3],
                'oi': row[4],
            }
            ticks.append(tick)

        logger.info(f"✅ Loaded {len(ticks):,} raw ticks")

        return ticks
    
    def load_ticks_aggregated(self, date: Any, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Load AGGREGATED ticks (OHLC per second) from ClickHouse.
        
        This is MUCH more efficient than loading raw ticks and aggregating in Python:
        - 10x less data transfer (1 row/second vs 10+ rows/second)
        - 10x less memory usage
        - No Python aggregation overhead
        - ClickHouse does the aggregation at source
        
        Args:
            date: Date to load ticks for
            symbols: List of symbols to load
        
        Returns:
            List of aggregated tick dictionaries (OHLC format)
        """
        trading_day = date.strftime('%Y-%m-%d')
        logger.info(f"📥 Loading aggregated ticks (OHLC/second) from ClickHouse for {trading_day}...")
        logger.info(f"   Symbols: {symbols}")

        symbol_list = ','.join(f"'{s}'" for s in symbols)

        # Aggregate in ClickHouse - MUCH faster than Python!
        # Use groupArray to collect all ltps, then pick first/last for open/close
        # Truncate timestamp to seconds manually (compatible with all ClickHouse versions)
        query = f"""
            SELECT 
                symbol,
                toDateTime(toInt64(timestamp)) as second,
                groupArray(ltp)[1] as open,             -- First LTP in second
                max(ltp) as high,                       -- Highest LTP in second
                min(ltp) as low,                        -- Lowest LTP in second
                groupArray(ltp)[-1] as close,           -- Last LTP in second
                sum(ltq) as volume,                     -- Sum of volumes
                groupArray(oi)[-1] as oi               -- Last OI in second
            FROM nse_ticks_indices
            WHERE trading_day = '{trading_day}'
              AND timestamp >= '{trading_day} 09:15:00'
              AND timestamp <= '{trading_day} 15:30:00'
              AND symbol IN ({symbol_list})
            GROUP BY symbol, toDateTime(toInt64(timestamp))
            ORDER BY second ASC
        """
        
        logger.debug(f"   Query: {query}")

        result = self.clickhouse_client.query(query)

        ticks: List[Dict[str, Any]] = []
        for row in result.result_rows:
            # close and ltp are the same value (last traded price)
            close_ltp = float(row[5]) if row[5] else None
            tick = {
                'symbol': row[0],
                'timestamp': row[1],
                'open': float(row[2]) if row[2] else None,
                'high': float(row[3]) if row[3] else None,
                'low': float(row[4]) if row[4] else None,
                'close': close_ltp,
                'ltp': close_ltp,  # Same as close
                'volume': int(row[6]) if row[6] else 0,
                'oi': int(row[7]) if row[7] else 0,
            }
            ticks.append(tick)

        logger.info(f"✅ Loaded {len(ticks):,} aggregated ticks (OHLC/second)")

        return ticks

    def load_option_ticks(self, date: Any, tickers: List[str]) -> List[Dict[str, Any]]:
        """Load raw option ticks from ClickHouse.

        Mirrors DynamicOptionSubscriber.load_option_ticks but scoped to a
        provided ticker list, and returns rows ordered by timestamp so that
        candle high/low can be derived from all underlying ticks.

        Args:
            date: Date to load ticks for
            tickers: List of option ticker symbols in ClickHouse format

        Returns:
            List of option tick dictionaries
        """
        if not tickers:
            logger.info("ℹ️  load_option_ticks called with empty ticker list; returning []")
            return []

        trading_day = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
        logger.info(f"📥 Loading raw option ticks from ClickHouse for {trading_day}...")

        ticker_list = "', '".join(tickers)

        query = f"""
            SELECT 
                ticker,
                timestamp,
                ltp
            FROM nse_ticks_options
            WHERE trading_day = '{trading_day}'
              AND ticker IN ('{ticker_list}')
            ORDER BY timestamp ASC
        """

        result = self.clickhouse_client.query(query)

        ticks: List[Dict[str, Any]] = []
        for row in result.result_rows:
            tick = {
                'symbol': row[0],
                'timestamp': row[1],
                'ltp': row[2],
                'volume': 0,  # Not available in nse_ticks_options
                'oi': 0,      # Not available in nse_ticks_options
            }
            ticks.append(tick)

        logger.info(f"✅ Loaded {len(ticks):,} raw option ticks")

        return ticks
    
    def load_option_ticks_aggregated(
        self, 
        date: Any, 
        tickers: List[str], 
        from_timestamp: Any = None
    ) -> List[Dict[str, Any]]:
        """
        Load AGGREGATED option ticks (one per second per contract) from ClickHouse.
        
        For options we only track LTP changes, not candles, so we use argMax to get
        the last LTP value per second. This is MUCH more efficient than loading
        every intra-second tick:
        - 10x less data transfer (1 row/second vs 10+ rows/second)
        - No Python grouping/looping needed
        - ClickHouse does the aggregation (C++ optimized)
        
        Args:
            date: Date to load ticks for
            tickers: List of option ticker symbols in ClickHouse format
            from_timestamp: Optional timestamp to load from (for dynamic subscription)
        
        Returns:
            List of aggregated option tick dictionaries (one per symbol per second)
        """
        if not tickers:
            logger.info("ℹ️  load_option_ticks_aggregated called with empty ticker list; returning []")
            return []

        trading_day = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
        ticker_list = "', '".join(tickers)
        
        # Build timestamp filter
        timestamp_filter = ""
        if from_timestamp:
            if hasattr(from_timestamp, 'strftime'):
                from_ts_str = from_timestamp.strftime('%Y-%m-%d %H:%M:%S')
            else:
                from_ts_str = str(from_timestamp)
            timestamp_filter = f"AND timestamp >= '{from_ts_str}'"
            logger.info(f"📥 Loading aggregated option ticks from {from_ts_str} for {len(tickers)} contracts...")
        else:
            logger.info(f"📥 Loading aggregated option ticks for {trading_day} ({len(tickers)} contracts)...")

        # Aggregate in ClickHouse - get last LTP per second per contract
        # Use groupArray to collect all ltps in a second, then pick the last one
        # Note: ClickHouse tickers have .NFO extension (e.g., NIFTY03OCT2425950CE.NFO)
        # We generate tickers without extension, so use startsWith for matching
        
        # Build ticker filter using OR conditions with startsWith
        ticker_conditions = " OR ".join([f"startsWith(ticker, '{t}')" for t in tickers])
        
        query = f"""
            SELECT 
                ticker,
                toDateTime(toInt64(timestamp)) as second,
                groupArray(ltp)[-1] as ltp
            FROM nse_ticks_options
            WHERE trading_day = '{trading_day}'
              AND ({ticker_conditions})
              {timestamp_filter}
            GROUP BY ticker, toDateTime(toInt64(timestamp))
            ORDER BY second ASC
        """

        result = self.clickhouse_client.query(query)

        ticks: List[Dict[str, Any]] = []
        for row in result.result_rows:
            # Strip .NFO extension from ticker to maintain consistent format
            ticker = row[0].replace('.NFO', '') if row[0] else row[0]
            
            tick = {
                'symbol': ticker,
                'timestamp': row[1],
                'ltp': float(row[2]) if row[2] else None,
                'volume': 0,  # Not tracked for options
                'oi': 0,      # Not tracked for options
            }
            ticks.append(tick)

        logger.info(f"✅ Loaded {len(ticks):,} aggregated option ticks for {len(tickers)} contracts")
        if ticks:
            logger.info(f"   Sample tickers: {list(set([t['symbol'] for t in ticks[:10]]))}")

        return ticks
