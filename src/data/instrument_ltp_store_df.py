"""
DataFrame-Based Instrument Master + LTP Store

Simplified implementation using pandas DataFrame for efficient querying.
Stores the entire AngelOne scrip master as a DataFrame.

Features:
- Fast DataFrame queries
- Simple and clean code
- Easy filtering and searching
- Real-time LTP updates
- Minimal memory overhead
"""

import pandas as pd
import requests
from typing import Optional, Dict, List
from datetime import datetime
import threading


class InstrumentLTPStore:
    """
    DataFrame-based instrument master + LTP store.
    
    Stores entire AngelOne scrip master as pandas DataFrame.
    Provides fast queries and real-time LTP updates.
    """
    
    def __init__(self):
        """Initialize the store."""
        self.df = None  # Main DataFrame with all instruments
        self.lock = threading.RLock()
        self.last_update_time = None
    
    def load_instrument_master(self, force_refresh: bool = False) -> int:
        """
        Load instrument master from AngelOne API.
        
        Args:
            force_refresh: Force download even if already loaded
            
        Returns:
            Number of instruments loaded
        """
        with self.lock:
            if self.df is not None and not force_refresh:
                print(f"✅ Instrument master already loaded ({len(self.df):,} instruments)")
                return len(self.df)
            
            print("📥 Downloading instrument master from AngelOne...")
            
            try:
                # Download scrip master
                url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                # Convert to DataFrame
                self.df = pd.DataFrame(response.json())
                
                # Normalize column names to lowercase
                self.df.columns = [c.lower() for c in self.df.columns]
                
                # Add LTP columns (initially None)
                self.df['ltp'] = None
                self.df['ltp_timestamp'] = None
                self.df['volume_live'] = None
                self.df['oi_live'] = None
                
                # Convert strike to float (from paise to rupees)
                if 'strike' in self.df.columns:
                    self.df['strike'] = pd.to_numeric(self.df['strike'], errors='coerce') / 100.0
                
                # Parse expiry dates
                if 'expiry' in self.df.columns:
                    self.df['expiry'] = pd.to_datetime(self.df['expiry'], errors='coerce')
                
                # Convert token to string for easy lookup
                if 'token' in self.df.columns:
                    self.df['token'] = self.df['token'].astype(str)
                
                self.last_update_time = datetime.now()
                
                print(f"✅ Loaded {len(self.df):,} instruments")
                print(f"   Columns: {list(self.df.columns)}")
                
                return len(self.df)
                
            except Exception as e:
                print(f"❌ Error loading instrument master: {e}")
                raise
    
    def update_ltp(self, token: str, ltp_data: Dict) -> bool:
        """
        Update LTP for an instrument.
        
        Args:
            token: Instrument token
            ltp_data: LTP data from WebSocket
            
        Returns:
            True if updated successfully
        """
        with self.lock:
            if self.df is None:
                return False
            
            # Find instrument by token
            mask = self.df['token'] == str(token)
            
            if not mask.any():
                return False
            
            # Update LTP fields
            self.df.loc[mask, 'ltp'] = ltp_data.get('ltp') or ltp_data.get('last_traded_price')
            self.df.loc[mask, 'ltp_timestamp'] = datetime.now()
            self.df.loc[mask, 'volume_live'] = ltp_data.get('volume')
            self.df.loc[mask, 'oi_live'] = ltp_data.get('oi') or ltp_data.get('open_interest')
            
            return True
    
    def get_instrument(self, symbol: str) -> Optional[Dict]:
        """
        Get instrument by symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Instrument dict or None
        """
        with self.lock:
            if self.df is None:
                return None
            
            result = self.df[self.df['symbol'] == symbol]
            
            if result.empty:
                return None
            
            return result.iloc[0].to_dict()
    
    def get_index_instrument(self, index_name: str) -> Optional[Dict]:
        """
        Get index instrument (e.g., NIFTY, BANKNIFTY).
        Indices have empty instrumenttype.
        
        Args:
            index_name: Index name (e.g., 'NIFTY', 'BANKNIFTY')
            
        Returns:
            Instrument dict or None
        """
        with self.lock:
            if self.df is None:
                return None
            
            # For indices, instrumenttype is empty/blank
            result = self.df[
                (self.df['name'] == index_name) & 
                (self.df['instrumenttype'] == "")
            ]
            
            if result.empty:
                return None
            
            return result.iloc[0].to_dict()
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get current LTP for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            LTP or None
        """
        inst = self.get_instrument(symbol)
        return inst.get('ltp') if inst else None
    
    def search_instruments(self,
                          name: str = None,
                          exchange: str = None,
                          instrument_type: str = None,
                          expiry_date: datetime = None,
                          min_strike: float = None,
                          max_strike: float = None) -> pd.DataFrame:
        """
        Search instruments using DataFrame queries.
        
        Args:
            name: Underlying name (e.g., 'NIFTY')
            exchange: Exchange segment (e.g., 'NFO', 'NSE')
            instrument_type: Instrument type (e.g., 'OPTIDX', 'FUTIDX', '' for index)
            expiry_date: Expiry date
            min_strike: Minimum strike price
            max_strike: Maximum strike price
            
        Returns:
            DataFrame with matching instruments
        
        Examples:
            # Get NIFTY index
            search_instruments(name='NIFTY', instrument_type='')
            
            # Get NIFTY options
            search_instruments(name='NIFTY', instrument_type='OPTIDX')
            
            # Get NIFTY futures
            search_instruments(name='NIFTY', instrument_type='FUTIDX')
        """
        with self.lock:
            if self.df is None:
                return pd.DataFrame()
            
            # Start with all instruments
            result = self.df.copy()
            
            # Apply filters
            if name is not None:
                result = result[result['name'] == name]
            
            if exchange is not None:
                result = result[result['exch_seg'] == exchange]
            
            if instrument_type is not None:
                if instrument_type == '':
                    # For index, instrumenttype is empty
                    result = result[result['instrumenttype'] == '']
                elif 'OPT' in instrument_type:
                    # For options, use contains (handles OPTIDX, OPTSTK, etc.)
                    result = result[result['instrumenttype'].str.contains(instrument_type, na=False)]
                else:
                    # Exact match for others (FUTIDX, FUTSTK, etc.)
                    result = result[result['instrumenttype'] == instrument_type]
            
            if expiry_date is not None:
                result = result[result['expiry'] == expiry_date]
            
            if min_strike is not None:
                result = result[result['strike'] >= min_strike]
            
            if max_strike is not None:
                result = result[result['strike'] <= max_strike]
            
            return result
    
    def get_available_expiries(self, 
                               underlying: str,
                               exchange: str = 'NFO',
                               instrument_type: str = 'OPTIDX') -> List[datetime]:
        """
        Get available expiry dates for an underlying.
        
        Args:
            underlying: Underlying name (e.g., 'NIFTY')
            exchange: Exchange segment
            instrument_type: Instrument type (e.g., 'OPTIDX', 'FUTIDX')
            
        Returns:
            List of expiry dates (sorted)
        """
        with self.lock:
            if self.df is None:
                return []
            
            # Filter instruments using correct logic
            if 'OPT' in instrument_type:
                # For options, use contains
                mask = (
                    (self.df['name'] == underlying) &
                    (self.df['exch_seg'] == exchange) &
                    (self.df['instrumenttype'].str.contains(instrument_type, na=False)) &
                    (self.df['expiry'].notna())
                )
            else:
                # For futures, exact match
                mask = (
                    (self.df['name'] == underlying) &
                    (self.df['exch_seg'] == exchange) &
                    (self.df['instrumenttype'] == instrument_type) &
                    (self.df['expiry'].notna())
                )
            
            expiries = self.df[mask]['expiry'].unique()
            expiries = sorted([pd.Timestamp(e) for e in expiries if pd.notna(e)])
            
            return expiries
    
    def get_options_chain(self,
                         underlying: str,
                         expiry_date: datetime,
                         exchange: str = 'NFO',
                         spot_price: float = None,
                         strike_range: int = 10) -> Dict[str, pd.DataFrame]:
        """
        Get options chain for an underlying.
        
        Args:
            underlying: Underlying name (e.g., 'NIFTY')
            expiry_date: Expiry date
            exchange: Exchange segment
            spot_price: Current spot price (for filtering)
            strike_range: Number of strikes above/below spot
            
        Returns:
            Dict with 'CE' and 'PE' DataFrames
        """
        with self.lock:
            if self.df is None:
                return {'CE': pd.DataFrame(), 'PE': pd.DataFrame()}
            
            # Get all options for this expiry
            options = self.search_instruments(
                name=underlying,
                exchange=exchange,
                instrument_type='OPTIDX',
                expiry_date=expiry_date
            )
            
            # Filter by strike range if spot_price provided
            if spot_price and strike_range:
                # Determine strike interval
                interval = 50 if underlying == 'NIFTY' else 100
                min_strike = spot_price - (strike_range * interval)
                max_strike = spot_price + (strike_range * interval)
                
                options = options[
                    (options['strike'] >= min_strike) &
                    (options['strike'] <= max_strike)
                ]
            
            # Separate CE and PE
            calls = options[options['symbol'].str.endswith('CE')].sort_values('strike')
            puts = options[options['symbol'].str.endswith('PE')].sort_values('strike')
            
            return {'CE': calls, 'PE': puts}
    
    def get_statistics(self) -> Dict:
        """
        Get store statistics.
        
        Returns:
            Statistics dict
        """
        with self.lock:
            if self.df is None:
                return {
                    'total_instruments': 0,
                    'instruments_with_ltp': 0,
                    'ltp_coverage': '0%'
                }
            
            total = len(self.df)
            with_ltp = self.df['ltp'].notna().sum()
            
            return {
                'total_instruments': total,
                'instruments_with_ltp': with_ltp,
                'ltp_coverage': f"{(with_ltp / total * 100):.2f}%" if total > 0 else "0%",
                'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None
            }
    
    def save_to_parquet(self, filepath: str):
        """
        Save DataFrame to parquet file (efficient storage).
        
        Args:
            filepath: Path to save file
        """
        with self.lock:
            if self.df is None:
                print("⚠️ No data to save")
                return
            
            self.df.to_parquet(filepath, compression='gzip')
            print(f"✅ Saved instrument master to {filepath}")
    
    def load_from_parquet(self, filepath: str) -> int:
        """
        Load DataFrame from parquet file.
        
        Args:
            filepath: Path to load file
            
        Returns:
            Number of instruments loaded
        """
        with self.lock:
            self.df = pd.read_parquet(filepath)
            self.last_update_time = datetime.now()
            print(f"✅ Loaded {len(self.df):,} instruments from {filepath}")
            return len(self.df)
    
    def __repr__(self):
        if self.df is None:
            return "<InstrumentLTPStore: Not loaded>"
        
        total = len(self.df)
        with_ltp = self.df['ltp'].notna().sum()
        return f"<InstrumentLTPStore: {total:,} instruments, {with_ltp:,} with LTP>"
