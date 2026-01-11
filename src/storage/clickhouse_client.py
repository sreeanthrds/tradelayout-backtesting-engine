import os
import clickhouse_connect
from src.config.clickhouse_config import CLICKHOUSE_CONFIG

def get_clickhouse_client():
    """
    Central ClickHouse client factory.
    DO NOT create clients anywhere else.
    Raises RuntimeError if connection fails.
    """

    # Use the centralized configuration instead of hardcoded values
    config = CLICKHOUSE_CONFIG

    try:
        client = clickhouse_connect.get_client(
            host=config['host'],
            port=config['port'],
            username=config['username'],
            password=config['password'],
            database=config['database'],
        )
        
        # Test the connection with a simple query
        client.command("SELECT 1")
        return client
        
    except Exception as e:
        error_msg = f"❌ CRITICAL: Failed to connect to ClickHouse at {config['host']}:{config['port']}/{config['database']}"
        raise RuntimeError(f"{error_msg}: {e}") from e
