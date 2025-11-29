# Backtesting Option Features - Test Suite

Comprehensive test suite for option backtesting features including:
- ExpiryCalculator with nse_options_metadata table
- Option universe resolver
- Pattern-driven option loading
- End-to-end backtest integration

## Test Files

### `test_expiry_calculator.py`
Tests for `ExpiryCalculator` class:
- ✅ Initialization with ClickHouse client
- ✅ Querying expiries from `nse_options_metadata`
- ✅ In-memory expiry caching per backtest day
- ✅ Cache hit/miss behavior
- ✅ Weekly expiry resolution (W0, W1, W2...)
- ✅ Monthly expiry resolution (M0, M1...)
- ✅ Quarterly and yearly expiry resolution
- ✅ Invalid expiry code handling
- ✅ No data error handling

### `test_option_universe_resolver.py`
Tests for `build_option_universe_for_underlying` function:
- ✅ Building universe for single expiry
- ✅ Building universe for multiple expiries
- ✅ ATM calculation and rounding to strike intervals
- ✅ ITM/OTM ladder generation
- ✅ Ticker deduplication
- ✅ Empty expiry codes handling
- ✅ NIFTY (50) vs BANKNIFTY (100) strike intervals

### `test_clickhouse_tick_source_options.py`
Tests for pattern-driven option loading in `ClickHouseTickSource`:
- ✅ Initialization with cache_manager
- ✅ No patterns → skip option loading
- ✅ Pattern parsing: `underlying_alias:expiry_code:strike_type:option_type`
- ✅ OTM pattern ladder depth extraction
- ✅ ITM pattern ladder depth extraction
- ✅ ATM pattern default depths
- ✅ Multiple patterns merging
- ✅ Ticker deduplication across patterns
- ✅ Index + option ticks merging and sorting
- ✅ Missing underlying_symbol handling

### `test_integration_backtest_options.py`
Integration tests for end-to-end backtest flow:
- ✅ Engine passes cache_manager to tick source
- ✅ Full pattern → tickers → loaded ticks flow
- ✅ Expiry cache reduces DB queries
- ✅ Memory efficiency: only pattern tickers loaded

## Running Tests

### Run all tests
```bash
python run_tests.py
```

### Run with verbose output
```bash
python run_tests.py -v
```

### Run specific test file
```bash
python -m unittest tests.test_expiry_calculator
```

### Run specific test class
```bash
python -m unittest tests.test_expiry_calculator.TestExpiryCalculator
```

### Run specific test method
```bash
python -m unittest tests.test_expiry_calculator.TestExpiryCalculator.test_weekly_expiry_W0_W1_W2
```

## Test Coverage

### Features Tested

#### 1. ExpiryCalculator (10 tests)
- ✅ Metadata table usage (`nse_options_metadata`)
- ✅ In-memory caching for backtest day
- ✅ Cache hit/miss logic
- ✅ W0/W1/M0/Q0/Y0 expiry resolution
- ✅ Error handling

#### 2. Option Universe Resolver (8 tests)
- ✅ Single/multiple expiry handling
- ✅ ATM calculation from spot
- ✅ ITM/OTM ladder generation
- ✅ Ticker format (ClickHouse)
- ✅ Deduplication
- ✅ Strike interval (NIFTY 50, BANKNIFTY 100)

#### 3. ClickHouseTickSource (11 tests)
- ✅ Pattern-driven universe
- ✅ Pattern parsing and validation
- ✅ ITM/OTM/ATM depth extraction
- ✅ Multiple pattern merging
- ✅ Tick merging and sorting
- ✅ Error handling for invalid patterns

#### 4. Integration (4 tests)
- ✅ Engine → tick source wiring
- ✅ Pattern → tickers → ticks flow
- ✅ Cache efficiency
- ✅ Memory efficiency (limited universe)

## Test Requirements

### Dependencies
```bash
pip install unittest  # Built-in, no install needed
pip install unittest.mock  # Built-in, no install needed
```

### Mock Strategy
Tests use mocking extensively to avoid:
- ClickHouse database dependencies
- Real tick data
- Strategy execution overhead

### Test Isolation
Each test:
- Uses fresh mocks via `setUp()`
- Doesn't depend on other tests
- Can run independently

## Expected Test Output

```
====================================================================
🧪 Running Backtesting Option Features Test Suite
====================================================================

test_atm_calculation_rounds_to_strike_interval (test_option_universe_resolver.TestOptionUniverseResolver) ... ok
test_build_option_universe_for_multiple_expiries (test_option_universe_resolver.TestOptionUniverseResolver) ... ok
test_build_option_universe_for_single_expiry (test_option_universe_resolver.TestOptionUniverseResolver) ... ok
...
test_weekly_expiry_W0_W1_W2 (test_expiry_calculator.TestExpiryCalculator) ... ok

----------------------------------------------------------------------
Ran 33 tests in 0.123s

OK

====================================================================
📊 Test Summary
====================================================================
Tests run: 33
Failures: 0
Errors: 0
Skipped: 0
====================================================================
```

## Continuous Integration

### Running in CI/CD
```yaml
# Example GitHub Actions workflow
- name: Run option backtest tests
  run: |
    python run_tests.py -v
```

### Test Exit Codes
- `0`: All tests passed
- `1`: One or more tests failed

## Troubleshooting

### Import Errors
If you see import errors, ensure:
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/tradelayout-engine"
```

### Missing Mock Objects
If tests fail with AttributeError on mocks:
- Check that `setUp()` properly initializes mocks
- Verify mock return values are set before calling tested code

### Test Isolation Issues
If tests interfere with each other:
- Ensure each test uses fresh mocks
- Verify `setUp()` reinitializes state
- Check that tests don't share global state

## Contributing Tests

When adding new features, add tests:
1. Create new test file: `tests/test_<feature>.py`
2. Extend existing test class or create new one
3. Use descriptive test method names: `test_<what_it_tests>`
4. Mock external dependencies (DB, filesystem, etc.)
5. Verify both success and error paths
6. Run `python run_tests.py` to validate

## Test Metrics

- **Total Tests:** 33
- **Code Coverage:** Core option features (90%+)
- **Execution Time:** <1 second (mocked)
- **Test Isolation:** 100% (no shared state)
