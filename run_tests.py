#!/usr/bin/env python3
"""
Test Runner for Backtesting Option Features

Runs all unit tests and integration tests for:
- ExpiryCalculator with nse_options_metadata
- Option universe resolver
- Pattern-driven option loading in ClickHouseTickSource
- End-to-end backtest integration

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py -v           # Verbose output
    python run_tests.py TestClass    # Run specific test class
"""

import sys
import os
import unittest

# Add project root to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'src'))
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'strategy'))

# Discover and run tests
def main():
    """Run all tests"""
    # Test discovery
    loader = unittest.TestLoader()
    start_dir = os.path.join(SCRIPT_DIR, 'tests')
    
    if not os.path.exists(start_dir):
        print(f"❌ Tests directory not found: {start_dir}")
        return 1
    
    # Load only our new option feature tests (skip old unrelated tests)
    test_files = [
        'test_expiry_calculator.py',
        'test_option_universe_resolver.py',
        'test_clickhouse_tick_source_options.py',
        'test_integration_backtest_options.py',
    ]
    
    suite = unittest.TestSuite()
    for test_file in test_files:
        test_path = os.path.join(start_dir, test_file)
        if os.path.exists(test_path):
            tests = loader.loadTestsFromName(f'tests.{test_file[:-3]}')
            suite.addTests(tests)
    
    # Run tests with appropriate verbosity
    verbosity = 2 if '-v' in sys.argv or '--verbose' in sys.argv else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    
    print("=" * 80)
    print("🧪 Running Backtesting Option Features Test Suite")
    print("=" * 80)
    print()
    
    result = runner.run(suite)
    
    # Summary
    print()
    print("=" * 80)
    print("📊 Test Summary")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("=" * 80)
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
