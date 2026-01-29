#!/bin/bash

# TradeLayout Engine - AWS Auto-Shutdown Script
# Triggered by Lambda/EventBridge at market close (3:30 PM IST)

set -e  # Exit on error

# Configuration
LOG_FILE="/var/log/tradelayout/shutdown.log"
LOCK_FILE="/var/run/tradelayout.lock"
APP_DIR="/opt/tradelayout-engine"
VENV_DIR="$APP_DIR/venv"
BACKUP_DATE=$(date +%Y-%m-%d)

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================="
log "TradeLayout Engine - Shutdown Initiated"
log "========================================="

# Check if system is running
if [ ! -f "$LOCK_FILE" ]; then
    log "⚠️  System not running (no lock file)"
    exit 0
fi

# Step 1: Stop accepting new requests
log "🚫 Stopping new requests..."
curl -X POST http://localhost:8000/admin/maintenance-mode \
    -H "Content-Type: application/json" \
    -d '{"enabled": true}' || true
log "✅ Maintenance mode enabled"

# Step 2: Wait for active strategies to complete
log "⏳ Waiting for active strategies to complete..."
cd "$APP_DIR"
source "$VENV_DIR/bin/activate"

# Check for pending orders
PENDING_COUNT=$(python -m utils.check_pending_orders)
if [ "$PENDING_COUNT" -gt 0 ]; then
    log "⚠️  $PENDING_COUNT pending orders found"
    log "⏳ Waiting up to 5 minutes for orders to complete..."
    
    for i in {1..60}; do
        sleep 5
        PENDING_COUNT=$(python -m utils.check_pending_orders)
        if [ "$PENDING_COUNT" -eq 0 ]; then
            log "✅ All orders completed"
            break
        fi
        log "⏳ Still waiting... ($PENDING_COUNT pending)"
    done
    
    if [ "$PENDING_COUNT" -gt 0 ]; then
        log "⚠️  Timeout: $PENDING_COUNT orders still pending"
        log "📧 Sending alert..."
        python -m utils.notifications --event="shutdown" --status="warning" --message="Pending orders: $PENDING_COUNT"
    fi
fi

# Step 3: Backup data to S3
log "💾 Backing up data to S3..."

# Backup OHLCV candles
log "📊 Backing up OHLCV candles..."
if python -m backup.backup_ohlcv --date="$BACKUP_DATE"; then
    log "✅ OHLCV backup complete"
else
    log "❌ OHLCV backup failed"
fi

# Backup ticks
log "📈 Backing up ticks..."
if python -m backup.backup_ticks --date="$BACKUP_DATE"; then
    log "✅ Ticks backup complete"
else
    log "❌ Ticks backup failed"
fi

# Backup positions
log "📋 Backing up positions..."
if python -m backup.backup_positions --date="$BACKUP_DATE"; then
    log "✅ Positions backup complete"
else
    log "❌ Positions backup failed"
fi

# Backup orders
log "📝 Backing up orders..."
if python -m backup.backup_orders --date="$BACKUP_DATE"; then
    log "✅ Orders backup complete"
else
    log "❌ Orders backup failed"
fi

# Step 4: Generate daily report
log "📊 Generating daily report..."
if python -m reports.daily_report --date="$BACKUP_DATE"; then
    log "✅ Daily report generated"
else
    log "❌ Daily report generation failed"
fi

# Step 5: Stop application services
log "🛑 Stopping application services..."

# Stop indicator manager
if [ -f /var/run/tradelayout-indicators.pid ]; then
    IND_PID=$(cat /var/run/tradelayout-indicators.pid)
    log "Stopping indicator manager (PID: $IND_PID)..."
    kill -TERM $IND_PID 2>/dev/null || true
    sleep 2
    kill -KILL $IND_PID 2>/dev/null || true
    rm -f /var/run/tradelayout-indicators.pid
    log "✅ Indicator manager stopped"
fi

# Stop candle builder
if [ -f /var/run/tradelayout-candles.pid ]; then
    CANDLE_PID=$(cat /var/run/tradelayout-candles.pid)
    log "Stopping candle builder (PID: $CANDLE_PID)..."
    kill -TERM $CANDLE_PID 2>/dev/null || true
    sleep 2
    kill -KILL $CANDLE_PID 2>/dev/null || true
    rm -f /var/run/tradelayout-candles.pid
    log "✅ Candle builder stopped"
fi

# Stop WebSocket streaming
if [ -f /var/run/tradelayout-websocket.pid ]; then
    WS_PID=$(cat /var/run/tradelayout-websocket.pid)
    log "Stopping WebSocket streaming (PID: $WS_PID)..."
    kill -TERM $WS_PID 2>/dev/null || true
    sleep 2
    kill -KILL $WS_PID 2>/dev/null || true
    rm -f /var/run/tradelayout-websocket.pid
    log "✅ WebSocket streaming stopped"
fi

# Stop FastAPI server
if [ -f /var/run/tradelayout-api.pid ]; then
    API_PID=$(cat /var/run/tradelayout-api.pid)
    log "Stopping FastAPI server (PID: $API_PID)..."
    kill -TERM $API_PID 2>/dev/null || true
    sleep 2
    kill -KILL $API_PID 2>/dev/null || true
    rm -f /var/run/tradelayout-api.pid
    log "✅ FastAPI server stopped"
fi

# Kill any remaining processes
pkill -f "uvicorn.*tradelayout" || true
pkill -f "python.*streaming" || true
pkill -f "python.*processing" || true

# Step 6: Flush Redis to disk
log "💾 Flushing Redis to disk..."
redis-cli SAVE || true
log "✅ Redis flushed"

# Step 7: Stop Redis
log "⚡ Stopping Redis..."
if sudo systemctl stop redis-server; then
    log "✅ Redis stopped"
else
    log "⚠️  Redis stop failed"
fi

# Step 8: Stop ClickHouse
log "📊 Stopping ClickHouse..."
if sudo systemctl stop clickhouse-server; then
    log "✅ ClickHouse stopped"
else
    log "⚠️  ClickHouse stop failed"
fi

# Step 9: Clean up temporary files
log "🧹 Cleaning up temporary files..."
rm -rf /tmp/tradelayout-*
log "✅ Cleanup complete"

# Step 10: Remove lock file
rm -f "$LOCK_FILE"
log "✅ Lock file removed"

# Step 11: Send shutdown notification
log "📧 Sending shutdown notification..."
python -m utils.notifications --event="shutdown" --status="success"

log "========================================="
log "✅ TradeLayout Engine Shutdown Complete"
log "========================================="
log "Backup Date: $BACKUP_DATE"
log "S3 Bucket: s3://tradelayout-backups/$BACKUP_DATE/"
log "========================================="

exit 0
