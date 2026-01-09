"""
Dynamic F&O Resolver - Resolves relative F&O references to absolute symbols.

Handles:
- Expiry codes: W0, W1, M0, M1, Q0, Y0, etc.
- Strike codes: ATM, OTM1-15, ITM1-15
- Option types: CE, PE
- Instrument types: FUT, OPT

Example:
    Input:  NIFTY:W0:ATM:CE (with spot=19547)
    Output: NIFTY:2024-11-14:OPT:19550:CE
"""

from datetime import date, datetime, timedelta
from typing import Dict, Optional, Tuple, List
import calendar
from src.data.fo_config import get_config, get_strike_interval


class ExpiryCalculator:
    """
    Calculate expiry dates based on expiry codes using scrip master data ONLY.
    
    ⚠️  REQUIRES scrip master data - NO calendar fallback!
    
    Pattern:
    - W0, W1, W2: All expiries from scrip master (1st, 2nd, 3rd available)
    - M0, M1, M2: Monthly expiries - Group by YYYYMM, keep LAST of each month
    - Q0, Q1: Quarterly expiries - Group by YYYYQQ, keep LAST of each quarter
    - Y0, Y1: Yearly expiries - Group by YYYY, keep LAST of each year
    
    Note: This ensures we only use actual tradeable contracts from broker.
          Will raise ValueError if scrip master data is not available.
    """
    
    # Day ranges for weekly expiry (keep as is)
    WEEKLY_DAY_RANGE = 13
    
    def __init__(self, instrument_store=None):
        """
        Initialize with optional instrument store.
        
        Args:
            instrument_store: InstrumentLTPStore instance for fetching expiries
        """
        self.instrument_store = instrument_store
    
    @staticmethod
    def _get_expiry_weekday(symbol: str) -> int:
        """
        Get the expiry weekday for a symbol (index or commodity).
        
        Args:
            symbol: Symbol name (e.g., NIFTY, GOLD, SILVER)
        
        Returns:
            Weekday (0=Monday, 1=Tuesday, ..., 6=Sunday)
        """
        config = get_config(symbol)
        expiry_day_config = config["expiry_day"]
        
        weekday_map = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
            'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }
        
        # Try to get from any expiry type config
        for key in ['weekly', 'monthly', 'quarterly', 'yearly']:
            day_config = expiry_day_config.get(key)
            if day_config:
                # Handle patterns like 'last_tuesday', 'first_friday', 'third_tuesday'
                if '_' in day_config:
                    day_name = day_config.split('_')[-1].capitalize()
                else:
                    day_name = day_config.capitalize()
                
                if day_name in weekday_map:
                    return weekday_map[day_name]
        
        raise ValueError(f"Could not determine expiry weekday for {symbol}")
    
    @staticmethod
    def _find_next_expiry_in_range(
        start_date: date,
        expiry_weekday: int,
        max_days: int
    ) -> date:
        """
        Find next expiry date within a day range (for weekly expiries).
        
        Args:
            start_date: Starting date
            expiry_weekday: Expiry weekday (0=Mon, 6=Sun)
            max_days: Maximum days to search
        
        Returns:
            Next expiry date within range
        
        Raises:
            ValueError: If no expiry found within range
        """
        # Start from tomorrow (not today)
        search_date = start_date + timedelta(days=1)
        end_date = start_date + timedelta(days=max_days)
        
        while search_date <= end_date:
            if search_date.weekday() == expiry_weekday:
                return search_date
            search_date += timedelta(days=1)
        
        raise ValueError(
            f"No expiry found within {max_days} days from {start_date}"
        )
    
    def _get_available_expiries_from_master(
        self,
        symbol: str,
        reference_date: date,
        instrument_category: str = 'options'
    ) -> List[date]:
        """
        Get available expiries from instrument master (scrip master).
        
        Args:
            symbol: Symbol name (e.g., NIFTY, NATURALGAS)
            reference_date: Reference date (today)
            instrument_category: 'futures' or 'options' (default: 'options')
        
        Returns:
            List of expiry dates (sorted, future only)
        """
        if not self.instrument_store:
            # Fallback to calendar-based calculation
            return []
        
        # Get config to determine exchange and instrument type
        try:
            config = get_config(symbol)
            exchange = config['exchange']
        except:
            exchange = 'NFO'  # Default
        
        # Determine instrument type for F&O instruments
        # For indices: OPTIDX for options, FUTIDX for futures
        # For stocks: OPTSTK for options, FUTSTK for futures
        # For commodities: OPTFUT for options, FUTCOM for futures
        if exchange == 'NFO':
            # Check if it's an index or stock
            if symbol in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX', 'BANKEX']:
                instrument_type = 'FUTIDX' if instrument_category == 'futures' else 'OPTIDX'
            else:
                instrument_type = 'FUTSTK' if instrument_category == 'futures' else 'OPTSTK'
        elif exchange == 'MCX':
            # MCX commodities (Natural Gas, Crude Oil, Gold, etc.)
            instrument_type = 'FUTCOM' if instrument_category == 'futures' else 'OPTFUT'
        else:
            instrument_type = None  # For spot/equity
        
        # Search for all instruments of this underlying
        instruments = self.instrument_store.search_instruments(
            name=symbol,
            exchange=exchange,
            instrument_type=instrument_type
        )
        
        # Extract unique expiry dates
        expiry_dates = set()
        
        # Convert reference_date to date object if it's a timestamp
        if isinstance(reference_date, (int, float)):
            reference_date = datetime.fromtimestamp(reference_date / 1000).date()
        
        for inst in instruments:
            expiry_str = inst.get('expiry')
            
            # If expiry field is null/NaT, parse from symbol name
            if not expiry_str or expiry_str in ['null', 'NaT', 'None']:
                symbol_name = inst.get('symbol', '')
