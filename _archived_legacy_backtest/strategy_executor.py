"""
Strategy Executor

Executes strategy logic:
- Evaluates entry/exit conditions on every tick
- Manages positions
- Calculates PnL
- Tracks performance
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position."""
    position_id: str
    entry_time: datetime
    symbol: str  # Option symbol (e.g., NIFTY:26400:CE:W0)
    strike: int
    option_type: str  # CE or PE
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    
    def update_price(self, price: float):
        """Update current price and unrealized PnL."""
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.quantity


@dataclass
class Trade:
    """Represents a completed trade."""
    trade_id: str
    entry_time: datetime
    exit_time: datetime
    symbol: str
    strike: int
    option_type: str
    quantity: int
    entry_price: float
    exit_price: float
    realized_pnl: float
    duration_seconds: float


class StrategyExecutor:
    """
    Executes strategy logic on every tick.
    
    Features:
    - Evaluates conditions on every tick (not waiting for candle completion)
    - Uses previous completed candle for comparison
    - Manages positions and calculates PnL
    """
    
    def __init__(self, strategy_config: dict, option_data: Dict):
        """
        Initialize strategy executor.
        
        Args:
            strategy_config: Strategy configuration from Supabase
            option_data: Option tick data loaded from ClickHouse
        """
        self.strategy_config = strategy_config
        self.option_data = option_data
        
        # Candle tracking
        self.previous_candle: Optional[Dict] = None
        self.current_candle_data: Optional[Dict] = None
        
        # Position tracking
        self.open_positions: Dict[str, Position] = {}
        self.closed_trades: List[Trade] = []
        self.next_position_id = 1
        self.next_trade_id = 1
        
        # Trade tracking (max 1 CE and 1 PE per day)
        self.ce_trade_taken = False
        self.pe_trade_taken = False
        
        # Performance tracking
        self.total_pnl = 0.0
        self.winning_trades = 0
        self.losing_trades = 0
        
        logger.info(f"StrategyExecutor initialized for: {strategy_config.get('name', 'Unknown')}")
    
    def _update_candle(self, tick) -> bool:
        """
        Update candle with tick data.
        
        Args:
            tick: Current tick
            
        Returns:
            True if a new candle started (previous candle completed)
        """
        tick_minute = tick.timestamp.replace(second=0, microsecond=0)
        
        # Check if new minute started
        if self.current_candle_data is None or tick_minute != self.current_candle_data['timestamp']:
            # Save previous candle
            if self.current_candle_data:
                self.previous_candle = self.current_candle_data.copy()
                logger.debug(f"Candle completed: {self.previous_candle['timestamp']} "
                           f"H={self.previous_candle['high']:.2f} L={self.previous_candle['low']:.2f}")
            
            # Start new candle
            self.current_candle_data = {
                'timestamp': tick_minute,
                'open': tick.ltp,
                'high': tick.ltp,
                'low': tick.ltp,
                'close': tick.ltp
            }
            
            return True  # New candle started
        
        # Update current candle
        self.current_candle_data['high'] = max(self.current_candle_data['high'], tick.ltp)
        self.current_candle_data['low'] = min(self.current_candle_data['low'], tick.ltp)
        self.current_candle_data['close'] = tick.ltp
        
        return False  # Same candle continuing
    
    def _calculate_otm_strike(self, spot: float, otm_level: int, option_type: str) -> int:
        """
        Calculate OTM strike.
        
        Args:
            spot: Current spot price
            otm_level: Number of strikes OTM (e.g., 10 for OTM10)
            option_type: CE or PE
            
        Returns:
            Strike price
        """
        # Round to nearest 50
        atm = round(spot / 50) * 50
        
        if option_type == 'CE':
            # For CALL, OTM is above spot
            strike = atm + (otm_level * 50)
        else:  # PE
            # For PUT, OTM is below spot
            strike = atm - (otm_level * 50)
        
        return strike
    
    def _get_option_price(self, strike: int, option_type: str, timestamp: datetime) -> Optional[float]:
        """
        Get option price at specific timestamp.
        
        Args:
            strike: Strike price
            option_type: CE or PE
            timestamp: Timestamp to get price for
            
        Returns:
            Option LTP or None if not available
        """
        contract_id = f"NIFTY:{strike}:{option_type}:W0"
        
        if contract_id not in self.option_data:
            return None
        
        ticks = self.option_data[contract_id]
        
        # Find closest tick (linear search for now)
        for tick_ts, ltp, oi in ticks:
            if tick_ts >= timestamp:
                return ltp
        
        # Return last price if timestamp is after all ticks
        if ticks:
            return ticks[-1][1]
        
        return None
    
    def _check_call_entry(self, tick) -> bool:
        """
        Check if CALL entry condition is met.
        
        Condition: Current LTP > Previous candle High
        
        Args:
            tick: Current tick
            
        Returns:
            True if condition met
        """
        if not self.previous_candle:
            return False
        
        return tick.ltp > self.previous_candle['high']
    
    def _check_put_entry(self, tick) -> bool:
        """
        Check if PUT entry condition is met.
        
        Condition: Current LTP < Previous candle Low
        
        Args:
            tick: Current tick
            
        Returns:
            True if condition met
        """
        if not self.previous_candle:
            return False
        
        return tick.ltp < self.previous_candle['low']
    
    def _check_call_exit(self, tick) -> bool:
        """
        Check if CALL exit condition is met.
        
        Condition: Current LTP < Previous candle Low
        
        Args:
            tick: Current tick
            
        Returns:
            True if condition met
        """
        if not self.previous_candle:
            return False
        
        return tick.ltp < self.previous_candle['low']
    
    def _check_put_exit(self, tick) -> bool:
        """
        Check if PUT exit condition is met.
        
        Condition: Current LTP > Previous candle High
        
        Args:
            tick: Current tick
            
        Returns:
            True if condition met
        """
        if not self.previous_candle:
            return False
        
        return tick.ltp > self.previous_candle['high']
    
    def _enter_position(self, tick, option_type: str):
        """
        Enter a new position.
        
        Args:
            tick: Current tick
            option_type: CE or PE
        """
        # Check if we've already taken this type of trade
        if option_type == 'CE' and self.ce_trade_taken:
            return
        if option_type == 'PE' and self.pe_trade_taken:
            return
        
        # Calculate OTM10 strike
        strike = self._calculate_otm_strike(tick.ltp, 10, option_type)
        
        # Get option price
        option_price = self._get_option_price(strike, option_type, tick.timestamp)
        
        if option_price is None:
            logger.warning(f"No option price available for {strike} {option_type} at {tick.timestamp}")
            return
        
        # Mark this trade type as taken
        if option_type == 'CE':
            self.ce_trade_taken = True
        else:
            self.pe_trade_taken = True
        
        # Create position
        position_id = f"pos_{self.next_position_id}"
        self.next_position_id += 1
        
        position = Position(
            position_id=position_id,
            entry_time=tick.timestamp,
            symbol=f"NIFTY:{strike}:{option_type}:W0",
            strike=strike,
            option_type=option_type,
            quantity=50,  # NIFTY lot size
            entry_price=option_price,
            current_price=option_price,
            unrealized_pnl=0.0
        )
        
        self.open_positions[position_id] = position
        
        logger.info(f"✅ ENTRY: {option_type} at {tick.timestamp.strftime('%H:%M:%S')}")
        logger.info(f"   Spot: {tick.ltp:.2f} | Strike: {strike} | Price: {option_price:.2f}")
    
    def _exit_position(self, position: Position, tick):
        """
        Exit an open position.
        
        Args:
            position: Position to exit
            tick: Current tick
        """
        # Get exit price
        exit_price = self._get_option_price(position.strike, position.option_type, tick.timestamp)
        
        if exit_price is None:
            logger.warning(f"No exit price available for {position.symbol} at {tick.timestamp}")
            return
        
        # Calculate PnL
        realized_pnl = (exit_price - position.entry_price) * position.quantity
        duration = (tick.timestamp - position.entry_time).total_seconds()
        
        # Create trade record
        trade_id = f"trade_{self.next_trade_id}"
        self.next_trade_id += 1
        
        trade = Trade(
            trade_id=trade_id,
            entry_time=position.entry_time,
            exit_time=tick.timestamp,
            symbol=position.symbol,
            strike=position.strike,
            option_type=position.option_type,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            duration_seconds=duration
        )
        
        self.closed_trades.append(trade)
        
        # Update statistics
        self.total_pnl += realized_pnl
        if realized_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Remove from open positions
        del self.open_positions[position.position_id]
        
        logger.info(f"❌ EXIT: {position.option_type} at {tick.timestamp.strftime('%H:%M:%S')}")
        logger.info(f"   Strike: {position.strike} | Entry: {position.entry_price:.2f} | Exit: {exit_price:.2f}")
        logger.info(f"   PnL: ₹{realized_pnl:.2f} | Duration: {duration:.0f}s")
    
    def process_tick(self, tick):
        """
        Process a single tick.
        
        This is called for every tick in chronological order.
        
        Args:
            tick: Market tick
        """
        # Update candle
        self._update_candle(tick)
        
        # Skip if no previous candle yet
        if not self.previous_candle:
            return
        
        # Check exit conditions first (for open positions)
        positions_to_exit = []
        
        for position_id, position in self.open_positions.items():
            if position.option_type == 'CE':
                # Exit CALL if price drops below previous low
                if self._check_call_exit(tick):
                    positions_to_exit.append(position)
            else:  # PE
                # Exit PUT if price rises above previous high
                if self._check_put_exit(tick):
                    positions_to_exit.append(position)
        
        # Exit positions
        for position in positions_to_exit:
            self._exit_position(position, tick)
        
        # Check entry conditions (only if no open positions)
        if not self.open_positions:
            # Check CALL entry
            if self._check_call_entry(tick):
                self._enter_position(tick, 'CE')
            
            # Check PUT entry
            elif self._check_put_entry(tick):
                self._enter_position(tick, 'PE')
    
    def get_statistics(self) -> Dict:
        """Get performance statistics."""
        total_trades = len(self.closed_trades)
        win_rate = (self.winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_pnl,
            'open_positions': len(self.open_positions)
        }
    
    def print_summary(self):
        """Print performance summary."""
        stats = self.get_statistics()
        
        print("\n" + "="*70)
        print("📊 STRATEGY PERFORMANCE SUMMARY")
        print("="*70)
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Winning Trades: {stats['winning_trades']}")
        print(f"Losing Trades: {stats['losing_trades']}")
        print(f"Win Rate: {stats['win_rate']:.1f}%")
        print(f"Total PnL: ₹{stats['total_pnl']:,.2f}")
        print(f"Open Positions: {stats['open_positions']}")
        print("="*70)
        
        # Print all context/variables
        print("\n" + "="*70)
        print("📋 ALL VARIABLES & CONTEXT")
        print("="*70)
        
        print(f"\n🔢 Closed Trades ({len(self.closed_trades)}):")
        for i, trade in enumerate(self.closed_trades, 1):
            print(f"  Trade {i}:")
            print(f"    Type: {trade.option_type}")
            print(f"    Strike: {trade.strike}")
            print(f"    Entry: ₹{trade.entry_price:.2f} @ {trade.entry_time.strftime('%H:%M:%S')}")
            print(f"    Exit: ₹{trade.exit_price:.2f} @ {trade.exit_time.strftime('%H:%M:%S')}")
            print(f"    PnL: ₹{trade.realized_pnl:.2f}")
            print(f"    Duration: {trade.duration_seconds:.0f}s")
        
        print(f"\n💼 Open Positions ({len(self.open_positions)}):")
        for pos_id, position in self.open_positions.items():
            print(f"  {pos_id}:")
            print(f"    Type: {position.option_type}")
            print(f"    Strike: {position.strike}")
            print(f"    Entry: ₹{position.entry_price:.2f} @ {position.entry_time.strftime('%H:%M:%S')}")
        
        print(f"\n📊 Internal State:")
        print(f"  Current Candle: {getattr(self, 'current_candle_data', 'N/A')}")
        print(f"  Previous Candle: {getattr(self, 'previous_candle', 'N/A')}")
        print(f"  Last Entry Time: {getattr(self, 'last_entry_time', 'N/A')}")
        print(f"  Last Signal Time: {getattr(self, 'last_signal_time', 'N/A')}")
        
        print("="*70)
