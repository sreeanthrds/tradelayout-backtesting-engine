-- ClickHouse Database Schema for TradeLayout Engine
-- Zero dependency on old context - all data stored in DB/Cache

-- Create database
CREATE DATABASE IF NOT EXISTS tradelayout;

USE tradelayout;

-- ============================================================================
-- 1. RAW TICKS TABLE
-- ============================================================================
-- Stores all incoming tick data from WebSocket
CREATE TABLE IF NOT EXISTS raw_ticks (
    timestamp DateTime64(3, 'UTC'),
    symbol String,
    exchange LowCardinality(String),
    ltp Decimal(18, 2),
    volume UInt64,
    open_interest UInt64,
    bid Decimal(18, 2),
    ask Decimal(18, 2),
    bid_qty UInt32,
    ask_qty UInt32,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (symbol, exchange, timestamp)
TTL timestamp + INTERVAL 1 YEAR
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 2. OHLCV CANDLES TABLE
-- ============================================================================
-- Stores built candles for all timeframes
CREATE TABLE IF NOT EXISTS ohlcv_candles (
    ts DateTime64(3, 'UTC'),
    symbol String,
    timeframe LowCardinality(String),  -- '1m', '5m', '15m', '30m', '1h', '1d'
    open Decimal(18, 2),
    high Decimal(18, 2),
    low Decimal(18, 2),
    close Decimal(18, 2),
    volume UInt64,
    is_closed UInt8,  -- 0 = building, 1 = closed
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, timeframe, ts)
TTL ts + INTERVAL 1 YEAR
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 3. INDICATOR VALUES TABLE
-- ============================================================================
-- Stores calculated indicator values
CREATE TABLE IF NOT EXISTS indicator_values (
    ts DateTime64(3, 'UTC'),
    symbol String,
    timeframe LowCardinality(String),
    indicator_name String,  -- 'EMA_20', 'RSI_14', 'MACD', etc.
    value Decimal(18, 4),
    created_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, timeframe, indicator_name, ts)
TTL ts + INTERVAL 1 YEAR
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 4. NODE VARIABLES TABLE
-- ============================================================================
-- Stores node variable values (replaces in-memory node_variables)
CREATE TABLE IF NOT EXISTS node_variables (
    user_id String,
    strategy_id String,
    node_id String,
    variable_name String,
    value Decimal(18, 4),
    updated_at DateTime64(3, 'UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, strategy_id, node_id, variable_name)
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 5. NODE STATES TABLE
-- ============================================================================
-- Stores node states (replaces in-memory node_states)
CREATE TABLE IF NOT EXISTS node_states (
    user_id String,
    strategy_id String,
    node_id String,
    status LowCardinality(String),  -- 'Active', 'Inactive', 'Pending'
    visited UInt8,
    re_entry_num UInt32,
    updated_at DateTime64(3, 'UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, strategy_id, node_id)
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 6. POSITIONS TABLE
-- ============================================================================
-- Stores position data (replaces GPS in-memory)
CREATE TABLE IF NOT EXISTS positions (
    position_id String,
    user_id String,
    strategy_id String,
    symbol String,
    exchange LowCardinality(String),
    transaction_type LowCardinality(String),  -- 'BUY', 'SELL'
    quantity Int32,
    entry_price Decimal(18, 2),
    current_price Decimal(18, 2),
    pnl Decimal(18, 2),
    status LowCardinality(String),  -- 'OPEN', 'CLOSED'
    entry_time DateTime64(3, 'UTC'),
    exit_time Nullable(DateTime64(3, 'UTC')),
    exit_price Nullable(Decimal(18, 2)),
    created_at DateTime DEFAULT now(),
    updated_at DateTime64(3, 'UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, strategy_id, position_id)
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 7. ORDERS TABLE
-- ============================================================================
-- Stores order data
CREATE TABLE IF NOT EXISTS orders (
    order_id String,
    user_id String,
    strategy_id String,
    position_id Nullable(String),
    symbol String,
    exchange LowCardinality(String),
    transaction_type LowCardinality(String),
    order_type LowCardinality(String),  -- 'MARKET', 'LIMIT', 'SL', 'SL-M'
    quantity Int32,
    price Nullable(Decimal(18, 2)),
    trigger_price Nullable(Decimal(18, 2)),
    filled_quantity Int32,
    average_price Nullable(Decimal(18, 2)),
    status LowCardinality(String),  -- 'PENDING', 'COMPLETE', 'REJECTED', 'CANCELLED'
    order_time DateTime64(3, 'UTC'),
    fill_time Nullable(DateTime64(3, 'UTC')),
    broker_order_id Nullable(String),
    error_message Nullable(String),
    created_at DateTime DEFAULT now(),
    updated_at DateTime64(3, 'UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, strategy_id, order_id)
SETTINGS index_granularity = 8192;

-- ============================================================================
-- INDEXES FOR FASTER QUERIES
-- ============================================================================

-- Index for latest candles query
ALTER TABLE ohlcv_candles ADD INDEX idx_symbol_tf (symbol, timeframe) TYPE minmax GRANULARITY 4;

-- Index for latest indicators query
ALTER TABLE indicator_values ADD INDEX idx_symbol_tf_ind (symbol, timeframe, indicator_name) TYPE minmax GRANULARITY 4;

-- Index for open positions query
ALTER TABLE positions ADD INDEX idx_status (status) TYPE set(0) GRANULARITY 4;

-- ============================================================================
-- MATERIALIZED VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Latest candles per symbol-timeframe
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_latest_candles
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (symbol, timeframe)
AS SELECT
    symbol,
    timeframe,
    argMax(ts, updated_at) as ts,
    argMax(open, updated_at) as open,
    argMax(high, updated_at) as high,
    argMax(low, updated_at) as low,
    argMax(close, updated_at) as close,
    argMax(volume, updated_at) as volume,
    argMax(is_closed, updated_at) as is_closed,
    max(updated_at) as updated_at
FROM ohlcv_candles
WHERE is_closed = 1
GROUP BY symbol, timeframe;

-- Latest indicators per symbol-timeframe-indicator
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_latest_indicators
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (symbol, timeframe, indicator_name)
AS SELECT
    symbol,
    timeframe,
    indicator_name,
    argMax(ts, created_at) as ts,
    argMax(value, created_at) as value,
    max(created_at) as created_at
FROM indicator_values
GROUP BY symbol, timeframe, indicator_name;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get latest N candles
-- Usage: SELECT * FROM get_latest_candles('NIFTY', '5m', 100)
CREATE OR REPLACE FUNCTION get_latest_candles AS (symbol, timeframe, n) -> (
    SELECT *
    FROM ohlcv_candles
    WHERE symbol = symbol
      AND timeframe = timeframe
      AND is_closed = 1
    ORDER BY ts DESC
    LIMIT n
);

-- Function to get latest indicators
-- Usage: SELECT * FROM get_latest_indicators('NIFTY', '5m')
CREATE OR REPLACE FUNCTION get_latest_indicators AS (symbol, timeframe) -> (
    SELECT
        indicator_name,
        value
    FROM mv_latest_indicators
    WHERE symbol = symbol
      AND timeframe = timeframe
);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE raw_ticks IS 'Stores all incoming tick data from WebSocket';
COMMENT ON TABLE ohlcv_candles IS 'Stores built candles for all timeframes';
COMMENT ON TABLE indicator_values IS 'Stores calculated indicator values';
COMMENT ON TABLE node_variables IS 'Stores node variable values (replaces in-memory)';
COMMENT ON TABLE node_states IS 'Stores node states (replaces in-memory)';
COMMENT ON TABLE positions IS 'Stores position data (replaces GPS)';
COMMENT ON TABLE orders IS 'Stores order data';
