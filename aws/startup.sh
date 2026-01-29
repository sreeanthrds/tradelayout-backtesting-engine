#!/bin/bash

# TradeLayout Engine - AWS Auto-Startup Script
# Triggered by Lambda/EventBridge at market open (9:00 AM IST)

set -e  # Exit on error

# Configuration
LOG_FILE="/var/log/tradelayout/startup.log"
LOCK_FILE="/var/run/tradelayout.lock"
APP_DIR="/opt/tradelayout-engine"
VENV_DIR="$APP_DIR/venv"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================="
log "TradeLayout Engine - Startup Initiated"
log "========================================="

# Check if already running
if [ -f "$LOCK_FILE" ]; then
    log "⚠️  System already running (lock file exists)"
    exit 0
fi

# Create lock file
touch "$LOCK_FILE"
log "✅ Lock file created"

# Step 1: Start ClickHouse
log "📊 Starting ClickHouse..."
if sudo systemctl start clickhouse-server; then
    log "✅ ClickHouse started"
else
    log "❌ ClickHouse failed to start"
    rm -f "$LOCK_FILE"
    exit 1
fi

# Wait for ClickHouse to be ready
log "⏳ Waiting for ClickHouse to be ready..."
for i in {1..30}; do
    if clickhouse-client --query "SELECT 1" > /dev/null 2>&1; then
        log "✅ ClickHouse is ready"
        break
    fi
    sleep 1
done

# Step 2: Start Redis
log "⚡ Starting Redis..."
if sudo systemctl start redis-server; then
    log "✅ Redis started"
else
    log "❌ Redis failed to start"
    rm -f "$LOCK_FILE"
    exit 1
fi

# Wait for Redis to be ready
log "⏳ Waiting for Redis to be ready..."
for i in {1..10}; do
    if redis-cli ping > /dev/null 2>&1; then
        log "✅ Redis is ready"
        break
    fi
    sleep 1
done

# Step 3: Load Backup from S3
log "📥 Loading backup from S3..."
cd "$APP_DIR"
source "$VENV_DIR/bin/activate"

if python -m backup.loader --date=$(date -d "yesterday" +%Y-%m-%d); then
    log "✅ Backup loaded successfully"
else
    log "⚠️  Backup load failed (may be first run)"
fi

# Step 4: Warm up Redis cache
log "🔥 Warming up Redis cache..."
if python -m backup.cache_warmer; then
    log "✅ Cache warmed up"
else
    log "⚠️  Cache warmup failed"
fi

# Step 5: Start FastAPI server
log "🚀 Starting FastAPI server..."
cd "$APP_DIR"

# Kill any existing uvicorn processes
pkill -f "uvicorn.*tradelayout" || true

# Start FastAPI in background
nohup uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info \
    > /var/log/tradelayout/api.log 2>&1 &

API_PID=$!
echo $API_PID > /var/run/tradelayout-api.pid
log "✅ FastAPI started (PID: $API_PID)"

# Wait for API to be ready
log "⏳ Waiting for API to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log "✅ API is ready"
        break
    fi
    sleep 1
done

# Step 6: Start WebSocket streaming
log "📡 Starting WebSocket streaming..."
nohup python -m streaming.websocket_manager \
    > /var/log/tradelayout/websocket.log 2>&1 &

WS_PID=$!
echo $WS_PID > /var/run/tradelayout-websocket.pid
log "✅ WebSocket streaming started (PID: $WS_PID)"

# Step 7: Start candle builder
log "🕯️  Starting candle builder..."
nohup python -m processing.candle_builder \
    > /var/log/tradelayout/candles.log 2>&1 &

CANDLE_PID=$!
echo $CANDLE_PID > /var/run/tradelayout-candles.pid
log "✅ Candle builder started (PID: $CANDLE_PID)"

# Step 8: Start indicator manager
log "📈 Starting indicator manager..."
nohup python -m processing.indicator_manager \
    > /var/log/tradelayout/indicators.log 2>&1 &

IND_PID=$!
echo $IND_PID > /var/run/tradelayout-indicators.pid
log "✅ Indicator manager started (PID: $IND_PID)"

# Step 9: Health check
log "🏥 Running health check..."
sleep 5

HEALTH_STATUS=$(curl -s http://localhost:8000/health | jq -r '.status')
if [ "$HEALTH_STATUS" = "healthy" ]; then
    log "✅ Health check passed"
else
    log "❌ Health check failed"
    rm -f "$LOCK_FILE"
    exit 1
fi

# Step 10: Send startup notification
log "📧 Sending startup notification..."
python -m utils.notifications --event="startup" --status="success"

log "========================================="
log "✅ TradeLayout Engine Started Successfully"
log "========================================="
log "API: http://localhost:8000"
log "Logs: /var/log/tradelayout/"
log "========================================="

exit 0
