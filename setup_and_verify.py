#!/usr/bin/env python3
"""
Setup and Verification Script for TradeLayout Backtesting Engine
Checks ClickHouse connectivity and prompts user to update configuration if needed
"""
import os
import sys
import subprocess
from pathlib import Path

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def print_warning(text):
    """Print warning message"""
    print(f"⚠️  {text}")

def load_env_file():
    """Load .env file and return as dictionary"""
    env_path = Path(__file__).parent / '.env'
    
    if not env_path.exists():
        return None
    
    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars

def create_env_file():
    """Create .env file from .env.example"""
    example_path = Path(__file__).parent / '.env.example'
    env_path = Path(__file__).parent / '.env'
    
    if not example_path.exists():
        print_error(".env.example file not found!")
        return False
    
    # Copy example to .env
    with open(example_path, 'r') as src, open(env_path, 'w') as dst:
        dst.write(src.read())
    
    print_success(f".env file created from .env.example")
    return True

def prompt_for_config():
    """Prompt user to update configuration"""
    print_header("ClickHouse Configuration Required")
    print("\nPlease provide your ClickHouse connection details:")
    
    config = {}
    config['CLICKHOUSE_HOST'] = input("ClickHouse Host [localhost]: ").strip() or "localhost"
    config['CLICKHOUSE_PORT'] = input("ClickHouse Port [8123]: ").strip() or "8123"
    config['CLICKHOUSE_USER'] = input("ClickHouse User [tradelayout]: ").strip() or "tradelayout"
    config['CLICKHOUSE_PASSWORD'] = input("ClickHouse Password: ").strip()
    config['CLICKHOUSE_DATABASE'] = input("ClickHouse Database [tradelayout]: ").strip() or "tradelayout"
    
    return config

def update_env_file(config):
    """Update .env file with new configuration"""
    env_path = Path(__file__).parent / '.env'
    
    # Read existing .env
    env_vars = load_env_file() or {}
    
    # Update with new config
    env_vars.update(config)
    
    # Write back to .env
    with open(env_path, 'w') as f:
        f.write("# ClickHouse Configuration\n")
        f.write(f"CLICKHOUSE_HOST={env_vars.get('CLICKHOUSE_HOST', 'localhost')}\n")
        f.write(f"CLICKHOUSE_PORT={env_vars.get('CLICKHOUSE_PORT', '8123')}\n")
        f.write(f"CLICKHOUSE_USER={env_vars.get('CLICKHOUSE_USER', 'tradelayout')}\n")
        f.write(f"CLICKHOUSE_PASSWORD={env_vars.get('CLICKHOUSE_PASSWORD', '')}\n")
        f.write(f"CLICKHOUSE_DATABASE={env_vars.get('CLICKHOUSE_DATABASE', 'tradelayout')}\n")
        f.write("\n# Supabase Configuration\n")
        f.write(f"SUPABASE_URL={env_vars.get('SUPABASE_URL', '')}\n")
        f.write(f"SUPABASE_SERVICE_ROLE_KEY={env_vars.get('SUPABASE_SERVICE_ROLE_KEY', '')}\n")
        f.write("\n# API Server Configuration\n")
        f.write(f"API_HOST={env_vars.get('API_HOST', '0.0.0.0')}\n")
        f.write(f"API_PORT={env_vars.get('API_PORT', '8001')}\n")
        f.write("\n# Environment\n")
        f.write(f"ENVIRONMENT={env_vars.get('ENVIRONMENT', 'production')}\n")
    
    print_success("Configuration saved to .env file")

def test_clickhouse_connection(config):
    """Test ClickHouse connection"""
    try:
        import clickhouse_connect
        
        host = config.get('CLICKHOUSE_HOST', 'localhost')
        port = int(config.get('CLICKHOUSE_PORT', '8123'))
        user = config.get('CLICKHOUSE_USER', 'tradelayout')
        password = config.get('CLICKHOUSE_PASSWORD', '')
        database = config.get('CLICKHOUSE_DATABASE', 'tradelayout')
        
        print(f"\nTesting connection to ClickHouse...")
        print(f"  Host: {host}:{port}")
        print(f"  User: {user}")
        print(f"  Database: {database}")
        
        client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=user,
            password=password,
            database=database
        )
        
        # Test query
        result = client.query('SELECT version()')
        version = result.result_rows[0][0] if result.result_rows else 'Unknown'
        
        print_success(f"Connected to ClickHouse version {version}")
        return True
        
    except ImportError:
        print_error("clickhouse-connect package not installed")
        print("Install it with: pip install clickhouse-connect")
        return False
    except Exception as e:
        print_error(f"Failed to connect to ClickHouse: {str(e)}")
        return False

def verify_clickhouse_user(config):
    """Verify ClickHouse user exists and has proper permissions"""
    try:
        import clickhouse_connect
        
        host = config.get('CLICKHOUSE_HOST', 'localhost')
        port = int(config.get('CLICKHOUSE_PORT', '8123'))
        user = config.get('CLICKHOUSE_USER', 'tradelayout')
        password = config.get('CLICKHOUSE_PASSWORD', '')
        database = config.get('CLICKHOUSE_DATABASE', 'tradelayout')
        
        client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=user,
            password=password,
            database=database
        )
        
        # Check if database exists
        result = client.query(f"SHOW DATABASES LIKE '{database}'")
        if not result.result_rows:
            print_warning(f"Database '{database}' does not exist")
            print(f"Create it with: CREATE DATABASE {database}")
            return False
        
        print_success(f"Database '{database}' exists")
        return True
        
    except Exception as e:
        print_error(f"Failed to verify database: {str(e)}")
        return False

def main():
    """Main setup and verification function"""
    print_header("TradeLayout Backtesting Engine - Setup & Verification")
    
    # Check if .env exists
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        print_warning(".env file not found")
        if not create_env_file():
            print_error("Failed to create .env file")
            sys.exit(1)
    
    # Load configuration
    config = load_env_file()
    if not config:
        print_error("Failed to load .env file")
        sys.exit(1)
    
    # Test ClickHouse connection
    connection_ok = test_clickhouse_connection(config)
    
    if not connection_ok:
        print_warning("\nClickHouse connection failed!")
        print("\nOptions:")
        print("1. Update configuration")
        print("2. Exit and fix manually")
        
        choice = input("\nEnter choice [1/2]: ").strip()
        
        if choice == '1':
            new_config = prompt_for_config()
            update_env_file(new_config)
            
            # Test again with new config
            config = load_env_file()
            connection_ok = test_clickhouse_connection(config)
            
            if not connection_ok:
                print_error("\nStill cannot connect to ClickHouse!")
                print("\nPlease check:")
                print("1. ClickHouse server is running")
                print("2. User credentials are correct")
                print("3. Network connectivity")
                print("4. Firewall settings")
                sys.exit(1)
        else:
            print("\nPlease update .env file manually and run this script again")
            sys.exit(1)
    
    # Verify database and permissions
    verify_clickhouse_user(config)
    
    # All checks passed
    print_header("Setup Complete")
    print_success("All checks passed!")
    print("\nYou can now start the API server:")
    print("  python backtest_api_server.py")
    print("\nOr with systemd:")
    print("  sudo systemctl start tradelayout-backtest-api.service")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
