#!/bin/bash
set -e

# ClickHouse to S3 Backup Script
# This will backup your 47.43 GB ClickHouse data to S3

echo "🔄 ClickHouse to S3 Backup Started"
echo "===================================="
echo "Time: $(date)"
echo ""

# Configuration
CLICKHOUSE_HOST="${CLICKHOUSE_HOST:-blo67czt7m.ap-south-1.aws.clickhouse.cloud}"
CLICKHOUSE_PORT="${CLICKHOUSE_PORT:-9440}"
CLICKHOUSE_USER="${CLICKHOUSE_USER:-default}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD}"
CLICKHOUSE_DATABASE="${CLICKHOUSE_DATABASE:-default}"
S3_BUCKET="${S3_BUCKET:-tradelayout-backup}"
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/clickhouse_backup_${BACKUP_DATE}"
S3_PREFIX="clickhouse-backups/${BACKUP_DATE}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Installing..."
    curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
    sudo installer -pkg AWSCLIV2.pkg -target /
    rm AWSCLIV2.pkg
fi

# Check if clickhouse-client is installed
if ! command -v clickhouse-client &> /dev/null; then
    echo "❌ clickhouse-client not found. Installing..."
    if [ ! -f "./clickhouse" ]; then
        curl https://clickhouse.com/ | sh
    fi
    # Use local clickhouse binary
    CLICKHOUSE_CLIENT="./clickhouse client"
else
    CLICKHOUSE_CLIENT="clickhouse-client"
fi

# Create backup directory
mkdir -p "${BACKUP_DIR}"
echo "✅ Created backup directory: ${BACKUP_DIR}"
echo ""

# Get list of all tables
echo "📋 Getting list of tables..."
TABLES=$($CLICKHOUSE_CLIENT \
    --host="${CLICKHOUSE_HOST}" \
    --port="${CLICKHOUSE_PORT}" \
    --user="${CLICKHOUSE_USER}" \
    --password="${CLICKHOUSE_PASSWORD}" \
    --database="${CLICKHOUSE_DATABASE}" \
    --secure \
    --query="SHOW TABLES" \
    --format=TSV)

if [ -z "$TABLES" ]; then
    echo "❌ No tables found!"
    exit 1
fi

echo "Found tables:"
echo "$TABLES"
echo ""

# Backup each table
TOTAL_SIZE=0
TABLE_COUNT=0

for TABLE in $TABLES; do
    TABLE_COUNT=$((TABLE_COUNT + 1))
    echo "📦 Backing up table: ${TABLE}"
    
    # Get table row count
    ROW_COUNT=$($CLICKHOUSE_CLIENT \
        --host="${CLICKHOUSE_HOST}" \
        --port="${CLICKHOUSE_PORT}" \
        --user="${CLICKHOUSE_USER}" \
        --password="${CLICKHOUSE_PASSWORD}" \
        --database="${CLICKHOUSE_DATABASE}" \
        --secure \
        --query="SELECT count() FROM ${TABLE}" \
        --format=TSV)
    
    echo "  Rows: ${ROW_COUNT}"
    
    # Export to Parquet (best compression)
    OUTPUT_FILE="${BACKUP_DIR}/${TABLE}.parquet"
    
    $CLICKHOUSE_CLIENT \
        --host="${CLICKHOUSE_HOST}" \
        --port="${CLICKHOUSE_PORT}" \
        --user="${CLICKHOUSE_USER}" \
        --password="${CLICKHOUSE_PASSWORD}" \
        --database="${CLICKHOUSE_DATABASE}" \
        --secure \
        --query="SELECT * FROM ${TABLE} FORMAT Parquet" \
        > "${OUTPUT_FILE}"
    
    # Get file size
    FILE_SIZE=$(stat -f%z "${OUTPUT_FILE}" 2>/dev/null || stat -c%s "${OUTPUT_FILE}" 2>/dev/null)
    TOTAL_SIZE=$((TOTAL_SIZE + FILE_SIZE))
    FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
    
    echo "  ✅ Exported: ${FILE_SIZE_MB} MB"
    echo ""
done

# Create metadata file
echo "📝 Creating metadata..."
cat > "${BACKUP_DIR}/metadata.json" << EOF
{
    "backup_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "clickhouse_host": "${CLICKHOUSE_HOST}",
    "database": "${CLICKHOUSE_DATABASE}",
    "table_count": ${TABLE_COUNT},
    "total_size_bytes": ${TOTAL_SIZE},
    "total_size_gb": $(echo "scale=2; ${TOTAL_SIZE} / 1024 / 1024 / 1024" | bc),
    "tables": [
$(for TABLE in $TABLES; do
    FILE="${BACKUP_DIR}/${TABLE}.parquet"
    SIZE=$(stat -f%z "${FILE}" 2>/dev/null || stat -c%s "${FILE}" 2>/dev/null)
    echo "        {\"table\": \"${TABLE}\", \"size_bytes\": ${SIZE}},"
done | sed '$ s/,$//')
    ]
}
EOF

echo "✅ Metadata created"
echo ""

# Upload to S3
echo "☁️  Uploading to S3..."
echo "Bucket: s3://${S3_BUCKET}/${S3_PREFIX}/"
echo ""

# Create S3 bucket if it doesn't exist
aws s3 mb "s3://${S3_BUCKET}" 2>/dev/null || true

# Upload files
aws s3 sync "${BACKUP_DIR}/" "s3://${S3_BUCKET}/${S3_PREFIX}/" \
    --storage-class STANDARD \
    --no-progress

echo ""
echo "✅ Upload complete!"
echo ""

# Verify upload
echo "🔍 Verifying upload..."
S3_FILES=$(aws s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}/" --recursive | wc -l)
LOCAL_FILES=$(ls -1 "${BACKUP_DIR}" | wc -l)

if [ "$S3_FILES" -eq "$LOCAL_FILES" ]; then
    echo "✅ Verification successful: ${S3_FILES} files uploaded"
else
    echo "⚠️  Warning: File count mismatch (Local: ${LOCAL_FILES}, S3: ${S3_FILES})"
fi

echo ""

# Calculate costs
TOTAL_SIZE_GB=$(echo "scale=2; ${TOTAL_SIZE} / 1024 / 1024 / 1024" | bc)
MONTHLY_COST=$(echo "scale=4; ${TOTAL_SIZE_GB} * 0.023" | bc)

echo "📊 BACKUP SUMMARY"
echo "===================================="
echo "Tables backed up: ${TABLE_COUNT}"
echo "Total size: ${TOTAL_SIZE_GB} GB"
echo "S3 location: s3://${S3_BUCKET}/${S3_PREFIX}/"
echo "Monthly S3 cost: \$${MONTHLY_COST}"
echo "Backup completed: $(date)"
echo ""

# Cleanup local files (optional)
read -p "Delete local backup files? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "${BACKUP_DIR}"
    echo "✅ Local files deleted"
else
    echo "ℹ️  Local files kept at: ${BACKUP_DIR}"
fi

echo ""
echo "🎉 BACKUP COMPLETE!"
echo ""
echo "To restore, run:"
echo "  ./restore_clickhouse_from_s3.sh ${BACKUP_DATE}"
