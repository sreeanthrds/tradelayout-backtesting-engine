#!/bin/bash

# Run All Tests - TradeLayout Engine
# Run this when you come back!

set -e

echo "======================================================================"
echo "🧪 Running All TradeLayout Engine Tests"
echo "======================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${BLUE}Starting Redis...${NC}"
    redis-server --daemonize yes
    sleep 2
fi

echo -e "${GREEN}✅ Redis running${NC}"
echo ""

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo -e "${GREEN}✅ Environment variables loaded${NC}"
else
    echo -e "${RED}❌ .env file not found${NC}"
    exit 1
fi

echo ""
echo "======================================================================"
echo "📊 Test Summary"
echo "======================================================================"
echo ""

# Run tests with pytest
pytest tests/ \
    -v \
    --tb=short \
    --color=yes \
    -s \
    --cov=. \
    --cov-report=html \
    --cov-report=term-missing \
    --cov-report=term:skip-covered

TEST_EXIT_CODE=$?

echo ""
echo "======================================================================"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
fi
echo "======================================================================"
echo ""
echo "Coverage report: htmlcov/index.html"
echo ""

exit $TEST_EXIT_CODE
