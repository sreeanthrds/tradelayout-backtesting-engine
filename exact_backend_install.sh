#!/bin/bash

echo "🔧 EXACT Backend Installation - Match Local Environment"
echo "======================================================="

echo ""
echo "📋 Local Backend Environment (What We Need to Match):"
echo "  Python: 3.12.3"
echo "  FastAPI: 0.116.1"
echo "  Uvicorn: 0.35.0"
echo "  Pandas: 2.3.2"
echo "  NumPy: 2.2.6"

echo ""
echo "🔧 Step 1: Install EXACT Python 3.12.3"
echo "---------------------------------------"
echo "⚠️  IMPORTANT: Don't use system Python - use specific version!"

# Remove any existing Python packages
sudo apt-get remove -y python3-pip python3-venv
sudo apt-get autoremove -y

# Install pyenv dependencies
sudo apt-get update
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev

# Install pyenv
curl https://pyenv.run | bash
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Install EXACT Python 3.12.3
echo "📦 Installing Python 3.12.3..."
pyenv install 3.12.3
pyenv global 3.12.3

echo ""
echo "🔧 Step 2: Create Virtual Environment"
echo "-------------------------------------"
echo "📦 Creating virtual environment..."
python -m venv venv
source venv/bin/activate

echo ""
echo "🔧 Step 3: Install EXACT Package Versions"
echo "------------------------------------------"
echo "⚠️  IMPORTANT: Use exact versions, not 'latest'!"

# Upgrade pip to exact version
echo "📦 Installing pip 24.0..."
pip install pip==24.0

# Install exact FastAPI version
echo "📦 Installing FastAPI 0.116.1..."
pip install fastapi==0.116.1

# Install exact Uvicorn version
echo "📦 Installing Uvicorn 0.35.0..."
pip install uvicorn==0.35.0

# Install exact Pandas version
echo "📦 Installing Pandas 2.3.2..."
pip install pandas==2.3.2

# Install exact NumPy version
echo "📦 Installing NumPy 2.2.6..."
pip install numpy==2.2.6

# Install other exact versions from requirements
echo "📦 Installing other exact dependencies..."
pip install \
    aiohttp==3.9.0 \
    aiofiles==23.0.0 \
    aioredis==2.0.0 \
    clickhouse-driver==0.2.6 \
    clickhouse-connect==0.7.0 \
    redis==5.0.0 \
    scipy==1.11.0 \
    scikit-learn==1.3.0 \
    pandas-ta==0.4.71b0 \
    yfinance==0.2.0 \
    pydantic==2.0.0 \
    sse-starlette==1.6.0 \
    websocket-client==1.6.0 \
    python-socketio==5.10.0 \
    python-jose[cryptography]==3.3.0 \
    passlib[bcrypt]==1.7.4 \
    python-multipart==0.0.6 \
    supabase==2.0.0 \
    razorpay==1.3.0 \
    boto3==1.28.0 \
    python-dotenv==1.0.0 \
    pytz==2023.3 \
    requests==2.31.0 \
    pyotp==2.9.0 \
    loguru==0.7.0

echo ""
echo "🔧 Step 4: Verify EXACT Versions"
echo "--------------------------------"
echo "Python version:"
python --version  # Should be 3.12.3

echo "pip version:"
pip --version     # Should be 24.0

echo "FastAPI version:"
pip show fastapi | grep Version  # Should be 0.116.1

echo "Uvicorn version:"
pip show uvicorn | grep Version  # Should be 0.35.0

echo "Pandas version:"
pip show pandas | grep Version   # Should be 2.3.2

echo "NumPy version:"
pip show numpy | grep Version    # Should be 2.2.6

echo ""
echo "🔧 Step 5: Clone and Setup Backend"
echo "---------------------------------"
cd /tmp

# Clone repository
git clone https://github.com/sreeanthrds/tradelayout-backtesting-engine.git
cd tradelayout-backtesting-engine

# Switch to production branch
git checkout production

echo ""
echo "🔧 Step 6: Test Backend Server"
echo "-----------------------------"
echo "🚀 Starting backend server..."
python backtest_api_server.py &

# Wait for server to start
sleep 5

# Test server
echo "🧪 Testing server health..."
curl -f http://localhost:8001/health || echo "❌ Server health check failed"

echo ""
echo "🧪 Testing backtest endpoint..."
curl -f http://localhost:8001/docs || echo "❌ API docs not accessible"

echo ""
echo "✅ Backend Installation Complete!"
echo "================================="
echo "🎯 Your VM backend now has EXACT same versions as local:"
echo "  Python: 3.12.3"
echo "  FastAPI: 0.116.1"
echo "  Uvicorn: 0.35.0"
echo "  Pandas: 2.3.2"
echo "  NumPy: 2.2.6"

echo ""
echo "🔧 To start backend in future:"
echo "  cd /tmp/tradelayout-backtesting-engine"
echo "  source venv/bin/activate"
echo "  python backtest_api_server.py"
