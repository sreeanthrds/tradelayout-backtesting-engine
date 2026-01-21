# Automated Deployment & Configuration Management

## ✅ Best Approach: Automated Verification

Your deployment now includes **automated ClickHouse verification** that:

1. ✅ **Checks connection** before starting the service
2. ✅ **Prompts for configuration** if connection fails
3. ✅ **Validates credentials** automatically
4. ✅ **Updates .env file** with user input
5. ✅ **Prevents service start** if database is unreachable

## Quick Start

### Option 1: Automated Deployment (Recommended)
```bash
./deploy.sh
```

This single command will:
- Check if `.env` exists (creates from template if not)
- Test ClickHouse connection
- Prompt for configuration if needed
- Verify database and permissions
- Start the service

### Option 2: Verification Only
```bash
python3 setup_and_verify.py
```

This will verify configuration without starting the service.

## How It Works

### 1. Initial Deployment
```bash
# Clone code
git clone <repo-url>
cd tradelayout-backtesting-engine

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run automated deployment
./deploy.sh
```

**What happens:**
1. Script checks if `.env` exists
2. If not, creates from `.env.example`
3. Tests ClickHouse connection with current config
4. If connection fails:
   - Prompts user for correct credentials
   - Updates `.env` file
   - Tests connection again
5. If connection succeeds:
   - Verifies database exists
   - Checks permissions
   - Starts service

### 2. Moving to New Server
```bash
# Clone code (no .env file)
git clone <repo-url>
cd tradelayout-backtesting-engine

# Run deployment
./deploy.sh
```

**What happens:**
1. No `.env` file found → creates from template
2. Tests connection with default values
3. Connection fails → prompts for new server credentials
4. User enters:
   - ClickHouse Host: `new-server-ip`
   - ClickHouse Port: `8123`
   - ClickHouse User: `tradelayout`
   - ClickHouse Password: `new-password`
   - ClickHouse Database: `tradelayout`
5. Script updates `.env` with new values
6. Tests connection again
7. If successful → starts service
8. If failed → shows error and exits

### 3. Configuration Update
```bash
# Update existing deployment
./deploy.sh
```

**What happens:**
1. `.env` exists → loads current config
2. Tests connection
3. If fails → prompts for updated credentials
4. Updates `.env` and retests
5. Starts service when connection succeeds

## Files Created

### `setup_and_verify.py`
**Purpose:** Automated verification and configuration management

**Features:**
- ✅ Tests ClickHouse connectivity
- ✅ Prompts for configuration if needed
- ✅ Updates `.env` file automatically
- ✅ Validates database exists
- ✅ Checks user permissions
- ✅ Provides clear error messages

**Usage:**
```bash
python3 setup_and_verify.py
```

### `deploy.sh`
**Purpose:** Complete deployment automation

**Features:**
- ✅ Runs setup_and_verify.py
- ✅ Activates virtual environment
- ✅ Offers multiple start options:
  - Foreground (testing)
  - Background (nohup)
  - Systemd (production)
  - Skip (verify only)

**Usage:**
```bash
./deploy.sh
```

### `.env.example`
**Purpose:** Template for environment variables

**Tracked in Git:** ✅ Yes

**Contains:**
- Default/example values
- Comments explaining each variable
- No sensitive data

### `.env`
**Purpose:** Actual server configuration

**Tracked in Git:** ❌ No (in .gitignore)

**Contains:**
- Server-specific values
- Actual credentials
- Updated by setup_and_verify.py

## Example Workflow

### First Deployment on New Server

```bash
$ ./deploy.sh

==========================================
TradeLayout Backtesting Engine Deployment
==========================================

Running setup and verification...

================================================================================
  TradeLayout Backtesting Engine - Setup & Verification
================================================================================

⚠️  .env file not found
✅ .env file created from .env.example

Testing connection to ClickHouse...
  Host: localhost:8123
  User: tradelayout
  Database: tradelayout

❌ Failed to connect to ClickHouse: Connection refused

⚠️  ClickHouse connection failed!

Options:
1. Update configuration
2. Exit and fix manually

Enter choice [1/2]: 1

================================================================================
  ClickHouse Configuration Required
================================================================================

Please provide your ClickHouse connection details:
ClickHouse Host [localhost]: 10.0.1.50
ClickHouse Port [8123]: 8123
ClickHouse User [tradelayout]: tradelayout
ClickHouse Password: MySecurePassword123
ClickHouse Database [tradelayout]: tradelayout

✅ Configuration saved to .env file

Testing connection to ClickHouse...
  Host: 10.0.1.50:8123
  User: tradelayout
  Database: tradelayout

✅ Connected to ClickHouse version 23.8.2.7
✅ Database 'tradelayout' exists

================================================================================
  Setup Complete
================================================================================
✅ All checks passed!

You can now start the API server:
  python backtest_api_server.py

Or with systemd:
  sudo systemctl start tradelayout-backtest-api.service

✅ All checks passed!

How would you like to start the service?
1. Foreground (for testing)
2. Background (nohup)
3. Systemd service (production)
4. Skip (just verify)

Enter choice [1-4]: 3

Starting systemd service...
● tradelayout-backtest-api.service - TradeLayout Backtest API Server
   Loaded: loaded
   Active: active (running)

==========================================
Deployment Complete!
==========================================
```

## Benefits

### 1. No Manual Configuration Needed
- Script prompts for all required values
- Automatically updates `.env` file
- No need to edit files manually

### 2. Prevents Invalid Deployments
- Service won't start if database is unreachable
- Validates credentials before starting
- Clear error messages guide user

### 3. Portable Across Servers
- Same deployment process everywhere
- No hardcoded values in code
- Configuration stored in `.env` (not in Git)

### 4. Easy Troubleshooting
- Clear error messages
- Step-by-step prompts
- Verification before service start

### 5. Automated Updates
- Run `./deploy.sh` to update configuration
- Tests connection before restarting service
- Rollback if new config fails

## Troubleshooting

### Connection Still Fails After Update
```bash
# Check ClickHouse is running
sudo systemctl status clickhouse-server

# Test connection manually
curl "http://localhost:8123/?user=tradelayout&password=your_password&query=SELECT%201"

# Check firewall
sudo ufw status

# Check network connectivity
ping clickhouse-server-ip
```

### Script Doesn't Prompt for Configuration
```bash
# Delete .env and run again
rm .env
./deploy.sh
```

### Want to Update Configuration
```bash
# Option 1: Run deployment script
./deploy.sh

# Option 2: Edit .env manually
nano .env

# Option 3: Run verification only
python3 setup_and_verify.py
```

## Summary

**Problem:** Moving code to new server requires manual configuration updates

**Solution:** Automated verification script that:
- ✅ Tests ClickHouse connection
- ✅ Prompts for configuration if needed
- ✅ Updates `.env` automatically
- ✅ Prevents service start if database unreachable
- ✅ Works the same on every server

**Result:** One command deployment with automatic configuration management! 🚀
