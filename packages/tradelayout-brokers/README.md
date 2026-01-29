# tradelayout-brokers

Unified broker adapter interface for live trading and backtesting.

## Features

- ✅ Unified interface for all brokers
- ✅ AngelOne, Dhan, AliceBlue support
- ✅ Backtest broker with ClickHouse/AngelOne data sources
- ✅ WebSocket tick streaming
- ✅ Order management
- ✅ Position tracking

## Usage

```python
from tradelayout_brokers import AngelOneBroker, BacktestBroker

# Live trading
broker = AngelOneBroker(api_key="...", client_id="...")
await broker.connect()
await broker.subscribe(["NIFTY", "BANKNIFTY"])

# Backtesting
broker = BacktestBroker(
    data_source="clickhouse",
    start_date="2024-01-01",
    end_date="2024-01-31"
)
await broker.connect()
```

## Architecture

All brokers implement the `BrokerAdapter` interface:

```python
class BrokerAdapter(ABC):
    @abstractmethod
    async def connect(self): pass
    
    @abstractmethod
    async def subscribe(self, symbols: List[str]): pass
    
    @abstractmethod
    def on_tick(self, callback: Callable): pass
    
    @abstractmethod
    async def place_order(self, order: Order): pass
```

## Testing

```bash
pytest tests/ -v
```
