"""Test suite for ClickHouseTickSource pattern-driven option loading"""

import unittest
from datetime import datetime, date
from unittest.mock import Mock, MagicMock, patch
from src.core.clickhouse_tick_source import ClickHouseTickSource


class TestClickHouseTickSourceOptions(unittest.TestCase):
    """Test ClickHouseTickSource option loading from patterns"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.mock_cache_manager = Mock()
        
        self.tick_source = ClickHouseTickSource(
            clickhouse_client=self.mock_client,
            backtest_date=datetime(2024, 10, 1),
            symbols=['NIFTY'],
            cache_manager=self.mock_cache_manager,
        )
        
    def test_init_with_cache_manager(self):
        """Test initialization with cache_manager"""
        self.assertIsNotNone(self.tick_source.cache_manager)
        self.assertEqual(self.tick_source.cache_manager, self.mock_cache_manager)
        
    def test_no_patterns_skips_option_loading(self):
        """Test that no patterns in cache skips option loading"""
        # Mock: no patterns in cache
        self.mock_cache_manager.get_option_patterns.return_value = {}
        
        # Mock index ticks
        with patch('src.core.clickhouse_tick_source.DataManager') as mock_dm_class:
            mock_dm = Mock()
            mock_dm_class.return_value = mock_dm
            mock_dm.load_ticks.return_value = [
                {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15)}
            ]
            mock_dm.load_option_ticks.return_value = []
            
            self.tick_source._load_ticks()
            
            # Verify option ticks NOT loaded
            mock_dm.load_option_ticks.assert_not_called()
            
    def test_parses_pattern_correctly(self):
        """Test pattern parsing: underlying_alias:expiry_code:strike_type:option_type"""
        # Mock patterns
        self.mock_cache_manager.get_option_patterns.return_value = {
            'TI:W0:OTM10:CE': {
                'underlying_symbol': 'NIFTY',
                'used_by_strategies': ['strat1']
            }
        }
        
        # Mock index ticks
        with patch('src.core.clickhouse_tick_source.DataManager') as mock_dm_class, \
             patch('src.core.clickhouse_tick_source.ExpiryCalculator') as mock_calc_class, \
             patch('src.core.clickhouse_tick_source.build_option_universe_for_underlying') as mock_builder:
            
            mock_dm = Mock()
            mock_dm_class.return_value = mock_dm
            mock_dm.load_ticks.return_value = [
                {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15)}
            ]
            mock_dm.load_option_ticks.return_value = []
            
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            mock_builder.return_value = ['NIFTY03OCT2422000CE.NFO']
            
            self.tick_source._load_ticks()
            
            # Verify builder called with correct params
            mock_builder.assert_called_once()
            call_kwargs = mock_builder.call_args[1]
            self.assertEqual(call_kwargs['underlying'], 'NIFTY')
            self.assertEqual(call_kwargs['expiry_codes'], ['W0'])
            self.assertEqual(call_kwargs['spot_price'], 22000.0)
            self.assertEqual(call_kwargs['itm_depth'], 0)  # OTM pattern
            self.assertEqual(call_kwargs['otm_depth'], 10)  # OTM10
            
    def test_parses_itm_pattern(self):
        """Test ITM pattern parsing extracts ITM depth"""
        self.mock_cache_manager.get_option_patterns.return_value = {
            'TI:W0:ITM5:PE': {
                'underlying_symbol': 'NIFTY',
            }
        }
        
        with patch('src.core.clickhouse_tick_source.DataManager') as mock_dm_class, \
             patch('src.core.clickhouse_tick_source.ExpiryCalculator') as mock_calc_class, \
             patch('src.core.clickhouse_tick_source.build_option_universe_for_underlying') as mock_builder:
            
            mock_dm = Mock()
            mock_dm_class.return_value = mock_dm
            mock_dm.load_ticks.return_value = [
                {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15)}
            ]
            mock_dm.load_option_ticks.return_value = []
            
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            mock_builder.return_value = []
            
            self.tick_source._load_ticks()
            
            # Verify ITM depth parsed
            call_kwargs = mock_builder.call_args[1]
            self.assertEqual(call_kwargs['itm_depth'], 5)
            self.assertEqual(call_kwargs['otm_depth'], 0)
            
    def test_atm_pattern_uses_defaults(self):
        """Test ATM pattern uses default ITM/OTM depths"""
        self.mock_cache_manager.get_option_patterns.return_value = {
            'TI:W0:ATM:CE': {
                'underlying_symbol': 'NIFTY',
            }
        }
        
        with patch('src.core.clickhouse_tick_source.DataManager') as mock_dm_class, \
             patch('src.core.clickhouse_tick_source.ExpiryCalculator') as mock_calc_class, \
             patch('src.core.clickhouse_tick_source.build_option_universe_for_underlying') as mock_builder:
            
            mock_dm = Mock()
            mock_dm_class.return_value = mock_dm
            mock_dm.load_ticks.return_value = [
                {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15)}
            ]
            mock_dm.load_option_ticks.return_value = []
            
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            mock_builder.return_value = []
            
            self.tick_source._load_ticks()
            
            # Verify defaults used
            call_kwargs = mock_builder.call_args[1]
            self.assertEqual(call_kwargs['itm_depth'], 16)
            self.assertEqual(call_kwargs['otm_depth'], 16)
            
    def test_multiple_patterns_merged(self):
        """Test multiple patterns result in merged ticker list"""
        self.mock_cache_manager.get_option_patterns.return_value = {
            'TI:W0:OTM5:CE': {'underlying_symbol': 'NIFTY'},
            'TI:W1:OTM5:CE': {'underlying_symbol': 'NIFTY'},
        }
        
        with patch('src.core.clickhouse_tick_source.DataManager') as mock_dm_class, \
             patch('src.core.clickhouse_tick_source.ExpiryCalculator') as mock_calc_class, \
             patch('src.core.clickhouse_tick_source.build_option_universe_for_underlying') as mock_builder:
            
            mock_dm = Mock()
            mock_dm_class.return_value = mock_dm
            mock_dm.load_ticks.return_value = [
                {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15)}
            ]
            mock_dm.load_option_ticks.return_value = [
                {'symbol': 'NIFTY03OCT2422000CE', 'ltp': 100.0, 'timestamp': datetime(2024, 10, 1, 9, 15)}
            ]
            
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            # Return different tickers for each pattern
            mock_builder.side_effect = [
                ['NIFTY03OCT2422000CE.NFO'],  # W0
                ['NIFTY10OCT2422000CE.NFO'],  # W1
            ]
            
            self.tick_source._load_ticks()
            
            # Verify builder called twice (once per pattern)
            self.assertEqual(mock_builder.call_count, 2)
            
            # Verify load_option_ticks called with deduplicated list
            mock_dm.load_option_ticks.assert_called_once()
            tickers_arg = mock_dm.load_option_ticks.call_args[1]['tickers']
            self.assertEqual(len(tickers_arg), 2)
            
    def test_tickers_deduplicated(self):
        """Test duplicate tickers across patterns are deduplicated"""
        self.mock_cache_manager.get_option_patterns.return_value = {
            'TI:W0:OTM5:CE': {'underlying_symbol': 'NIFTY'},
            'TI:W0:OTM5:PE': {'underlying_symbol': 'NIFTY'},  # Same expiry, different type
        }
        
        with patch('src.core.clickhouse_tick_source.DataManager') as mock_dm_class, \
             patch('src.core.clickhouse_tick_source.ExpiryCalculator') as mock_calc_class, \
             patch('src.core.clickhouse_tick_source.build_option_universe_for_underlying') as mock_builder:
            
            mock_dm = Mock()
            mock_dm_class.return_value = mock_dm
            mock_dm.load_ticks.return_value = [
                {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15)}
            ]
            mock_dm.load_option_ticks.return_value = []
            
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            # Both patterns return same ticker (should dedupe)
            mock_builder.side_effect = [
                ['NIFTY03OCT2422000CE.NFO', 'NIFTY03OCT2422000PE.NFO'],
                ['NIFTY03OCT2422000CE.NFO', 'NIFTY03OCT2422000PE.NFO'],
            ]
            
            self.tick_source._load_ticks()
            
            # Verify deduplication
            tickers_arg = mock_dm.load_option_ticks.call_args[1]['tickers']
            self.assertEqual(len(tickers_arg), 2)  # Deduped from 4
            
    def test_index_and_option_ticks_merged_and_sorted(self):
        """Test index and option ticks are merged and sorted by timestamp"""
        self.mock_cache_manager.get_option_patterns.return_value = {
            'TI:W0:ATM:CE': {'underlying_symbol': 'NIFTY'},
        }
        
        with patch('src.core.clickhouse_tick_source.DataManager') as mock_dm_class, \
             patch('src.core.clickhouse_tick_source.ExpiryCalculator') as mock_calc_class, \
             patch('src.core.clickhouse_tick_source.build_option_universe_for_underlying') as mock_builder:
            
            mock_dm = Mock()
            mock_dm_class.return_value = mock_dm
            
            # Index ticks with timestamps
            mock_dm.load_ticks.return_value = [
                {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15, 2)},
                {'symbol': 'NIFTY', 'ltp': 22010.0, 'timestamp': datetime(2024, 10, 1, 9, 15, 4)},
            ]
            
            # Option ticks with interleaved timestamps
            mock_dm.load_option_ticks.return_value = [
                {'symbol': 'NIFTY03OCT2422000CE', 'ltp': 100.0, 'timestamp': datetime(2024, 10, 1, 9, 15, 1)},
                {'symbol': 'NIFTY03OCT2422000CE', 'ltp': 101.0, 'timestamp': datetime(2024, 10, 1, 9, 15, 3)},
            ]
            
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            mock_builder.return_value = ['NIFTY03OCT2422000CE.NFO']
            
            self.tick_source._load_ticks()
            
            # Verify ticks merged and sorted
            self.assertEqual(len(self.tick_source.ticks), 4)
            
            # Verify chronological order
            timestamps = [t['timestamp'] for t in self.tick_source.ticks]
            self.assertEqual(timestamps, sorted(timestamps))
            
    def test_missing_underlying_symbol_skips_pattern(self):
        """Test pattern without underlying_symbol is skipped"""
        self.mock_cache_manager.get_option_patterns.return_value = {
            'TI:W0:ATM:CE': {},  # Missing underlying_symbol
        }
        
        with patch('src.core.clickhouse_tick_source.DataManager') as mock_dm_class, \
             patch('src.core.clickhouse_tick_source.ExpiryCalculator') as mock_calc_class, \
             patch('src.core.clickhouse_tick_source.build_option_universe_for_underlying') as mock_builder:
            
            mock_dm = Mock()
            mock_dm_class.return_value = mock_dm
            mock_dm.load_ticks.return_value = [
                {'symbol': 'NIFTY', 'ltp': 22000.0, 'timestamp': datetime(2024, 10, 1, 9, 15)}
            ]
            
            mock_calc = Mock()
            mock_calc_class.return_value = mock_calc
            
            self.tick_source._load_ticks()
            
            # Verify builder never called (pattern skipped)
            mock_builder.assert_not_called()


if __name__ == '__main__':
    unittest.main()
