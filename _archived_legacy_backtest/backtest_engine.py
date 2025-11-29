"""
Backtest Engine

Main backtesting engine with:
- Date range support
- Breakpoint debugging
- Error handling (never fail silently)
- Tick processing
- Candle building
- Strategy execution
"""

from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
import logging
from dataclasses import dataclass

from backtest_config import BacktestConfig
from backtest_strike_loader import BacktestStrikeLoader
from strategy_executor import StrategyExecutor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Tick:
    """Represents a market tick."""
    timestamp: datetime
    symbol: str
    ltp: float
    ltq: int
    oi: int


@dataclass
class Candle:
    """Represents a 1-minute candle."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class CandleBuilder:
    """Builds 1-minute candles from ticks."""
    
    def __init__(self):
        self.current_candle: Optional[Dict] = None
        self.completed_candles: List[Candle] = []
    
    def add_tick(self, tick: Tick) -> Optional[Candle]:
        """
        Add tick and return completed candle if minute changed.
        
        Args:
            tick: Market tick
            
        Returns:
            Completed candle if minute changed, None otherwise
        """
        # Get minute timestamp (truncate seconds)
        minute_ts = tick.timestamp.replace(second=0, microsecond=0)
        
        # Initialize or update current candle
        if self.current_candle is None:
            # First tick - start new candle
            self.current_candle = {
                'timestamp': minute_ts,
                'open': tick.ltp,
                'high': tick.ltp,
                'low': tick.ltp,
                'close': tick.ltp,
                'volume': tick.ltq
            }
            return None
        
        # Check if minute changed
        if minute_ts > self.current_candle['timestamp']:
            # Complete previous candle
            completed = Candle(**self.current_candle)
            self.completed_candles.append(completed)
            
            # Start new candle
            self.current_candle = {
                'timestamp': minute_ts,
                'open': tick.ltp,
                'high': tick.ltp,
                'low': tick.ltp,
                'close': tick.ltp,
                'volume': tick.ltq
            }
            
            return completed
        
        # Update current candle
        self.current_candle['high'] = max(self.current_candle['high'], tick.ltp)
        self.current_candle['low'] = min(self.current_candle['low'], tick.ltp)
        self.current_candle['close'] = tick.ltp
        self.current_candle['volume'] += tick.ltq
        
        return None
    
    def get_last_candle(self) -> Optional[Candle]:
        """Get the last completed candle."""
        if self.completed_candles:
            return self.completed_candles[-1]
        return None
    
    def get_candles(self, n: int = None) -> List[Candle]:
        """Get last N completed candles."""
        if n is None:
            return self.completed_candles
        return self.completed_candles[-n:]


class BacktestEngine:
    """
    Main backtesting engine.
    
    Features:
    - Date range support
    - Breakpoint debugging
    - Error handling (never fail silently)
    - Tick processing
    - Candle building
    """
    
    def __init__(
        self,
        config: BacktestConfig,
        clickhouse_config: dict,
        strategy_config: dict
    ):
        """
        Initialize backtest engine.
        
        Args:
            config: Backtest configuration
            clickhouse_config: ClickHouse connection config
            strategy_config: Strategy configuration from Supabase
        """
        self.config = config
        self.clickhouse_config = clickhouse_config
        self.strategy_config = strategy_config
        
        # Components
        self.strike_loader = BacktestStrikeLoader(
            clickhouse_config=clickhouse_config,
            underlying="NIFTY",
            strike_interval=50
        )
        self.candle_builder = CandleBuilder()
        self.strategy_executor: Optional[StrategyExecutor] = None
        
        # State
        self.breakpoint_flag = 1  # Initialize before first tick
        self.current_date: Optional[date] = None
        self.tick_count = 0
        self.candle_count = 0
        
        # Data
        self.spot_ticks: List[Tick] = []
        self.option_data: Dict = {}
        
        logger.info(f"BacktestEngine initialized with config: {config}")
    
    def _handle_error(self, error: Exception, context: str):
        """
        Handle errors according to config.
        
        Args:
            error: The exception
            context: Context where error occurred
        """
        error_msg = f"Error in {context}: {type(error).__name__}: {error}"
        logger.error(error_msg)
        
        if self.config.raise_on_error:
            # Development mode - raise immediately
            raise error
        else:
            # Production mode - log and continue
            logger.warning(f"Continuing despite error (raise_on_error=False)")
    
    def _check_breakpoint(self, tick: Tick):
        """
        Check if breakpoint should be triggered.
        
        Args:
            tick: Current tick
        """
        tick_time = tick.timestamp.strftime("%H:%M:%S")
        
        # Only trigger if time matches AND flag is still active
        if self.config.breakpoint_time == tick_time and self.breakpoint_flag == 1:
            print(f"\n🔴 BREAKPOINT HIT at {tick.timestamp}")
            print(f"   Date: {self.current_date}")
            print(f"   Tick: {tick}")
            print(f"   Tick count: {self.tick_count}")
            print(f"   Candle count: {self.candle_count}")
            
            # Disable flag so we don't break again
            self.breakpoint_flag = 0
            
            logger.info(f"Breakpoint hit at {tick.timestamp}")
    
    def _load_spot_ticks(self, backtest_date: date) -> List[Tick]:
        """
        Load NIFTY spot ticks for a date.
        
        Args:
            backtest_date: Date to load
            
        Returns:
            List of ticks (filtered from 9:15 AM onwards)
        """
        try:
            query = f"""
            SELECT 
                timestamp,
                ltp,
                ltq,
                oi
            FROM nse_ticks_indices
            WHERE toDate(timestamp) = '{backtest_date}'
              AND symbol = 'NIFTY'
              AND timestamp >= toDateTime('{backtest_date} 09:15:00')
            ORDER BY timestamp
            """
            
            result = self.strike_loader.client.query(query)
            
            ticks = [
                Tick(
                    timestamp=row[0],
                    symbol='NIFTY',
                    ltp=row[1],
                    ltq=row[2],
                    oi=row[3]
                )
                for row in result.result_rows
            ]
            
            logger.info(f"Loaded {len(ticks):,} spot ticks for {backtest_date}")
            return ticks
            
        except Exception as e:
            self._handle_error(e, f"_load_spot_ticks for {backtest_date}")
            return []
    
    def _process_tick(self, tick: Tick):
        """
        Process a single tick.
        
        Args:
            tick: Market tick
        """
        try:
            # Check breakpoint (only if configured)
            if tick.timestamp.strftime("%H:%M:%S") == self.config.breakpoint_time:
                self._check_breakpoint(tick)
            
            # Execute strategy (evaluates conditions on every tick)
            if self.strategy_executor:
                self.strategy_executor.process_tick(tick)
            
            # Build candle (for tracking)
            completed_candle = self.candle_builder.add_tick(tick)
            
            if completed_candle:
                self.candle_count += 1
                logger.debug(f"Candle completed: {completed_candle}")
            
            self.tick_count += 1
            
        except Exception as e:
            self._handle_error(e, f"_process_tick at {tick.timestamp}")
    
    def _run_single_day(self, backtest_date: date):
        """
        Run backtest for a single day.
        
        Args:
            backtest_date: Date to backtest
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"BACKTESTING: {backtest_date}")
        logger.info(f"{'='*70}")
        
        self.current_date = backtest_date
        self.breakpoint_flag = 1  # Reset flag for each day
        self.tick_count = 0
        self.candle_count = 0
        
        try:
            # Load spot ticks
            logger.info("Loading spot ticks...")
            self.spot_ticks = self._load_spot_ticks(backtest_date)
            
            if not self.spot_ticks:
                logger.warning(f"No spot ticks found for {backtest_date}")
                return
            
            # Load option data
            logger.info("Loading option data...")
            self.option_data = self.strike_loader.prepare_backtest_data(
                backtest_date=backtest_date,
                expiry="W0"
            )
            
            # Initialize strategy executor
            logger.info("Initializing strategy executor...")
            self.strategy_executor = StrategyExecutor(
                strategy_config=self.strategy_config,
                option_data=self.option_data
            )
            
            # Process ticks
            logger.info(f"Processing {len(self.spot_ticks):,} ticks...")
            for tick in self.spot_ticks:
                self._process_tick(tick)
            
            logger.info(f"Day complete: {self.tick_count:,} ticks, {self.candle_count} candles")
            
            # Print strategy results
            if self.strategy_executor:
                self.strategy_executor.print_summary()
            
        except Exception as e:
            self._handle_error(e, f"_run_single_day for {backtest_date}")
    
    def run(self):
        """Run backtest for configured date range."""
        logger.info(f"\n{'='*70}")
        logger.info(f"STARTING BACKTEST")
        logger.info(f"{'='*70}")
        logger.info(f"Config: {self.config}")
        logger.info(f"Strategy: {self.strategy_config.get('name', 'Unknown')}")
        
        try:
            # Connect to ClickHouse
            self.strike_loader.connect()
            
            # Run for each day in range
            current_date = self.config.start_date
            while current_date <= self.config.end_date:
                self._run_single_day(current_date)
                current_date += timedelta(days=1)
            
            # Disconnect
            self.strike_loader.disconnect()
            
            logger.info(f"\n{'='*70}")
            logger.info(f"BACKTEST COMPLETE")
            logger.info(f"{'='*70}")
            
        except Exception as e:
            self._handle_error(e, "run")
            # Ensure cleanup
            if self.strike_loader.client:
                self.strike_loader.disconnect()


if __name__ == "__main__":
    # Test backtest engine
    from datetime import date
    
    # Configuration
    config = BacktestConfig(
        start_date=date(2024, 10, 1),
        end_date=date(2024, 10, 1),
        breakpoint_time="10:00:00",  # Break at 10 AM
        raise_on_error=True  # Development mode
    )
    
    # ClickHouse config
    clickhouse_config = {
        'host': 'blo67czt7m.ap-south-1.aws.clickhouse.cloud',
        'port': 8443,
        'username': 'default',
        'password': '0DNor8RIL2.7r',
        'database': 'default',
        'secure': True
    }
    
    # Dummy strategy config
    strategy_config = {
        'name': 'Test Strategy',
        'symbol': 'NIFTY 50'
    }
    
    # Create and run engine
    engine = BacktestEngine(
        config=config,
        clickhouse_config=clickhouse_config,
        strategy_config=strategy_config
    )
    
    engine.run()
