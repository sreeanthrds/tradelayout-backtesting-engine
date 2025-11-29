-- ClickHouse Database Schema for TradeLayout Engine (Simplified)
-- Zero dependency on old context - all data stored in DB/Cache

-- Create database
CREATE DATABASE IF NOT EXISTS tradelayout;

USE tradelayout;

-- ============================================================================
-- 1. RAW TICKS TABLE
-- ============================================================================
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
CREATE TABLE IF NOT EXISTS ohlcv_candles (
    ts DateTime64(3, 'UTC'),
    symbol String,
    timeframe LowCardinality(String),
    open Decimal(18, 2),
    high Decimal(18, 2),
    low Decimal(18, 2),
    close Decimal(18, 2),
    volume UInt64,
    is_closed UInt8,
    created_at DateTime DEFAULT now(),
    updated_at DateTime64(3, 'UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, timeframe, ts)
TTL ts + INTERVAL 1 YEAR
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 3. INDICATOR VALUES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS indicator_values (
    ts DateTime64(3, 'UTC'),
    symbol String,
    timeframe LowCardinality(String),
    indicator_name String,
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
CREATE TABLE IF NOT EXISTS node_states (
    user_id String,
    strategy_id String,
    node_id String,
    status LowCardinality(String),
    visited UInt8,
    re_entry_num UInt32,
    updated_at DateTime64(3, 'UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, strategy_id, node_id)
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 6. POSITIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS positions (
    position_id String,
    user_id String,
    strategy_id String,
    symbol String,
    exchange LowCardinality(String),
    transaction_type LowCardinality(String),
    quantity Int32,
    entry_price Decimal(18, 2),
    current_price Decimal(18, 2),
    pnl Decimal(18, 2),
    status LowCardinality(String),
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
CREATE TABLE IF NOT EXISTS orders (
    order_id String,
    user_id String,
    strategy_id String,
    position_id Nullable(String),
    symbol String,
    exchange LowCardinality(String),
    transaction_type LowCardinality(String),
    order_type LowCardinality(String),
    quantity Int32,
    price Nullable(Decimal(18, 2)),
    trigger_price Nullable(Decimal(18, 2)),
    filled_quantity Int32,
    average_price Nullable(Decimal(18, 2)),
    status LowCardinality(String),
    order_time DateTime64(3, 'UTC'),
    fill_time Nullable(DateTime64(3, 'UTC')),
    broker_order_id Nullable(String),
    error_message Nullable(String),
    created_at DateTime DEFAULT now(),
    updated_at DateTime64(3, 'UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (user_id, strategy_id, order_id)
SETTINGS index_granularity = 8192;
