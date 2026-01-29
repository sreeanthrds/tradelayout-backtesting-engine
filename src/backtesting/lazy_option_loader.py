"""
Lazy Option Loader for Backtesting

Loads option contracts on-demand from ClickHouse.
- Load once per contract on first access
- Cache for entire trading day
- Uses universal format for all external interfaces
- Converts to ClickHouse format only for queries
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import clickhouse_connect

from src.utils.logger import logger


class LazyOptionLoader:
    """
    Lazy loads option contracts from ClickHouse on-demand.
    
    Features:
    - Load only when needed (entry node execution)
    - Cache entire day's ticks per contract
    - No duplicate loads
    - Fast binary search for LTP at timestamp
    - Universal format for all keys
    """
    
    def __init__(self, clickhouse_client: clickhouse_connect.driver.Client, backtest_date: Any):
        """
        Initialize lazy option loader.
        
        Args:
            clickhouse_client: ClickHouse client instance
            backtest_date: Date of backtest (datetime or string)
        """
        self.clickhouse_client = clickhouse_client
        self.backtest_date = backtest_date
        
        # Cache storage (all keys in UNIVERSAL format)
        self.loaded_contracts = set()  # {contract_key}
        self.contract_cache = {}       # {contract_key: [ticks]}
        
        # Statistics
        self.stats = {
            'total_loads': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        logger.info("📦 LazyOptionLoader initialized")
    
    def get_option_ltp(self, contract_key: str, current_timestamp: str) -> Optional[float]:
        """
        Get option LTP at specific timestamp.
        Loads from ClickHouse on first access, uses cache on subsequent access.
        
        Args:
            contract_key: Universal format "NIFTY:2024-11-28:OPT:24350:CE"
            current_timestamp: Timestamp to get LTP at (e.g., "2024-11-28 09:16:54")
        
        Returns:
            LTP value, or None if not available
        """
        # Check if already loaded
        if contract_key not in self.loaded_contracts:
            # Cache miss - load from ClickHouse
            self.stats['cache_misses'] += 1
            self._load_contract(contract_key)
        else:
            # Cache hit
            self.stats['cache_hits'] += 1
        
        # Get from cache
        ticks = self.contract_cache.get(contract_key, [])
        if not ticks:
            logger.warning(f"⚠️  No ticks available for {contract_key}")
            return None
        
        # Find LTP at timestamp
        ltp = self._find_ltp_at_timestamp(ticks, current_timestamp)
        return ltp
    
    def _load_contract(self, contract_key: str):
        """
        Load contract from ClickHouse.
        Called only once per contract on first access.
        
        Args:
            contract_key: Universal format "NIFTY:2024-11-28:OPT:24350:CE"
        """
        # Convert to ClickHouse format for query
        ch_symbol = self._to_clickhouse_format(contract_key)
        
        # Format date
        if isinstance(self.backtest_date, str):
            trading_day = self.backtest_date
        else:
            trading_day = self.backtest_date.strftime('%Y-%m-%d')
        
        logger.info(f"📥 Loading option contract: {contract_key}")
        logger.debug(f"   ClickHouse symbol: {ch_symbol}")
        
        # Query ClickHouse for this contract
        query = f"""
        SELECT
            toUnixTimestamp(timestamp) as ts_unix,
            timestamp,
            ltp,
            volume,
            oi
        FROM ticks.option_ticks
        WHERE trading_day = '{trading_day}'
          AND symbol = '{ch_symbol}'
        ORDER BY timestamp ASC
        """
        
        try:
            result = self.clickhouse_client.query(query)
            rows = result.result_rows
            
            # Parse into tick dicts
            ticks = []
            for row in rows:
                tick = {
                    'ts_unix': row[0],
                    'timestamp': str(row[1]),
                    'ltp': float(row[2]),
                    'volume': int(row[3]) if row[3] else 0,
                    'oi': int(row[4]) if row[4] else 0
                }
                ticks.append(tick)
            
            # Store in cache with UNIVERSAL format key
            self.contract_cache[contract_key] = ticks
            self.loaded_contracts.add(contract_key)
            self.stats['total_loads'] += 1
            
            logger.info(f"✅ Loaded {len(ticks)} ticks for {contract_key}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load {contract_key}: {e}")
            # Store empty list to avoid repeated attempts
            self.contract_cache[contract_key] = []
            self.loaded_contracts.add(contract_key)
    
    def _find_ltp_at_timestamp(self, ticks: List[Dict], timestamp: str) -> Optional[float]:
        """
        Binary search to find LTP at or before timestamp.
        
        Args:
            ticks: List of tick dicts sorted by timestamp
            timestamp: Target timestamp (string or datetime)
        
        Returns:
            LTP value at or before timestamp, or None
        """
        if not ticks:
            return None
        
        # Convert timestamp to string if needed
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp_str = str(timestamp)
        
        # Binary search for tick at or before timestamp
        left, right = 0, len(ticks) - 1
        result_idx = 0
        
        while left <= right:
            mid = (left + right) // 2
            tick_ts = ticks[mid]['timestamp']
            
            if tick_ts <= timestamp_str:
                result_idx = mid
                left = mid + 1
            else:
                right = mid - 1
        
        # Return LTP at found index
        return ticks[result_idx]['ltp']
    
    def _to_clickhouse_format(self, contract_key: str) -> str:
        """
        Convert universal format to ClickHouse format.
        ONLY used for database queries!
        
        Args:
            contract_key: "NIFTY:2024-11-28:OPT:24350:CE"
        
        Returns:
            ClickHouse format: "NIFTY28NOV2424350CE.NFO"
        """
        parts = contract_key.split(':')
        if len(parts) != 5:
            raise ValueError(f"Invalid contract key format: {contract_key}")
        
        symbol = parts[0]
        expiry_str = parts[1]  # "2024-11-28"
        # parts[2] is "OPT"
        strike = parts[3]
        opt_type = parts[4]  # CE or PE
        
        # Parse expiry date
        dt = datetime.strptime(expiry_str, '%Y-%m-%d')
        expiry_formatted = dt.strftime('%d%b%y').upper()
        
        # Build ClickHouse format
        ch_symbol = f"{symbol}{expiry_formatted}{strike}{opt_type}.NFO"
        
        return ch_symbol
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get loader statistics.
        
        Returns:
            Dict with stats: total_loads, cache_hits, cache_misses
        """
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_loads': self.stats['total_loads'],
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'total_requests': total_requests,
            'cache_hit_rate': f"{hit_rate:.1f}%",
            'unique_contracts': len(self.loaded_contracts)
        }
    
    def preload_contracts(self, contract_keys: List[str]):
        """
        Preload multiple contracts in batch (optional optimization).
        
        Args:
            contract_keys: List of contract keys to preload
        """
        logger.info(f"📦 Preloading {len(contract_keys)} contracts...")
        
        for contract_key in contract_keys:
            if contract_key not in self.loaded_contracts:
                self._load_contract(contract_key)
        
        logger.info(f"✅ Preload complete")
