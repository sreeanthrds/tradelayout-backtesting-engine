"""
Backtesting Strike Loader

For backtesting, we don't "subscribe" to live data.
We just identify which strikes we need and query them from ClickHouse.

Key Difference:
- Live Trading: Subscribe → Load → Store
- Backtesting: Identify → Query → Use
"""

import clickhouse_connect
from typing import List, Dict, Set
from datetime import date, datetime
from strike_manager import AdditiveStrikeManager
from expiry_calculator import ExpiryCalculator


class BacktestStrikeLoader:
    """
    Loads option strike data for backtesting.
    
    Uses AdditiveStrikeManager to identify which strikes are needed,
    then queries ClickHouse for historical data.
    """
    
    def __init__(
        self,
        clickhouse_config: dict,
        underlying: str = "NIFTY",
        strike_interval: int = 50
    ):
        """
        Initialize backtest strike loader.
        
        Args:
            clickhouse_config: ClickHouse connection config
            underlying: Underlying symbol (NIFTY, BANKNIFTY)
            strike_interval: Strike interval (50 for NIFTY, 100 for BANKNIFTY)
        """
        self.clickhouse_config = clickhouse_config
        self.underlying = underlying
        self.strike_interval = strike_interval
        
        # Strike manager to track which strikes we need
        self.strike_manager = AdditiveStrikeManager(
            underlying=underlying,
            strike_interval=strike_interval,
            num_otm=16,
            num_itm=16
        )
        
        # Expiry calculator
        self.expiry_calculator: ExpiryCalculator = None
        
        # Cache for loaded option data
        self.option_data_cache: Dict[str, List] = {}
        
        # ClickHouse client
        self.client = None
    
    def connect(self):
        """Connect to ClickHouse."""
        self.client = clickhouse_connect.get_client(**self.clickhouse_config)
        # Initialize expiry calculator with ClickHouse client
        self.expiry_calculator = ExpiryCalculator(clickhouse_client=self.client)
        print(f"✅ Connected to ClickHouse for backtesting")
    
    def disconnect(self):
        """Disconnect from ClickHouse."""
        if self.client:
            self.client.close()
    
    def scan_day_for_spot_range(self, backtest_date: date) -> tuple:
        """
        Scan the day to find min/max spot prices.
        This helps us pre-calculate all strikes needed for the day.
        
        Args:
            backtest_date: Date to backtest
            
        Returns:
            (min_spot, max_spot)
        """
        query = f"""
        SELECT 
            MIN(ltp) as min_spot,
            MAX(ltp) as max_spot
        FROM nse_ticks_indices
        WHERE toDate(timestamp) = '{backtest_date}'
          AND symbol = '{self.underlying}'
          AND timestamp >= toDateTime('{backtest_date} 09:15:00')
        """
        
        result = self.client.query(query)
        if result.result_rows:
            min_spot, max_spot = result.result_rows[0]
            return min_spot, max_spot
        
        return None, None
    
    def calculate_all_strikes_for_day(
        self, 
        min_spot: float, 
        max_spot: float
    ) -> List[int]:
        """
        Calculate all strikes needed for the entire day.
        
        This pre-calculates strikes so we can load all option data upfront.
        
        Args:
            min_spot: Minimum spot price during the day
            max_spot: Maximum spot price during the day
            
        Returns:
            List of all strikes needed
        """
        # Subscribe at min spot
        self.strike_manager.subscribe_initial(min_spot)
        
        # Add strikes at max spot
        self.strike_manager.check_and_add_strikes(max_spot)
        
        # Get all strikes
        all_strikes = self.strike_manager.get_all_strikes()
        
        print(f"\n📊 Strikes needed for the day:")
        print(f"   Spot range: {min_spot:,.2f} to {max_spot:,.2f}")
        print(f"   Strike range: {all_strikes[0]} to {all_strikes[-1]}")
        print(f"   Total strikes: {len(all_strikes)}")
        
        return all_strikes
    
    def _calculate_expiry_date(self, backtest_date: date, expiry_code: str = "W0") -> date:
        """
        Calculate expiry date from expiry code using ExpiryCalculator.
        
        Args:
            backtest_date: Current backtest date
            expiry_code: W0 (current week), W1 (next week), M0 (current month), etc.
            
        Returns:
            Expiry date
        """
        if not self.expiry_calculator:
            raise ValueError("ExpiryCalculator not initialized. Call connect() first.")
        
        return self.expiry_calculator.get_expiry_date(
            symbol=self.underlying,
            expiry_code=expiry_code,
            reference_date=backtest_date
        )
    
    def load_option_data_for_strikes(
        self,
        strikes: List[int],
        backtest_date: date,
        expiry: str = "W0",
        option_types: List[str] = ["CE", "PE"]
    ) -> Dict[str, List]:
        """
        Load option tick data for specified strikes.
        
        Args:
            strikes: List of strikes to load
            backtest_date: Date to load data for
            expiry: Expiry code (W0, W1, M0, etc.)
            option_types: Option types to load (CE, PE)
            
        Returns:
            Dictionary of option data keyed by contract identifier
        """
        # Calculate expiry date
        expiry_date = self._calculate_expiry_date(backtest_date, expiry)
        
        print(f"\n📥 Loading option data from ClickHouse...")
        print(f"   Date: {backtest_date}")
        print(f"   Expiry: {expiry} ({expiry_date})")
        print(f"   Strikes: {len(strikes)} strikes")
        print(f"   Option types: {option_types}")
        
        option_data = {}
        
        for strike in strikes:
            for option_type in option_types:
                # Contract identifier
                contract_id = f"{self.underlying}:{strike}:{option_type}:{expiry}"
                
                # Query option data with expiry filter
                query = f"""
                SELECT 
                    timestamp,
                    ltp,
                    oi
                FROM nse_ticks_options
                WHERE toDate(timestamp) = '{backtest_date}'
                  AND underlying = '{self.underlying}'
                  AND strike_price = {strike}
                  AND option_type = '{option_type}'
                  AND expiry_date = '{expiry_date}'
                  AND timestamp >= toDateTime('{backtest_date} 09:15:00')
                ORDER BY timestamp
                """
                
                try:
                    result = self.client.query(query)
                    if result.result_rows:
                        option_data[contract_id] = result.result_rows
                        print(f"   ✅ {contract_id}: {len(result.result_rows):,} ticks")
                except Exception as e:
                    # Strike might not have data (too far OTM/ITM)
                    pass
        
        print(f"\n✅ Loaded data for {len(option_data)} contracts")
        
        self.option_data_cache = option_data
        return option_data
    
    def prepare_backtest_data(
        self,
        backtest_date: date,
        expiry: str = "W0"
    ) -> Dict[str, List]:
        """
        Complete preparation for backtesting.
        
        This is the main method to call:
        1. Scans day for spot range
        2. Calculates all strikes needed
        3. Loads all option data
        
        Args:
            backtest_date: Date to backtest
            expiry: Expiry to use
            
        Returns:
            Dictionary of option data
        """
        print("\n" + "="*70)
        print(f"🎯 PREPARING BACKTEST DATA FOR {backtest_date}")
        print("="*70)
        
        # Step 1: Scan day for spot range
        print("\n📊 Step 1: Scanning day for spot range...")
        min_spot, max_spot = self.scan_day_for_spot_range(backtest_date)
        
        if min_spot is None:
            print(f"❌ No data found for {backtest_date}")
            return {}
        
        print(f"   Min spot: {min_spot:,.2f}")
        print(f"   Max spot: {max_spot:,.2f}")
        
        # Step 2: Calculate all strikes needed
        print("\n📊 Step 2: Calculating strikes needed...")
        all_strikes = self.calculate_all_strikes_for_day(min_spot, max_spot)
        
        # Step 3: Load option data
        print("\n📊 Step 3: Loading option data...")
        option_data = self.load_option_data_for_strikes(
            strikes=all_strikes,
            backtest_date=backtest_date,
            expiry=expiry
        )
        
        print("\n" + "="*70)
        print("✅ BACKTEST DATA READY")
        print("="*70)
        
        return option_data
    
    def get_option_price(
        self,
        strike: int,
        option_type: str,
        timestamp: datetime,
        expiry: str = "W0"
    ) -> float:
        """
        Get option price at specific timestamp.
        
        Args:
            strike: Strike price
            option_type: CE or PE
            timestamp: Timestamp to get price for
            expiry: Expiry code
            
        Returns:
            Option LTP at that timestamp (or None if not available)
        """
        contract_id = f"{self.underlying}:{strike}:{option_type}:{expiry}"
        
        if contract_id not in self.option_data_cache:
            return None
        
        # Find closest tick to timestamp
        ticks = self.option_data_cache[contract_id]
        
        # Binary search or linear search for closest tick
        # For now, simple linear search
        for tick_ts, ltp, oi in ticks:
            if tick_ts >= timestamp:
                return ltp
        
        # Return last price if timestamp is after all ticks
        if ticks:
            return ticks[-1][1]
        
        return None


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # ClickHouse config
    config = {
        'host': 'blo67czt7m.ap-south-1.aws.clickhouse.cloud',
        'port': 8443,
        'username': 'default',
        'password': '0DNor8RIL2.7r',
        'database': 'default',
        'secure': True
    }
    
    # Create loader
    loader = BacktestStrikeLoader(
        clickhouse_config=config,
        underlying="NIFTY",
        strike_interval=50
    )
    
    # Connect
    loader.connect()
    
    # Prepare backtest data for Oct 1st, 2024
    backtest_date = date(2024, 10, 1)
    option_data = loader.prepare_backtest_data(backtest_date, expiry="W0")
    
    # Disconnect
    loader.disconnect()
    
    print(f"\n✅ Ready to backtest with {len(option_data)} option contracts!")
