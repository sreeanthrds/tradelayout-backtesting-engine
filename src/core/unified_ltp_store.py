"""
Unified LTP Store - Thread-safe, encapsulated LTP storage.

This module provides a centralized LTP store that:
1. Stores LTP for all symbols (spot, futures, options)
2. Thread-safe (optional, for live trading)
3. Clean interface (methods instead of direct dict access)
4. Backward compatible (dict-like access)

Author: UniTrader Team
Created: 2024-11-12
"""

import threading
from typing import Dict, Any, Optional
from datetime import datetime
from src.utils.logger import log_debug


class UnifiedLTPStore:
    """
    Unified LTP store for centralized tick processor.
    
    Features:
    - Symbol-based storage (no role-based, that's per-strategy)
    - Thread-safe (optional, for live trading)
    - Clean interface (get_ltp, update, etc.)
    - Backward compatible (dict-like access: store['NIFTY'])
    
    Usage:
        # Backtesting (no thread safety needed)
        store = UnifiedLTPStore(thread_safe=False)
        
        # Live trading (thread-safe)
        store = UnifiedLTPStore(thread_safe=True)
        
        # Update
        store.update('NIFTY', 25850.50, timestamp)
        
        # Access
        ltp = store.get_ltp('NIFTY')
        tick_data = store.get_tick_data('NIFTY')
        tick_data = store['NIFTY']  # Dict-like
    """
    
    def __init__(self, thread_safe: bool = False):
        """
        Initialize unified LTP store.
        
        Args:
            thread_safe: Enable thread safety (use Lock). 
                        Set to True for live trading, False for backtesting.
        """
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock() if thread_safe else None
        self._thread_safe = thread_safe
        
        log_debug(f"📊 UnifiedLTPStore initialized (thread_safe={thread_safe})")
    
    def update(
        self, 
        symbol: str, 
        ltp: float, 
        timestamp: Any = None,
        volume: int = 0,
        oi: int = 0,
        **kwargs
    ):
        """
        Update LTP for a symbol.
        
        Args:
            symbol: Symbol name (e.g., 'NIFTY', 'NIFTY:2024-10-28:OPT:25850:CE')
            ltp: Last traded price
            timestamp: Tick timestamp (optional)
            volume: Volume (optional)
            oi: Open interest (optional)
            **kwargs: Additional fields to store
        
        Example:
            store.update('NIFTY', 25850.50, timestamp, volume=1000, oi=5000)
        """
        if not symbol:
            raise ValueError("Symbol is required")
        
        if ltp is None or ltp < 0:
            raise ValueError(f"Invalid LTP: {ltp}")
        
        # Prepare data
        data = {
            'ltp': float(ltp),
            'timestamp': timestamp or datetime.now(),
            'volume': int(volume),
            'oi': int(oi)
        }
        
        # Add any additional fields
        data.update(kwargs)
        
        # Store with thread safety if enabled
        if self._lock:
            with self._lock:
                self._store[symbol] = data
        else:
            self._store[symbol] = data
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get LTP for a symbol.
        
        Args:
            symbol: Symbol name
        
        Returns:
            LTP value or None if symbol not found
        
        Example:
            ltp = store.get_ltp('NIFTY')  # Returns 25850.50 or None
        """
        if self._lock:
            with self._lock:
                data = self._store.get(symbol)
        else:
            data = self._store.get(symbol)
        
        return data.get('ltp') if data else None
    
    def get_tick_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get full tick data for a symbol.
        
        Args:
            symbol: Symbol name
        
        Returns:
            Dict with ltp, timestamp, volume, oi or None if not found
        
        Example:
            data = store.get_tick_data('NIFTY')
            # Returns: {'ltp': 25850.50, 'timestamp': ..., 'volume': 1000, 'oi': 5000}
        """
        if self._lock:
            with self._lock:
                return self._store.get(symbol)
        else:
            return self._store.get(symbol)
    
    def get(self, symbol: str, default=None) -> Optional[Dict[str, Any]]:
        """
        Dict-like get method for backward compatibility.
        
        Args:
            symbol: Symbol name
            default: Default value if symbol not found
        
        Returns:
            Tick data dict or default
        
        Example:
            data = store.get('NIFTY', {})
        """
        if self._lock:
            with self._lock:
                return self._store.get(symbol, default)
        else:
            return self._store.get(symbol, default)
    
    def __getitem__(self, symbol: str) -> Dict[str, Any]:
        """
        Dict-like access: store['NIFTY']
        
        Args:
            symbol: Symbol name
        
        Returns:
            Tick data dict
        
        Raises:
            KeyError: If symbol not found
        
        Example:
            data = store['NIFTY']
            ltp = store['NIFTY']['ltp']
        """
        if self._lock:
            with self._lock:
                return self._store[symbol]
        else:
            return self._store[symbol]
    
    def __setitem__(self, symbol: str, data: Dict[str, Any]):
        """
        Dict-like assignment: store['NIFTY'] = {...}
        
        Args:
            symbol: Symbol name
            data: Tick data dict
        
        Example:
            store['NIFTY'] = {'ltp': 25850.50, 'timestamp': ...}
        """
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
        
        if self._lock:
            with self._lock:
                self._store[symbol] = data
        else:
            self._store[symbol] = data
    
    def __contains__(self, symbol: str) -> bool:
        """
        Check if symbol exists: 'NIFTY' in store
        
        Args:
            symbol: Symbol name
        
        Returns:
            True if symbol exists, False otherwise
        
        Example:
            if 'NIFTY' in store:
                print("NIFTY exists")
        """
        if self._lock:
            with self._lock:
                return symbol in self._store
        else:
            return symbol in self._store
    
    def keys(self):
        """
        Get all symbols (dict-like).
        
        Returns:
            Dict keys view of all symbols
        
        Example:
            for symbol in store.keys():
                print(symbol)
        """
        if self._lock:
            with self._lock:
                return list(self._store.keys())
        else:
            return list(self._store.keys())
    
    def values(self):
        """
        Get all tick data (dict-like).
        
        Returns:
            List of all tick data dicts
        
        Example:
            for data in store.values():
                print(data['ltp'])
        """
        if self._lock:
            with self._lock:
                return list(self._store.values())
        else:
            return list(self._store.values())
    
    def items(self):
        """
        Get all (symbol, data) pairs (dict-like).
        
        Returns:
            List of (symbol, data) tuples
        
        Example:
            for symbol, data in store.items():
                print(f"{symbol}: {data['ltp']}")
        """
        if self._lock:
            with self._lock:
                return list(self._store.items())
        else:
            return list(self._store.items())
    
    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        Export as plain dict for context (backward compatibility).
        
        Returns:
            Copy of internal store as dict
        
        Example:
            context['ltp_store'] = store.to_dict()
        """
        if self._lock:
            with self._lock:
                return self._store.copy()
        else:
            return self._store.copy()
    
    def clear(self):
        """
        Clear all data.
        
        Example:
            store.clear()
        """
        if self._lock:
            with self._lock:
                self._store.clear()
        else:
            self._store.clear()
    
    def __len__(self) -> int:
        """
        Get number of symbols: len(store)
        
        Returns:
            Number of symbols in store
        
        Example:
            print(f"Store has {len(store)} symbols")
        """
        if self._lock:
            with self._lock:
                return len(self._store)
        else:
            return len(self._store)
    
    def __repr__(self) -> str:
        """String representation."""
        thread_safe_str = "thread-safe" if self._thread_safe else "not thread-safe"
        return f"UnifiedLTPStore({len(self)} symbols, {thread_safe_str})"
