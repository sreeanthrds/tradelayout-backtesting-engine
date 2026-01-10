import os

CLICKHOUSE_CONFIG = {
    "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
    "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
    "username": os.getenv("CLICKHOUSE_USER", "tradelayout"),
    "password": os.getenv("CLICKHOUSE_PASSWORD", "Unificater123*"),
    "database": os.getenv("CLICKHOUSE_DATABASE", "default"),
} 