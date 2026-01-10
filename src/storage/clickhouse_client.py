import os
import clickhouse_connect

def get_clickhouse_client():
    """
    Central ClickHouse client factory.
    DO NOT create clients anywhere else.
    """

    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    user = os.getenv("CLICKHOUSE_USER", "tradelayout")
    password = os.getenv("CLICKHOUSE_PASSWORD", "Unificater123*")
    database = os.getenv("CLICKHOUSE_DATABASE", "tradelayout")

    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=user,
        password=password,
        database=database,
    )
