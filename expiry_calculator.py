"""
Expiry Calculator for Backtesting

SIMPLE LOGIC:
1. Get all expiries from ClickHouse for a symbol
2. Sort them
3. W0 = 1st expiry, W1 = 2nd expiry, W2 = 3rd expiry...
4. M0 = MAX expiry of 1st month, M1 = MAX expiry of 2nd month...
5. Q0 = MAX expiry of 1st quarter, Q1 = MAX expiry of 2nd quarter...
6. Y0 = MAX expiry of 1st year, Y1 = MAX expiry of 2nd year...

NO assumptions about weekdays (Thursday, etc.)!
"""

from datetime import date
from typing import List


class ExpiryCalculator:
    """
    Calculate expiry dates based on expiry codes.
    
    Simple logic:
    - W0, W1, W2... = 1st, 2nd, 3rd... expiry from sorted list
    - M0, M1, M2... = MAX expiry of 1st, 2nd, 3rd... month
    - Q0, Q1, Q2... = MAX expiry of 1st, 2nd, 3rd... quarter
    - Y0, Y1, Y2... = MAX expiry of 1st, 2nd, 3rd... year
    """
    
    def __init__(self, clickhouse_client=None):
        """
        Initialize with ClickHouse client.
        
        Args:
            clickhouse_client: ClickHouse client for fetching expiries
        """
        self.clickhouse_client = clickhouse_client
        self._expiry_cache = {}
        self._cache_reference_date = None
    
    def _get_available_expiries_from_clickhouse(
        self,
        symbol: str,
        reference_date: date
    ) -> List[date]:
        """
        Get available expiries from ClickHouse option data.
        
        Args:
            symbol: Symbol name (e.g., NIFTY)
            reference_date: Reference date (for safety filter)
            
        Returns:
            List of expiry dates >= reference_date (sorted)
        """
        if not self.clickhouse_client:
            return []
        
        # Query unique expiry dates from ClickHouse
        # Filter: expiry_date >= reference_date (for safety)
        query = f"""
        SELECT DISTINCT expiry_date
        FROM nse_options_metadata
        WHERE underlying = '{symbol}'
          AND expiry_date >= '{reference_date}'
        ORDER BY expiry_date
        """
        
        try:
            result = self.clickhouse_client.query(query)
            expiry_dates = [row[0] for row in result.result_rows]
            return expiry_dates
        except Exception as e:
            print(f"Error fetching expiries from ClickHouse: {e}")
            return []
    
    def _get_weekly_expiry(
        self,
        all_expiries: List[date],
        week_offset: int
    ) -> date:
        """
        Get weekly expiry.
        
        Logic: W0 = 1st expiry, W1 = 2nd expiry, W2 = 3rd expiry...
        
        Args:
            all_expiries: Sorted list of all expiries
            week_offset: 0 (W0), 1 (W1), 2 (W2), etc.
            
        Returns:
            Expiry date
        """
        if week_offset >= len(all_expiries):
            raise ValueError(
                f"❌ Not enough expiries for W{week_offset}. "
                f"Only {len(all_expiries)} expiries available."
            )
        
        # Simply return the Nth expiry
        return all_expiries[week_offset]
    
    def _get_monthly_expiry(
        self,
        all_expiries: List[date],
        month_offset: int
    ) -> date:
        """
        Get monthly expiry.
        
        Logic:
        - Group by month (YYYYMM)
        - Keep MAX (last) expiry of each month
        - M0 = MAX of 1st month, M1 = MAX of 2nd month...
        
        Args:
            all_expiries: Sorted list of all expiries
            month_offset: 0 (M0), 1 (M1), 2 (M2)
            
        Returns:
            Expiry date
        """
        # Group by YYYYMM, keep MAX (last) expiry of each month
        monthly_map = {}
        for exp in all_expiries:
            month_key = f"{exp.year}{exp.month:02d}"  # "202410"
            # Keep updating - last one wins (MAX since list is sorted)
            monthly_map[month_key] = exp
        
        # Sort by key
        sorted_keys = sorted(monthly_map.keys())
        
        if month_offset >= len(sorted_keys):
            raise ValueError(
                f"❌ Not enough monthly expiries for M{month_offset}. "
                f"Only {len(sorted_keys)} months available."
            )
        
        # Return the Nth monthly MAX expiry
        return monthly_map[sorted_keys[month_offset]]
    
    def _get_quarterly_expiry(
        self,
        all_expiries: List[date],
        quarter_offset: int
    ) -> date:
        """
        Get quarterly expiry.
        
        Logic:
        - Group by quarter (Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec)
        - Keep MAX (last) expiry of each quarter
        - Q0 = MAX of 1st quarter, Q1 = MAX of 2nd quarter...
        
        Args:
            all_expiries: Sorted list of all expiries
            quarter_offset: 0 (Q0), 1 (Q1), 2 (Q2)
            
        Returns:
            Expiry date
        """
        # Group by YYYYQQ, keep MAX (last) expiry of each quarter
        quarterly_map = {}
        for exp in all_expiries:
            # Calculate quarter: (month-1)//3 + 1 gives 1-4
            quarter = (exp.month - 1) // 3 + 1
            quarter_key = f"{exp.year}{quarter:02d}"  # "202504" for Q4
            # Keep updating - last one wins (MAX since list is sorted)
            quarterly_map[quarter_key] = exp
        
        # Sort by key
        sorted_keys = sorted(quarterly_map.keys())
        
        if quarter_offset >= len(sorted_keys):
            raise ValueError(
                f"❌ Not enough quarterly expiries for Q{quarter_offset}. "
                f"Only {len(sorted_keys)} quarters available."
            )
        
        # Return the Nth quarterly MAX expiry
        return quarterly_map[sorted_keys[quarter_offset]]
    
    def _get_yearly_expiry(
        self,
        all_expiries: List[date],
        year_offset: int
    ) -> date:
        """
        Get yearly expiry.
        
        Logic:
        - Group by year (YYYY)
        - Keep MAX (last) expiry of each year
        - Y0 = MAX of 1st year, Y1 = MAX of 2nd year...
        
        Args:
            all_expiries: Sorted list of all expiries
            year_offset: 0 (Y0), 1 (Y1), 2 (Y2)
            
        Returns:
            Expiry date
        """
        # Group by YYYY, keep MAX (last) expiry of each year
        yearly_map = {}
        for exp in all_expiries:
            year_key = f"{exp.year}"  # "2025"
            # Keep updating - last one wins (MAX since list is sorted)
            yearly_map[year_key] = exp
        
        # Sort by key
        sorted_keys = sorted(yearly_map.keys())
        
        if year_offset >= len(sorted_keys):
            raise ValueError(
                f"❌ Not enough yearly expiries for Y{year_offset}. "
                f"Only {len(sorted_keys)} years available."
            )
        
        # Return the Nth yearly MAX expiry
        return yearly_map[sorted_keys[year_offset]]
    
    def get_expiry_date(
        self,
        symbol: str,
        expiry_code: str,
        reference_date: date = None
    ) -> date:
        """
        Get expiry date for an expiry code.
        
        SIMPLE LOGIC:
        1. Get ALL expiries from ClickHouse for the symbol
        2. Sort them
        3. W0 = 1st, W1 = 2nd, W2 = 3rd...
        4. M0 = MAX of 1st month, M1 = MAX of 2nd month...
        5. Q0 = MAX of 1st quarter, Q1 = MAX of 2nd quarter...
        6. Y0 = MAX of 1st year, Y1 = MAX of 2nd year...
        
        Args:
            symbol: Symbol name (NIFTY, BANKNIFTY, GOLD, etc.)
            expiry_code: W0, W1, M0, M1, Q0, Q1, Y0, Y1, etc.
            reference_date: Reference date (default: today)
            
        Returns:
            Expiry date
            
        Examples:
            get_expiry_date('NIFTY', 'W0', date(2024, 10, 1)) → date(2024, 10, 3)
            get_expiry_date('NIFTY', 'M0', date(2024, 10, 1)) → date(2024, 10, 31)
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Parse expiry code
        expiry_type = expiry_code[0]  # W, M, Q, Y
        offset = int(expiry_code[1:])  # 0, 1, 2, etc.
        
        # Get ALL expiries from cache if available for this reference date,
        # otherwise fetch from ClickHouse (sorted)
        if (
            self._cache_reference_date is not None
            and self._cache_reference_date == reference_date
            and symbol in self._expiry_cache
        ):
            all_expiries = self._expiry_cache.get(symbol, [])
        else:
            all_expiries = self._get_available_expiries_from_clickhouse(symbol, reference_date)
        
        if not all_expiries:
            raise ValueError(
                f"❌ No expiry data available for {symbol}. "
                f"Cannot resolve {expiry_code}."
            )
        
        # Route to appropriate method based on expiry type
        if expiry_type == 'W':
            return self._get_weekly_expiry(all_expiries, offset)
        
        elif expiry_type == 'M':
            return self._get_monthly_expiry(all_expiries, offset)
        
        elif expiry_type == 'Q':
            return self._get_quarterly_expiry(all_expiries, offset)
        
        elif expiry_type == 'Y':
            return self._get_yearly_expiry(all_expiries, offset)
        
        else:
            raise ValueError(f"Invalid expiry type: {expiry_type}. Supported: W, M, Q, Y")

    def preload_expiries_for_symbols(self, symbols: List[str], reference_date: date) -> None:
        """Preload expiry dates for a list of symbols into memory.

        This helps backtesting by avoiding repeated ClickHouse queries for
        get_expiry_date when the reference date and symbols are fixed for a
        backtest run.
        """
        if not self.clickhouse_client:
            return

        self._expiry_cache = {}
        self._cache_reference_date = reference_date

        for symbol in symbols:
            expiries = self._get_available_expiries_from_clickhouse(symbol, reference_date)
            self._expiry_cache[symbol] = expiries


# Test
if __name__ == "__main__":
    import clickhouse_connect
    
    client = clickhouse_connect.get_client(
        host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
        port=8443,
        username='default',
        password='0DNor8RIL2.7r',
        database='default',
        secure=True
    )
    
    calc = ExpiryCalculator(clickhouse_client=client)
    
    # Test W0 for Oct 1, 2024
    ref_date = date(2024, 10, 1)
    w0_expiry = calc.get_expiry_date('NIFTY', 'W0', ref_date)
    print(f"NIFTY W0 expiry for {ref_date}: {w0_expiry}")
    
    # Test M0
    m0_expiry = calc.get_expiry_date('NIFTY', 'M0', ref_date)
    print(f"NIFTY M0 expiry for {ref_date}: {m0_expiry}")
    
    client.close()
