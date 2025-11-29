"""
Tick Data Source Abstraction
=============================

Abstract interface for tick data sources.

This abstraction allows the same trading engine to work with different data sources:
- Backtesting: ClickHouse (batch historical data)
- Live Trading: WebSocket (real-time streaming data)
- Testing: Mock data (predefined ticks)

Author: UniTrader Team
Created: 2024-11-12
"""

from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, Optional


class TickDataSource(ABC):
    """
    Abstract base class for tick data sources.
    
    A tick data source is responsible for:
    1. Providing ticks to the trading engine
    2. Managing the lifecycle (start, stop)
    3. Handling errors and reconnections
    
    Different implementations:
    - ClickHouseTickSource: Reads historical ticks from ClickHouse
    - WebSocketTickSource: Receives real-time ticks from broker WebSocket
    - MockTickSource: Provides predefined ticks for testing
    """
    
    @abstractmethod
    def start(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Start providing ticks.
        
        For each tick received, call the callback function with tick data.
        
        Args:
            callback: Function to call for each tick.
                     Signature: callback(tick_data: Dict) -> None
        
        Example:
            def on_tick(tick_data):
                print(f"Received tick: {tick_data}")
            
            tick_source.start(callback=on_tick)
        """
        pass
    
    @abstractmethod
    def stop(self):
        """
        Stop providing ticks.
        
        Clean up resources, close connections, etc.
        
        Example:
            tick_source.stop()
        """
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """
        Check if tick source is currently running.
        
        Returns:
            True if running, False otherwise
        
        Example:
            if tick_source.is_running():
                print("Receiving ticks...")
        """
        pass
    
    def wait_completion(self):
        """
        Wait for all ticks to be processed (backtesting only).
        
        For backtesting, this blocks until all historical ticks are processed.
        For live trading, this is not applicable (raises NotImplementedError).
        
        Raises:
            NotImplementedError: If not applicable for this source type
        
        Example:
            # Backtesting
            tick_source.start(callback)
            tick_source.wait_completion()  # Blocks until done
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support wait_completion(). "
            "This method is only for backtesting sources."
        )
    
    def run_forever(self):
        """
        Run forever (live trading only).
        
        For live trading, this keeps the process alive to receive ticks.
        For backtesting, this is not applicable (raises NotImplementedError).
        
        Raises:
            NotImplementedError: If not applicable for this source type
        
        Example:
            # Live trading
            tick_source.start(callback)
            tick_source.run_forever()  # Blocks forever
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support run_forever(). "
            "This method is only for live trading sources."
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about tick source.
        
        Returns:
            Dict with statistics (ticks_received, errors, etc.)
        
        Example:
            stats = tick_source.get_stats()
            print(f"Ticks received: {stats['ticks_received']}")
        """
        return {
            'ticks_received': 0,
            'errors': 0,
            'status': 'unknown'
        }
