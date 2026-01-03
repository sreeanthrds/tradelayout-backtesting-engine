#!/bin/bash

# Set Razorpay environment variables
export RAZORPAY_KEY_ID="rzp_test_RyzAl59FmaZZtg"
export RAZORPAY_KEY_SECRET="35qAudhvwfREFOPlKYW3ORkt"

echo "🚀 Starting backend with Razorpay test keys..."
echo "Key ID: $RAZORPAY_KEY_ID"
echo "Key Secret: [HIDDEN]"

python backtest_api_server.py
