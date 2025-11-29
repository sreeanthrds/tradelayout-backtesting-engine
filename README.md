# 🚀 TradeLayout Engine

Modern, scalable trading engine with incremental indicators and unified live/backtest execution.

## 📋 Overview

TradeLayout Engine is a complete rewrite of the trading system with:
- ✅ Incremental indicator updates (O(1) per tick)
- ✅ Multi-timeframe candle building (1m to 1d)
- ✅ Unified live/backtest code path
- ✅ Modular package architecture
- ✅ Self-hosted infrastructure ($10/month)

## 🏗️ Architecture

```
Broker WS → CandleStore → IndicatorHub → Executor → Orders
              ↓              ↓
           Redis          Redis
              ↓              ↓
         ClickHouse    ClickHouse
```

## 📦 Packages

- **tradelayout-brokers** - Broker adapters (AngelOne, Dhan, Backtest)
- **tradelayout-candles** - Multi-timeframe candle builder
- **tradelayout-indicators** - Incremental indicator runtime
- **tradelayout-data** - ClickHouse data layer
- **tradelayout-redis** - Redis sync layer
- **tradelayout-backtest** - Backtesting engine

## 🚀 Quick Start

### 1. Setup Infrastructure
```bash
cd infrastructure
cp .env.example .env
# Edit .env with your settings
./scripts/setup.sh
```

### 2. Deploy Services
```bash
./scripts/deploy.sh
```

### 3. Run Tests
```bash
cd tests
pytest -v
```

## 📊 Cost

- **Current:** $500-1000/month (ClickHouse Cloud)
- **New:** $10-65/month (Self-hosted)
- **Savings:** 98% reduction!

## 📖 Documentation

- [Architecture](docs/architecture.md)
- [API Reference](docs/api.md)
- [Deployment Guide](docs/deployment.md)
- [Migration Guide](docs/migration.md)

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# Parity tests (vs old system)
pytest tests/parity -v
```

## 🔧 Development

```bash
# Install dependencies
poetry install

# Run in development mode
poetry run python -m tradelayout_engine

# Run tests with coverage
poetry run pytest --cov=tradelayout_engine
```

## 📝 License

MIT
