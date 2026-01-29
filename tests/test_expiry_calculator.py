"""Test suite for ExpiryCalculator with nse_options_metadata and in-memory caching"""

import unittest
from datetime import date
from unittest.mock import Mock, MagicMock, patch
from expiry_calculator import ExpiryCalculator


class TestExpiryCalculator(unittest.TestCase):
    """Test ExpiryCalculator functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_client = Mock()
        self.calc = ExpiryCalculator(clickhouse_client=self.mock_client)
        
    def test_init(self):
        """Test ExpiryCalculator initialization"""
        self.assertIsNotNone(self.calc.clickhouse_client)
        self.assertEqual(self.calc._expiry_cache, {})
        self.assertIsNone(self.calc._cache_reference_date)
        
    def test_get_available_expiries_from_clickhouse(self):
        """Test fetching expiries from nse_options_metadata"""
        # Mock ClickHouse response
        mock_result = Mock()
        mock_result.result_rows = [
            (date(2024, 10, 3),),
            (date(2024, 10, 10),),
            (date(2024, 10, 31),),
        ]
        self.mock_client.query.return_value = mock_result
        
        # Call method
        expiries = self.calc._get_available_expiries_from_clickhouse(
            'NIFTY',
            date(2024, 10, 1)
        )
        
        # Verify query uses nse_options_metadata
        call_args = self.mock_client.query.call_args[0][0]
        self.assertIn('nse_options_metadata', call_args)
        self.assertIn("underlying = 'NIFTY'", call_args)
        self.assertIn("expiry_date >= '2024-10-01'", call_args)
        
        # Verify results
        self.assertEqual(len(expiries), 3)
        self.assertEqual(expiries[0], date(2024, 10, 3))
        self.assertEqual(expiries[1], date(2024, 10, 10))
        self.assertEqual(expiries[2], date(2024, 10, 31))
        
    def test_preload_expiries_for_symbols(self):
        """Test preloading expiries into memory cache"""
        # Mock ClickHouse responses for two symbols
        mock_result_nifty = Mock()
        mock_result_nifty.result_rows = [
            (date(2024, 10, 3),),
            (date(2024, 10, 10),),
        ]
        
        mock_result_banknifty = Mock()
        mock_result_banknifty.result_rows = [
            (date(2024, 10, 2),),
            (date(2024, 10, 9),),
        ]
        
        self.mock_client.query.side_effect = [mock_result_nifty, mock_result_banknifty]
        
        # Preload
        ref_date = date(2024, 10, 1)
        self.calc.preload_expiries_for_symbols(['NIFTY', 'BANKNIFTY'], ref_date)
        
        # Verify cache populated
        self.assertEqual(self.calc._cache_reference_date, ref_date)
        self.assertIn('NIFTY', self.calc._expiry_cache)
        self.assertIn('BANKNIFTY', self.calc._expiry_cache)
        self.assertEqual(len(self.calc._expiry_cache['NIFTY']), 2)
        self.assertEqual(len(self.calc._expiry_cache['BANKNIFTY']), 2)
        
    def test_get_expiry_date_uses_cache(self):
        """Test get_expiry_date uses cache when available"""
        # Populate cache
        ref_date = date(2024, 10, 1)
        self.calc._cache_reference_date = ref_date
        self.calc._expiry_cache['NIFTY'] = [
            date(2024, 10, 3),
            date(2024, 10, 10),
            date(2024, 10, 31),
        ]
        
        # Call get_expiry_date for W0
        expiry = self.calc.get_expiry_date('NIFTY', 'W0', ref_date)
        
        # Verify no DB query was made (cache hit)
        self.mock_client.query.assert_not_called()
        
        # Verify correct expiry returned
        self.assertEqual(expiry, date(2024, 10, 3))
        
    def test_get_expiry_date_queries_db_on_cache_miss(self):
        """Test get_expiry_date queries DB when cache miss"""
        # Mock ClickHouse response
        mock_result = Mock()
        mock_result.result_rows = [
            (date(2024, 10, 3),),
            (date(2024, 10, 10),),
        ]
        self.mock_client.query.return_value = mock_result
        
        # Call get_expiry_date (no cache)
        expiry = self.calc.get_expiry_date('NIFTY', 'W0', date(2024, 10, 1))
        
        # Verify DB query was made
        self.mock_client.query.assert_called_once()
        
        # Verify correct expiry returned
        self.assertEqual(expiry, date(2024, 10, 3))
        
    def test_weekly_expiry_W0_W1_W2(self):
        """Test weekly expiry resolution W0, W1, W2"""
        ref_date = date(2024, 10, 1)
        self.calc._cache_reference_date = ref_date
        self.calc._expiry_cache['NIFTY'] = [
            date(2024, 10, 3),   # W0
            date(2024, 10, 10),  # W1
            date(2024, 10, 17),  # W2
            date(2024, 10, 31),  # M0
        ]
        
        w0 = self.calc.get_expiry_date('NIFTY', 'W0', ref_date)
        w1 = self.calc.get_expiry_date('NIFTY', 'W1', ref_date)
        w2 = self.calc.get_expiry_date('NIFTY', 'W2', ref_date)
        
        self.assertEqual(w0, date(2024, 10, 3))
        self.assertEqual(w1, date(2024, 10, 10))
        self.assertEqual(w2, date(2024, 10, 17))
        
    def test_monthly_expiry_M0(self):
        """Test monthly expiry resolution M0"""
        ref_date = date(2024, 10, 1)
        self.calc._cache_reference_date = ref_date
        # Multiple expiries in Oct, last one is M0
        self.calc._expiry_cache['NIFTY'] = [
            date(2024, 10, 3),
            date(2024, 10, 10),
            date(2024, 10, 17),
            date(2024, 10, 24),
            date(2024, 10, 31),  # Last expiry of Oct = M0
            date(2024, 11, 7),
        ]
        
        m0 = self.calc.get_expiry_date('NIFTY', 'M0', ref_date)
        
        self.assertEqual(m0, date(2024, 10, 31))
        
    def test_invalid_expiry_code_raises_error(self):
        """Test invalid expiry code raises ValueError"""
        ref_date = date(2024, 10, 1)
        self.calc._cache_reference_date = ref_date
        self.calc._expiry_cache['NIFTY'] = [date(2024, 10, 3)]
        
        with self.assertRaises(ValueError) as ctx:
            self.calc.get_expiry_date('NIFTY', 'X0', ref_date)
        
        self.assertIn('Invalid expiry type', str(ctx.exception))
        
    def test_no_expiry_data_raises_error(self):
        """Test no expiry data raises ValueError"""
        mock_result = Mock()
        mock_result.result_rows = []
        self.mock_client.query.return_value = mock_result
        
        with self.assertRaises(ValueError) as ctx:
            self.calc.get_expiry_date('NIFTY', 'W0', date(2024, 10, 1))
        
        self.assertIn('No expiry data available', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
