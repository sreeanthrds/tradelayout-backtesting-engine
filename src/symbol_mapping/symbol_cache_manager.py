"""
Symbol Cache Manager
====================

Pre-loads and manages symbol mappings for all brokers.
Provides O(1) lookups for symbol conversion and token retrieval.

Supports:
- AngelOne
- Zerodha
- AliceBlue
- ClickHouse (Backtesting)

Memory: ~2-5 MB for 5 brokers × 1,950 instruments
Lookup: 1-5 microseconds (O(1) with DataFrame index)
"""

import logging
import pandas as pd
from typing import Dict, Optional, Any, List
from datetime import datetime
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class SymbolCacheManager:
    """
    Singleton manager for all broker symbol mappings.
    
    Pre-loads scrip masters and builds unified symbol mappings.
    Thread-safe for concurrent access.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize symbol cache manager (singleton)."""
        if self._initialized:
            return
        
        # Main DataFrame with all brokers' data
        self.df: Optional[pd.DataFrame] = None
        
        # Indexed DataFrames for fast lookup
        self.df_by_broker_symbol: Dict[str, pd.DataFrame] = {}  # {broker: indexed_df}
        self.df_by_unified: Optional[pd.DataFrame] = None
        
        # Broker-specific mappers
        self.brokers_loaded: List[str] = []
        
        # Thread lock for loading
        self.load_lock = threading.Lock()
        
        # Supported indices
        self.supported_indices = ['NIFTY', 'SENSEX', 'BANKNIFTY', 'FINNIFTY', 'BANKEX']
        
        self._initialized = True
        logger.info("📊 Symbol Cache Manager initialized")
    
    def load_all_brokers(
        self,
        scrip_master_paths: Dict[str, str],
        async_load: bool = False
    ):
        """
        Load scrip masters for all brokers.
        
        Args:
            scrip_master_paths: Dict of {broker_name: path_to_scrip_master}
                Example: {
                    'angelone': 'data/angelone_scrip_master.csv',
                    'zerodha': 'data/zerodha_instruments.csv',
                    'aliceblue': 'data/aliceblue_scrip_master.csv',
                    'clickhouse': 'data/clickhouse_symbols.csv'
                }
            async_load: If True, load in background thread
        """
        if async_load:
            thread = threading.Thread(
                target=self._load_all_brokers_sync,
                args=(scrip_master_paths,),
                daemon=True
            )
            thread.start()
            logger.info("🔄 Loading scrip masters in background thread...")
        else:
            self._load_all_brokers_sync(scrip_master_paths)
    
    def _load_all_brokers_sync(self, scrip_master_paths: Dict[str, str]):
        """Load all brokers synchronously."""
        with self.load_lock:
            start_time = datetime.now()
            
            all_dfs = []
            
            for broker_name, path in scrip_master_paths.items():
                try:
                    df = self._load_broker_scrip_master(broker_name, path)
                    if df is not None and len(df) > 0:
                        all_dfs.append(df)
                        self.brokers_loaded.append(broker_name)
                        logger.info(f"✅ Loaded {broker_name}: {len(df)} instruments")
                    else:
                        logger.error(f"❌ Failed to load {broker_name}: Empty or invalid scrip master")
                        raise ValueError(f"Empty or invalid scrip master for {broker_name}")
                except FileNotFoundError as e:
                    logger.error(f"❌ Scrip master file not found for {broker_name}: {path}")
                    raise
                except pd.errors.EmptyDataError as e:
                    logger.error(f"❌ Empty CSV file for {broker_name}: {path}")
                    raise
                except pd.errors.ParserError as e:
                    logger.error(f"❌ Failed to parse CSV for {broker_name}: {e}")
                    raise
                except Exception as e:
                    logger.error(f"❌ Unexpected error loading {broker_name}: {type(e).__name__}: {e}")
                    raise
            
            if not all_dfs:
                error_msg = "No scrip masters loaded! All brokers failed to load."
                logger.error(f"❌ {error_msg}")
                raise RuntimeError(error_msg)
            
            # Combine all DataFrames
            self.df = pd.concat(all_dfs, ignore_index=True)
            
            # Build indexed DataFrames for fast lookup
            self._build_indexes()
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"✅ Symbol cache loaded: {len(self.df)} total instruments "
                f"from {len(self.brokers_loaded)} brokers in {elapsed:.2f}s"
            )
    
    def _load_broker_scrip_master(
        self,
        broker_name: str,
        path: str
    ) -> Optional[pd.DataFrame]:
        """
        Load scrip master for one broker.
        
        Args:
            broker_name: Broker name
            path: Path to scrip master CSV
        
        Returns:
            DataFrame with broker's instruments
        """
        if not Path(path).exists():
            error_msg = f"Scrip master file not found: {path}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        # Load CSV
        df = pd.read_csv(path)
        
        # Add broker column
        df['broker'] = broker_name
        
        # Standardize column names (broker-specific logic)
        df = self._standardize_columns(broker_name, df)
        
        # Filter to supported indices only
        if 'name' in df.columns:
            df = df[df['name'].isin(self.supported_indices)]
        
        # Build unified symbol
        df['unified_symbol'] = df.apply(self._build_unified_symbol, axis=1)
        
        return df
    
    def _standardize_columns(self, broker_name: str, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize column names across brokers.
        
        Different brokers have different column names.
        Map them to standard names.
        """
        # Standard columns we need:
        # - tradingsymbol (broker's symbol)
        # - name (underlying: NIFTY, BANKNIFTY, etc.)
        # - instrument_token (for subscription)
        # - expiry (expiry date)
        # - strike (strike price)
        # - instrument_type (CE, PE, FUT, etc.)
        # - lot_size
        # - exchange
        
        if broker_name == 'angelone':
            # AngelOne format
            column_map = {
                'symbol': 'tradingsymbol',
                'name': 'name',
                'token': 'instrument_token',
                'expiry': 'expiry',
                'strike': 'strike',
                'instrumenttype': 'instrument_type',
                'lotsize': 'lot_size',
                'exch_seg': 'exchange'
            }
        elif broker_name == 'zerodha':
            # Zerodha format
            column_map = {
                'tradingsymbol': 'tradingsymbol',
                'name': 'name',
                'instrument_token': 'instrument_token',
                'expiry': 'expiry',
                'strike': 'strike',
                'instrument_type': 'instrument_type',
                'lot_size': 'lot_size',
                'exchange': 'exchange'
            }
        elif broker_name == 'aliceblue':
            # AliceBlue format
            column_map = {
                'Symbol': 'tradingsymbol',
                'Underlying': 'name',
                'Token': 'instrument_token',
                'Expiry': 'expiry',
                'Strike': 'strike',
                'OptionType': 'instrument_type',
                'LotSize': 'lot_size',
                'Exchange': 'exchange'
            }
        elif broker_name == 'clickhouse':
            # ClickHouse format (backtesting)
            column_map = {
                'symbol': 'tradingsymbol',
                'underlying': 'name',
                'token': 'instrument_token',
                'expiry': 'expiry',
                'strike': 'strike',
                'option_type': 'instrument_type',
                'lot_size': 'lot_size',
                'exchange': 'exchange'
            }
        else:
            # Default: assume standard names
            column_map = {}
        
        # Rename columns
        df = df.rename(columns=column_map)
        
        # Ensure required columns exist
        required_cols = ['tradingsymbol', 'name', 'instrument_token']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            error_msg = f"Missing required columns in {broker_name} scrip master: {missing_cols}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        return df
    
    def _build_unified_symbol(self, row: pd.Series) -> str:
        """
        Build unified symbol from scrip master row.
        
        Format: UNDERLYING_DDMMMYY_STRIKE_TYPE
        Examples:
            - NIFTY (index)
            - NIFTY_28NOV24_FUT (future)
            - NIFTY_28NOV24_25800_CE (option)
        
        Args:
            row: DataFrame row
        
        Returns:
            Unified symbol string
        """
        name = row.get('name', '')
        instrument_type = row.get('instrument_type', '')
        
        # Index/Stock (no expiry)
        if instrument_type in ['EQ', 'INDEX', '']:
            return name
        
        # Get expiry date
        expiry = row.get('expiry')
        if pd.isna(expiry) or expiry == '' or expiry == 'NaT':
            return row.get('tradingsymbol', name)
        
        # Parse expiry date
        try:
            if isinstance(expiry, str):
                # Try multiple date formats
                for fmt in ['%Y-%m-%d', '%d-%b-%Y', '%d%b%Y', '%Y%m%d']:
                    try:
                        expiry_date = datetime.strptime(expiry, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    # Could not parse
                    error_msg = f"Could not parse expiry date: {expiry} for symbol {row.get('tradingsymbol')}"
                    logger.error(f"❌ {error_msg}")
                    raise ValueError(error_msg)
            else:
                # Already a date object
                expiry_date = pd.to_datetime(expiry).date()
            
            expiry_str = expiry_date.strftime('%d%b%y').upper()  # 28NOV24
        except ValueError as e:
            logger.error(f"❌ Invalid expiry date format: {expiry} for {row.get('tradingsymbol')} - {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error parsing expiry: {expiry} for {row.get('tradingsymbol')} - {type(e).__name__}: {e}")
            raise
        
        # Futures
        if instrument_type in ['FUT', 'FUTIDX', 'FUTSTK']:
            return f"{name}_{expiry_str}_FUT"
        
        # Options
        if instrument_type in ['CE', 'PE', 'OPTIDX', 'OPTSTK']:
            strike = row.get('strike', 0)
            if pd.isna(strike):
                strike = 0
            strike = int(float(strike))
            
            # Normalize option type
            opt_type = instrument_type
            if opt_type in ['OPTIDX', 'OPTSTK']:
                # Need to determine CE/PE from symbol
                symbol = row.get('tradingsymbol', '')
                if 'CE' in symbol:
                    opt_type = 'CE'
                elif 'PE' in symbol:
                    opt_type = 'PE'
            
            return f"{name}_{expiry_str}_{strike}_{opt_type}"
        
        # Fallback
        return row.get('tradingsymbol', name)
    
    def _build_indexes(self):
        """Build indexed DataFrames for O(1) lookups."""
        if self.df is None or len(self.df) == 0:
            return
        
        # Index by (broker, tradingsymbol) for broker -> unified lookup
        for broker in self.brokers_loaded:
            broker_df = self.df[self.df['broker'] == broker].copy()
            broker_df = broker_df.set_index('tradingsymbol')
            self.df_by_broker_symbol[broker] = broker_df
        
        # Index by unified_symbol for unified -> broker lookup
        self.df_by_unified = self.df.set_index('unified_symbol')
        
        logger.info("✅ Built indexes for fast lookups")
    
    def to_unified(self, broker_name: str, broker_symbol: str) -> str:
        """
        Convert broker symbol to unified format.
        
        Args:
            broker_name: Broker name
            broker_symbol: Broker-specific symbol
        
        Returns:
            Unified symbol
        
        Raises:
            ValueError: If broker not loaded or symbol not found
        """
        if not self.is_loaded():
            error_msg = "Symbol cache not loaded! Call load_all_brokers() first."
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        if broker_name not in self.df_by_broker_symbol:
            error_msg = f"Broker '{broker_name}' not loaded. Available: {self.brokers_loaded}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        try:
            df = self.df_by_broker_symbol[broker_name]
            return df.loc[broker_symbol, 'unified_symbol']
        except KeyError:
            error_msg = f"Symbol '{broker_symbol}' not found in {broker_name} scrip master"
            logger.error(f"❌ {error_msg}")
            raise KeyError(error_msg)
    
    def from_unified(self, broker_name: str, unified_symbol: str) -> str:
        """
        Convert unified symbol to broker format.
        
        Args:
            broker_name: Broker name
            unified_symbol: Unified symbol
        
        Returns:
            Broker-specific symbol
        
        Raises:
            ValueError: If broker not loaded or symbol not found
        """
        if not self.is_loaded():
            error_msg = "Symbol cache not loaded! Call load_all_brokers() first."
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        if broker_name not in self.brokers_loaded:
            error_msg = f"Broker '{broker_name}' not loaded. Available: {self.brokers_loaded}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        try:
            # Filter by broker and unified symbol
            matches = self.df_by_unified[
                self.df_by_unified['broker'] == broker_name
            ]
            if unified_symbol in matches.index:
                return matches.loc[unified_symbol, 'tradingsymbol']
            else:
                error_msg = f"Unified symbol '{unified_symbol}' not found for broker '{broker_name}'"
                logger.error(f"❌ {error_msg}")
                raise KeyError(error_msg)
        except KeyError:
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error in from_unified: {type(e).__name__}: {e}")
            raise
    
    def get_token(self, broker_name: str, unified_symbol: str) -> int:
        """
        Get instrument token for subscription.
        
        Args:
            broker_name: Broker name
            unified_symbol: Unified symbol
        
        Returns:
            Instrument token
        
        Raises:
            ValueError: If broker not loaded or symbol not found
            ValueError: If token is missing or invalid
        """
        if not self.is_loaded():
            error_msg = "Symbol cache not loaded! Call load_all_brokers() first."
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        if broker_name not in self.brokers_loaded:
            error_msg = f"Broker '{broker_name}' not loaded. Available: {self.brokers_loaded}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        try:
            matches = self.df_by_unified[
                self.df_by_unified['broker'] == broker_name
            ]
            if unified_symbol not in matches.index:
                error_msg = f"Unified symbol '{unified_symbol}' not found for broker '{broker_name}'"
                logger.error(f"❌ {error_msg}")
                raise KeyError(error_msg)
            
            token = matches.loc[unified_symbol, 'instrument_token']
            if pd.isna(token):
                error_msg = f"Token is missing for symbol '{unified_symbol}' in broker '{broker_name}'"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            return int(token)
        except KeyError:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error in get_token: {type(e).__name__}: {e}")
            raise
    
    def get_lot_size(self, unified_symbol: str) -> int:
        """
        Get lot size for symbol.
        
        Args:
            unified_symbol: Unified symbol
        
        Returns:
            Lot size (default: 1)
        """
        if self.df_by_unified is None:
            raise RuntimeError(
                f"Symbol cache not initialized. Cannot get lot size for '{unified_symbol}'"
            )
        
        if unified_symbol not in self.df_by_unified.index:
            raise KeyError(
                f"Symbol '{unified_symbol}' not found in cache. "
                f"Total symbols available: {len(self.df_by_unified)}"
            )
        
        try:
            lot_size = self.df_by_unified.loc[unified_symbol, 'lot_size'].iloc[0]
            
            if pd.isna(lot_size):
                raise ValueError(f"Lot size is NaN for symbol '{unified_symbol}'")
            
            lot_size_int = int(lot_size)
            if lot_size_int <= 0:
                raise ValueError(
                    f"Invalid lot size {lot_size_int} for '{unified_symbol}'. "
                    f"Lot size must be positive."
                )
            
            return lot_size_int
            
        except Exception as e:
            raise RuntimeError(
                f"Failed to get lot size for '{unified_symbol}': {e}"
            ) from e
    
    def get_info(self, broker_name: str, unified_symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get complete instrument info.
        
        Args:
            broker_name: Broker name
            unified_symbol: Unified symbol
        
        Returns:
            Dictionary with instrument info or None
        """
        if self.df_by_unified is None:
            return None
        
        try:
            matches = self.df_by_unified[
                self.df_by_unified['broker'] == broker_name
            ]
            if unified_symbol in matches.index:
                row = matches.loc[unified_symbol]
                return row.to_dict()
        except Exception:
            pass
        
        return None
    
    def get_symbols_for_subscription(
        self,
        broker_name: str,
        indices: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all symbols that need to be subscribed for given indices.
        
        Args:
            broker_name: Broker name
            indices: List of indices (default: all supported)
        
        Returns:
            List of dicts with {unified_symbol, broker_symbol, token, exchange}
        """
        if self.df is None:
            return []
        
        if indices is None:
            indices = self.supported_indices
        
        # Filter by broker and indices
        filtered = self.df[
            (self.df['broker'] == broker_name) &
            (self.df['name'].isin(indices))
        ]
        
        symbols = []
        for idx, row in filtered.iterrows():
            symbols.append({
                'unified_symbol': row['unified_symbol'],
                'broker_symbol': row['tradingsymbol'],
                'token': int(row['instrument_token']) if pd.notna(row['instrument_token']) else None,
                'exchange': row.get('exchange', 'NFO'),
                'name': row['name'],
                'instrument_type': row.get('instrument_type', ''),
                'lot_size': int(row['lot_size']) if pd.notna(row.get('lot_size')) else 1
            })
        
        return symbols
    
    def is_loaded(self) -> bool:
        """Check if symbol cache is loaded."""
        return self.df is not None and len(self.df) > 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.df is None:
            return {'loaded': False}
        
        return {
            'loaded': True,
            'total_instruments': len(self.df),
            'brokers': self.brokers_loaded,
            'instruments_per_broker': {
                broker: len(self.df[self.df['broker'] == broker])
                for broker in self.brokers_loaded
            },
            'supported_indices': self.supported_indices
        }


# Singleton instance
_symbol_cache_manager = None

def get_symbol_cache_manager() -> SymbolCacheManager:
    """Get singleton instance of SymbolCacheManager."""
    global _symbol_cache_manager
    if _symbol_cache_manager is None:
        _symbol_cache_manager = SymbolCacheManager()
    return _symbol_cache_manager
