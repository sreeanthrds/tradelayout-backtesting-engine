"""
Complete End-to-End Example Strategy

Shows how to use the entire TradeLayout Engine.
"""

import asyncio
from datetime import datetime

from adapters.redis_clickhouse_data_reader import RedisClickHouseDataReader
from adapters.redis_clickhouse_data_writer import RedisClickHouseDataWriter
from adapters.order_placer_impl import OrderPlacerImpl
from strategy.strategy_executor import StrategyExecutor


async def main():
    """Run example strategy."""
    
    print("="*60)
    print("🚀 TradeLayout Engine - Example Strategy")
    print("="*60)
    print()
    
    # 1. Create DataReader
    print("1️⃣  Creating DataReader...")
    data_reader = RedisClickHouseDataReader(
        clickhouse_host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
        clickhouse_port=8443,
        clickhouse_user='default',
        clickhouse_password='0DNor8RIL2.7r',
        clickhouse_database='tradelayout',
        clickhouse_secure=True
    )
    await data_reader.connect()
    print("   ✅ DataReader connected")
    
    # 2. Create DataWriter
    print("2️⃣  Creating DataWriter...")
    data_writer = RedisClickHouseDataWriter(
        clickhouse_host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
        clickhouse_port=8443,
        clickhouse_user='default',
        clickhouse_password='0DNor8RIL2.7r',
        clickhouse_database='tradelayout',
        clickhouse_secure=True
    )
    await data_writer.connect()
    print("   ✅ DataWriter connected")
    
    # 3. Create OrderPlacer
    print("3️⃣  Creating OrderPlacer...")
    order_placer = OrderPlacerImpl(data_writer=data_writer)
    print("   ✅ OrderPlacer created")
    
    # 4. Define Strategy
    print("4️⃣  Defining strategy...")
    strategy_config = {
        'start_node': 'condition-1',
        'nodes': [
            {
                'id': 'condition-1',
                'type': 'condition',
                'condition': 'ltp_TI > 25000',
                'true_next': ['entry-1'],
                'false_next': [],
                'allow_re_entry': False
            },
            {
                'id': 'entry-1',
                'type': 'entry',
                'entry_condition': 'ltp_TI > 25000 AND ltp_TI < 26000',
                'instrument': 'NIFTY',
                'transaction_type': 'BUY',
                'quantity': 75,
                'order_type': 'MARKET',
                'exchange': 'NSE',
                'next': ['exit-1']
            },
            {
                'id': 'exit-1',
                'type': 'exit',
                'exit_condition': 'ltp_TI > 26000 OR ltp_TI < 24500',
                'position_id': 'pos-123'
            }
        ]
    }
    print("   ✅ Strategy defined")
    
    # 5. Create StrategyExecutor
    print("5️⃣  Creating StrategyExecutor...")
    executor = StrategyExecutor(
        user_id='demo-user',
        strategy_id='demo-strategy',
        strategy_config=strategy_config,
        data_reader=data_reader,
        data_writer=data_writer,
        order_placer=order_placer
    )
    await executor.initialize()
    print("   ✅ StrategyExecutor initialized")
    print(f"   📊 Nodes created: {len(executor.nodes)}")
    
    # 6. Start Strategy
    print("6️⃣  Starting strategy...")
    await executor.start()
    print("   ✅ Strategy started")
    
    # 7. Simulate Ticks
    print("7️⃣  Processing ticks...")
    ticks = [
        {'symbol': 'NIFTY', 'ltp': 24900.0, 'timestamp': datetime.now()},
        {'symbol': 'NIFTY', 'ltp': 25100.0, 'timestamp': datetime.now()},
        {'symbol': 'NIFTY', 'ltp': 25500.0, 'timestamp': datetime.now()},
        {'symbol': 'NIFTY', 'ltp': 26100.0, 'timestamp': datetime.now()},
    ]
    
    for i, tick in enumerate(ticks, 1):
        print(f"   📈 Tick {i}: LTP = {tick['ltp']}")
        await executor.process_tick(tick)
        await asyncio.sleep(0.2)  # Wait for processing
    
    print("   ✅ All ticks processed")
    
    # 8. Get Status
    print("8️⃣  Getting status...")
    status = await executor.get_status()
    print(f"   📊 Status:")
    print(f"      - Running: {status['is_running']}")
    print(f"      - Ticks: {status['tick_count']}")
    print(f"      - Active nodes: {len(status['active_nodes'])}")
    print(f"      - Can shutdown: {status['can_shutdown']}")
    
    # 9. Get Positions
    print("9️⃣  Getting positions...")
    positions = await executor.get_positions()
    print(f"   📊 Positions: {len(positions)}")
    
    # 10. Calculate PNL
    print("🔟 Calculating PNL...")
    pnl = await executor.calculate_pnl()
    print(f"   💰 Total PNL: {pnl}")
    
    # 11. Stop Strategy
    print("1️⃣1️⃣  Stopping strategy...")
    await executor.stop()
    print("   ✅ Strategy stopped")
    
    # 12. Cleanup
    print("1️⃣2️⃣  Cleaning up...")
    await data_reader.disconnect()
    await data_writer.disconnect()
    print("   ✅ Cleanup complete")
    
    print()
    print("="*60)
    print("✅ Example Complete!")
    print("="*60)


if __name__ == '__main__':
    asyncio.run(main())
