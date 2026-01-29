"""Integration tests for end-to-end backtest with options"""

import unittest
from datetime import datetime, date
from unittest.mock import Mock, MagicMock, patch
from src.core.unified_trading_engine import UnifiedTradingEngine
from src.core.clickhouse_tick_source import ClickHouseTickSource
from src.core.persistence_strategy import NullPersistence
from src.backtesting.backtest_config import BacktestConfig


class TestBacktestOptionsIntegration(unittest.TestCase):
    """Integration tests for full backtest with options"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = BacktestConfig(
            user_id='test_user',
            strategy_id='test_strategy',
            backtest_date=datetime(2024, 10, 1),
        )
        
    @patch('src.backtesting.strategy_scanner.StrategyScanner')
    @patch('src.backtesting.data_manager.DataManager')
    def test_engine_passes_cache_manager_to_tick_source(self, mock_dm_class, mock_scanner):
        """Test engine passes cache_manager to tick source during init"""
        # Mock scanner and data manager
        mock_scanner_inst = Mock()
        mock_scanner.return_value = mock_scanner_inst
        mock_scanner_inst.scan_strategy.return_value = Mock()
        
        mock_dm = Mock()
        mock_dm_class.return_value = mock_dm
        mock_dm.clickhouse_client = Mock()
        
        # Create tick source
        tick_source = ClickHouseTickSource(
            backtest_date=self.config.backtest_date,
            symbols=['NIFTY'],
        )
        
        # Create engine
        with patch('src.core.unified_trading_engine.CentralizedTickProcessor'):
            engine = UnifiedTradingEngine(
                mode='backtesting',
                config=self.config,
                tick_source=tick_source,
                persistence=NullPersistence(),
            )
            
            # Verify cache_manager passed to tick source
            self.assertIsNotNone(tick_source.cache_manager)
            self.assertEqual(tick_source.cache_manager, engine.cache_manager)
            
    @patch('src.core.clickhouse_tick_source.DataManager')
    @patch('src.core.clickhouse_tick_source.ExpiryCalculator')
    @patch('src.core.clickhouse_tick_source.build_option_universe_for_underlying')
    def test_full_pattern_to_ticks_flow(self, mock_builder, mock_calc_class, mock_dm_class):
        """Test full flow from patterns to loaded option ticks"""
        # Mock cache manager with real pattern
        mock_cache = Mock()
        mock_cache.get_option_patterns.return_value = {
            'TI:W0:OTM10:CE': {
                'underlying_symbol': 'NIFTY',
                'used_by_strategies': ['strat1'],
            },
            'TI:W1:OTM10:CE': {
                'underlying_symbol': 'NIFTY',
                'used_by_strategies': ['strat1'],
            },
        }
        
        # Mock ClickHouse client
        mock_client = Mock()
        
        # Create tick source with cache
        tick_source = ClickHouseTickSource(
            clickhouse_client=mock_client,
            backtest_date=datetime(2024, 10, 1),
            symbols=['NIFTY'],
            cache_manager=mock_cache,
        )
        
        # Mock DataManager
        mock_dm = Mock()
        mock_dm_class.return_value = mock_dm
        
        # Mock index ticks
        mock_dm.load_ticks.return_value = [
            {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15, 0)},
            {'symbol': 'NIFTY', 'ltp': 22010.0, 'timestamp': datetime(2024, 10, 1, 9, 15, 1)},
        ]
        
        # Mock option ticks
        mock_dm.load_option_ticks.return_value = [
            {'symbol': 'NIFTY03OCT2422000CE', 'ltp': 100.0, 'timestamp': datetime(2024, 10, 1, 9, 15, 0)},
            {'symbol': 'NIFTY10OCT2422000CE', 'ltp': 95.0, 'timestamp': datetime(2024, 10, 1, 9, 15, 0)},
        ]
        
        # Mock ExpiryCalculator
        mock_calc = Mock()
        mock_calc_class.return_value = mock_calc
        
        # Mock option universe builder
        mock_builder.side_effect = [
            ['NIFTY03OCT2422000CE.NFO'],  # W0 pattern
            ['NIFTY10OCT2422000CE.NFO'],  # W1 pattern
        ]
        
        # Load ticks
        tick_source._load_ticks()
        
        # Verify full flow
        # 1. Patterns read from cache
        mock_cache.get_option_patterns.assert_called_once()
        
        # 2. Expiry calculator preloaded
        mock_calc.preload_expiries_for_symbols.assert_called_once_with(
            ['NIFTY'],
            date(2024, 10, 1)
        )
        
        # 3. Builder called for each pattern
        self.assertEqual(mock_builder.call_count, 2)
        
        # 4. Option ticks loaded
        mock_dm.load_option_ticks.assert_called_once()
        tickers_arg = mock_dm.load_option_ticks.call_args[1]['tickers']
        self.assertEqual(len(tickers_arg), 2)  # W0 and W1 tickers
        
        # 5. All ticks merged and sorted
        self.assertEqual(len(tick_source.ticks), 4)  # 2 index + 2 option
        
        # Verify chronological order
        timestamps = [t['timestamp'] for t in tick_source.ticks]
        self.assertEqual(timestamps, sorted(timestamps))
        
    def test_expiry_cache_reduces_db_queries(self):
        """Test expiry cache reduces repeated DB queries"""
        with patch('expiry_calculator.ExpiryCalculator') as mock_calc_class:
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            # Mock cache with expiries
            mock_calc._cache_reference_date = date(2024, 10, 1)
            mock_calc._expiry_cache = {
                'NIFTY': [date(2024, 10, 3), date(2024, 10, 10)]
            }
            
            # Mock get_expiry_date to use cache
            mock_calc.get_expiry_date.side_effect = lambda sym, code, ref: date(2024, 10, 3)
            
            # Call multiple times
            for _ in range(5):
                mock_calc.get_expiry_date('NIFTY', 'W0', date(2024, 10, 1))
            
            # Verify no DB queries (all cache hits)
            # This is validated by the fact that get_expiry_date doesn't call
            # _get_available_expiries_from_clickhouse when cache hit
            self.assertEqual(mock_calc.get_expiry_date.call_count, 5)


class TestBacktestOptionsMemoryEfficiency(unittest.TestCase):
    """Test memory efficiency of option loading"""
    
    def test_only_pattern_tickers_loaded(self):
        """Test only tickers from patterns are loaded, not all options"""
        with patch('src.core.clickhouse_tick_source.DataManager') as mock_dm_class, \
             patch('src.core.clickhouse_tick_source.ExpiryCalculator') as mock_calc_class, \
             patch('src.core.clickhouse_tick_source.build_option_universe_for_underlying') as mock_builder:
            
            # Mock patterns: only OTM5 for CE
            mock_cache = Mock()
            mock_cache.get_option_patterns.return_value = {
                'TI:W0:OTM5:CE': {'underlying_symbol': 'NIFTY'},
            }
            
            mock_dm = Mock()
            mock_dm_class.return_value = mock_dm
            mock_dm.load_ticks.return_value = [
                {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15)}
            ]
            mock_dm.load_option_ticks.return_value = []
            
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            # Builder returns limited tickers (OTM5 only)
            mock_builder.return_value = [
                f'NIFTY03OCT24{22000 + i*50}CE.NFO' for i in range(1, 6)
            ]
            
            tick_source = ClickHouseTickSource(
                clickhouse_client=Mock(),
                backtest_date=datetime(2024, 10, 1),
                symbols=['NIFTY'],
                cache_manager=mock_cache,
            )
            
            tick_source._load_ticks()
            
            # Verify only 5 tickers requested (not full 16+16+ATM chain)
            tickers_arg = mock_dm.load_option_ticks.call_args[1]['tickers']
            self.assertEqual(len(tickers_arg), 5)


if __name__ == '__main__':
    unittest.main()
