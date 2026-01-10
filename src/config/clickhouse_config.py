#!/usr/bin/env python3
"""
ClickHouse Configuration for Live Trading Engine
"""

import os
from typing import Dict, Any


class ClickHouseConfig:
    """ClickHouse database configuration."""
    
    # Connection settings - Using localhost
    HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
    PORT = int(os.getenv('CLICKHOUSE_PORT', '8123'))  # Added missing PORT setting
    USER = os.getenv('CLICKHOUSE_USER', 'tradelayout')  # Fixed: changed from 'default' to 'tradelayout'
    PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', 'Unificater123*')  # Fixed: added default password
    SECURE = os.getenv('CLICKHOUSE_SECURE', 'false').lower() == 'true'
    DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'default')
    
    # Table settings
    TABLE_NAME = os.getenv('CLICKHOUSE_TABLE', 'nse_ticks_stocks')
    
    # Query settings
    BATCH_SIZE = int(os.getenv('CLICKHOUSE_BATCH_SIZE', '10000'))
    QUERY_TIMEOUT = int(os.getenv('CLICKHOUSE_QUERY_TIMEOUT', '300'))  # seconds
    
    # Market hours (IST)
    MARKET_OPEN_TIME = '09:15:00'
    MARKET_CLOSE_TIME = '15:30:00'
    
    @classmethod
    def get_connection_config(cls) -> Dict[str, Any]:
        """Get ClickHouse connection configuration."""
        return {
            'host': cls.HOST,
            'port': cls.PORT,  # Added port to connection config
            'user': cls.USER,
            'password': cls.PASSWORD,
            'secure': cls.SECURE,
            'database': cls.DATABASE
        }
    
    @classmethod
    def get_table_config(cls) -> Dict[str, Any]:
        """Get ClickHouse table configuration."""
        return {
            'table': cls.TABLE_NAME,
            'batch_size': cls.BATCH_SIZE,
            'query_timeout': cls.QUERY_TIMEOUT
        }
    
    @classmethod
    def get_market_hours_config(cls) -> Dict[str, str]:
        """Get market hours configuration."""
        return {
            'open_time': cls.MARKET_OPEN_TIME,
            'close_time': cls.MARKET_CLOSE_TIME
        }
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate ClickHouse configuration."""
        required_fields = ['HOST', 'USER', 'PASSWORD', 'TABLE_NAME']
        
        for field in required_fields:
            if not getattr(cls, field):
                print(f"Error: Missing required ClickHouse configuration: {field}")
                return False
        
        return True


# Default configuration instance
clickhouse_config = ClickHouseConfig()

# Also provide the dict format for the centralized client factory
CLICKHOUSE_CONFIG = {
    "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
    "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
    "username": os.getenv("CLICKHOUSE_USER", "tradelayout"),
    "password": os.getenv("CLICKHOUSE_PASSWORD", "Unificater123*"),
    "database": os.getenv("CLICKHOUSE_DATABASE", "default"),
} 