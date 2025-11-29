#!/bin/bash
set -e

# TradeLayout Infrastructure Setup Script
# Run this on a fresh Ubuntu 22.04 server

echo "🚀 TradeLayout Infrastructure Setup"
echo "===================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ Please run as root (use sudo)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Running as root${NC}"
echo ""

# Step 1: Update system
echo -e "${YELLOW}📦 Step 1: Updating system packages...${NC}"
apt update && apt upgrade -y
echo -e "${GREEN}✅ System updated${NC}"
echo ""

# Step 2: Install required packages
echo -e "${YELLOW}📦 Step 2: Installing required packages...${NC}"
apt install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    ufw \
    fail2ban \
    ca-certificates \
    gnupg \
    lsb-release
echo -e "${GREEN}✅ Packages installed${NC}"
echo ""

# Step 3: Setup firewall
echo -e "${YELLOW}🔒 Step 3: Configuring firewall...${NC}"
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 8123/tcp  # ClickHouse HTTP
ufw allow 9000/tcp  # ClickHouse Native
ufw --force enable
echo -e "${GREEN}✅ Firewall configured${NC}"
echo ""

# Step 4: Install Docker
echo -e "${YELLOW}🐳 Step 4: Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo -e "${GREEN}✅ Docker installed${NC}"
else
    echo -e "${GREEN}✅ Docker already installed${NC}"
fi
echo ""

# Step 5: Install Docker Compose
echo -e "${YELLOW}🐳 Step 5: Installing Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    apt install -y docker-compose
    echo -e "${GREEN}✅ Docker Compose installed${NC}"
else
    echo -e "${GREEN}✅ Docker Compose already installed${NC}"
fi
echo ""

# Step 6: Create project structure
echo -e "${YELLOW}📁 Step 6: Creating project structure...${NC}"
mkdir -p /opt/tradelayout
cd /opt/tradelayout

mkdir -p data/{clickhouse,redis}
mkdir -p config/{clickhouse,redis}
mkdir -p backups
mkdir -p logs/{clickhouse,redis}
mkdir -p scripts

echo -e "${GREEN}✅ Project structure created${NC}"
echo ""

# Step 7: Set permissions
echo -e "${YELLOW}🔐 Step 7: Setting permissions...${NC}"
chown -R root:root /opt/tradelayout
chmod -R 755 /opt/tradelayout
chmod 700 /opt/tradelayout/backups
echo -e "${GREEN}✅ Permissions set${NC}"
echo ""

# Step 8: Verify installations
echo -e "${YELLOW}✅ Step 8: Verifying installations...${NC}"
echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker-compose --version)"
echo ""

# Summary
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Copy your infrastructure files to /opt/tradelayout/"
echo "2. Create .env file with your credentials"
echo "3. Run: docker-compose up -d"
echo ""
echo "Project directory: /opt/tradelayout"
echo ""
