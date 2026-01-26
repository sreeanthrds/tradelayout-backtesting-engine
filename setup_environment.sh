#!/bin/bash
# Silent environment setup for TradeLayout Backtesting Engine
# Ensures consistent clickhouse-connect version

echo "🔧 Setting up TradeLayout environment..."

# Install pinned version silently
pip install clickhouse-connect==0.8.18 -q

# Verify installation
if pip list | grep -q "clickhouse-connect 0.8.18"; then
    echo "✅ clickhouse-connect 0.8.18 installed successfully"
else
    echo "❌ Failed to install clickhouse-connect 0.8.18"
    exit 1
fi

echo "🚀 Environment ready for backtesting!"
