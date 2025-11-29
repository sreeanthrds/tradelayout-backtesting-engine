#!/bin/bash
set -e

# ClickHouse Restore from S3 Script

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_date>"
    echo "Example: $0 20251105_062700"
    echo ""
    echo "Available backups:"
    aws s3 ls s3://${S3_BUCKET:-tradelayout-backup}/clickhouse-backups/ | grep PRE
    exit 1
fi

BACKUP_DATE=$1

echo "🔄 ClickHouse Restore from S3"
echo "===================================="
echo "Backup date: ${BACKUP_DATE}"
echo "Time: $(date)"
echo ""

# Configuration
CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-localhost}"
CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-9000}"
CLICKHOUSE_USER="${CLICKHOUSE_USER:-default}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD}"
CLICKHOUSE_DATABASE="${CLICKHOUSE_DATABASE:-tradelayout}"
S3_BUCKET="${S3_BUCKET:-tradelayout-backup}"
S3_PREFIX="clickhouse-backups/${BACKUP_DATE}"
RESTORE_DIR="/tmp/clickhouse_restore_${BACKUP_DATE}"

# Create restore directory
mkdir -p "${RESTORE_DIR}"
echo "✅ Created restore directory: ${RESTORE_DIR}"
echo ""

# Download from S3
echo "☁️  Downloading from S3..."
echo "Source: s3://${S3_BUCKET}/${S3_PREFIX}/"
echo ""

aws s3 sync "s3://${S3_BUCKET}/${S3_PREFIX}/" "${RESTORE_DIR}/" \
    --no-progress

echo "✅ Download complete!"
echo ""

# Read metadata
if [ -f "${RESTORE_DIR}/metadata.json" ]; then
    echo "📋 Backup metadata:"
    cat "${RESTORE_DIR}/metadata.json" | jq .
    echo ""
fi

# Start ClickHouse (if using Docker)
if command -v docker-compose &> /dev/null; then
    echo "🐳 Starting ClickHouse..."
    docker-compose up -d clickhouse
    sleep 15
    echo "✅ ClickHouse started"
    echo ""
fi

# Create database
echo "🗄️  Creating database..."
clickhouse-client \
    --host="${CLICKHOUSE_HOST}" \
    --port="${CLICKHOUSE_PORT}" \
    --user="${CLICKHOUSE_USER}" \
    --password="${CLICKHOUSE_PASSWORD}" \
    --query="CREATE DATABASE IF NOT EXISTS ${CLICKHOUSE_DATABASE}"

echo "✅ Database created"
echo ""

# Restore each table
TABLE_COUNT=0
for PARQUET_FILE in "${RESTORE_DIR}"/*.parquet; do
    if [ -f "$PARQUET_FILE" ]; then
        TABLE_NAME=$(basename "$PARQUET_FILE" .parquet)
        TABLE_COUNT=$((TABLE_COUNT + 1))
        
        echo "📦 Restoring table: ${TABLE_NAME}"
        
        # Import from Parquet
        clickhouse-client \
            --host="${CLICKHOUSE_HOST}" \
            --port="${CLICKHOUSE_PORT}" \
            --user="${CLICKHOUSE_USER}" \
            --password="${CLICKHOUSE_PASSWORD}" \
            --database="${CLICKHOUSE_DATABASE}" \
            --query="INSERT INTO ${TABLE_NAME} FORMAT Parquet" \
            < "$PARQUET_FILE"
        
        # Get row count
        ROW_COUNT=$(clickhouse-client \
            --host="${CLICKHOUSE_HOST}" \
            --port="${CLICKHOUSE_PORT}" \
            --user="${CLICKHOUSE_USER}" \
            --password="${CLICKHOUSE_PASSWORD}" \
            --database="${CLICKHOUSE_DATABASE}" \
            --query="SELECT count() FROM ${TABLE_NAME}" \
            --format=TSV)
        
        echo "  ✅ Restored: ${ROW_COUNT} rows"
        echo ""
    fi
done

# Cleanup
read -p "Delete downloaded files? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "${RESTORE_DIR}"
    echo "✅ Downloaded files deleted"
else
    echo "ℹ️  Downloaded files kept at: ${RESTORE_DIR}"
fi

echo ""
echo "🎉 RESTORE COMPLETE!"
echo "Tables restored: ${TABLE_COUNT}"
echo ""
