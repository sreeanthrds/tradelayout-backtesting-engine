"""
Instrument Master + LTP Store

Stores instrument master data along with real-time LTP updates.
Provides fast lookups and market scanning capabilities.

Features:
- In-memory store for fast access
- Real-time LTP updates via WebSocket
- Periodic snapshots to database
- Market scanning and filtering
- Options chain analysis
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path
import threading
import time


class InstrumentLTPStore:
    """
    Store instrument master data with real-time LTP updates.
    
    Features:
    - Fast in-memory lookups
    - Real-time LTP updates
    - Market scanning
    - Options chain analysis
    - Periodic persistence
    """
    
    def __init__(self, cache_dir: str = '/tmp'):
        """
        Initialize the store.
        
        Args:
            cache_dir: Directory for caching data
        """
        self.instruments = {}  # symbol -> instrument data
        self.token_map = {}    # token -> symbol (for WebSocket updates)
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / 'instrument_ltp_store.json'
        
        # Statistics
        self.total_instruments = 0
        self.instruments_with_ltp = 0
        self.last_update_time = None
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Auto-save settings
        self.auto_save_enabled = False
        self.auto_save_interval = 300  # 5 minutes
        self._auto_save_thread = None
        
    def load_instrument_master(self, instruments: List[Dict]) -> int:
        """
        Load instrument master data.
        
        Args:
            instruments: List of instrument dicts from AngelOne API
            
        Returns:
            Number of instruments loaded
        """
        with self.lock:
            count = 0
            for inst in instruments:
                symbol = inst.get('symbol')
                token = inst.get('token')
                
                if not symbol or not token:
                    continue
                
                # Parse strike price (in paise, convert to rupees)
                strike_str = inst.get('strike', '0')
                try:
                    strike = float(strike_str) / 100.0
                except (ValueError, TypeError):
                    strike = 0.0
                
                # Parse expiry date (handle both string and Timestamp)
                expiry_raw = inst.get('expiry', '')
                expiry_date = None
                if expiry_raw:
                    try:
                        # Check if it's already a datetime/Timestamp object
                        if hasattr(expiry_raw, 'date'):
                            expiry_date = expiry_raw.date()
                        # Otherwise try parsing as string
                        elif isinstance(expiry_raw, str) and expiry_raw.strip():
                            expiry_date = datetime.strptime(expiry_raw, '%d%b%Y').date()
                    except (ValueError, TypeError, AttributeError):
                        pass
                
                # Store instrument data
                self.instruments[symbol] = {
                    'token': token,
                    'symbol': symbol,
                    'name': inst.get('name', ''),
                    'expiry': expiry_date.isoformat() if expiry_date else None,
                    'strike': strike,
                    'lot_size': int(inst.get('lotsize', 1)),
                    'instrument_type': inst.get('instrumenttype', ''),
                    'exchange': inst.get('exch_seg', ''),
                    'tick_size': float(inst.get('tick_size', 0.05)),
                    # LTP fields (initially None)
                    'ltp': None,
                    'ltp_timestamp': None,
                    'volume': None,
                    'oi': None,
                    'bid': None,
                    'ask': None,
                    'high': None,
                    'low': None,
                    'open': None,
                    'close': None
                }
                
                # Create token -> symbol mapping
                self.token_map[token] = symbol
                count += 1
            
            self.total_instruments = count
            self.last_update_time = datetime.now()
            
            print(f"✅ Loaded {count:,} instruments into LTP store")
            return count
    
    def update_ltp(self, token: str, ltp_data: Dict) -> bool:
        """
        Update LTP for an instrument (called from WebSocket callback).
        
        Args:
            token: Instrument token
            ltp_data: LTP data from WebSocket
            
        Returns:
            True if updated successfully
        """
        with self.lock:
            symbol = self.token_map.get(token)
            if not symbol or symbol not in self.instruments:
                return False
            
            inst = self.instruments[symbol]
            
            # Update LTP fields
            inst['ltp'] = ltp_data.get('ltp') or ltp_data.get('last_traded_price')
            inst['ltp_timestamp'] = datetime.now().isoformat()
            inst['volume'] = ltp_data.get('volume')
            inst['oi'] = ltp_data.get('oi') or ltp_data.get('open_interest')
            inst['bid'] = ltp_data.get('best_bid_price')
            inst['ask'] = ltp_data.get('best_ask_price')
            inst['high'] = ltp_data.get('high')
            inst['low'] = ltp_data.get('low')
            inst['open'] = ltp_data.get('open')
            inst['close'] = ltp_data.get('close')
            
            # Update statistics
            if inst['ltp'] is not None:
                self.instruments_with_ltp = sum(
                    1 for i in self.instruments.values() if i['ltp'] is not None
                )
            
            return True
    
    def get_instrument(self, symbol: str) -> Optional[Dict]:
        """
        Get instrument data by symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Instrument dict or None
        """
        with self.lock:
            return self.instruments.get(symbol)
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get current LTP for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            LTP or None
        """
        inst = self.get_instrument(symbol)
        return inst['ltp'] if inst else None
    
    def search_instruments(self, 
                          name: str = None,
                          exchange: str = None,
                          instrument_type: str = None,
                          expiry_date: str = None,
                          min_strike: float = None,
                          max_strike: float = None,
                          has_ltp: bool = None) -> List[Dict]:
        """
        Search instruments by criteria.
        
        Args:
            name: Underlying name (e.g., 'NIFTY')
            exchange: Exchange (e.g., 'NFO')
            instrument_type: Instrument type (e.g., 'OPTIDX')
            expiry_date: Expiry date (ISO format)
            min_strike: Minimum strike price
            max_strike: Maximum strike price
            has_ltp: Filter by LTP availability
            
        Returns:
            List of matching instruments
        """
        with self.lock:
            results = []
            
            for inst in self.instruments.values():
                # Apply filters
                if name and inst['name'] != name:
                    continue
                if exchange and inst['exchange'] != exchange:
                    continue
                if instrument_type and inst['instrument_type'] != instrument_type:
                    continue
                if expiry_date and inst['expiry'] != expiry_date:
                    continue
                if min_strike is not None and inst['strike'] < min_strike:
                    continue
                if max_strike is not None and inst['strike'] > max_strike:
                    continue
                if has_ltp is not None and (inst['ltp'] is not None) != has_ltp:
                    continue
                
                results.append(inst.copy())
            
            return results
    
    def get_options_chain(self, 
                         underlying: str,
                         expiry_date: str,
                         exchange: str = 'NFO',
                         spot_price: float = None,
                         strike_range: int = 10) -> Dict[str, List[Dict]]:
        """
        Get options chain for an underlying.
        
        Args:
            underlying: Underlying name (e.g., 'NIFTY')
            expiry_date: Expiry date (ISO format)
            exchange: Exchange
            spot_price: Current spot price (for filtering strikes)
            strike_range: Number of strikes above/below spot
            
        Returns:
            Dict with 'CE' and 'PE' lists
        """
        # Get all options for this expiry
        options = self.search_instruments(
            name=underlying,
            exchange=exchange,
            instrument_type='OPTIDX',
            expiry_date=expiry_date
        )
        
        # Filter by strike range if spot_price provided
        if spot_price and strike_range:
            # Calculate strike interval (assume 50 for NIFTY, 100 for BANKNIFTY)
            interval = 50 if underlying == 'NIFTY' else 100
            min_strike = spot_price - (strike_range * interval)
            max_strike = spot_price + (strike_range * interval)
            
            options = [
                opt for opt in options
                if min_strike <= opt['strike'] <= max_strike
            ]
        
        # Separate CE and PE
        calls = [opt for opt in options if opt['symbol'].endswith('CE')]
        puts = [opt for opt in options if opt['symbol'].endswith('PE')]
        
        # Sort by strike
        calls.sort(key=lambda x: x['strike'])
        puts.sort(key=lambda x: x['strike'])
        
        return {
            'CE': calls,
            'PE': puts
        }
    
    def get_top_movers(self, limit: int = 10, by: str = 'volume') -> List[Dict]:
        """
        Get top moving instruments.
        
        Args:
            limit: Number of results
            by: Sort by 'volume', 'oi', or 'ltp'
            
        Returns:
            List of top instruments
        """
        with self.lock:
            # Filter instruments with LTP
            instruments_with_data = [
                inst for inst in self.instruments.values()
                if inst['ltp'] is not None and inst.get(by) is not None
            ]
            
            # Sort by criteria
            instruments_with_data.sort(key=lambda x: x.get(by, 0), reverse=True)
            
            return instruments_with_data[:limit]
    
    def save_to_file(self, filepath: str = None) -> bool:
        """
        Save store to JSON file.
        
        Args:
            filepath: Path to save file (default: cache_file)
            
        Returns:
            True if successful
        """
        if filepath is None:
            filepath = self.cache_file
        
        try:
            with self.lock:
                data = {
                    'instruments': self.instruments,
                    'token_map': self.token_map,
                    'metadata': {
                        'total_instruments': self.total_instruments,
                        'instruments_with_ltp': self.instruments_with_ltp,
                        'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None,
                        'saved_at': datetime.now().isoformat()
                    }
                }
                
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
                
                print(f"✅ Saved instrument LTP store to {filepath}")
                return True
                
        except Exception as e:
            print(f"❌ Error saving store: {e}")
            return False
    
    def load_from_file(self, filepath: str = None) -> bool:
        """
        Load store from JSON file.
        
        Args:
            filepath: Path to load file (default: cache_file)
            
        Returns:
            True if successful
        """
        if filepath is None:
            filepath = self.cache_file
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with self.lock:
                self.instruments = data['instruments']
                self.token_map = data['token_map']
                
                metadata = data.get('metadata', {})
                self.total_instruments = metadata.get('total_instruments', 0)
                self.instruments_with_ltp = metadata.get('instruments_with_ltp', 0)
                
                saved_at = metadata.get('saved_at')
                if saved_at:
                    print(f"✅ Loaded store from {filepath} (saved at {saved_at})")
                
                return True
                
        except FileNotFoundError:
            print(f"⚠️ Store file not found: {filepath}")
            return False
        except Exception as e:
            print(f"❌ Error loading store: {e}")
            return False
    
    def start_auto_save(self, interval: int = 300):
        """
        Start auto-save thread.
        
        Args:
            interval: Save interval in seconds (default: 5 minutes)
        """
        if self.auto_save_enabled:
            print("⚠️ Auto-save already running")
            return
        
        self.auto_save_enabled = True
        self.auto_save_interval = interval
        
        def auto_save_loop():
            while self.auto_save_enabled:
                time.sleep(self.auto_save_interval)
                if self.auto_save_enabled:
                    self.save_to_file()
        
        self._auto_save_thread = threading.Thread(target=auto_save_loop, daemon=True)
        self._auto_save_thread.start()
        
        print(f"✅ Auto-save started (interval: {interval}s)")
    
    def stop_auto_save(self):
        """Stop auto-save thread."""
        if self.auto_save_enabled:
            self.auto_save_enabled = False
            if self._auto_save_thread:
                self._auto_save_thread.join(timeout=5)
            print("✅ Auto-save stopped")
    
    def get_statistics(self) -> Dict:
        """
        Get store statistics.
        
        Returns:
            Statistics dict
        """
        with self.lock:
            return {
                'total_instruments': self.total_instruments,
                'instruments_with_ltp': self.instruments_with_ltp,
                'ltp_coverage': f"{(self.instruments_with_ltp / self.total_instruments * 100):.2f}%" if self.total_instruments > 0 else "0%",
                'last_update_time': self.last_update_time.isoformat() if self.last_update_time else None
            }
    
    def __repr__(self):
        return f"<InstrumentLTPStore: {self.total_instruments:,} instruments, {self.instruments_with_ltp:,} with LTP>"
