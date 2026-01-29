#!/bin/bash

# Prepare TradeLayout Engine for Deployment
# Run this on your Mac before deploying to EC2

set -e

echo "======================================================================"
echo "📦 Preparing TradeLayout Engine for Deployment"
echo "======================================================================"
echo ""

# Get EC2 details
read -p "Enter EC2 IP Address: " EC2_IP
read -p "Enter SSH Key Path (e.g., ~/.ssh/your-key.pem): " SSH_KEY
read -p "Enter EC2 User (default: ubuntu): " EC2_USER
EC2_USER=${EC2_USER:-ubuntu}

echo ""
echo "Configuration:"
echo "  EC2 IP: $EC2_IP"
echo "  SSH Key: $SSH_KEY"
echo "  User: $EC2_USER"
echo ""

# Test SSH connection
echo "Testing SSH connection..."
if ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$EC2_USER@$EC2_IP" "echo 'Connection successful'" 2>/dev/null; then
    echo "✅ SSH connection successful"
else
    echo "❌ SSH connection failed. Please check your credentials."
    exit 1
fi

echo ""
echo "======================================================================"
echo "📤 Deploying to EC2..."
echo "======================================================================"
echo ""

# Copy files to EC2
echo "Copying files to EC2..."
scp -i "$SSH_KEY" -r . "$EC2_USER@$EC2_IP:/tmp/tradelayout-engine"

# Run deployment on EC2
echo ""
echo "Running deployment script on EC2..."
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'ENDSSH'
    # Move to /opt
    sudo rm -rf /opt/tradelayout-engine
    sudo mv /tmp/tradelayout-engine /opt/
    sudo chown -R ubuntu:ubuntu /opt/tradelayout-engine
    
    # Run deployment
    cd /opt/tradelayout-engine
    chmod +x deploy/deploy.sh
    ./deploy/deploy.sh aws
ENDSSH

echo ""
echo "======================================================================"
echo "✅ Deployment Complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. SSH to EC2: ssh -i $SSH_KEY $EC2_USER@$EC2_IP"
echo "  2. Configure AWS: aws configure"
echo "  3. Update .env: nano /opt/tradelayout-engine/.env"
echo "  4. Run tests: cd /opt/tradelayout-engine && source venv/bin/activate && pytest tests/ -v"
echo ""
echo "Services running on EC2:"
echo "  - ClickHouse: localhost:9000"
echo "  - Redis: localhost:6379"
echo "  - API: http://$EC2_IP:8000"
echo ""