#                 # Extract expiry from symbol like "NIFTY29DEC2630000CE"
#                 # Format: SYMBOL + DDMMMYY + STRIKE + CE/PE
#                 try:
#                     # Find the date part (DDMMMYY format)
#                     import re
#                     # Match pattern: 2 digits + 3 letters + 2 digits
#                     match = re.search(r'(\d{2})([A-Z]{3})(\d{2})', symbol_name)
#                     if match:
#                         day = int(match.group(1))
#                         month_str = match.group(2)
#                         year = int('20' + match.group(3))  # Assuming 20xx
#                         
#                         # Convert month string to number
#                         month_map = {
#                             'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
#                             'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
#                             'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
#                         }
#                         month = month_map.get(month_str)
#                         
#                         if month:
#                             expiry_date = date(year, month, day)
#                             # Only include future dates (including today)
                pass
#                         pass
#             else:
#                 # Use expiry field if available
#                 try:
#                     expiry_date = date.fromisoformat(expiry_str)
#                     except Exception as e:
#                         logger.error(f"❌ ERROR in fo_dynamic_resolver.py:214: {e}")
#                         # Fix the error instead of continuing
#                         raise  # Re-raise to expose the error
#                     if expiry_date >= reference_date:
#                         expiry_dates.add(expiry_date)
#                 except (ValueError, TypeError):
#                     continue
#         
#         # Sort and return all expiries
#         return sorted(list(expiry_dates))
#     
#     @staticmethod
#     def _find_last_weekday_in_month(
#         year: int,
#         month: int,
#         weekday: int
#     ) -> Optional[date]:
#         """
#         Find the LAST occurrence of a weekday in a month.
#         
#         Args:
#             year: Year
#             month: Month (1-12)
#             weekday: Weekday (0=Mon, 6=Sun)
#         
#         Returns:
#             Last occurrence of weekday in that month, or None if not found
#         """
#         # Get last day of month
#         last_day = calendar.monthrange(year, month)[1]
#         
#         # Search backwards from last day
#         for day in range(last_day, 0, -1):
#             check_date = date(year, month, day)
#             if check_date.weekday() == weekday:
#                 return check_date
#         
#         return None
#     
    def _get_weekly_expiry(
        self,
        symbol: str,
        week_offset: int,
        reference_date: date,
        instrument_category: str = 'options'
    ) -> date:
        """
        Get weekly expiry from scrip master.
        
        Logic:
        - Get all available expiries from scrip master
        - No grouping - use all expiries as-is
        - W0 = 1st expiry, W1 = 2nd expiry, W2 = 3rd expiry, etc.
        
        Args:
            symbol: Symbol name
            week_offset: 0 (W0), 1 (W1), 2 (W2), etc.
            reference_date: Reference date
        
        Returns:
            Expiry date
            
        Raises:
            ValueError: If scrip master not available or not enough expiries
        """
        # Get all expiries from scrip master
        all_expiries = self._get_available_expiries_from_master(symbol, reference_date, instrument_category)
        
        if not all_expiries:
            raise ValueError(
                f"❌ Scrip master data not available for {symbol}. "
                f"Cannot resolve W{week_offset}. "
                f"Please ensure instrument_store is loaded with scrip master data."
            )
        
        # Check if we have enough expiries
        if week_offset >= len(all_expiries):
            raise ValueError(
                f"❌ Not enough expiries for {symbol} W{week_offset}. "
                f"Only {len(all_expiries)} expiries available in scrip master."
            )
        
        # Return the Nth expiry (no grouping)
        return all_expiries[week_offset]
    
    def _get_monthly_expiry(
        self,
        symbol: str,
        month_offset: int,
        reference_date: date,
        instrument_category: str = 'options'
    ) -> date:
        """
        Get monthly expiry from scrip master.
        
        Logic:
        - Get all available expiries from scrip master
        - Group by YYYYMM format
        - Keep LAST expiry of each month
        - M0 = last expiry of 1st month, M1 = last expiry of 2nd month, etc.
        
        Args:
            symbol: Symbol name
            month_offset: 0 (M0), 1 (M1), 2 (M2)
            reference_date: Reference date
        
        Returns:
            Expiry date
            
        Raises:
            ValueError: If scrip master not available or not enough expiries
        """
        # Get all expiries from scrip master
        all_expiries = self._get_available_expiries_from_master(symbol, reference_date, instrument_category)
        
        if not all_expiries:
            raise ValueError(
                f"❌ Scrip master data not available for {symbol}. "
                f"Cannot resolve M{month_offset}. "
                f"Please ensure instrument_store is loaded with scrip master data."
            )
        
        # Group by YYYYMM, keep LAST expiry of each month
        monthly_map = {}
        for exp in all_expiries:
            month_key = f"{exp.year}{exp.month:02d}"  # "202510"
            # Keep updating - last one wins (since list is sorted)
            monthly_map[month_key] = exp
        
        # Sort by key (string comparison works correctly)
        sorted_keys = sorted(monthly_map.keys())
        
        # Check if we have enough expiries
        if month_offset >= len(sorted_keys):
            raise ValueError(
                f"❌ Not enough monthly expiries for {symbol} M{month_offset}. "
                f"Only {len(sorted_keys)} months available in scrip master."
            )
        
        # Return the Nth monthly expiry
        return monthly_map[sorted_keys[month_offset]]
    
    def _get_quarterly_expiry(
        self,
        symbol: str,
        quarter_offset: int,
        reference_date: date
    ) -> date:
        """
        Get quarterly expiry from scrip master.
        
        Logic:
        - Get all available expiries from scrip master
        - Group by YYYYQQ format (Q1=01, Q2=02, Q3=03, Q4=04)
        - Keep LAST expiry of each quarter
        - Q0 = last expiry of 1st quarter, Q1 = last expiry of 2nd quarter, etc.
        
        Args:
            symbol: Symbol name
            quarter_offset: 0 (Q0), 1 (Q1)
            reference_date: Reference date
        
        Returns:
            Expiry date
            
        Raises:
            ValueError: If scrip master not available or not enough expiries
        """
        # Get all expiries from scrip master
        all_expiries = self._get_available_expiries_from_master(symbol, reference_date, instrument_category)
        
        if not all_expiries:
            raise ValueError(
                f"❌ Scrip master data not available for {symbol}. "
                f"Cannot resolve Q{quarter_offset}. "
                f"Please ensure instrument_store is loaded with scrip master data."
            )
        
        # Group by YYYYQQ, keep LAST expiry of each quarter
        quarterly_map = {}
        for exp in all_expiries:
            quarter = (exp.month - 1) // 3 + 1  # 1-4
            quarter_key = f"{exp.year}{quarter:02d}"  # "202504"
            # Keep updating - last one wins (since list is sorted)
            quarterly_map[quarter_key] = exp
        
        # Sort by key (string comparison works correctly)
        sorted_keys = sorted(quarterly_map.keys())
        
        # Check if we have enough expiries
        if quarter_offset >= len(sorted_keys):
            raise ValueError(
                f"❌ Not enough quarterly expiries for {symbol} Q{quarter_offset}. "
                f"Only {len(sorted_keys)} quarters available in scrip master."
            )
        
        # Return the Nth quarterly expiry
        return quarterly_map[sorted_keys[quarter_offset]]
    
    def _get_yearly_expiry(
        self,
        symbol: str,
        year_offset: int,
        reference_date: date
    ) -> date:
        """
        Get yearly expiry from scrip master.
        
        Logic:
        - Get all available expiries from scrip master
        - Group by YYYY format
        - Keep LAST expiry of each year
        - Y0 = last expiry of 1st year, Y1 = last expiry of 2nd year, etc.
        
        Args:
            symbol: Symbol name
            year_offset: 0 (Y0), 1 (Y1)
            reference_date: Reference date
        
        Returns:
            Expiry date
            
        Raises:
            ValueError: If scrip master not available or not enough expiries
        """
        # Get all expiries from scrip master
        all_expiries = self._get_available_expiries_from_master(symbol, reference_date, instrument_category)
        
        if not all_expiries:
            raise ValueError(
                f"❌ Scrip master data not available for {symbol}. "
                f"Cannot resolve Y{year_offset}. "
                f"Please ensure instrument_store is loaded with scrip master data."
            )
        
        # Group by YYYY, keep LAST expiry of each year
        yearly_map = {}
        for exp in all_expiries:
            year_key = f"{exp.year}"  # "2025"
            # Keep updating - last one wins (since list is sorted)
            yearly_map[year_key] = exp
        
        # Sort by key (string comparison works correctly)
        sorted_keys = sorted(yearly_map.keys())
        
        # Check if we have enough expiries
        if year_offset >= len(sorted_keys):
            raise ValueError(
                f"❌ Not enough yearly expiries for {symbol} Y{year_offset}. "
                f"Only {len(sorted_keys)} years available in scrip master."
            )
        
        # Return the Nth yearly expiry
        return yearly_map[sorted_keys[year_offset]]
    
    def get_expiry_date(
        self,
        symbol: str,
        expiry_code: str,
        reference_date: date = None,
        instrument_category: str = 'options'
    ) -> date:
        """
        Get expiry date for an expiry code.
        
        Args:
            symbol: Symbol name (NIFTY, GOLD, SILVER, etc.)
            expiry_code: W0, W1, M0, M1, Q0, Y0, etc.
            reference_date: Reference date (default: today)
            instrument_category: 'futures' or 'options' (default: 'options')
        
        Returns:
            Expiry date
        
        Examples:
            get_expiry_date('NIFTY', 'W0') -> First Thursday within 13 days
            get_expiry_date('NIFTY', 'M0') -> Last Thursday of current month (if not expired)
            get_expiry_date('NATURALGAS', 'M0', instrument_category='futures') -> Last Tuesday of current month
            get_expiry_date('NATURALGAS', 'M0', instrument_category='options') -> Next available options expiry
        
        Pattern:
            W0, W1, W2: First expiry within 13 days (iterative)
            M0: Last expiry of current month (if not expired), else next month
            M1: Last expiry of next month after M0
            Q0: Last expiry of current quarter (if not expired), else next quarter
            Y0: Last expiry of current year (if not expired), else next year
        """
        if reference_date is None:
            reference_date = date.today()
        
        # Parse expiry code
        expiry_type = expiry_code[0]  # W, M, Q, Y
        offset = int(expiry_code[1:])  # 0, 1, 2, etc.
        
        # Route to appropriate method based on expiry type
        if expiry_type == 'W':
            # Weekly: Use scrip master (same as monthly)
            return self._get_weekly_expiry(symbol, offset, reference_date, instrument_category)
        
        elif expiry_type == 'M':
            # Monthly: From scrip master
            return self._get_monthly_expiry(symbol, offset, reference_date, instrument_category)
        
        elif expiry_type == 'Q':
            # Quarterly: From scrip master
            return self._get_quarterly_expiry(symbol, offset, reference_date)
        
        elif expiry_type == 'Y':
            # Yearly: From scrip master
            return self._get_yearly_expiry(symbol, offset, reference_date)
        
        else:
            raise ValueError(f"Invalid expiry type: {expiry_type}")


