#!/bin/bash

echo "🔧 COMPLETE VM Installation - Frontend + Backend"
echo "================================================="

echo ""
echo "📋 Local Environment (What We Need to Match):"
echo "  Python: 3.12.3"
echo "  Node.js: v20.17.0"
echo "  npm: 10.8.2"
echo "  FastAPI: 0.116.1"
echo "  Uvicorn: 0.35.0"
echo "  Pandas: 2.3.2"
echo "  NumPy: 2.2.6"
echo "  TA-Lib: 0.4.28"

echo ""
echo "🔧 Step 1: System Dependencies"
echo "------------------------------"
echo "⚠️  Installing system packages required for compilation..."

sudo apt-get update
sudo apt-get install -y build-essential python3-dev python3-pip
sudo apt-get install -y libssl-dev libffi-dev libhdf5-dev
sudo apt-get install -y libpng-dev libfreetype6-dev libta-lib-dev
sudo apt-get install -y curl wget git unzip

echo ""
echo "🔧 Step 2: Install EXACT Python 3.12.3"
echo "--------------------------------------"
echo "⚠️  Using pyenv for precise version control..."

# Remove any existing Python packages
sudo apt-get remove -y python3-pip python3-venv 2>/dev/null || true
sudo apt-get autoremove -y 2>/dev/null || true

# Install pyenv dependencies
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev

# Install pyenv
curl https://pyenv.run | bash
export PYENV_ROOT="$HOME/.nvm"
[ -s "$PYENV_ROOT/bin/pyenv" ] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Install EXACT Python 3.12.3
echo "📦 Installing Python 3.12.3..."
pyenv install 3.12.3
pyenv global 3.12.3

echo ""
echo "🔧 Step 3: Install EXACT Node.js v20.17.0"
echo "----------------------------------------"
echo "⚠️  Using nvm for precise version control..."

# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# Install EXACT Node.js v20.17.0
echo "📦 Installing Node.js v20.17.0..."
nvm install 20.17.0
nvm use 20.17.0
nvm alias default 20.17.0

# Install EXACT npm 10.8.2
echo "📦 Installing npm 10.8.2..."
npm install -g npm@10.8.2

echo ""
echo "🔧 Step 4: Setup Backend Environment"
echo "------------------------------------"
cd /tmp

# Clone backend repository
git clone https://github.com/sreeanthrds/tradelayout-backtesting-engine.git
cd tradelayout-backtesting-engine

# Switch to production branch
git checkout production

# Create virtual environment
echo "📦 Creating Python virtual environment..."
python -m venv venv
source venv/bin/activate

# Upgrade pip to exact version
echo "📦 Upgrading pip to 24.0..."
pip install pip==24.0

# Install complete requirements
echo "📦 Installing ALL backend dependencies..."
echo "⏱️ This will take 10-15 minutes..."

# Install with binary packages where possible for speed
pip install --only-binary=:all: -r /tmp/complete_requirements.txt

# If binary install fails, install from source
if [ $? -ne 0 ]; then
    echo "⚠️ Binary install failed, installing from source..."
    pip install -r /tmp/complete_requirements.txt
fi

echo ""
echo "🔧 Step 5: Setup Frontend Environment"
echo "------------------------------------"
cd /tmp

# Clone frontend repository
git clone https://github.com/sreeanthrds/lovable-code-transplant.git
cd lovable-code-transplant

# Switch to production branch
git checkout production

# Clean install
echo "📦 Cleaning frontend dependencies..."
rm -rf node_modules package-lock.json
npm cache clean --force

# Install with exact same conditions as local
echo "📦 Installing frontend dependencies..."
NODE_OPTIONS=--max-old-space-size=4096 npm install --legacy-peer-deps

echo ""
echo "🔧 Step 6: Configuration Setup"
echo "------------------------------"
echo "📦 Setting up environment configurations..."

# Create environment file for backend
cd /tmp/tradelayout-backtesting-engine
cat > .env << EOF
# ClickHouse Configuration
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=default
CLICKHOUSE_TABLE=nse_ticks_stocks
CLICKHOUSE_BATCH_SIZE=10000
CLICKHOUSE_QUERY_TIMEOUT=300
CLICKHOUSE_SECURE=false

# API Configuration
API_HOST=0.0.0.0
API_PORT=8001

# Logging
LOG_LEVEL=INFO

# Supabase Configuration
SUPABASE_URL=https://oonepfqgzpdssfzvokgk.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vbmVwZnFnenBkc3NmenZva2drIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTAxOTk5MTQsImV4cCI6MjA2NTc3NTkxNH0.lDCxgwj36EniiZthzZxhM_8coXQhXlrvv9UzemyYu6A
EOF

echo ""
echo "🔧 Step 7: Verify Installation"
echo "------------------------------"
echo "📊 Checking Python versions..."
source /tmp/tradelayout-backtesting-engine/venv/bin/activate
python --version  # Should be 3.12.3
pip --version     # Should be 24.0

echo "📊 Checking Node.js versions..."
node --version    # Should be v20.17.0
npm --version     # Should be 10.8.2

echo "📊 Checking critical packages..."
pip show fastapi | grep Version  # Should be 0.116.1
pip show uvicorn | grep Version  # Should be 0.35.0
pip show pandas | grep Version   # Should be 2.3.2
pip show numpy | grep Version    # Should be 2.2.6
python -c "import talib" && echo "✅ TA-Lib working" || echo "❌ TA-Lib failed"

echo ""
echo "🔧 Step 8: Test Services"
echo "------------------------"
echo "🚀 Starting backend server..."
cd /tmp/tradelayout-backtesting-engine
source venv/bin/activate
python backtest_api_server.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 10

echo "🧪 Testing backend health..."
curl -f http://localhost:8001/health && echo "✅ Backend healthy" || echo "❌ Backend health failed"

echo "🚀 Starting frontend server..."
cd /tmp/lovable-code-transplant
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 10

echo "🧪 Testing frontend..."
curl -f http://localhost:8080 && echo "✅ Frontend healthy" || echo "❌ Frontend health failed"

echo ""
echo "✅ COMPLETE VM Installation Finished!"
echo "===================================="
echo "🎯 Your VM now has EXACT same environment as local:"
echo "  Python: 3.12.3"
echo "  Node.js: v20.17.0"
echo "  npm: 10.8.2"
echo "  FastAPI: 0.116.1"
echo "  Uvicorn: 0.35.0"
echo "  Pandas: 2.3.2"
echo "  NumPy: 2.2.6"
echo "  TA-Lib: 0.4.28"

echo ""
echo "🔧 To start services in future:"
echo "  Backend: cd /tmp/tradelayout-backtesting-engine && source venv/bin/activate && python backtest_api_server.py"
echo "  Frontend: cd /tmp/lovable-code-transplant && npm run dev"

echo ""
echo "🔧 To stop services:"
echo "  kill $BACKEND_PID $FRONTEND_PID"

echo ""
echo "🔧 Service URLs:"
echo "  Backend API: http://localhost:8001"
echo "  Frontend: http://localhost:8080"
echo "  API Docs: http://localhost:8001/docs"
