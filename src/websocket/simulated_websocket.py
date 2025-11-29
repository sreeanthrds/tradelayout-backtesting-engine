"""
Simulated WebSocket for Backtesting

Replays historical ticks from ClickHouse to simulate live trading.
- Queries ticks for specific date
- Sorts by timestamp
- Replays at max speed
- Emits to tick handlers (same interface as live WebSocket)
"""

from typing import List, Dict, Callable, Optional
from datetime import datetime, date
import clickhouse_connect

from src.config.clickhouse_config import ClickHouseConfig
from src.utils.logger import log_info, log_debug, log_warning, log_error


class SimulatedWebSocket:
    """
    Simulated WebSocket for backtesting.
    
    Replays historical ticks from ClickHouse to simulate live trading.
    """
    
    def __init__(
        self,
        backtest_date: str,
        symbols: List[str] = None,
        clickhouse_config: ClickHouseConfig = None
    ):
        """
        Initialize simulated WebSocket.
        
        Args:
            backtest_date: Date to backtest (YYYY-MM-DD)
            symbols: List of symbols to subscribe (None = all)
            clickhouse_config: ClickHouse configuration
        """
        self.backtest_date = backtest_date
        self.symbols = symbols or []
        self.config = clickhouse_config or ClickHouseConfig()
        
        # ClickHouse client
        self.client = None
        
        # Tick handlers
        self.tick_handlers: List[Callable] = []
        
        # Statistics
        self.total_ticks_processed = 0
        self.ticks_by_symbol: Dict[str, int] = {}
        
        # State
        self.is_running = False
        
        log_info(f"🎬 Simulated WebSocket initialized for {backtest_date}")
    
    def connect(self) -> bool:
        """Connect to ClickHouse."""
        try:
            self.client = clickhouse_connect.get_client(
                host=self.config.HOST,
                user=self.config.USER,
                password=self.config.PASSWORD,
                secure=self.config.SECURE,
                database=self.config.DATABASE
            )
            
            log_info("✅ Connected to ClickHouse for tick replay")
            return True
            
        except Exception as e:
            log_error(f"❌ Failed to connect to ClickHouse: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from ClickHouse."""
        if self.client:
            self.client.close()
            self.client = None
        
        log_info("🔌 Disconnected from ClickHouse")
    
    def subscribe_tick_handler(self, handler: Callable):
        """
        Subscribe to tick events.
        
        Args:
            handler: Callback function(tick_data: Dict)
        """
        self.tick_handlers.append(handler)
        log_debug(f"📡 Tick handler subscribed: {handler.__name__}")
    
    def _emit_tick(self, tick_data: Dict):
        """
        Emit tick to all handlers.
        
        Args:
            tick_data: Tick data dictionary
        """
        for handler in self.tick_handlers:
            try:
                handler(tick_data)
            except Exception as e:
                log_error(f"❌ Error in tick handler {handler.__name__}: {e}")
    
    def _query_index_ticks(self) -> List[Dict]:
        """
        Query index ticks from ClickHouse.
        
        Returns:
            List of tick dictionaries
        """
        query = f"""
        SELECT 
            symbol,
            timestamp,
            ltp,
            buy_price,
            buy_qty,
            sell_price,
            sell_qty,
            ltq,
            oi
        FROM nse_ticks_indices
        WHERE trading_day = '{self.backtest_date}'
        """
        
        if self.symbols:
            # Filter by symbols
            symbols_str = "', '".join(self.symbols)
            query += f" AND symbol IN ('{symbols_str}')"
        
        query += " ORDER BY timestamp ASC"
        
        log_info(f"📊 Querying index ticks for {self.backtest_date}...")
        
        try:
            result = self.client.query(query)
            
            ticks = []
            for row in result.result_rows:
                tick = {
                    'symbol': row[0],
                    'timestamp': row[1],
                    'ltp': float(row[2]),
                    'buy_price': float(row[3]) if row[3] else 0.0,
                    'buy_qty': int(row[4]) if row[4] else 0,
                    'sell_price': float(row[5]) if row[5] else 0.0,
                    'sell_qty': int(row[6]) if row[6] else 0,
                    'ltq': int(row[7]) if row[7] else 0,
                    'oi': int(row[8]) if row[8] else 0,
                    'instrument_type': 'INDEX'
                }
                ticks.append(tick)
            
            log_info(f"✅ Loaded {len(ticks)} index ticks")
            return ticks
            
        except Exception as e:
            log_error(f"❌ Failed to query index ticks: {e}")
            return []
    
    def _query_option_ticks(self) -> List[Dict]:
        """
        Query option ticks from ClickHouse.
        
        Returns:
            List of tick dictionaries
        """
        query = f"""
        SELECT 
            underlying,
            ticker,
            expiry_date,
            strike_price,
            option_type,
            timestamp,
            ltp,
            buy_price,
            buy_qty,
            sell_price,
            sell_qty,
            ltq,
            oi
        FROM nse_ticks_options
        WHERE trading_day = '{self.backtest_date}'
        ORDER BY timestamp ASC
        """
        
        log_info(f"📊 Querying option ticks for {self.backtest_date}...")
        
        try:
            result = self.client.query(query)
            
            ticks = []
            for row in result.result_rows:
                tick = {
                    'underlying': row[0],
                    'symbol': row[1],  # ticker (e.g., BANKNIFTY03JAN2437500PE.NFO)
                    'expiry_date': row[2],
                    'strike_price': float(row[3]),
                    'option_type': row[4],
                    'timestamp': row[5],
                    'ltp': float(row[6]),
                    'buy_price': float(row[7]) if row[7] else 0.0,
                    'buy_qty': int(row[8]) if row[8] else 0,
                    'sell_price': float(row[9]) if row[9] else 0.0,
                    'sell_qty': int(row[10]) if row[10] else 0,
                    'ltq': int(row[11]) if row[11] else 0,
                    'oi': int(row[12]) if row[12] else 0,
                    'instrument_type': 'OPTION'
                }
                ticks.append(tick)
            
            log_info(f"✅ Loaded {len(ticks)} option ticks")
            return ticks
            
        except Exception as e:
            log_error(f"❌ Failed to query option ticks: {e}")
            return []
    
    def _merge_and_sort_ticks(self, index_ticks: List[Dict], option_ticks: List[Dict]) -> List[Dict]:
        """
        Merge and sort ticks by timestamp.
        
        Args:
            index_ticks: Index ticks
            option_ticks: Option ticks
            
        Returns:
            Sorted list of all ticks
        """
        all_ticks = index_ticks + option_ticks
        
        # Sort by timestamp
        all_ticks.sort(key=lambda x: x['timestamp'])
        
        log_info(f"✅ Merged and sorted {len(all_ticks)} total ticks")
        return all_ticks
    
    def replay_ticks(self, include_options: bool = True) -> int:
        """
        Replay all ticks for the backtest date.
        
        Args:
            include_options: Include option ticks (default: True)
            
        Returns:
            Number of ticks processed
        """
        if not self.client:
            log_error("❌ Not connected to ClickHouse")
            return 0
        
        self.is_running = True
        self.total_ticks_processed = 0
        self.ticks_by_symbol.clear()
        
        # Query ticks
        index_ticks = self._query_index_ticks()
        option_ticks = self._query_option_ticks() if include_options else []
        
        # Merge and sort
        all_ticks = self._merge_and_sort_ticks(index_ticks, option_ticks)
        
        if not all_ticks:
            log_warning(f"⚠️  No ticks found for {self.backtest_date}")
            return 0
        
        # Replay ticks
        log_info(f"▶️  Starting tick replay: {len(all_ticks)} ticks")
        log_info(f"⏱️  Time range: {all_ticks[0]['timestamp']} to {all_ticks[-1]['timestamp']}")
        
        start_time = datetime.now()
        
        for i, tick in enumerate(all_ticks):
            if not self.is_running:
                log_warning("⏸️  Tick replay stopped")
                break
            
            # Emit tick
            self._emit_tick(tick)
            
            # Update statistics
            self.total_ticks_processed += 1
            symbol = tick.get('symbol', 'UNKNOWN')
            self.ticks_by_symbol[symbol] = self.ticks_by_symbol.get(symbol, 0) + 1
            
            # Progress logging (every 10000 ticks)
            if (i + 1) % 10000 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                ticks_per_sec = (i + 1) / elapsed if elapsed > 0 else 0
                progress = ((i + 1) / len(all_ticks)) * 100
                log_info(f"📈 Progress: {i+1}/{len(all_ticks)} ({progress:.1f}%) | {ticks_per_sec:.0f} ticks/sec")
        
        # Final statistics
        elapsed = (datetime.now() - start_time).total_seconds()
        ticks_per_sec = self.total_ticks_processed / elapsed if elapsed > 0 else 0
        
        log_info(f"✅ Tick replay complete!")
        log_info(f"   Total ticks: {self.total_ticks_processed}")
        log_info(f"   Time elapsed: {elapsed:.2f} seconds")
        log_info(f"   Speed: {ticks_per_sec:.0f} ticks/second")
        log_info(f"   Unique symbols: {len(self.ticks_by_symbol)}")
        
        return self.total_ticks_processed
    
    def stop(self):
        """Stop tick replay."""
        self.is_running = False
        log_info("⏹️  Tick replay stopped")
    
    def get_statistics(self) -> Dict:
        """
        Get replay statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            'backtest_date': self.backtest_date,
            'total_ticks_processed': self.total_ticks_processed,
            'unique_symbols': len(self.ticks_by_symbol),
            'ticks_by_symbol': self.ticks_by_symbol.copy()
        }


# Example usage
if __name__ == '__main__':
    # Initialize simulated WebSocket
    websocket = SimulatedWebSocket(
        backtest_date='2024-10-01',
        symbols=['NIFTY', 'BANKNIFTY']
    )
    
    # Define tick handler
    def on_tick(tick_data):
        print(f"Tick: {tick_data['symbol']} @ {tick_data['ltp']:.2f}")
    
    # Subscribe handler
    websocket.subscribe_tick_handler(on_tick)
    
    # Connect and replay
    if websocket.connect():
        websocket.replay_ticks(include_options=False)
        websocket.disconnect()
    
    # Print statistics
    stats = websocket.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total ticks: {stats['total_ticks_processed']}")
    print(f"  Unique symbols: {stats['unique_symbols']}")
