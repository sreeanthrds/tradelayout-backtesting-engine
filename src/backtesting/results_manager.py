"""
Results Manager
===============

Handles results collection and reporting for backtesting.
"""

import logging
from typing import Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BacktestResults:
    """Backtest results container."""
    
    positions: List[Any]
    candles: Dict[str, int]
    signals: int
    ticks_processed: int
    duration_seconds: float
    strategies_agg: Dict[str, Any] = None  # Strategy aggregation metadata
    
    @property
    def ticks_per_second(self) -> float:
        """Calculate processing speed."""
        if self.duration_seconds > 0:
            return self.ticks_processed / self.duration_seconds
        return 0.0
    
    def print(self):
        """Print results to console."""
        print("\n" + "=" * 80)
        print("📊 BACKTEST RESULTS")
        print("=" * 80)
        
        print(f"\n💰 Signals Triggered: {self.signals}")
        print(f"📝 Positions Created: {len(self.positions)}")
        print(f"⚡ Ticks Processed: {self.ticks_processed:,}")
        print(f"⏱️  Duration: {self.duration_seconds:.2f}s")
        print(f"🚀 Speed: {self.ticks_per_second:.0f} ticks/second")
        
        if self.candles:
            print(f"\n📊 Candles Built:")
            for key, count in sorted(self.candles.items()):
                print(f"   {key}: {count} candles")
        
        if self.positions:
            print(f"\n📋 Sample Positions (first 5):")
            for i, pos in enumerate(self.positions[:5]):
                print(f"   {i+1}. {pos}")
        
        print("\n" + "=" * 80)


class ResultsManager:
    """
    Manages results collection and reporting.
    
    Responsibilities:
    - Collect results from GPS
    - Generate summary statistics
    - Print formatted reports
    """
    
    def __init__(self, gps: Any, data_writer: Any):
        """
        Initialize results manager.
        
        Args:
            gps: Global Position Store instance
            data_writer: DataFrameWriter instance
        """
        self.gps = gps
        self.data_writer = data_writer
        logger.info("📈 Results Manager initialized")
    
    def generate_results(
        self,
        ticks_processed: int,
        duration_seconds: float,
        strategies_agg: Dict[str, Any] = None
    ) -> BacktestResults:
        """
        Generate backtest results.
        
        Args:
            ticks_processed: Number of ticks processed
            duration_seconds: Duration in seconds
            strategies_agg: Strategy aggregation metadata (optional)
        
        Returns:
            BacktestResults object
        """
        logger.info("📊 Generating results...")
        
        # Get positions from GPS
        positions = self.gps.get_all_positions()
        
        # Get candles summary
        candles = self._get_candles_summary()
        
        # Count signals (same as positions for now)
        signals = len(positions)
        
        results = BacktestResults(
            positions=positions,
            candles=candles,
            signals=signals,
            ticks_processed=ticks_processed,
            duration_seconds=duration_seconds,
            strategies_agg=strategies_agg
        )
        
        logger.info(f"✅ Results generated: {signals} signals, {len(positions)} positions")
        
        return results
    
    def _get_candles_summary(self) -> Dict[str, int]:
        """
        Get summary of candles built.
        
        Returns:
            Dictionary of {key: candle_count}
        """
        summary = {}
        
        for key, df in self.data_writer.dataframes.items():
            summary[key] = len(df)
        
        return summary
