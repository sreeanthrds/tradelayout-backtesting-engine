import os
import clickhouse_connect
from src.config.clickhouse_config import CLICKHOUSE_CONFIG

def get_clickhouse_client():
    """
    Central ClickHouse client factory.
    DO NOT create clients anywhere else.
    """
    return clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
