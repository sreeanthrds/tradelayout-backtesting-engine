#!/bin/bash

# Complete System Runner - TradeLayout Engine
# Runs all tests and example strategy

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================================================"
echo "🚀 TradeLayout Engine - Complete System Runner"
echo "======================================================================"
echo ""

# Check virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Check Redis
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${BLUE}Starting Redis...${NC}"
    redis-server --daemonize yes
    sleep 2
fi

echo -e "${GREEN}✅ Environment ready${NC}"
echo ""

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Menu
echo "What would you like to do?"
echo ""
echo "1) Run all tests (70 tests)"
echo "2) Run example strategy"
echo "3) Run both tests and example"
echo "4) Check system status"
echo "5) Exit"
echo ""
read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        echo ""
        echo "======================================================================"
        echo "🧪 Running All Tests"
        echo "======================================================================"
        echo ""
        ./run_all_tests.sh
        ;;
    2)
        echo ""
        echo "======================================================================"
        echo "📊 Running Example Strategy"
        echo "======================================================================"
        echo ""
        python3 example_strategy.py
        ;;
    3)
        echo ""
        echo "======================================================================"
        echo "🧪 Running All Tests"
        echo "======================================================================"
        echo ""
        ./run_all_tests.sh
        
        echo ""
        echo "======================================================================"
        echo "📊 Running Example Strategy"
        echo "======================================================================"
        echo ""
        python3 example_strategy.py
        ;;
    4)
        echo ""
        echo "======================================================================"
        echo "📊 System Status"
        echo "======================================================================"
        echo ""
        
        # Check ClickHouse
        echo "Checking ClickHouse Cloud..."
        python3 << 'EOF'
import clickhouse_connect
try:
    client = clickhouse_connect.get_client(
        host='blo67czt7m.ap-south-1.aws.clickhouse.cloud',
        port=8443,
        username='default',
        password='0DNor8RIL2.7r',
        database='tradelayout',
        secure=True
    )
    result = client.query('SHOW TABLES')
    print(f"✅ ClickHouse Cloud: {len(result.result_rows)} tables")
except Exception as e:
    print(f"❌ ClickHouse Cloud: {e}")
EOF
        
        # Check Redis
        echo ""
        echo "Checking Redis..."
        if redis-cli ping > /dev/null 2>&1; then
            echo "✅ Redis: Running"
        else
            echo "❌ Redis: Not running"
        fi
        
        # Check files
        echo ""
        echo "Checking files..."
        echo "✅ Code files: $(find . -name '*.py' | wc -l | tr -d ' ')"
        echo "✅ Test files: $(find tests -name '*.py' | wc -l | tr -d ' ')"
        echo "✅ Documentation: $(find . -name '*.md' | wc -l | tr -d ' ')"
        
        echo ""
        echo "======================================================================"
        echo "✅ System Status Check Complete"
        echo "======================================================================"
        ;;
    5)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "======================================================================"
echo "✅ Complete!"
echo "======================================================================"