class StrikeCalculator:
    """Calculate strike prices based on strike codes."""
    
    @staticmethod
    def calculate_atm_strike(spot_price: float, strike_interval: int) -> int:
        """
        Calculate ATM strike.
        
        Formula: ATM = round(spot_price ÷ strike_interval) × strike_interval
        
        Args:
            spot_price: Current spot price
            strike_interval: Strike interval for the index
        
        Returns:
            ATM strike price
        
        Examples:
            calculate_atm_strike(19547, 50) -> 19550
            calculate_atm_strike(48234, 100) -> 48200
        """
        return round(spot_price / strike_interval) * strike_interval
    
    @staticmethod
    def get_strike_price(
        symbol: str,
        spot_price: float,
        strike_code: str,
        option_type: str
    ) -> int:
        """
        Get strike price for a strike code.
        
        Args:
            symbol: Symbol name (NIFTY, GOLD, SILVER, etc.)
            spot_price: Current spot price
            strike_code: ATM, OTM1-15, ITM1-15
            option_type: CE or PE
        
        Returns:
            Strike price
        
        Examples:
            get_strike_price('NIFTY', 19547, 'ATM', 'CE') -> 19550
            get_strike_price('NIFTY', 19547, 'OTM2', 'CE') -> 19650 (ATM + 2*50)
            get_strike_price('GOLD', 73250, 'ATM', 'CE') -> 73000 (ATM rounded)
            get_strike_price('GOLD', 73250, 'OTM2', 'CE') -> 73200 (ATM + 2*100)
        """
        config = get_config(symbol)
        strike_interval = config["strike_interval"]
        atm_strike = StrikeCalculator.calculate_atm_strike(spot_price, strike_interval)
        
        if strike_code == 'ATM':
            return atm_strike
        
        # Parse strike code (OTM1, ITM2, etc.)
        if strike_code.startswith('OTM'):
            offset = int(strike_code[3:])
            # For CE: OTM = higher strikes (ATM + offset)
            # For PE: OTM = lower strikes (ATM - offset)
            if option_type == 'CE':
                return atm_strike + (offset * strike_interval)
            else:  # PE
                return atm_strike - (offset * strike_interval)
        
        elif strike_code.startswith('ITM'):
            offset = int(strike_code[3:])
            # For CE: ITM = lower strikes (ATM - offset)
            # For PE: ITM = higher strikes (ATM + offset)
            if option_type == 'CE':
                return atm_strike - (offset * strike_interval)
            else:  # PE
                return atm_strike + (offset * strike_interval)
        
        else:
            raise ValueError(f"Invalid strike code: {strike_code}")


