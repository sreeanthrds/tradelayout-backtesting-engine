"""
ClickHouse Configuration
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class ClickHouseConfig:
    """ClickHouse database configuration"""
    host: str = 'localhost'
    port: int = 8123
    user: str = 'default'
    password: str = ''
    database: str = 'tradelayout'
    
    @classmethod
    def from_env(cls) -> 'ClickHouseConfig':
        """Create configuration from environment variables"""
        return cls(
            host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
            port=int(os.getenv('CLICKHOUSE_PORT', '8123')),
            user=os.getenv('CLICKHOUSE_USER', 'tradelayout'),
            password=os.getenv('CLICKHOUSE_PASSWORD', ''),
            database=os.getenv('CLICKHOUSE_DATABASE', 'tradelayout')
        )
    
    @property
    def connection_url(self) -> str:
        """Get ClickHouse connection URL"""
        if self.password:
            return f"clickhouse://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"clickhouse://{self.user}@{self.host}:{self.port}/{self.database}"
    
    @property
    def http_url(self) -> str:
        """Get ClickHouse HTTP URL"""
        if self.password:
            return f"http://{self.user}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"

# Default configuration instance
default_config = ClickHouseConfig.from_env()
