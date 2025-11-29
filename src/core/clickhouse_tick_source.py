"""
ClickHouse Tick Source
======================

Tick data source for backtesting - reads historical ticks from ClickHouse.

This source:
1. Loads all ticks for a given date and symbols
2. Processes them sequentially (one at a time)
3. Completes when all ticks are processed

Author: UniTrader Team
Created: 2024-11-12
"""

import logging
from typing import Callable, Dict, Any, List, Optional, Any as TypingAny
from datetime import datetime, date

from src.core.tick_data_source import TickDataSource
from src.symbol_mapping.clickhouse_format_adapter import ClickHouseFormatAdapter
from expiry_calculator import ExpiryCalculator
from src.backtesting.option_universe_resolver import build_option_universe_for_underlying

logger = logging.getLogger(__name__)

# Strike interval configuration for different underlyings
STRIKE_INTERVALS = {
    'NIFTY': 50,
    'BANKNIFTY': 100,
    'FINNIFTY': 50,
    'MIDCPNIFTY': 25,
    'SENSEX': 100,
    'BANKEX': 100,
}
DEFAULT_STRIKE_INTERVAL = 100  # Fallback for unknown symbols


class ClickHouseTickSource(TickDataSource):
    """
    Tick source for backtesting with dynamic option subscription.
    
    Simulates live websocket behavior:
    - Processes index ticks batch-by-batch (by second)
    - Discovers index symbols as they appear in batches
    - Dynamically resolves and loads option contracts
    - Only includes option ticks from discovery point forward
    - Never peeks at future data
    
    Characteristics:
    - Batch processing (per-second batches like websocket)
    - Dynamic option subscription (not pre-calculated)
    - Realistic live-like simulation
    - Memory efficient (streams batches)
    
    Usage:
        source = ClickHouseTickSource(
            clickhouse_client=client,
            backtest_date=datetime(2024, 10, 1),
            symbols=['NIFTY', 'BANKNIFTY'],
            cache_manager=cache_manager
        )
        
        source.start(callback=on_tick)
        # Batches processed sequentially with dynamic option loading
    """
    
    def __init__(
        self,
        clickhouse_client=None,
        backtest_date: datetime = None,
        symbols: List[str] = None,
        cache_manager=None
    ):
        """
        Initialize ClickHouse tick source.
        
        Args:
            clickhouse_client: ClickHouse client (optional, will be set by engine)
            backtest_date: Date to backtest
            symbols: List of symbols to load
            cache_manager: CacheManager for reading option patterns (optional)
        """
        self.clickhouse_client = clickhouse_client
        self.backtest_date = backtest_date.date() if backtest_date else None
        self.symbols = symbols or []
        self.cache_manager = cache_manager
        
        self.ticks: List[Dict] = []
        self.callback: Optional[Callable] = None
        self.running = False
        
        # Statistics
        self.ticks_received = 0
        self.errors = 0
        
        # Dynamic option subscription tracking
        self.discovered_indices: Dict[str, float] = {}  # symbol -> first_ltp
        self.subscribed_options: Dict[str, List[str]] = {}  # underlying -> [option_symbols]
        self.option_ticks_cache: Dict[str, Dict[datetime, List[Dict]]] = {}  # option_symbol -> {second -> [ticks]}
        self.current_atm_strike: Dict[str, float] = {}  # symbol -> current_atm_strike (for rebalancing)
        
        # Pattern-to-symbol mapping: {pattern_str: {atm_strike: resolved_symbol}}
        # This ensures we reuse same symbols when ATM oscillates back
        self.pattern_symbol_cache: Dict[str, Dict[float, str]] = {}

        # Symbol mapper: ClickHouse format → unified format
        # This ensures the rest of the engine sees only unified symbols
        self.symbol_mapper = ClickHouseFormatAdapter()
        
        logger.info(f"📊 ClickHouseTickSource initialized for {backtest_date}")
    
    def start(self, callback: Callable[[TypingAny], None]):
        """
        Start processing ticks with dynamic option subscription.
        
        Simulates live websocket behavior:
        1. Load index ticks in batches (by second)
        2. When a new index symbol appears, resolve and load its options
        3. Only include option ticks from the discovery point forward
        4. Never peek at future data
        
        Args:
            callback: Function to call for each tick batch
        """
        if self.running:
            logger.warning("⚠️ ClickHouseTickSource already running")
            return
        
        self.running = True
        self.callback = callback
        
        logger.info(f"🚀 Starting ClickHouseTickSource with dynamic option subscription...")
        
        # Process ticks batch-by-batch with dynamic option loading
        self._process_ticks_dynamically()
        
        # Mark as completed
        self.running = False
        
        logger.info(f"✅ ClickHouseTickSource completed: {self.ticks_received:,} ticks processed")
    
    def _load_index_ticks(self) -> List[Dict[str, Any]]:
        """
        Load AGGREGATED index ticks from ClickHouse.
        
        Uses ClickHouse aggregation (OHLC per second) instead of loading
        raw ticks and aggregating in Python. This is 10x more efficient!
        """
        try:
            logger.info(f"📥 Loading aggregated index ticks for {self.backtest_date}...")
            logger.info(f"   Date type: {type(self.backtest_date)}, Value: {self.backtest_date}")
            logger.info(f"   Symbols: {self.symbols}")
            
            from src.backtesting.data_manager import DataManager
            
            temp_dm = DataManager(cache=None, broker_name='clickhouse')
            temp_dm.clickhouse_client = self.clickhouse_client
            
            # Load AGGREGATED index ticks (OHLC per second from ClickHouse)
            # This is MUCH faster than load_ticks() + Python aggregation!
            index_ticks = temp_dm.load_ticks_aggregated(
                date=self.backtest_date,
                symbols=self.symbols
            )
            logger.info(f"✅ Loaded {len(index_ticks):,} aggregated index ticks (OHLC/second)")
            
            # DEBUG: If no aggregated ticks, try old method to compare
            if len(index_ticks) == 0:
                logger.warning("⚠️ No aggregated ticks loaded! Testing with raw ticks method...")
                raw_ticks = temp_dm.load_ticks(
                    date=self.backtest_date,
                    symbols=self.symbols
                )
                logger.info(f"   Raw ticks method returned: {len(raw_ticks):,} ticks")
                if len(raw_ticks) > 0:
                    logger.error("❌ ISSUE CONFIRMED: Raw method works but aggregated doesn't!")
                    logger.error("   This suggests the aggregation query has an issue")
                else:
                    logger.info("   Both methods return 0 rows - likely no data for this date/symbols")
            
            return list(index_ticks)
        except Exception as e:
            logger.error(f"❌ Failed to load index ticks: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _process_ticks_dynamically(self):
        """
        Process ticks batch-by-batch with dynamic option subscription.
        
        Simulates live websocket behavior:
        - Process index ticks in chronological order
        - When new index symbol discovered, resolve and load its options
        - Only include option ticks from discovery timestamp forward
        """
        print(f"\n🚀 DEBUG: Starting _process_ticks_dynamically() for date {self.backtest_date}")
        
        # Load index ticks (ALREADY aggregated per second from ClickHouse)
        index_ticks = self._load_index_ticks()
        if not index_ticks:
            logger.warning("⚠️ No index ticks loaded")
            return
        
        # Group ticks by timestamp using defaultdict (faster than groupby)
        # Ticks are already sorted by timestamp from ClickHouse query
        # Multiple symbols can share same timestamp, so group into lists
        from collections import defaultdict
        index_batches: Dict[datetime, List[Dict]] = defaultdict(list)
        for tick in index_ticks:
            ts = tick.get('timestamp')
            if ts:
                index_batches[ts].append(tick)
        
        logger.info(f"📦 Organized {len(index_ticks):,} index ticks into {len(index_batches):,} second-batches")
        
        # Setup for option resolution
        from src.backtesting.data_manager import DataManager
        temp_dm = DataManager(cache=None, broker_name='clickhouse')
        temp_dm.clickhouse_client = self.clickhouse_client
        
        calc = ExpiryCalculator(clickhouse_client=self.clickhouse_client)
        print(f"\n🔍 DEBUG: Preloading expiries for {self.symbols} on {self.backtest_date}...")
        logger.info(f"🔍 Preloading expiries for {self.symbols} on {self.backtest_date}...")
        
        # DEBUG: Check what expiry data exists in ClickHouse
        try:
            test_query = f"""
                SELECT DISTINCT expiry_date 
                FROM nse_options_metadata 
                WHERE underlying = 'NIFTY' 
                  AND expiry_date >= '{self.backtest_date}' 
                ORDER BY expiry_date 
                LIMIT 5
            """
            result = self.clickhouse_client.query(test_query)
            expiries_in_db = [row[0] for row in result.result_rows]
            print(f"   ✅ Available NIFTY expiries in ClickHouse: {expiries_in_db}")
            logger.info(f"   Available NIFTY expiries in ClickHouse (>= {self.backtest_date}): {expiries_in_db}")
        except Exception as e:
            print(f"   ❌ Could not query expiries: {e}")
            logger.error(f"   ❌ Could not query expiries from ClickHouse: {e}")
        
        calc.preload_expiries_for_symbols(self.symbols, self.backtest_date)
        
        # DEBUG: Check what expiries were loaded
        if hasattr(calc, '_expiry_cache'):
            logger.info(f"   Expiry cache after preload: {calc._expiry_cache}")
        if hasattr(calc, 'expiry_cache'):
            logger.info(f"   Expiry cache after preload: {calc.expiry_cache}")
        logger.info(f"✅ Expiry preload completed")
        
        # Get option patterns from cache
        patterns = {}
        
        if self.cache_manager:
            try:
                patterns = self.cache_manager.get_option_patterns() or {}
                if patterns:
                    logger.info(f"📋 Loaded {len(patterns)} option patterns from cache")
                else:
                    logger.warning("⚠️ No option patterns found in cache - backtesting index-only")
            except Exception as e:
                import traceback
                logger.error(f"❌ Failed to load option patterns: {e}")
                logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                logger.warning("   Continuing with index-only backtesting")
                patterns = {}
        
        # Generate ALL seconds in trading day (09:15:00 to 15:30:00)
        # This ensures we process every second chronologically, regardless of data availability
        from datetime import datetime as dt, timedelta
        
        # Convert date to datetime if needed
        if isinstance(self.backtest_date, dt):
            backtest_datetime = self.backtest_date
        else:
            backtest_datetime = dt.combine(self.backtest_date, dt.min.time())
        
        start_time = backtest_datetime.replace(hour=9, minute=15, second=0)
        end_time = backtest_datetime.replace(hour=15, minute=30, second=0)
        
        all_seconds = []
        current = start_time
        while current <= end_time:
            all_seconds.append(current)
            current += timedelta(seconds=1)
        
        logger.info(f"📅 Processing {len(all_seconds):,} seconds from {start_time.time()} to {end_time.time()}")
        
        # Process every second in chronological order
        batch_count = 0
        for second_key in all_seconds:
            if not self.running:
                break
            
            batch_count += 1
            # Get index batch for this second (may be empty)
            index_batch = index_batches.get(second_key, [])
            
            # Check for NEW index symbols OR strike changes in this batch
            for tick in index_batch:
                symbol = tick.get('symbol')
                ltp = tick.get('ltp')
                
                if not symbol or not ltp:
                    continue
                
                ltp = float(ltp)
                
                if symbol not in self.discovered_indices:
                    # NEW INDEX DISCOVERED!
                    self.discovered_indices[symbol] = ltp
                    logger.info(f"🔔 NEW INDEX: {symbol} @ {ltp} at {second_key}")
                    
                    # Resolve options for this symbol NOW
                    self._subscribe_options_for_index(
                        symbol=symbol,
                        spot_ltp=ltp,
                        from_timestamp=second_key,
                        patterns=patterns,
                        calc=calc,
                        temp_dm=temp_dm
                    )
                else:
                    # Check if ATM strike has shifted
                    self._check_and_rebalance_strikes(
                        symbol=symbol,
                        spot_ltp=ltp,
                        from_timestamp=second_key,
                        patterns=patterns,
                        calc=calc,
                        temp_dm=temp_dm
                    )
            
            # Index ticks are already aggregated (OHLC from ClickHouse)
            # No Python aggregation needed - use directly!
            aggregated_index_batch = index_batch  # Already OHLC format
            
            # Collect option ticks for THIS EXACT SECOND only
            # Keep ALL option ticks (no aggregation - we need all LTP updates)
            option_batch = []
            for opt_symbol, seconds_dict in self.option_ticks_cache.items():
                # Get ticks for this specific second
                if second_key in seconds_dict:
                    option_batch.extend(seconds_dict[second_key])
            
            # Combine aggregated index + all option ticks
            combined_batch = aggregated_index_batch + option_batch
            
            # Skip this second if no ticks at all
            # This handles gaps where neither index nor options have data
            if not combined_batch:
                logger.debug(f"  ⏭️  Skipping {second_key} - no ticks available")
                continue
            
            # Normalize symbols and yield batch
            normalized_batch = []
            for tick in combined_batch:
                try:
                    symbol = tick.get('symbol')
                    if symbol:
                        unified_symbol = self.symbol_mapper.to_unified(symbol)
                        tick['symbol'] = unified_symbol
                    normalized_batch.append(tick)
                    self.ticks_received += 1
                except Exception as e:
                    import traceback
                    logger.error(f"❌ CRITICAL: Error normalizing symbol: {e}")
                    logger.error(f"   Tick: {tick}")
                    logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                    self.errors += 1
                    # Re-raise on first error - don't continue with bad data
                    if self.errors == 1:
                        raise RuntimeError(f"Symbol normalization failed: {e}") from e
            
            # Yield this batch to callback
            if normalized_batch and self.callback:
                try:
                    self.callback(normalized_batch)
                except Exception as e:
                    import traceback
                    logger.error(f"❌ CRITICAL: Error in callback at {second_key}: {e}")
                    logger.error(f"   Batch size: {len(normalized_batch)}")
                    logger.error(f"   Full traceback:\n{traceback.format_exc()}")
                    # Re-raise - callback failures must not be silent
                    raise RuntimeError(f"Callback failed at {second_key}: {e}") from e
            
            # Progress reporting
            if batch_count % 1000 == 0:
                logger.info(f"Progress: {batch_count}/{len(all_seconds)} seconds processed")
    
    def _subscribe_options_for_index(self, symbol: str, spot_ltp: float, from_timestamp: datetime, patterns: Dict, calc, temp_dm):
        """
        Dynamically subscribe to options for a newly discovered index.
        
        Each pattern resolves to EXACTLY ONE contract (not a ladder).
        Example: "TI:W0:OTM10:CE" → ONLY the contract at ATM + (interval × 10)
        
        Args:
            symbol: Index symbol (e.g., 'NIFTY')
            spot_ltp: Current LTP of index
            from_timestamp: Timestamp when index was discovered
            patterns: Option patterns from cache
            calc: ExpiryCalculator instance
            temp_dm: DataManager instance
        """
        # Initialize subscribed options list if first time
        if symbol not in self.subscribed_options:
            self.subscribed_options[symbol] = []
        
        from src.data.fo_dynamic_resolver import FODynamicResolver
        
        # Initialize F&O resolver for this symbol
        # In backtesting mode: instrument_store=None, queries ClickHouse directly
        fo_resolver = FODynamicResolver(
            instrument_store=None,
            clickhouse_client=self.clickhouse_client,
            mode='backtesting'
        )
        
        option_tickers = []
        
        # Get strike interval from config (not hardcoded!)
        strike_interval = STRIKE_INTERVALS.get(symbol, DEFAULT_STRIKE_INTERVAL)
        current_atm = round(spot_ltp / strike_interval) * strike_interval
        logger.debug(f"  📊 Using strike_interval={strike_interval} for {symbol}, ATM={current_atm}")
        
        for pattern_str, pattern_data in patterns.items():
            # Parse pattern: underlying_alias:expiry_code:strike_type:option_type
            # Example: TI:W0:OTM10:CE
            parts = pattern_str.split(':')
            if len(parts) != 4:
                continue
            
            underlying_alias, expiry_code, strike_type, option_type = parts
            underlying = pattern_data.get('underlying_symbol')
            
            if underlying != symbol:
                continue  # This pattern is for a different underlying
            
            # Build universal pattern (e.g., "NIFTY:W0:OTM10:CE")
            universal_pattern = f"{underlying}:{expiry_code}:{strike_type}:{option_type}"
            
            # Check if we already resolved this pattern for this ATM
            if pattern_str not in self.pattern_symbol_cache:
                self.pattern_symbol_cache[pattern_str] = {}
            
            if current_atm in self.pattern_symbol_cache[pattern_str]:
                # Reuse cached symbol (ATM oscillated back)
                resolved_symbol = self.pattern_symbol_cache[pattern_str][current_atm]
                ticker = self._convert_universal_to_clickhouse_ticker(resolved_symbol)
                
                # Check if already subscribed
                if ticker not in self.subscribed_options.get(symbol, []):
                    option_tickers.append(ticker)
                    logger.info(f"  📊 Pattern {pattern_str} → {resolved_symbol} (cached)")
                continue
            
            try:
                # Resolve to SINGLE specific contract
                # This uses current spot LTP and returns ONE contract
                # Note: fo_resolver.resolve() expects spot_prices dict, not single price
                spot_prices = {symbol: spot_ltp}
                
                # Convert datetime to date - ClickHouse stores expiry_date as DATE, not DATETIME
                reference_date = from_timestamp.date() if hasattr(from_timestamp, 'date') else from_timestamp
                
                resolved_symbol = fo_resolver.resolve(
                    dynamic_symbol=universal_pattern,
                    spot_prices=spot_prices,
                    reference_date=reference_date
                )
                
                if resolved_symbol:
                    # Cache the pattern → ATM → symbol mapping
                    self.pattern_symbol_cache[pattern_str][current_atm] = resolved_symbol
                    
                    # Convert to ClickHouse ticker format for loading
                    # Universal: NIFTY:2024-10-28:OPT:26350:CE
                    # ClickHouse: NIFTY28OCT2426350CE
                    ticker = self._convert_universal_to_clickhouse_ticker(resolved_symbol)
                    option_tickers.append(ticker)
                    logger.info(f"  📊 Pattern {pattern_str} → {resolved_symbol} (ATM: {current_atm})")
                else:
                    logger.error(f"  ❌ Failed to resolve pattern {pattern_str} - resolver returned None")
                    
            except Exception as e:
                # CRITICAL ERROR - Don't fail silently! Show full traceback
                import traceback
                logger.error(f"  ❌ CRITICAL ERROR resolving pattern {pattern_str}: {e}")
                logger.error(f"     Pattern: {universal_pattern}")
                logger.error(f"     Spot LTP: {spot_ltp}, From: {from_timestamp}")
                logger.error(f"     Full traceback:\n{traceback.format_exc()}")
                # Re-raise to stop execution - we can't continue without option resolution
                raise RuntimeError(f"Option pattern resolution failed for {pattern_str}: {e}") from e
        
        # Deduplicate (though should be unique already since each pattern = 1 contract)
        option_tickers = list(dict.fromkeys(option_tickers))
        
        if option_tickers:
            # Load option ticks from subscription timestamp forward ONLY
            # Don't load all day's data - only what we need!
            # This matches live trading: you only get ticks after subscription
            
            try:
                # Use ClickHouse query to filter at source (not in Python)
                option_ticks = self._load_option_ticks_from_timestamp(
                    tickers=option_tickers,
                    from_timestamp=from_timestamp,
                    temp_dm=temp_dm
                )
                
                # Group option ticks into nested cache: symbol -> second -> [tick]
                # Ticks are ALREADY aggregated per second (1 per symbol per second)
                # So we just need to place each tick in the right bucket
                from collections import defaultdict
                for tick in option_ticks:
                    opt_symbol = tick.get('symbol')
                    opt_ts = tick.get('timestamp')  # Already rounded to second from ClickHouse
                    
                    if opt_symbol and opt_ts:
                        # Initialize nested structure using defaultdict
                        if opt_symbol not in self.option_ticks_cache:
                            self.option_ticks_cache[opt_symbol] = defaultdict(list)
                        
                        # Since ticks are aggregated, there's only 1 tick per (symbol, second)
                        self.option_ticks_cache[opt_symbol][opt_ts].append(tick)
                
                logger.info(f"  📥 Loaded {len(option_ticks):,} option ticks from {from_timestamp}")
            except Exception as e:
                import traceback
                logger.error(f"  ❌ CRITICAL: Failed to load option ticks: {e}")
                logger.error(f"     Tickers: {option_tickers}")
                logger.error(f"     From timestamp: {from_timestamp}")
                logger.error(f"     Full traceback:\n{traceback.format_exc()}")
                # Re-raise - can't continue without option data if patterns were defined
                raise RuntimeError(f"Failed to load option ticks for {len(option_tickers)} contracts") from e
            
            # Add new tickers to subscribed list (don't replace - accumulate!)
            self.subscribed_options[symbol].extend(option_tickers)
            
            # Calculate and store current ATM strike for rebalancing detection
            # Use the same strike_interval we calculated earlier (line 380)
            self.current_atm_strike[symbol] = current_atm
            
            logger.info(f"  ✅ Subscribed to {len(option_tickers)} specific contracts for {symbol} (ATM: {current_atm})")
        else:
            logger.warning(f"  ⚠️ No options resolved for {symbol}")
    
    def _check_and_rebalance_strikes(self, symbol: str, spot_ltp: float, from_timestamp: datetime, patterns: Dict, calc, temp_dm):
        """
        Check if ATM strike has shifted by one strike interval.
        If yes, resolve all patterns again and subscribe to new contracts.
        Never unsubscribe old contracts - accumulate subscriptions.
        
        Args:
            symbol: Index symbol (e.g., 'NIFTY')
            spot_ltp: Current LTP of index
            from_timestamp: Current timestamp
            patterns: Option patterns from cache
            calc: ExpiryCalculator instance
            temp_dm: DataManager instance
        """
        # Calculate current ATM
        strike_interval = 50 if symbol == 'NIFTY' else 100
        new_atm = round(spot_ltp / strike_interval) * strike_interval
        
        # Get previous ATM
        old_atm = self.current_atm_strike.get(symbol)
        
        if old_atm is None:
            # First time seeing this symbol after discovery
            self.current_atm_strike[symbol] = new_atm
            return
        
        # Check if ATM has shifted by one strike
        if abs(new_atm - old_atm) >= strike_interval:
            logger.info(f"🔄 ATM SHIFTED for {symbol}: {old_atm} → {new_atm} at {from_timestamp}")
            
            # Resubscribe all patterns with new ATM
            # This will add NEW contracts while keeping old ones
            self._subscribe_options_for_index(
                symbol=symbol,
                spot_ltp=spot_ltp,
                from_timestamp=from_timestamp,
                patterns=patterns,
                calc=calc,
                temp_dm=temp_dm
            )
    
    def _load_option_ticks_from_timestamp(self, tickers: List[str], from_timestamp: datetime, temp_dm) -> List[Dict]:
        """
        Load AGGREGATED option ticks from ClickHouse, filtered at SOURCE by timestamp.
        
        This is critical for performance and realism:
        - Only loads ticks >= from_timestamp (subscription time)
        - AGGREGATED per second in ClickHouse (argMax LTP per second)
        - Filtering done in ClickHouse query, not Python
        - Matches live trading: no historical ticks before subscription
        - 10x less data transfer (1 row/second vs 10+ rows/second)
        
        Args:
            tickers: List of option tickers to load
            from_timestamp: Start timestamp (subscription time)
            temp_dm: DataManager instance
            
        Returns:
            List of AGGREGATED tick dictionaries (one per symbol per second)
        """
        if not tickers:
            return []
        
        try:
            # Use DataManager's aggregated method - it handles ClickHouse aggregation
            # This is MUCH more efficient than loading raw ticks and aggregating in Python
            ticks = temp_dm.load_option_ticks_aggregated(
                date=self.backtest_date,
                tickers=tickers,
                from_timestamp=from_timestamp
            )
            
            logger.info(f"📦 Loaded {len(ticks):,} aggregated option ticks (1/second) for {len(tickers)} contracts")
            
            return ticks
            
        except Exception as e:
            import traceback
            logger.error(f"❌ CRITICAL: Failed to load option ticks from timestamp: {e}")
            logger.error(f"   Tickers: {tickers}")
            logger.error(f"   From timestamp: {from_timestamp}")
            logger.error(f"   Full traceback:\n{traceback.format_exc()}")
            # Re-raise - option tick loading failure is critical
            raise RuntimeError(f"Failed to load option ticks from timestamp {from_timestamp}") from e
    
    def _convert_universal_to_clickhouse_ticker(self, universal_symbol: str) -> str:
        """
        Convert universal format to ClickHouse ticker format.
        
        Universal: NIFTY:2024-10-28:OPT:26350:CE
        ClickHouse: NIFTY28OCT2426350CE
        
        Args:
            universal_symbol: Symbol in universal format
            
        Returns:
            Symbol in ClickHouse ticker format
        """
        try:
            parts = universal_symbol.split(':')
            if len(parts) != 5:
                return universal_symbol
            
            underlying, date_str, inst_type, strike, opt_type = parts
            
            if inst_type != 'OPT':
                return universal_symbol  # Not an option
            
            # Parse date: 2024-10-28
            from datetime import datetime
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Format: NIFTY28OCT2426350CE
            month_map = {
                1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR', 5: 'MAY', 6: 'JUN',
                7: 'JUL', 8: 'AUG', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DEC'
            }
            
            day = dt.day
            month = month_map[dt.month]
            year = dt.year % 100  # Last 2 digits
            
            ticker = f"{underlying}{day:02d}{month}{year:02d}{strike}{opt_type}"
            return ticker
            
        except Exception as e:
            import traceback
            logger.error(f"❌ CRITICAL: Failed to convert {universal_symbol} to ClickHouse format: {e}")
            logger.error(f"   Full traceback:\n{traceback.format_exc()}")
            # Re-raise - symbol conversion failure means wrong data
            raise RuntimeError(f"Symbol conversion failed for {universal_symbol}: {e}") from e
    
    def stop(self):
        """Stop processing ticks."""
        if self.running:
            logger.info("⏹️ Stopping ClickHouseTickSource...")
            self.running = False
    
    def is_running(self) -> bool:
        """Check if tick source is running."""
        return self.running
    
    def wait_completion(self):
        """
        Wait for all ticks to be processed.
        
        For ClickHouseTickSource, this is a no-op because start() already
        blocks until all ticks are processed.
        """
        # No-op: start() already blocks until completion
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return {
            'ticks_received': self.ticks_received,
            'errors': self.errors,
            'total_ticks': self.ticks_received,  # Same as ticks_received in batch mode
            'status': 'running' if self.running else 'completed',
            'backtest_date': str(self.backtest_date),
            'symbols': self.symbols,
            'discovered_indices': list(self.discovered_indices.keys()),
            'subscribed_options_count': sum(len(opts) for opts in self.subscribed_options.values())
        }
    
    def get_pattern_symbol_mapping(self, pattern: str, atm_strike: float = None) -> Optional[str]:
        """
        Get the resolved symbol for a pattern at a specific ATM strike.
        
        If atm_strike is None, returns the symbol at current ATM.
        This is critical for:
        1. Entry nodes: Get exact symbol to enter
        2. Position store: Store exact symbol
        3. Exit nodes: Exit the exact symbol that was entered
        
        Args:
            pattern: Pattern string (e.g., "TI:W0:OTM10:CE")
            atm_strike: ATM strike to look up (optional)
            
        Returns:
            Resolved symbol (e.g., "NIFTY:2024-10-28:OPT:26350:CE") or None
        """
        if pattern not in self.pattern_symbol_cache:
            return None
        
        if atm_strike is None:
            # Return most recent resolution (highest ATM key)
            atm_cache = self.pattern_symbol_cache[pattern]
            if not atm_cache:
                return None
            latest_atm = max(atm_cache.keys())
            return atm_cache[latest_atm]
        
        return self.pattern_symbol_cache[pattern].get(atm_strike)
