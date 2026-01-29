"""
Backtesting Simulator

Main orchestrator for backtesting simulation.
Simulates live trading with historical data:
1. Load historical OHLCV until day before backtest
2. Initialize indicators
3. Replay ticks for backtest date
4. Execute strategy
5. Collect results
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd

from src.adapters.supabase_adapter import SupabaseStrategyAdapter
from src.adapters.brokers.backtesting.backtesting_adapter import BacktestingBrokerAdapter
from src.websocket.simulated_websocket import SimulatedWebSocket
from src.backtesting.historical_data_preloader import HistoricalDataPreloader
from src.backtesting.backtesting_strategy_executor import BacktestingStrategyExecutor
from src.backtesting.dynamic_option_subscriber import DynamicOptionSubscriber
from src.backtesting.expiry_detector import ExpiryDetector
from src.data.instrument_ltp_store import InstrumentLTPStore
from src.utils.logger import log_info, log_debug, log_warning, log_error


class BacktestingSimulator:
    """
    Backtesting Simulator - Orchestrates all components.
    
    Simulates live trading with historical data:
    1. Fetch strategy from Supabase
    2. Load historical data until day before backtest
    3. Initialize indicators
    4. Replay ticks for backtest date
    5. Execute strategy on each tick
    6. Collect results
    """
    
    def __init__(
        self,
        strategy_id: str,
        user_id: str,
        backtest_date: str,
        initial_capital: float = 1000000.0,
        supabase_url: str = None,
        supabase_key: str = None
    ):
        """
        Initialize backtesting simulator.
        
        Args:
            strategy_id: Strategy ID from Supabase
            user_id: User ID
            backtest_date: Date to backtest (YYYY-MM-DD)
            initial_capital: Starting capital
            supabase_url: Supabase URL (optional)
            supabase_key: Supabase key (optional)
        """
        self.strategy_id = strategy_id
        self.user_id = user_id
        self.backtest_date = backtest_date
        self.initial_capital = initial_capital
        
        # Components
        self.supabase_adapter = SupabaseStrategyAdapter(url=supabase_url, key=supabase_key)
        self.broker_adapter = BacktestingBrokerAdapter(initial_capital=initial_capital)
        self.historical_preloader = HistoricalDataPreloader()
        self.simulated_websocket = SimulatedWebSocket(backtest_date=backtest_date)
        self.ltp_store = InstrumentLTPStore()
        
        # Dynamic option subscriber (ITM1-16, OTM1-16)
        self.option_subscriber = DynamicOptionSubscriber(
            underlying="NIFTY",
            expiries=[],  # Will be populated from strategy
            itm_depth=16,
            otm_depth=16
        )
        
        # Track if options are loaded
        self.options_loaded = False
        self.first_tick_processed = False
        
        # Strategy components
        self.strategy_config: Optional[Dict] = None
        self.strategy_executor: Optional[BacktestingStrategyExecutor] = None
        
        # Results
        self.results: Dict[str, Any] = {}
        
        log_info(f"🎯 Backtesting Simulator initialized")
        log_info(f"   Strategy: {strategy_id}")
        log_info(f"   Date: {backtest_date}")
        log_info(f"   Capital: ₹{initial_capital:,.2f}")
    
    def load_strategy(self) -> bool:
        """
        Load strategy from Supabase.
        
        Returns:
            True if successful
        """
        log_info(f"📥 Loading strategy {self.strategy_id}...")
        
        try:
            self.strategy_config = self.supabase_adapter.get_strategy(
                strategy_id=self.strategy_id,
                user_id=self.user_id
            )
            
            if not self.strategy_config:
                log_error(f"❌ Strategy not found: {self.strategy_id}")
                return False
            
            log_info(f"✅ Strategy loaded: {self.strategy_config.get('name', 'Unnamed')}")
            log_info(f"   Instrument: {self.strategy_config.get('instrument')}")
            log_info(f"   Timeframe: {self.strategy_config.get('timeframe')}")
            
            return True
            
        except Exception as e:
            log_error(f"❌ Failed to load strategy: {e}")
            return False
    
    def prepare_historical_data(self) -> bool:
        """
        Load historical data and initialize indicators.
        
        Returns:
            True if successful
        """
        if not self.strategy_config:
            log_error("❌ Strategy not loaded")
            return False
        
        log_info("📚 Preparing historical data...")
        
        # Calculate end date (day before backtest)
        backtest_date_obj = datetime.strptime(self.backtest_date, '%Y-%m-%d')
        end_date_obj = backtest_date_obj - timedelta(days=1)
        end_date = end_date_obj.strftime('%Y-%m-%d')
        
        # Get strategy parameters
        symbol = self.strategy_config.get('instrument', 'NIFTY')
        timeframe = self.strategy_config.get('timeframe', '5m')
        
        # Connect to ClickHouse
        if not self.historical_preloader.connect():
            log_error("❌ Failed to connect to ClickHouse")
            return False
        
        # Load historical OHLCV
        df = self.historical_preloader.load_historical_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            end_date=end_date,
            lookback_days=30  # Load 30 days of history
        )
        
        if df.empty:
            log_error(f"❌ No historical data for {symbol} {timeframe}")
            return False
        
        log_info(f"✅ Loaded {len(df)} historical candles")
        
        # Disconnect (we'll reconnect for tick replay)
        self.historical_preloader.disconnect()
        
        return True
    
    def initialize_strategy_executor(self) -> bool:
        """
        Initialize strategy executor with historical data.
        
        Returns:
            True if successful
        """
        if not self.strategy_config:
            log_error("❌ Strategy not loaded")
            return False
        
        log_info("🔧 Initializing strategy executor...")
        
        try:
            # Create BACKTESTING strategy executor (SYNCHRONOUS mode)
            # IMPORTANT: This uses BacktestingStrategyExecutor, NOT StrategyExecutor
            # Live trading continues to use StrategyExecutor with threading
            self.strategy_executor = BacktestingStrategyExecutor(
                strategy_config=self.strategy_config,
                broker_adapter=self.broker_adapter,
                ltp_store=self.ltp_store
            )
            
            # Initialize with historical data
            # (This will be done by the strategy executor's preloader)
            
            log_info("✅ Backtesting Strategy Executor initialized (SYNCHRONOUS mode)")
            log_info("   ⚠️  Threading DISABLED - all ticks processed sequentially")
            return True
            
        except Exception as e:
            log_error(f"❌ Failed to initialize strategy executor: {e}")
            return False
    
    def run_simulation(self) -> Dict[str, Any]:
        """
        Run backtesting simulation.
        
        Returns:
            Results dictionary
        """
        log_info("▶️  Starting backtesting simulation...")
        
        # Step 1: Load strategy
        if not self.load_strategy():
            return {'success': False, 'error': 'Failed to load strategy'}
        
        # Step 2: Prepare historical data
        if not self.prepare_historical_data():
            return {'success': False, 'error': 'Failed to prepare historical data'}
        
        # Step 3: Initialize strategy executor
        if not self.initialize_strategy_executor():
            return {'success': False, 'error': 'Failed to initialize strategy executor'}
        
        # Step 4: Detect available expiries
        log_info("📅 Detecting available option expiries...")
        expiry_detector = ExpiryDetector()
        available_expiries = expiry_detector.get_available_expiries(
            underlying="NIFTY",
            trading_day=self.backtest_date
        )
        
        # Update option subscriber with all expiries
        expiry_dates = [exp['expiry_date'] for exp in available_expiries]
        self.option_subscriber.expiries = expiry_dates
        
        log_info(f"✅ Found {len(expiry_dates)} expiries:")
        for exp in available_expiries[:5]:  # Show first 5
            log_info(f"   {exp['expiry_str']} ({exp['expiry_date']}) - {exp['contract_count']:,} contracts")
        if len(available_expiries) > 5:
            log_info(f"   ... and {len(available_expiries) - 5} more")
        
        # Step 5: Connect broker
        if not self.broker_adapter.connect():
            return {'success': False, 'error': 'Failed to connect broker'}
        
        # Step 5: Connect simulated WebSocket
        if not self.simulated_websocket.connect():
            return {'success': False, 'error': 'Failed to connect WebSocket'}
        
        # Step 6: Subscribe tick handler
        self.simulated_websocket.subscribe_tick_handler(self._on_tick)
        
        # Step 7: Replay ticks
        log_info(f"🎬 Replaying ticks for {self.backtest_date}...")
        log_info(f"   Note: Loading ONLY index ticks (NIFTY, BANKNIFTY)")
        log_info(f"   Options will be loaded on-demand when strategy trades them")
        
        start_time = datetime.now()
        # Only load index ticks - options loaded on-demand
        ticks_processed = self.simulated_websocket.replay_ticks(include_options=False)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        log_info(f"✅ Simulation complete!")
        log_info(f"   Ticks processed: {ticks_processed}")
        log_info(f"   Time elapsed: {elapsed:.2f} seconds")
        log_info(f"   Speed: {ticks_processed/elapsed:.0f} ticks/second")
        
        # Step 8: Collect results
        self.results = self._collect_results()
        
        # Step 9: Cleanup
        self.simulated_websocket.disconnect()
        self.broker_adapter.disconnect()
        
        return self.results
    
    def _on_tick(self, tick_data: Dict):
        """
        Handle tick event.
        
        Args:
            tick_data: Tick data dictionary
        """
        # Update LTP store
        symbol = tick_data.get('symbol')
        ltp = tick_data.get('ltp')
        
        if symbol and ltp:
            self.ltp_store.update_ltp(symbol, ltp)
            
            # Update broker adapter's market prices
            self.broker_adapter.update_market_price(symbol, ltp)
            
            # On first NIFTY tick, calculate ATM and subscribe to options
            if not self.first_tick_processed and symbol == 'NIFTY':
                self.first_tick_processed = True
                log_info(f"🎯 First NIFTY tick: {ltp:.2f}")
                
                # Update option subscription based on spot price
                update_info = self.option_subscriber.update_subscription(ltp)
                
                if update_info['changed']:
                    log_info(f"   ATM Strike: {update_info['new_atm']}")
                    log_info(f"   Subscribed Strikes: {len(update_info['total_strikes'])}")
                    log_info(f"   Range: {min(update_info['total_strikes'])} - {max(update_info['total_strikes'])}")
                    
                    # TODO: Load option ticks for subscribed strikes
                    # This would require modifying SimulatedWebSocket to support dynamic loading
                    # For now, we log the subscription
            
            # Check if spot moved significantly (ATM changed)
            elif symbol == 'NIFTY' and self.first_tick_processed:
                update_info = self.option_subscriber.update_subscription(ltp)
                
                if update_info['changed']:
                    # ATM changed - need to subscribe to new strikes
                    log_info(f"🔄 Spot moved: ATM changed {update_info['old_atm']} → {update_info['new_atm']}")
                    # TODO: Load new option strikes dynamically
        
        # Process tick through strategy executor
        if self.strategy_executor:
            try:
                self.strategy_executor.process_tick(tick_data)
            except Exception as e:
                log_error(f"❌ Error processing tick: {e}")
    
    def _collect_results(self) -> Dict[str, Any]:
        """
        Collect backtesting results.
        
        Returns:
            Results dictionary
        """
        log_info("📊 Collecting results...")
        
        # Get broker statistics
        broker_stats = self.broker_adapter.get_statistics()
        
        # Get orders
        orders = list(self.broker_adapter.orders.values())
        
        # Get positions
        positions = self.broker_adapter.get_positions()
        
        # Get trades
        trades = self.broker_adapter.get_trades()
        
        # Get WebSocket statistics
        ws_stats = self.simulated_websocket.get_statistics()
        
        results = {
            'success': True,
            'strategy_id': self.strategy_id,
            'backtest_date': self.backtest_date,
            'initial_capital': self.initial_capital,
            
            # Performance
            'final_capital': broker_stats['available_capital'],
            'portfolio_value': broker_stats['current_portfolio_value'],
            'total_pnl': broker_stats['total_pnl'],
            'total_pnl_percent': broker_stats['total_pnl_percent'],
            
            # Trading activity
            'total_orders': broker_stats['total_orders'],
            'filled_orders': broker_stats['filled_orders'],
            'rejected_orders': broker_stats['rejected_orders'],
            'total_trades': broker_stats['total_trades'],
            'open_positions': broker_stats['open_positions'],
            
            # Data
            'ticks_processed': ws_stats['total_ticks_processed'],
            'unique_symbols': ws_stats['unique_symbols'],
            
            # Details
            'orders': orders,
            'positions': positions,
            'trades': trades
        }
        
        # Log summary
        log_info("=" * 60)
        log_info("📊 BACKTESTING RESULTS")
        log_info("=" * 60)
        log_info(f"Strategy: {self.strategy_config.get('name', 'Unnamed')}")
        log_info(f"Date: {self.backtest_date}")
        log_info(f"")
        log_info(f"💰 Capital:")
        log_info(f"   Initial: ₹{results['initial_capital']:,.2f}")
        log_info(f"   Final: ₹{results['final_capital']:,.2f}")
        log_info(f"   Portfolio Value: ₹{results['portfolio_value']:,.2f}")
        log_info(f"")
        log_info(f"📈 Performance:")
        log_info(f"   Total P&L: ₹{results['total_pnl']:,.2f} ({results['total_pnl_percent']:.2f}%)")
        log_info(f"")
        log_info(f"📝 Trading Activity:")
        log_info(f"   Total Orders: {results['total_orders']}")
        log_info(f"   Filled Orders: {results['filled_orders']}")
        log_info(f"   Rejected Orders: {results['rejected_orders']}")
        log_info(f"   Total Trades: {results['total_trades']}")
        log_info(f"   Open Positions: {results['open_positions']}")
        log_info(f"")
        log_info(f"📊 Data:")
        log_info(f"   Ticks Processed: {results['ticks_processed']:,}")
        log_info(f"   Unique Symbols: {results['unique_symbols']}")
        log_info("=" * 60)
        
        return results


# Example usage
if __name__ == '__main__':
    # Initialize simulator
    simulator = BacktestingSimulator(
        strategy_id='your-strategy-id',
        user_id='your-user-id',
        backtest_date='2024-10-01',
        initial_capital=1000000.0
    )
    
    # Run simulation
    results = simulator.run_simulation()
    
    # Print results
    if results['success']:
        print(f"\n✅ Simulation successful!")
        print(f"Total P&L: ₹{results['total_pnl']:,.2f} ({results['total_pnl_percent']:.2f}%)")
        print(f"Total Trades: {results['total_trades']}")
    else:
        print(f"\n❌ Simulation failed: {results.get('error')}")
