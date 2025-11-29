"""Test suite for option universe resolver"""

import unittest
from datetime import date
from unittest.mock import Mock, patch
from src.backtesting.option_universe_resolver import build_option_universe_for_underlying
from expiry_calculator import ExpiryCalculator


class TestOptionUniverseResolver(unittest.TestCase):
    """Test option universe resolver functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_calc = Mock(spec=ExpiryCalculator)
        
    def test_build_option_universe_for_single_expiry(self):
        """Test building option universe for single expiry"""
        # Mock expiry resolution
        self.mock_calc.get_expiry_date.return_value = date(2024, 10, 3)
        
        # Build universe
        tickers = build_option_universe_for_underlying(
            underlying='NIFTY',
            backtest_date=date(2024, 10, 1),
            expiry_codes=['W0'],
            spot_price=22000.0,
            expiry_calculator=self.mock_calc,
            itm_depth=3,
            otm_depth=3,
        )
        
        # Verify expiry resolution was called
        self.mock_calc.get_expiry_date.assert_called_once_with(
            symbol='NIFTY',
            expiry_code='W0',
            reference_date=date(2024, 10, 1)
        )
        
        # Verify tickers generated
        self.assertIsInstance(tickers, list)
        self.assertGreater(len(tickers), 0)
        
        # Verify format: NIFTY03OCT24{strike}CE.NFO or PE.NFO
        for ticker in tickers:
            self.assertIn('NIFTY', ticker)
            self.assertIn('03OCT24', ticker)
            self.assertTrue(ticker.endswith('CE.NFO') or ticker.endswith('PE.NFO'))
            
    def test_build_option_universe_for_multiple_expiries(self):
        """Test building option universe for multiple expiries"""
        # Mock expiry resolution
        self.mock_calc.get_expiry_date.side_effect = [
            date(2024, 10, 3),   # W0
            date(2024, 10, 10),  # W1
        ]
        
        # Build universe
        tickers = build_option_universe_for_underlying(
            underlying='NIFTY',
            backtest_date=date(2024, 10, 1),
            expiry_codes=['W0', 'W1'],
            spot_price=22000.0,
            expiry_calculator=self.mock_calc,
            itm_depth=2,
            otm_depth=2,
        )
        
        # Verify both expiries resolved
        self.assertEqual(self.mock_calc.get_expiry_date.call_count, 2)
        
        # Verify tickers generated for both expiries
        self.assertGreater(len(tickers), 0)
        has_03oct = any('03OCT24' in t for t in tickers)
        has_10oct = any('10OCT24' in t for t in tickers)
        self.assertTrue(has_03oct)
        self.assertTrue(has_10oct)
        
    def test_atm_calculation_rounds_to_strike_interval(self):
        """Test ATM calculation rounds to nearest strike"""
        # Mock expiry
        self.mock_calc.get_expiry_date.return_value = date(2024, 10, 3)
        
        # Spot price 22023 should round to 22000 for NIFTY (50 interval)
        tickers = build_option_universe_for_underlying(
            underlying='NIFTY',
            backtest_date=date(2024, 10, 1),
            expiry_codes=['W0'],
            spot_price=22023.0,
            expiry_calculator=self.mock_calc,
            itm_depth=1,
            otm_depth=1,
        )
        
        # Should have ATM (22000) + ITM1 (21950) + OTM1 (22050) for CE and PE
        # Total: 3 strikes × 2 types = 6 tickers
        self.assertEqual(len(tickers), 6)
        
        # Verify ATM 22000 is present
        has_22000_ce = any('22000CE' in t for t in tickers)
        has_22000_pe = any('22000PE' in t for t in tickers)
        self.assertTrue(has_22000_ce)
        self.assertTrue(has_22000_pe)
        
    def test_itm_otm_ladder_generation(self):
        """Test ITM/OTM ladder generation"""
        self.mock_calc.get_expiry_date.return_value = date(2024, 10, 3)
        
        # Build with specific ITM/OTM depths
        tickers = build_option_universe_for_underlying(
            underlying='NIFTY',
            backtest_date=date(2024, 10, 1),
            expiry_codes=['W0'],
            spot_price=22000.0,
            expiry_calculator=self.mock_calc,
            itm_depth=2,
            otm_depth=2,
        )
        
        # Expected strikes: ITM2 (21900), ITM1 (21950), ATM (22000), OTM1 (22050), OTM2 (22100)
        # Total: 5 strikes × 2 types = 10 tickers
        self.assertEqual(len(tickers), 10)
        
        # Verify expected strikes present
        expected_strikes = [21900, 21950, 22000, 22050, 22100]
        for strike in expected_strikes:
            has_ce = any(f'{strike}CE' in t for t in tickers)
            has_pe = any(f'{strike}PE' in t for t in tickers)
            self.assertTrue(has_ce, f"Missing {strike}CE")
            self.assertTrue(has_pe, f"Missing {strike}PE")
            
    def test_deduplication(self):
        """Test ticker deduplication"""
        self.mock_calc.get_expiry_date.return_value = date(2024, 10, 3)
        
        # Build universe twice with same params
        tickers1 = build_option_universe_for_underlying(
            underlying='NIFTY',
            backtest_date=date(2024, 10, 1),
            expiry_codes=['W0'],
            spot_price=22000.0,
            expiry_calculator=self.mock_calc,
            itm_depth=1,
            otm_depth=1,
        )
        
        # Verify no duplicates in result
        self.assertEqual(len(tickers1), len(set(tickers1)))
        
    def test_empty_expiry_codes_returns_empty(self):
        """Test empty expiry codes returns empty list"""
        tickers = build_option_universe_for_underlying(
            underlying='NIFTY',
            backtest_date=date(2024, 10, 1),
            expiry_codes=[],
            spot_price=22000.0,
            expiry_calculator=self.mock_calc,
        )
        
        self.assertEqual(tickers, [])
        
    def test_banknifty_strike_interval(self):
        """Test BANKNIFTY uses 100 strike interval"""
        self.mock_calc.get_expiry_date.return_value = date(2024, 10, 2)
        
        # BANKNIFTY spot 46523 should round to 46500 (100 interval)
        tickers = build_option_universe_for_underlying(
            underlying='BANKNIFTY',
            backtest_date=date(2024, 10, 1),
            expiry_codes=['W0'],
            spot_price=46523.0,
            expiry_calculator=self.mock_calc,
            itm_depth=1,
            otm_depth=1,
        )
        
        # Expected strikes: ITM1 (46400), ATM (46500), OTM1 (46600)
        expected_strikes = [46400, 46500, 46600]
        for strike in expected_strikes:
            has_ce = any(f'{strike}CE' in t for t in tickers)
            has_pe = any(f'{strike}PE' in t for t in tickers)
            self.assertTrue(has_ce, f"Missing {strike}CE for BANKNIFTY")
            self.assertTrue(has_pe, f"Missing {strike}PE for BANKNIFTY")


if __name__ == '__main__':
    unittest.main()
