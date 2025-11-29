#!/bin/bash

# Deploy TradeLayout Engine to AWS EC2
# Using existing SSH key from old project

set -e

# Configuration
SSH_KEY="../full_trading_engine_docker/trading-platform-key.pem"
EC2_USER="ubuntu"

echo "======================================================================"
echo "🚀 TradeLayout Engine - Deploy to AWS EC2"
echo "======================================================================"
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found at: $SSH_KEY"
    echo "Please provide the correct path to your SSH key."
    exit 1
fi

# Set correct permissions for SSH key
chmod 400 "$SSH_KEY"

# Ask for EC2 IP
read -p "Enter your EC2 IP address: " EC2_IP

if [ -z "$EC2_IP" ]; then
    echo "❌ EC2 IP address is required"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  EC2 IP: $EC2_IP"
echo "  SSH Key: $SSH_KEY"
echo "  User: $EC2_USER"
echo ""

# Test SSH connection
echo "Testing SSH connection..."
if ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" "echo 'Connection successful'" 2>/dev/null; then
    echo "✅ SSH connection successful"
else
    echo "❌ SSH connection failed"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check if EC2 IP is correct"
    echo "  2. Check if security group allows SSH (port 22)"
    echo "  3. Check if EC2 instance is running"
    echo "  4. Try: ssh -i $SSH_KEY $EC2_USER@$EC2_IP"
    exit 1
fi

echo ""
read -p "Do you want to flush existing installation and install fresh? (y/n): " FLUSH
echo ""

# Deploy to EC2
echo "======================================================================"
echo "📤 Deploying to EC2: $EC2_IP"
echo "======================================================================"
echo ""

# Step 1: Copy files
echo "Step 1: Copying files to EC2..."
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no -r . "$EC2_USER@$EC2_IP:/tmp/tradelayout-engine-new"
echo "✅ Files copied"
echo ""

# Step 2: Run deployment on EC2
echo "Step 2: Running deployment on EC2..."
echo ""

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$EC2_USER@$EC2_IP" << ENDSSH
    set -e
    
    echo "======================================================================"
    echo "🔧 Setting up on EC2..."
    echo "======================================================================"
    echo ""
    
    # Flush if requested
    if [ "$FLUSH" = "y" ] || [ "$FLUSH" = "Y" ]; then
        echo "Flushing existing installation..."
        sudo systemctl stop tradelayout-api 2>/dev/null || true
        sudo rm -rf /opt/tradelayout-engine
        echo "✅ Existing installation removed"
        echo ""
    fi
    
    # Move to /opt
    echo "Moving files to /opt..."
    sudo mv /tmp/tradelayout-engine-new /opt/tradelayout-engine
    sudo chown -R ubuntu:ubuntu /opt/tradelayout-engine
    echo "✅ Files moved to /opt/tradelayout-engine"
    echo ""
    
    # Run deployment
    cd /opt/tradelayout-engine
    chmod +x deploy/deploy.sh
    
    echo "======================================================================"
    echo "🚀 Starting deployment (this will take ~15 minutes)..."
    echo "======================================================================"
    echo ""
    
    ./deploy/deploy.sh aws
ENDSSH

echo ""
echo "======================================================================"
echo "✅ Deployment Complete!"
echo "======================================================================"
echo ""
echo "Your TradeLayout Engine is now running on EC2!"
echo ""
echo "Services:"
echo "  - ClickHouse: $EC2_IP:9000"
echo "  - Redis: $EC2_IP:6379"
echo "  - API: http://$EC2_IP:8000"
echo ""
echo "Next steps:"
echo "  1. SSH to EC2:"
echo "     ssh -i $SSH_KEY $EC2_USER@$EC2_IP"
echo ""
echo "  2. Check services:"
echo "     sudo systemctl status clickhouse-server"
echo "     sudo systemctl status redis-server"
echo "     sudo systemctl status tradelayout-api"
echo ""
echo "  3. View logs:"
echo "     tail -f /var/log/tradelayout/api.log"
echo ""
echo "  4. Run tests:"
echo "     cd /opt/tradelayout-engine"
echo "     source venv/bin/activate"
echo "     pytest tests/ -v"
echo ""
echo "  5. Configure AWS credentials:"
echo "     aws configure"
echo ""
echo "======================================================================"
