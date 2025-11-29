#!/bin/bash

# TradeLayout Engine - Test Runner
# Run all tests in sequence, stop if any fail

set -e  # Exit on first failure

echo "======================================================================"
echo "🧪 TradeLayout Engine - Comprehensive Test Suite"
echo "======================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test file
run_test() {
    local test_file=$1
    local test_name=$2
    
    echo ""
    echo "----------------------------------------------------------------------"
    echo "📋 Running: $test_name"
    echo "----------------------------------------------------------------------"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if python -m pytest "$test_file" -v --tb=short --color=yes; then
        echo -e "${GREEN}✅ PASSED: $test_name${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}❌ FAILED: $test_name${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Check if ClickHouse is running
echo "Checking if ClickHouse is running..."
if ! clickhouse-client --query "SELECT 1" > /dev/null 2>&1; then
    echo -e "${RED}❌ ClickHouse is not running!${NC}"
    echo "Please start ClickHouse: clickhouse-server"
    exit 1
fi
echo -e "${GREEN}✅ ClickHouse is running${NC}"

# Check if Redis is running
echo "Checking if Redis is running..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${RED}❌ Redis is not running!${NC}"
    echo "Please start Redis: redis-server"
    exit 1
fi
echo -e "${GREEN}✅ Redis is running${NC}"

echo ""
echo "======================================================================"
echo "🚀 Starting Test Suite"
echo "======================================================================"

# Stage 1: Infrastructure Tests
echo ""
echo -e "${YELLOW}📦 STAGE 1: Infrastructure Tests${NC}"
run_test "tests/test_infrastructure.py" "Infrastructure Tests" || exit 1

# Stage 2: DataReader Tests
echo ""
echo -e "${YELLOW}📦 STAGE 2: DataReader Tests${NC}"
run_test "tests/test_data_reader.py" "DataReader Tests" || exit 1

# Stage 3: DataWriter Tests (when created)
if [ -f "tests/test_data_writer.py" ]; then
    echo ""
    echo -e "${YELLOW}📦 STAGE 3: DataWriter Tests${NC}"
    run_test "tests/test_data_writer.py" "DataWriter Tests" || exit 1
fi

# Stage 4: Expression Evaluator Tests (when created)
if [ -f "tests/test_expression_evaluator.py" ]; then
    echo ""
    echo -e "${YELLOW}📦 STAGE 4: Expression Evaluator Tests${NC}"
    run_test "tests/test_expression_evaluator.py" "Expression Evaluator Tests" || exit 1
fi

# Stage 5: Node Tests (when created)
if [ -f "tests/test_nodes.py" ]; then
    echo ""
    echo -e "${YELLOW}📦 STAGE 5: Node Tests${NC}"
    run_test "tests/test_nodes.py" "Node Tests" || exit 1
fi

# Stage 6: Strategy Executor Tests (when created)
if [ -f "tests/test_strategy_executor.py" ]; then
    echo ""
    echo -e "${YELLOW}📦 STAGE 6: Strategy Executor Tests${NC}"
    run_test "tests/test_strategy_executor.py" "Strategy Executor Tests" || exit 1
fi

# Final Summary
echo ""
echo "======================================================================"
echo "📊 TEST SUMMARY"
echo "======================================================================"
echo ""
echo "Total Test Suites: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    echo ""
    echo "🎉 Ready to proceed to next stage!"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED!${NC}"
    echo ""
    echo "⚠️  Please fix failing tests before proceeding."
    exit 1
fi
