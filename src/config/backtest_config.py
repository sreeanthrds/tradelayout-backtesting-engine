"""
Backtesting Configuration

Handles broker credentials for backtesting.
Note: These credentials are used ONLY for loading scrip master data,
NOT for actual trading (backtesting uses simulated orders).
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional

from src.utils.logger import log_info, log_warning, log_error


class BacktestConfig:
    """
    Configuration for backtesting.
    
    Provides broker credentials for scrip master loading.
    These credentials are NOT used for actual trading.
    """
    
    def __init__(self):
        """Initialize backtest configuration"""
        self.config_file = Path(__file__).parent.parent.parent / "config" / "backtest_broker_config.json"
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """
        Load configuration from file.
        
        Returns:
            Configuration dictionary
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    log_info(f"✅ Loaded backtest config from {self.config_file}")
                    return config
            else:
                log_warning(f"⚠️ Backtest config file not found: {self.config_file}")
                return {}
        except Exception as e:
            log_error(f"❌ Error loading backtest config: {e}")
            return {}
    
    def get_broker_credentials(self, broker: str = 'angelone') -> Optional[Dict]:
        """
        Get broker credentials for scrip master loading.
        
        Args:
            broker: Broker name (default: 'angelone')
            
        Returns:
            Credentials dictionary or None
        """
        credentials = self.config.get(broker)
        
        if not credentials:
            log_warning(f"⚠️ No credentials found for broker: {broker}")
            return None
        
        # Check if all required fields are present
        required_fields = ['api_key', 'client_id', 'password']
        missing_fields = [field for field in required_fields if not credentials.get(field)]
        
        if missing_fields:
            log_warning(f"⚠️ Missing required fields: {missing_fields}")
            return None
        
        log_info(f"✅ Loaded credentials for {broker} (for scrip master only)")
        return credentials
    
    def get_angelone_credentials(self) -> Optional[Dict]:
        """
        Get AngelOne credentials.
        
        Returns:
            Credentials dictionary or None
        """
        return self.get_broker_credentials('angelone')


# Singleton instance
_backtest_config = None

def get_backtest_config() -> BacktestConfig:
    """
    Get singleton backtest config instance.
    
    Returns:
        BacktestConfig instance
    """
    global _backtest_config
    if _backtest_config is None:
        _backtest_config = BacktestConfig()
    return _backtest_config
