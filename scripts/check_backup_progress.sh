#!/bin/bash

# Check backup progress

echo "🔍 Checking Backup Progress"
echo "============================"
echo ""

# Find latest backup directory
LATEST_BACKUP=$(ls -td /tmp/clickhouse_backup_* 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "❌ No backup in progress"
    exit 1
fi

echo "📂 Backup directory: $LATEST_BACKUP"
echo ""

# Count files
FILE_COUNT=$(ls -1 "$LATEST_BACKUP"/*.parquet 2>/dev/null | wc -l)
echo "📦 Files exported: $FILE_COUNT"

# Calculate total size
TOTAL_SIZE=$(du -sh "$LATEST_BACKUP" 2>/dev/null | cut -f1)
echo "💾 Total size: $TOTAL_SIZE"

echo ""
echo "📋 Files:"
ls -lh "$LATEST_BACKUP"/*.parquet 2>/dev/null | awk '{print "  " $9 " - " $5}'

echo ""
echo "⏱️  To monitor in real-time, run:"
echo "   watch -n 5 './scripts/check_backup_progress.sh'"
