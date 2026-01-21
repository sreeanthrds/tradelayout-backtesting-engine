#!/bin/bash
# Automated Deployment Script for TradeLayout Backtesting Engine
# This script verifies ClickHouse connectivity before starting the service

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "TradeLayout Backtesting Engine Deployment"
echo "=========================================="

# Check if running in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  Not in virtual environment${NC}"
    echo "Activating virtual environment..."
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        echo -e "${RED}❌ Virtual environment not found${NC}"
        echo "Create it with: python3 -m venv venv"
        exit 1
    fi
fi

# Run setup and verification
echo ""
echo "Running setup and verification..."
python3 setup_and_verify.py

# Check exit code
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Setup and verification failed${NC}"
    echo "Please fix the issues and try again"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ All checks passed!${NC}"
echo ""

# Ask user how to start the service
echo "How would you like to start the service?"
echo "1. Foreground (for testing)"
echo "2. Background (nohup)"
echo "3. Systemd service (production)"
echo "4. Skip (just verify)"

read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo "Starting in foreground..."
        python backtest_api_server.py
        ;;
    2)
        echo "Starting in background..."
        nohup python backtest_api_server.py > logs/api_server.log 2>&1 &
        echo $! > api_server.pid
        echo -e "${GREEN}✅ Server started in background (PID: $(cat api_server.pid))${NC}"
        echo "View logs: tail -f logs/api_server.log"
        echo "Stop server: kill \$(cat api_server.pid)"
        ;;
    3)
        echo "Starting systemd service..."
        sudo systemctl restart tradelayout-backtest-api.service
        sleep 2
        sudo systemctl status tradelayout-backtest-api.service
        ;;
    4)
        echo "Verification complete. Service not started."
        ;;
    *)
        echo "Invalid choice. Service not started."
        ;;
esac

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
