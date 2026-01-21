# Deployment Guide

## Automated Deployment (Recommended)

### Quick Start
```bash
# 1. Clone repository
git clone <repository-url>
cd tradelayout-backtesting-engine

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run automated deployment
./deploy.sh
```

The deployment script will:
- ✅ Check if `.env` file exists (creates from `.env.example` if not)
- ✅ Test ClickHouse connection
- ✅ Prompt for configuration if connection fails
- ✅ Verify database and permissions
- ✅ Start the service (with options)

## Manual Deployment

### 1. Prerequisites
- Python 3.8+
- ClickHouse server
- Node.js (for frontend)
- Git

### 2. Clone Repository
```bash
git clone <repository-url>
cd tradelayout-backtesting-engine
```

### 3. Configure Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your server-specific values:
```bash
nano .env
```

Update these values:
- `CLICKHOUSE_HOST` - Your ClickHouse server IP/hostname
- `CLICKHOUSE_PORT` - ClickHouse port (default: 8123)
- `CLICKHOUSE_USER` - ClickHouse username
- `CLICKHOUSE_PASSWORD` - ClickHouse password
- `CLICKHOUSE_DATABASE` - Database name
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Your Supabase service role key
- `API_HOST` - API server bind address (0.0.0.0 for all interfaces)
- `API_PORT` - API server port (default: 8001)

### 4. Install Dependencies
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 5. Verify Configuration
```bash
# Run setup and verification script
python3 setup_and_verify.py
```

This will:
- Check ClickHouse connectivity
- Prompt for configuration updates if needed
- Verify database exists
- Test permissions

### 5. Setup ClickHouse User

Login to ClickHouse and create user:
```bash
clickhouse-client
```

```sql
-- Create user (adjust password as needed)
CREATE USER IF NOT EXISTS tradelayout IDENTIFIED WITH plaintext_password BY 'your_password';

-- Grant privileges
GRANT ALL ON tradelayout.* TO tradelayout;
GRANT SELECT ON system.* TO tradelayout;

-- Verify
SELECT name FROM system.users WHERE name = 'tradelayout';
```

For older ClickHouse versions (< 20.x), create XML config:
```bash
sudo nano /etc/clickhouse-server/users.d/tradelayout.xml
```

```xml
<?xml version="1.0"?>
<yandex>
    <users>
        <tradelayout>
            <password>your_password</password>
            <networks>
                <ip>::/0</ip>
            </networks>
            <profile>default</profile>
            <quota>default</quota>
        </tradelayout>
    </users>
</yandex>
```

Restart ClickHouse:
```bash
sudo systemctl restart clickhouse-server
```

### 6. Run API Server

**Development:**
```bash
source venv/bin/activate
python backtest_api_server.py
```

**Production (with systemd):**
```bash
# Copy service file
sudo cp infrastructure/tradelayout-backtest-api.service /etc/systemd/system/

# Edit service file with correct paths
sudo nano /etc/systemd/system/tradelayout-backtest-api.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable tradelayout-backtest-api.service
sudo systemctl start tradelayout-backtest-api.service

# Check status
sudo systemctl status tradelayout-backtest-api.service
```

### 7. Verify Installation

Test ClickHouse connection:
```bash
curl "http://localhost:8123/?user=tradelayout&password=your_password&query=SELECT%20version()"
```

Test API server:
```bash
curl http://localhost:8001/health
```

## Configuration Files

### `.env` (Server-Specific - NOT in Git)
Contains all environment-specific configuration. This file should be created on each server and never committed to git.

### `.env.example` (In Git)
Template for `.env` file. Update this when adding new configuration options.

### `config_loader.py`
Loads configuration from environment variables. No hardcoded values.

### `src/config/clickhouse_config.py`
ClickHouse configuration using environment variables.

### `src/storage/clickhouse_client.py`
ClickHouse client factory using environment variables.

## Security Best Practices

1. **Never commit `.env` to git**
   ```bash
   # Add to .gitignore
   echo ".env" >> .gitignore
   ```

2. **Use strong passwords** for ClickHouse and Supabase

3. **Restrict network access** using firewalls and security groups

4. **Use SSH tunnels** for remote database access

5. **Rotate credentials** regularly

## Troubleshooting

### ClickHouse Connection Failed
```bash
# Check ClickHouse is running
sudo systemctl status clickhouse-server

# Check user exists
clickhouse-client --query "SELECT name FROM system.users"

# Test connection
curl "http://localhost:8123/?user=tradelayout&password=your_password&query=SELECT%201"
```

### API Server Not Starting
```bash
# Check logs
sudo journalctl -u tradelayout-backtest-api.service -n 50

# Check port is not in use
sudo netstat -tlnp | grep 8001

# Verify Python dependencies
pip list | grep clickhouse
```

### Missing Modules
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## Migration Checklist

- [ ] Clone repository on new server
- [ ] Create `.env` file with new server values
- [ ] Install Python dependencies
- [ ] Setup ClickHouse user
- [ ] Configure firewall/security groups
- [ ] Test ClickHouse connection
- [ ] Start API server
- [ ] Test API endpoints
- [ ] Setup systemd service (production)
- [ ] Configure monitoring/logging
