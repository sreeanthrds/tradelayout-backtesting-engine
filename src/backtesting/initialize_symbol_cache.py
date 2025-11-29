"""
Initialize Symbol Cache
========================

Loads scrip masters for all brokers and builds symbol cache.
Should be called at startup before processing first tick.

Can run in background thread for async loading.
"""

import logging
from pathlib import Path
from src.symbol_mapping.symbol_cache_manager import get_symbol_cache_manager

logger = logging.getLogger(__name__)


def initialize_symbol_cache(
    data_dir: str = 'data/scrip_masters',
    async_load: bool = True
) -> bool:
    """
    Initialize symbol cache with all broker scrip masters.
    
    Args:
        data_dir: Directory containing scrip master files
        async_load: If True, load in background thread
    
    Returns:
        True if initialization started successfully
    
    Expected file structure:
        data/scrip_masters/
        ├── angelone_scrip_master.csv
        ├── zerodha_instruments.csv
        ├── aliceblue_scrip_master.csv
        └── clickhouse_symbols.csv
    """
    data_path = Path(data_dir)
    
    if not data_path.exists():
        logger.error(f"❌ Data directory not found: {data_dir}")
        return False
    
    # Define scrip master paths
    scrip_master_paths = {
        'angelone': str(data_path / 'angelone_scrip_master.csv'),
        'zerodha': str(data_path / 'zerodha_instruments.csv'),
        'aliceblue': str(data_path / 'aliceblue_scrip_master.csv'),
        'clickhouse': str(data_path / 'clickhouse_symbols.csv')
    }
    
    # Filter to only existing files
    existing_paths = {
        broker: path
        for broker, path in scrip_master_paths.items()
        if Path(path).exists()
    }
    
    if not existing_paths:
        logger.error(f"❌ No scrip master files found in {data_dir}")
        return False
    
    logger.info(f"📊 Found scrip masters for: {', '.join(existing_paths.keys())}")
    
    # Get symbol cache manager
    cache_manager = get_symbol_cache_manager()
    
    # Load all brokers
    cache_manager.load_all_brokers(existing_paths, async_load=async_load)
    
    if async_load:
        logger.info("🔄 Symbol cache loading in background...")
    else:
        logger.info("✅ Symbol cache loaded successfully")
    
    return True


def wait_for_symbol_cache(timeout: int = 30) -> bool:
    """
    Wait for symbol cache to finish loading.
    
    Args:
        timeout: Maximum seconds to wait
    
    Returns:
        True if loaded, False if timeout
    """
    import time
    
    cache_manager = get_symbol_cache_manager()
    
    start_time = time.time()
    while not cache_manager.is_loaded():
        if time.time() - start_time > timeout:
            logger.error(f"❌ Symbol cache loading timeout after {timeout}s")
            return False
        
        time.sleep(0.1)
    
    logger.info("✅ Symbol cache ready")
    return True


def get_subscription_list(broker_name: str, indices: list = None) -> list:
    """
    Get list of symbols to subscribe for WebSocket.
    
    Args:
        broker_name: Broker name
        indices: List of indices (default: all supported)
    
    Returns:
        List of dicts with subscription info
    
    Example:
        symbols = get_subscription_list('angelone', ['NIFTY', 'BANKNIFTY'])
        for symbol in symbols:
            websocket.subscribe(symbol['token'], symbol['exchange'])
    """
    cache_manager = get_symbol_cache_manager()
    
    if not cache_manager.is_loaded():
        logger.warning("⚠️  Symbol cache not loaded yet")
        return []
    
    return cache_manager.get_symbols_for_subscription(broker_name, indices)


if __name__ == '__main__':
    # Test initialization
    logging.basicConfig(level=logging.INFO)
    
    # Initialize (sync for testing)
    success = initialize_symbol_cache(async_load=False)
    
    if success:
        # Get stats
        cache_manager = get_symbol_cache_manager()
        stats = cache_manager.get_stats()
        
        print("\n" + "="*60)
        print("SYMBOL CACHE STATISTICS")
        print("="*60)
        print(f"Loaded: {stats['loaded']}")
        print(f"Total Instruments: {stats['total_instruments']}")
        print(f"Brokers: {', '.join(stats['brokers'])}")
        print("\nInstruments per broker:")
        for broker, count in stats['instruments_per_broker'].items():
            print(f"  {broker}: {count}")
        print(f"\nSupported Indices: {', '.join(stats['supported_indices'])}")
        print("="*60)
        
        # Test conversion
        print("\n" + "="*60)
        print("CONVERSION TESTS")
        print("="*60)
        
        # AngelOne test
        if 'angelone' in stats['brokers']:
            broker_symbol = 'NIFTY28NOV2425800CE'
            unified = cache_manager.to_unified('angelone', broker_symbol)
            back = cache_manager.from_unified('angelone', unified)
            token = cache_manager.get_token('angelone', unified)
            print(f"\nAngelOne:")
            print(f"  Broker: {broker_symbol}")
            print(f"  Unified: {unified}")
            print(f"  Back: {back}")
            print(f"  Token: {token}")
        
        # Get subscription list
        print("\n" + "="*60)
        print("SUBSCRIPTION LIST (First 5)")
        print("="*60)
        
        if 'angelone' in stats['brokers']:
            symbols = get_subscription_list('angelone', ['NIFTY'])[:5]
            for sym in symbols:
                print(f"\n{sym['unified_symbol']}")
                print(f"  Broker: {sym['broker_symbol']}")
                print(f"  Token: {sym['token']}")
                print(f"  Exchange: {sym['exchange']}")
                print(f"  Type: {sym['instrument_type']}")
