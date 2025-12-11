"""
Expiry Detector for Backtesting

Automatically detects available option expiries for a given date.
"""

from typing import List, Dict
from datetime import datetime
import clickhouse_connect

from src.config.clickhouse_config import ClickHouseConfig
from src.utils.logger import log_info, log_debug


class ExpiryDetector:
    """
    Detects available option expiries from ClickHouse.
    """
    
    def __init__(self, clickhouse_config: ClickHouseConfig = None):
        """
        Initialize expiry detector.
        
        Args:
            clickhouse_config: ClickHouse configuration
        """
        self.config = clickhouse_config or ClickHouseConfig()
    
    def get_available_expiries(
        self,
        underlying: str,
        trading_day: str
    ) -> List[Dict[str, str]]:
        """
        Get all available expiries for an underlying on a specific date.
        
        Args:
            underlying: Underlying symbol (NIFTY, BANKNIFTY)
            trading_day: Trading day (YYYY-MM-DD)
            
        Returns:
            List of expiry dictionaries with 'expiry_str' and 'expiry_date'
        """
        # Connect to ClickHouse
        try:
            client = clickhouse_connect.get_client(
                host=self.config.HOST,
                user=self.config.USER,
                password=self.config.PASSWORD,
                secure=self.config.SECURE,
                database=self.config.DATABASE
            )
        except Exception as e:
            log_info(f"⚠️  ExpiryDetector: Cannot connect to ClickHouse: {e}")
            log_info("⚠️  Returning empty expiries list (backtest-only mode)")
            return []
        
        try:
            # Query to get unique expiries
            query = f"""
                SELECT DISTINCT 
                    substring(ticker, {len(underlying) + 1}, 7) as expiry_str,
                    COUNT(*) as contract_count
                FROM nse_ticks_options
                WHERE trading_day = '{trading_day}'
                  AND ticker LIKE '{underlying}%'
                GROUP BY expiry_str
                ORDER BY expiry_str
            """
            
            result = client.query(query)
            
            expiries = []
            month_map = {
                'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
                'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
                'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
            }
            
            for row in result.result_rows:
                expiry_str = row[0]
                contract_count = row[1]
                
                # Parse expiry (e.g., '03OCT24' -> '2024-10-03')
                day = expiry_str[:2]
                month = expiry_str[2:5]
                year = '20' + expiry_str[5:7]
                
                month_num = month_map.get(month, '??')
                expiry_date = f'{year}-{month_num}-{day}'
                
                expiries.append({
                    'expiry_str': expiry_str,
                    'expiry_date': expiry_date,
                    'contract_count': contract_count
                })
            
            log_info(f"📅 Found {len(expiries)} expiries for {underlying} on {trading_day}")
            for exp in expiries:
                log_debug(f"   {exp['expiry_str']} ({exp['expiry_date']}) - {exp['contract_count']:,} contracts")
            
            return expiries
            
        finally:
            client.close()
    
    def get_nearest_expiries(
        self,
        underlying: str,
        trading_day: str,
        count: int = 3
    ) -> List[Dict[str, str]]:
        """
        Get nearest N expiries.
        
        Args:
            underlying: Underlying symbol
            trading_day: Trading day (YYYY-MM-DD)
            count: Number of nearest expiries to return
            
        Returns:
            List of nearest expiry dictionaries
        """
        all_expiries = self.get_available_expiries(underlying, trading_day)
        
        # Sort by expiry date
        sorted_expiries = sorted(
            all_expiries,
            key=lambda x: datetime.strptime(x['expiry_date'], '%Y-%m-%d')
        )
        
        # Return nearest N
        return sorted_expiries[:count]