class FODynamicResolver:
    """
    Resolve dynamic F&O references to absolute universal symbols.
    
    Input format:  {INDEX}:{EXPIRY_CODE}:{STRIKE_CODE}:{OPTION_TYPE}
    Output format: {INDEX}:{EXPIRY_DATE}:{INST_TYPE}:{STRIKE}:{OPTION_TYPE}
    
    Examples:
        NIFTY:W0:ATM:CE (spot=19547)
        -> NIFTY:2024-11-14:OPT:19550:CE
        
        BANKNIFTY:M0:OTM2:PE (spot=48234)
        -> BANKNIFTY:2024-11-27:OPT:48000:PE
        
        NIFTY:M0:FUT
        -> NIFTY:2024-11-28:FUT
    """
    
    def __init__(self, instrument_store=None, clickhouse_client=None, mode='live'):
        """
        Initialize FODynamicResolver.
        
        Args:
            instrument_store: InstrumentLTPStore instance for fetching expiries from scrip master (live mode)
            clickhouse_client: ClickHouse client for fetching historical data (backtesting mode)
            mode: 'live' or 'backtesting'
        """
        self.instrument_store = instrument_store
        self.clickhouse_client = clickhouse_client
        self.mode = mode
        
        # Validate: Need either instrument_store OR clickhouse_client
        if mode == 'live' and not instrument_store:
            raise ValueError("instrument_store required for live mode")
        if mode == 'backtesting' and not clickhouse_client:
            raise ValueError("clickhouse_client required for backtesting mode")
        
        self.expiry_calculator = ExpiryCalculator(instrument_store)
        self.strike_calculator = StrikeCalculator()
    
    def _construct_angelone_symbol(self, underlying: str, expiry_date: date, strike: float, option_type: str) -> str:
        """
        Construct AngelOne symbol format.
        Format: {UNDERLYING}{DDMMMYY}{STRIKE}{CE/PE}
        Example: NIFTY20OCT2426000CE
        
        Args:
            underlying: Underlying symbol (e.g., NIFTY)
            expiry_date: Expiry date
            strike: Strike price
            option_type: CE or PE
        
        Returns:
            AngelOne formatted symbol
        """
        # Format: DDMMMYY (e.g., 20OCT24)
        expiry_str = expiry_date.strftime('%d%b%y').upper()
        # Strike as integer (no decimals)
        strike_str = str(int(strike))
        return f"{underlying}{expiry_str}{strike_str}{option_type}"
    
    def _validate_symbol_exists(self, angelone_symbol: str) -> bool:
        """
        Check if the constructed symbol exists in the instrument store.
        
        Args:
            angelone_symbol: AngelOne formatted symbol
        
        Returns:
            True if symbol exists, False otherwise
        """
        if not self.expiry_calculator.instrument_store:
            return False
        return angelone_symbol in self.expiry_calculator.instrument_store.instruments
    
    def _find_nearest_strike(self, underlying: str, expiry_date: date, target_strike: float, option_type: str) -> float:
        """
        Find the nearest available strike to the target strike.
        
        Args:
            underlying: Underlying symbol (e.g., NIFTY, NATURALGAS)
            expiry_date: Expiry date
            target_strike: Calculated target strike
            option_type: CE or PE
        
        Returns:
            Nearest available strike price
        """
        if not self.expiry_calculator.instrument_store:
            return target_strike
        
        # Get all instruments for this underlying, expiry, and option type
        instruments = self.expiry_calculator.instrument_store.instruments
        
        # Filter instruments matching our criteria
        expiry_str = expiry_date.strftime('%d%b%y').upper()  # e.g., 20NOV25
        available_strikes = []
        
        for symbol, data in instruments.items():
            if (data.get('name') == underlying and 
                symbol.endswith(option_type) and
                expiry_str in symbol):
                # Extract strike from data
                strike = data.get('strike')
                if strike and strike > 0:
                    available_strikes.append(float(strike))
        
        if not available_strikes:
            print(f"[FO_RESOLVER] WARNING: No strikes found for {underlying} {expiry_date} {option_type}")
            return target_strike
        
        # Find nearest strike
        available_strikes = sorted(set(available_strikes))
        nearest_strike = min(available_strikes, key=lambda x: abs(x - target_strike))
        
        if nearest_strike != target_strike:
            print(f"[FO_RESOLVER] Snapping strike: {target_strike} -> {nearest_strike} (nearest available)")
        
        return nearest_strike
    
    def _get_expiries_from_clickhouse(
        self,
        underlying: str,
        reference_date: date,
        instrument_category: str = 'options'
    ) -> List[date]:
        """
        Get all available expiries from ClickHouse for a trading date.
        
        Args:
            underlying: NIFTY, BANKNIFTY, etc.
            reference_date: Trading date (e.g., 2024-10-01)
            instrument_category: 'options' or 'futures'
            
        Returns:
            Sorted list of expiry dates
        """
        # Convert reference_date to date string (handle both date and datetime objects)
        if hasattr(reference_date, 'date'):
            # It's a datetime object, extract date part
            date_str = reference_date.date().isoformat()
        else:
            # It's already a date object
            date_str = reference_date.isoformat()
        
        # Query from nse_options_metadata table for expiry data
        if instrument_category == 'futures':
            # For futures, query nse_futures_metadata or fallback
            table = 'nse_ticks_futures'
            query = f"""
            SELECT DISTINCT expiry_date 
            FROM {table}
            WHERE underlying = '{underlying}'
              AND trading_day = '{date_str}'
              AND expiry_date >= '{date_str}'
            ORDER BY expiry_date
            """
        else:
            # For options, use nse_options_metadata table
            query = f"""
            SELECT DISTINCT expiry_date
            FROM nse_options_metadata
            WHERE underlying = '{underlying}'
              AND expiry_date >= '{date_str}'
            ORDER BY expiry_date
            """
        
        try:
            result = self.clickhouse_client.query(query)
            expiries = [row[0] for row in result.result_rows]
            return expiries
        except Exception as e:
            from src.utils.logger import log_error
            log_error(f"Error fetching expiries from ClickHouse: {e}")
            return []
    
    def _get_expiry_date_backtesting(
        self,
        index: str,
        expiry_code: str,
        reference_date: date,
        instrument_category: str = 'options'
    ) -> date:
        """
        Get expiry date for backtesting mode using ClickHouse data.
        
        Args:
            index: Index name (NIFTY, BANKNIFTY, etc.)
            expiry_code: Expiry code (W0, W1, M0, M1, etc.)
            reference_date: Reference date
            instrument_category: 'options' or 'futures'
            
        Returns:
            Expiry date
        """
        # Get all expiries from ClickHouse
        all_expiries = self._get_expiries_from_clickhouse(index, reference_date, instrument_category)
        
        if not all_expiries:
            raise ValueError(f"No expiries found for {index} on {reference_date} in ClickHouse")
        
        # Use ExpiryCalculator's logic to filter expiries based on code
        # W0, W1, W2 -> All expiries (1st, 2nd, 3rd)
        if expiry_code.startswith('W'):
            index_num = int(expiry_code[1:])
            if index_num >= len(all_expiries):
                raise ValueError(f"Expiry code {expiry_code} out of range (only {len(all_expiries)} expiries available)")
            return all_expiries[index_num]
        
        # M0, M1, M2 -> Monthly expiries (group by month, keep last)
        elif expiry_code.startswith('M'):
            index_num = int(expiry_code[1:])
            monthly_expiries = self._filter_monthly_expiries(all_expiries)
            if index_num >= len(monthly_expiries):
                raise ValueError(f"Monthly expiry code {expiry_code} out of range (only {len(monthly_expiries)} monthly expiries)")
            return monthly_expiries[index_num]
        
        # Q0, Q1 -> Quarterly expiries (group by quarter, keep last)
        elif expiry_code.startswith('Q'):
            index_num = int(expiry_code[1:])
            quarterly_expiries = self._filter_quarterly_expiries(all_expiries)
            if index_num >= len(quarterly_expiries):
                raise ValueError(f"Quarterly expiry code {expiry_code} out of range (only {len(quarterly_expiries)} quarterly expiries)")
            return quarterly_expiries[index_num]
        
        # Y0, Y1 -> Yearly expiries (group by year, keep last)
        elif expiry_code.startswith('Y'):
            index_num = int(expiry_code[1:])
            yearly_expiries = self._filter_yearly_expiries(all_expiries)
            if index_num >= len(yearly_expiries):
                raise ValueError(f"Yearly expiry code {expiry_code} out of range (only {len(yearly_expiries)} yearly expiries)")
            return yearly_expiries[index_num]
        
        else:
            raise ValueError(f"Invalid expiry code: {expiry_code}")
    
    def _filter_monthly_expiries(self, expiries: List[date]) -> List[date]:
        """Filter to keep only last expiry of each month."""
        monthly = {}
        for exp_date in expiries:
            month_key = (exp_date.year, exp_date.month)
            if month_key not in monthly or exp_date > monthly[month_key]:
                monthly[month_key] = exp_date
        return sorted(monthly.values())
    
    def _filter_quarterly_expiries(self, expiries: List[date]) -> List[date]:
        """Filter to keep only last expiry of each quarter."""
        quarterly = {}
        for exp_date in expiries:
            quarter = (exp_date.month - 1) // 3 + 1
            quarter_key = (exp_date.year, quarter)
            if quarter_key not in quarterly or exp_date > quarterly[quarter_key]:
                quarterly[quarter_key] = exp_date
        return sorted(quarterly.values())
    
    def _filter_yearly_expiries(self, expiries: List[date]) -> List[date]:
        """Filter to keep only last expiry of each year."""
        yearly = {}
        for exp_date in expiries:
            year_key = exp_date.year
            if year_key not in yearly or exp_date > yearly[year_key]:
                yearly[year_key] = exp_date
        return sorted(yearly.values())
    
    def resolve(
        self,
        dynamic_symbol: str,
        spot_prices: Dict[str, float],
        reference_date: date = None
    ) -> str:
        """
        Resolve dynamic symbol to universal symbol.
        
        Works for both live and backtesting modes.
        
        Args:
            dynamic_symbol: Dynamic symbol (e.g., NIFTY:W0:ATM:CE)
            spot_prices: Dictionary of spot prices {index: price}
            reference_date: Reference date (default: today)
        
        Returns:
            Universal symbol (e.g., NIFTY:2024-11-14:OPT:19550:CE)
        
        Examples:
            resolve('NIFTY:W0:ATM:CE', {'NIFTY': 19547})
            -> 'NIFTY:2024-11-14:OPT:19550:CE'
            
            resolve('NIFTY:M0:FUT', {})
            -> 'NIFTY:2024-11-28:FUT'
        """
        parts = dynamic_symbol.split(':')
        
        if len(parts) == 3:
            # Futures: INDEX:EXPIRY_CODE:FUT
            index, expiry_code, inst_type = parts
            
            if inst_type != 'FUT':
                raise ValueError(f"Invalid futures format: {dynamic_symbol}")
            
            # Get expiry date based on mode
            if self.mode == 'backtesting':
                expiry_date = self._get_expiry_date_backtesting(
                    index, expiry_code, reference_date, instrument_category='futures'
                )
            else:
                expiry_date = self.expiry_calculator.get_expiry_date(
                    index, expiry_code, reference_date, instrument_category='futures'
                )
            
            return f"{index}:{expiry_date.isoformat()}:FUT"
        
        elif len(parts) == 4:
            # Options: INDEX:EXPIRY_CODE:STRIKE_CODE:OPTION_TYPE
            index, expiry_code, strike_code, option_type = parts
            
            if option_type not in ['CE', 'PE']:
                raise ValueError(f"Invalid option type: {option_type}")
            
            # Get expiry date based on mode
            if self.mode == 'backtesting':
                expiry_date = self._get_expiry_date_backtesting(
                    index, expiry_code, reference_date, instrument_category='options'
                )
            else:
                expiry_date = self.expiry_calculator.get_expiry_date(
                    index, expiry_code, reference_date, instrument_category='options'
                )
            
            # Get spot price
            if index not in spot_prices:
                raise ValueError(f"Spot price not provided for {index}")
            
            spot_price = spot_prices[index]
            
            # Get strike price (same logic for both modes)
            strike_price = self.strike_calculator.get_strike_price(
                index, spot_price, strike_code, option_type
            )
            
            # Validate symbol exists (only in live mode)
            if self.mode == 'live':
                angelone_symbol = self._construct_angelone_symbol(index, expiry_date, strike_price, option_type)
                if not self._validate_symbol_exists(angelone_symbol):
                    print(f"[FO_RESOLVER] WARNING: Constructed symbol {angelone_symbol} not found in instrument store")
                    print(f"[FO_RESOLVER] Expiry: {expiry_date}, Strike: {strike_price}, Type: {option_type}")
                    
                    # Find nearest available strike
                    nearest_strike = self._find_nearest_strike(index, expiry_date, strike_price, option_type)
                    if nearest_strike != strike_price:
                        strike_price = nearest_strike
                        # Validate the new symbol
                        angelone_symbol = self._construct_angelone_symbol(index, expiry_date, strike_price, option_type)
                        if self._validate_symbol_exists(angelone_symbol):
                            print(f"[FO_RESOLVER] ✅ Using nearest available strike: {strike_price}")
                        else:
                            print(f"[FO_RESOLVER] ❌ Even nearest strike {strike_price} not found!")
            
            return f"{index}:{expiry_date.isoformat()}:OPT:{strike_price}:{option_type}"
        
        else:
            raise ValueError(f"Invalid dynamic symbol format: {dynamic_symbol}")
    
    def resolve_batch(
        self,
        dynamic_symbols: list,
        spot_prices: Dict[str, float],
        reference_date: date = None
    ) -> Dict[str, str]:
        """
        Resolve multiple dynamic symbols.
        
        Args:
            dynamic_symbols: List of dynamic symbols
            spot_prices: Dictionary of spot prices
            reference_date: Reference date
        
        Returns:
            Dictionary mapping dynamic -> universal symbols
        """
        results = {}
        for dynamic_symbol in dynamic_symbols:
            try:
                universal_symbol = self.resolve(dynamic_symbol, spot_prices, reference_date)
                results[dynamic_symbol] = universal_symbol
            except Exception as e:
                results[dynamic_symbol] = f"ERROR: {str(e)}"
        
        return results


# Convenience function
def resolve_fo_symbol(
    dynamic_symbol: str,
    spot_prices: Dict[str, float],
    reference_date: date = None
) -> str:
    """
    Convenience function to resolve a dynamic F&O symbol.
    
    Args:
        dynamic_symbol: Dynamic symbol (e.g., NIFTY:W0:ATM:CE)
        spot_prices: Dictionary of spot prices
        reference_date: Reference date (default: today)
    
    Returns:
        Universal symbol
    """
    resolver = FODynamicResolver()
    return resolver.resolve(dynamic_symbol, spot_prices, reference_date)
