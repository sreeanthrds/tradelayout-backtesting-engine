#!/bin/bash

# TradeLayout Engine - Installation Script
# Installs ClickHouse, Redis, and all dependencies

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "🚀 TradeLayout Engine - Installation"
echo "======================================================================"
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "Detected: macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "Detected: Linux"
else
    echo -e "${RED}❌ Unsupported OS: $OSTYPE${NC}"
    exit 1
fi

echo ""

# ============================================================================
# Step 1: Install ClickHouse
# ============================================================================
echo "----------------------------------------------------------------------"
echo "📊 Step 1: Installing ClickHouse"
echo "----------------------------------------------------------------------"

if command -v clickhouse-client &> /dev/null; then
    echo -e "${YELLOW}⚠️  ClickHouse already installed${NC}"
    clickhouse-client --query "SELECT version()" || true
else
    if [ "$OS" == "macos" ]; then
        echo "Installing ClickHouse via Homebrew..."
        brew install clickhouse
    else
        echo "Installing ClickHouse on Linux..."
        sudo apt-get install -y apt-transport-https ca-certificates dirmngr
        sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 8919F6BD2B48D754
        echo "deb https://packages.clickhouse.com/deb stable main" | sudo tee /etc/apt/sources.list.d/clickhouse.list
        sudo apt-get update
        sudo apt-get install -y clickhouse-server clickhouse-client
    fi
    echo -e "${GREEN}✅ ClickHouse installed${NC}"
fi

# Start ClickHouse
echo "Starting ClickHouse server..."
if [ "$OS" == "macos" ]; then
    # Check if already running
    if pgrep -x "clickhouse-server" > /dev/null; then
        echo -e "${YELLOW}⚠️  ClickHouse already running${NC}"
    else
        clickhouse-server &
        sleep 3
    fi
else
    sudo systemctl start clickhouse-server
    sudo systemctl enable clickhouse-server
fi

# Wait for ClickHouse to be ready
echo "Waiting for ClickHouse to be ready..."
for i in {1..30}; do
    if clickhouse-client --query "SELECT 1" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ ClickHouse is ready${NC}"
        break
    fi
    sleep 1
done

echo ""

# ============================================================================
# Step 2: Install Redis
# ============================================================================
echo "----------------------------------------------------------------------"
echo "⚡ Step 2: Installing Redis"
echo "----------------------------------------------------------------------"

if command -v redis-cli &> /dev/null; then
    echo -e "${YELLOW}⚠️  Redis already installed${NC}"
    redis-cli --version || true
else
    if [ "$OS" == "macos" ]; then
        echo "Installing Redis via Homebrew..."
        brew install redis
    else
        echo "Installing Redis on Linux..."
        sudo apt-get update
        sudo apt-get install -y redis-server
    fi
    echo -e "${GREEN}✅ Redis installed${NC}"
fi

# Start Redis
echo "Starting Redis server..."
if [ "$OS" == "macos" ]; then
    # Check if already running
    if pgrep -x "redis-server" > /dev/null; then
        echo -e "${YELLOW}⚠️  Redis already running${NC}"
    else
        redis-server &
        sleep 2
    fi
else
    sudo systemctl start redis-server
    sudo systemctl enable redis-server
fi

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
for i in {1..10}; do
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis is ready${NC}"
        break
    fi
    sleep 1
done

echo ""

# ============================================================================
# Step 3: Create Python Virtual Environment
# ============================================================================
echo "----------------------------------------------------------------------"
echo "🐍 Step 3: Setting up Python Environment"
echo "----------------------------------------------------------------------"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.9+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python version: $PYTHON_VERSION"

# Create virtual environment
if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment already exists${NC}"
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo -e "${GREEN}✅ Python dependencies installed${NC}"
echo ""

# ============================================================================
# Step 4: Create Database Schema
# ============================================================================
echo "----------------------------------------------------------------------"
echo "🗄️  Step 4: Creating Database Schema"
echo "----------------------------------------------------------------------"

echo "Creating ClickHouse database and tables..."
clickhouse-client --multiquery < db/schema.sql

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database schema created${NC}"
else
    echo -e "${RED}❌ Database schema creation failed${NC}"
    exit 1
fi

# Verify tables
echo "Verifying tables..."
TABLE_COUNT=$(clickhouse-client --query "SELECT count() FROM system.tables WHERE database = 'tradelayout'" 2>/dev/null)
echo "Tables created: $TABLE_COUNT"

if [ "$TABLE_COUNT" -ge 7 ]; then
    echo -e "${GREEN}✅ All tables created successfully${NC}"
else
    echo -e "${RED}❌ Some tables missing${NC}"
    exit 1
fi

echo ""

# ============================================================================
# Step 5: Create Log Directory
# ============================================================================
echo "----------------------------------------------------------------------"
echo "📝 Step 5: Setting up Logging"
echo "----------------------------------------------------------------------"

LOG_DIR="/var/log/tradelayout"

if [ "$OS" == "macos" ]; then
    # macOS - use local directory
    LOG_DIR="./logs"
fi

if [ ! -d "$LOG_DIR" ]; then
    echo "Creating log directory: $LOG_DIR"
    if [ "$OS" == "macos" ]; then
        mkdir -p "$LOG_DIR"
    else
        sudo mkdir -p "$LOG_DIR"
        sudo chown $USER:$USER "$LOG_DIR"
    fi
    echo -e "${GREEN}✅ Log directory created${NC}"
else
    echo -e "${YELLOW}⚠️  Log directory already exists${NC}"
fi

echo ""

# ============================================================================
# Step 6: Create .env File
# ============================================================================
echo "----------------------------------------------------------------------"
echo "⚙️  Step 6: Creating Environment Configuration"
echo "----------------------------------------------------------------------"

if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file already exists${NC}"
else
    echo "Creating .env file..."
    cat > .env << EOF
# Database
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=9000
CLICKHOUSE_DATABASE=tradelayout

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# AWS S3 (for backups)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET=tradelayout-backups

# Supabase (for user data)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Encryption
ENCRYPTION_KEY=your_encryption_key

# Logging
LOG_LEVEL=INFO
LOG_DIR=$LOG_DIR
EOF
    echo -e "${GREEN}✅ .env file created${NC}"
    echo -e "${YELLOW}⚠️  Please update .env with your actual credentials${NC}"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================
echo "======================================================================"
echo "✅ Installation Complete!"
echo "======================================================================"
echo ""
echo "Installed Components:"
echo "  ✅ ClickHouse - Database"
echo "  ✅ Redis - Cache"
echo "  ✅ Python Virtual Environment"
echo "  ✅ Python Dependencies"
echo "  ✅ Database Schema (7 tables)"
echo "  ✅ Log Directory"
echo "  ✅ Environment Configuration"
echo ""
echo "Next Steps:"
echo "  1. Update .env with your credentials"
echo "  2. Run tests: ./run_tests.sh"
echo "  3. If all tests pass, proceed to DataWriter implementation"
echo ""
echo "======================================================================"
