"""
ClickHouse Client Factory
Provides centralized ClickHouse client creation and connection management
"""
import os
import clickhouse_connect
from typing import Optional

_client_instance: Optional[clickhouse_connect.driver.Client] = None

def get_clickhouse_client():
    """
    Get or create ClickHouse client instance
    Uses environment variables for configuration
    """
    global _client_instance
    
    if _client_instance is None:
        host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        port = int(os.getenv('CLICKHOUSE_PORT', '8123'))
        user = os.getenv('CLICKHOUSE_USER', 'tradelayout')
        password = os.getenv('CLICKHOUSE_PASSWORD', 'Unificater123*')
        database = os.getenv('CLICKHOUSE_DATABASE', 'tradelayout')
        
        try:
            _client_instance = clickhouse_connect.get_client(
                host=host,
                port=port,
                username=user,
                password=password,
                database=database
            )
            print(f"✅ ClickHouse client connected: {host}:{port}/{database}")
        except Exception as e:
            print(f"❌ Failed to connect to ClickHouse: {e}")
            raise
    
    return _client_instance

def reset_client():
    """Reset the client instance (useful for testing or reconnection)"""
    global _client_instance
    if _client_instance:
        try:
            _client_instance.close()
        except:
            pass
    _client_instance = None
