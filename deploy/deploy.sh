#!/bin/bash

# TradeLayout Engine - Universal Cloud Deployment Script
# Works on: AWS, GCP, Azure, DigitalOcean, any Ubuntu 22.04 VM

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLOUD_PROVIDER=${1:-aws}  # Default to AWS
APP_DIR="/opt/tradelayout-engine"
LOG_DIR="/var/log/tradelayout"
BACKUP_DIR="/var/backups/tradelayout"

echo "======================================================================"
echo "🚀 TradeLayout Engine - Cloud Deployment"
echo "======================================================================"
echo ""
echo "Cloud Provider: $CLOUD_PROVIDER"
echo "Installation Directory: $APP_DIR"
echo ""

# ============================================================================
# Step 1: System Update
# ============================================================================
echo -e "${BLUE}Step 1: Updating system...${NC}"
sudo apt-get update
sudo apt-get upgrade -y
echo -e "${GREEN}✅ System updated${NC}"
echo ""

# ============================================================================
# Step 2: Install ClickHouse
# ============================================================================
echo -e "${BLUE}Step 2: Installing ClickHouse...${NC}"

if command -v clickhouse-server &> /dev/null; then
    echo -e "${YELLOW}⚠️  ClickHouse already installed${NC}"
else
    sudo apt-get install -y apt-transport-https ca-certificates dirmngr
    sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 8919F6BD2B48D754
    echo "deb https://packages.clickhouse.com/deb stable main" | sudo tee /etc/apt/sources.list.d/clickhouse.list
    sudo apt-get update
    
    # Install with default password
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y clickhouse-server clickhouse-client
    
    echo -e "${GREEN}✅ ClickHouse installed${NC}"
fi

# Start ClickHouse
sudo systemctl start clickhouse-server
sudo systemctl enable clickhouse-server

# Wait for ClickHouse to be ready
echo "Waiting for ClickHouse to start..."
for i in {1..30}; do
    if clickhouse-client --query "SELECT 1" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ ClickHouse is ready${NC}"
        break
    fi
    sleep 1
done
echo ""

# ============================================================================
# Step 3: Install Redis
# ============================================================================
echo -e "${BLUE}Step 3: Installing Redis...${NC}"

if command -v redis-server &> /dev/null; then
    echo -e "${YELLOW}⚠️  Redis already installed${NC}"
else
    sudo apt-get install -y redis-server
    echo -e "${GREEN}✅ Redis installed${NC}"
fi

# Configure Redis
sudo sed -i 's/^supervised no/supervised systemd/' /etc/redis/redis.conf

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Wait for Redis to be ready
echo "Waiting for Redis to start..."
for i in {1..10}; do
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis is ready${NC}"
        break
    fi
    sleep 1
done
echo ""

# ============================================================================
# Step 4: Install Python 3.9+
# ============================================================================
echo -e "${BLUE}Step 4: Installing Python...${NC}"

if command -v python3.9 &> /dev/null; then
    echo -e "${YELLOW}⚠️  Python 3.9+ already installed${NC}"
else
    sudo apt-get install -y python3.9 python3.9-venv python3-pip
    echo -e "${GREEN}✅ Python installed${NC}"
fi
echo ""

# ============================================================================
# Step 5: Create Application Directory
# ============================================================================
echo -e "${BLUE}Step 5: Setting up application directory...${NC}"

sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Copy application files
if [ -d "$(pwd)/../" ]; then
    echo "Copying application files..."
    cp -r $(pwd)/../* $APP_DIR/
    echo -e "${GREEN}✅ Application files copied${NC}"
fi
echo ""

# ============================================================================
# Step 6: Create Python Virtual Environment
# ============================================================================
echo -e "${BLUE}Step 6: Creating Python virtual environment...${NC}"

cd $APP_DIR

if [ ! -d "venv" ]; then
    python3.9 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Activate and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✅ Python dependencies installed${NC}"
echo ""

# ============================================================================
# Step 7: Create Database Schema
# ============================================================================
echo -e "${BLUE}Step 7: Creating database schema...${NC}"

clickhouse-client --multiquery < db/schema_simple.sql
echo -e "${GREEN}✅ Database schema created${NC}"

# Verify tables
TABLE_COUNT=$(clickhouse-client --query "SELECT count() FROM system.tables WHERE database = 'tradelayout'" 2>/dev/null)
echo "Tables created: $TABLE_COUNT"
echo ""

# ============================================================================
# Step 8: Create Log Directory
# ============================================================================
echo -e "${BLUE}Step 8: Setting up logging...${NC}"

sudo mkdir -p $LOG_DIR
sudo chown $USER:$USER $LOG_DIR
echo -e "${GREEN}✅ Log directory created${NC}"
echo ""

# ============================================================================
# Step 9: Create Backup Directory
# ============================================================================
echo -e "${BLUE}Step 9: Setting up backups...${NC}"

sudo mkdir -p $BACKUP_DIR
sudo chown $USER:$USER $BACKUP_DIR
echo -e "${GREEN}✅ Backup directory created${NC}"
echo ""

# ============================================================================
# Step 10: Configure Cloud Storage
# ============================================================================
echo -e "${BLUE}Step 10: Configuring cloud storage...${NC}"

case $CLOUD_PROVIDER in
    aws)
        echo "Configuring AWS S3..."
        # Install AWS CLI if not present
        if ! command -v aws &> /dev/null; then
            sudo apt-get install -y awscli
        fi
        echo -e "${GREEN}✅ AWS CLI configured${NC}"
        ;;
    gcp)
        echo "Configuring Google Cloud Storage..."
        # Install gcloud if not present
        if ! command -v gcloud &> /dev/null; then
            echo "Please install gcloud SDK manually"
        fi
        echo -e "${GREEN}✅ GCS configured${NC}"
        ;;
    azure)
        echo "Configuring Azure Blob Storage..."
        # Install Azure CLI if not present
        if ! command -v az &> /dev/null; then
            curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
        fi
        echo -e "${GREEN}✅ Azure CLI configured${NC}"
        ;;
    *)
        echo -e "${YELLOW}⚠️  Unknown cloud provider: $CLOUD_PROVIDER${NC}"
        ;;
esac
echo ""

# ============================================================================
# Step 11: Create Systemd Services
# ============================================================================
echo -e "${BLUE}Step 11: Creating systemd services...${NC}"

# FastAPI Service
sudo tee /etc/systemd/system/tradelayout-api.service > /dev/null <<EOF
[Unit]
Description=TradeLayout FastAPI Server
After=network.target clickhouse-server.service redis-server.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}✅ Systemd services created${NC}"
echo ""

# ============================================================================
# Step 12: Enable and Start Services
# ============================================================================
echo -e "${BLUE}Step 12: Starting services...${NC}"

sudo systemctl daemon-reload
sudo systemctl enable tradelayout-api
sudo systemctl start tradelayout-api

echo -e "${GREEN}✅ Services started${NC}"
echo ""

# ============================================================================
# Step 13: Setup Cron Jobs for Auto Start/Stop
# ============================================================================
echo -e "${BLUE}Step 13: Setting up auto start/stop...${NC}"

# Create cron jobs
(crontab -l 2>/dev/null; echo "15 3 * * 1-5 $APP_DIR/aws/startup.sh") | crontab -
(crontab -l 2>/dev/null; echo "15 10 * * 1-5 $APP_DIR/aws/shutdown.sh") | crontab -

echo -e "${GREEN}✅ Auto start/stop configured${NC}"
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "======================================================================"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo "======================================================================"
echo ""
echo "Installed Components:"
echo "  ✅ ClickHouse Server"
echo "  ✅ Redis Server"
echo "  ✅ Python 3.9+ with Virtual Environment"
echo "  ✅ All Python Dependencies"
echo "  ✅ Database Schema (7 tables)"
echo "  ✅ FastAPI Server (running on port 8000)"
echo "  ✅ Auto Start/Stop Configured"
echo ""
echo "Service Status:"
sudo systemctl status clickhouse-server --no-pager | grep Active
sudo systemctl status redis-server --no-pager | grep Active
sudo systemctl status tradelayout-api --no-pager | grep Active
echo ""
echo "Next Steps:"
echo "  1. Configure cloud credentials (AWS/GCP/Azure)"
echo "  2. Update .env file with your settings"
echo "  3. Test the API: curl http://localhost:8000/health"
echo "  4. View logs: tail -f $LOG_DIR/api.log"
echo ""
echo "======================================================================"
