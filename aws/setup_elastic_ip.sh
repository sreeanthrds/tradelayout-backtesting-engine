#!/bin/bash

# Setup Elastic IP for TradeLayout Engine EC2
# Ensures same IP address every time EC2 starts/stops

set -e

echo "======================================================================"
echo "🌐 Setting up Elastic IP for TradeLayout Engine"
echo "======================================================================"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first:"
    echo "   brew install awscli"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run:"
    echo "   aws configure"
    exit 1
fi

echo "✅ AWS CLI configured"
echo ""

# Get region
read -p "Enter AWS region (default: ap-south-1): " AWS_REGION
AWS_REGION=${AWS_REGION:-ap-south-1}

# Get instance ID
read -p "Enter EC2 Instance ID (e.g., i-xxxxx): " INSTANCE_ID

if [ -z "$INSTANCE_ID" ]; then
    echo "❌ Instance ID is required"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  Region: $AWS_REGION"
echo "  Instance ID: $INSTANCE_ID"
echo ""

# Check if instance exists
echo "Checking EC2 instance..."
if ! aws ec2 describe-instances --instance-ids $INSTANCE_ID --region $AWS_REGION &> /dev/null; then
    echo "❌ Instance not found: $INSTANCE_ID"
    exit 1
fi
echo "✅ Instance found"
echo ""

# Check if instance already has Elastic IP
CURRENT_EIP=$(aws ec2 describe-addresses \
    --filters "Name=instance-id,Values=$INSTANCE_ID" \
    --region $AWS_REGION \
    --query "Addresses[0].PublicIp" \
    --output text 2>/dev/null)

if [ "$CURRENT_EIP" != "None" ] && [ ! -z "$CURRENT_EIP" ]; then
    echo "✅ Instance already has Elastic IP: $CURRENT_EIP"
    echo ""
    read -p "Do you want to use this IP? (y/n): " USE_EXISTING
    
    if [ "$USE_EXISTING" = "y" ] || [ "$USE_EXISTING" = "Y" ]; then
        ELASTIC_IP=$CURRENT_EIP
        echo "Using existing Elastic IP: $ELASTIC_IP"
    else
        echo "Releasing current Elastic IP..."
        ALLOCATION_ID=$(aws ec2 describe-addresses \
            --filters "Name=instance-id,Values=$INSTANCE_ID" \
            --region $AWS_REGION \
            --query "Addresses[0].AllocationId" \
            --output text)
        
        aws ec2 disassociate-address \
            --association-id $(aws ec2 describe-addresses \
                --allocation-ids $ALLOCATION_ID \
                --region $AWS_REGION \
                --query "Addresses[0].AssociationId" \
                --output text) \
            --region $AWS_REGION
        
        aws ec2 release-address \
            --allocation-id $ALLOCATION_ID \
            --region $AWS_REGION
        
        echo "✅ Released old Elastic IP"
        CURRENT_EIP=""
    fi
fi

# Allocate new Elastic IP if needed
if [ -z "$CURRENT_EIP" ] || [ "$CURRENT_EIP" = "None" ]; then
    echo "Allocating new Elastic IP..."
    
    ALLOCATION_RESULT=$(aws ec2 allocate-address \
        --domain vpc \
        --region $AWS_REGION \
        --tag-specifications 'ResourceType=elastic-ip,Tags=[{Key=Name,Value=tradelayout-eip}]')
    
    ELASTIC_IP=$(echo $ALLOCATION_RESULT | jq -r '.PublicIp')
    ALLOCATION_ID=$(echo $ALLOCATION_RESULT | jq -r '.AllocationId')
    
    echo "✅ Elastic IP allocated: $ELASTIC_IP"
    echo "   Allocation ID: $ALLOCATION_ID"
    echo ""
    
    # Associate with instance
    echo "Associating Elastic IP with EC2 instance..."
    
    aws ec2 associate-address \
        --instance-id $INSTANCE_ID \
        --allocation-id $ALLOCATION_ID \
        --region $AWS_REGION
    
    echo "✅ Elastic IP associated with instance"
fi

echo ""
echo "======================================================================"
echo "✅ Elastic IP Setup Complete!"
echo "======================================================================"
echo ""
echo "Your EC2 Instance Details:"
echo "  Instance ID: $INSTANCE_ID"
echo "  Elastic IP: $ELASTIC_IP"
echo "  Region: $AWS_REGION"
echo ""
echo "This IP address will remain the same even when you:"
echo "  - Stop the instance"
echo "  - Start the instance"
echo "  - Reboot the instance"
echo ""
echo "Important Notes:"
echo "  1. Save this IP address: $ELASTIC_IP"
echo "  2. Use this IP in your configurations"
echo "  3. Cost: ~\$1-2/month when instance is stopped"
echo "  4. Cost: FREE when instance is running"
echo ""
echo "Update your .env file:"
echo "  EC2_PUBLIC_IP=$ELASTIC_IP"
echo "  API_URL=http://$ELASTIC_IP:8000"
echo ""
echo "Next steps:"
echo "  1. Deploy to EC2: ./deploy_to_ec2.sh"
echo "  2. Use IP: $ELASTIC_IP"
echo ""
echo "======================================================================"

# Save to config file
cat > aws/elastic_ip_config.txt << EOF
# TradeLayout Engine - Elastic IP Configuration
# Generated: $(date)

ELASTIC_IP=$ELASTIC_IP
ALLOCATION_ID=$ALLOCATION_ID
INSTANCE_ID=$INSTANCE_ID
AWS_REGION=$AWS_REGION

# Use this IP in all configurations
# This IP will never change!
EOF

echo "Configuration saved to: aws/elastic_ip_config.txt"
echo ""
