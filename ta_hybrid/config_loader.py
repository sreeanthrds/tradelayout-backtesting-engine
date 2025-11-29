"""
Config Loader for ta_hybrid
============================

Loads indicator configurations from JSON files.
"""

import json
import os
from typing import Dict, List, Any
from pathlib import Path


class ConfigLoader:
    """Load and manage indicator configurations"""
    
    def __init__(self):
        self.config_dir = Path(__file__).parent / 'config'
        self._configs = {}
        self._load_all_configs()
    
    def _load_all_configs(self):
        """Load all JSON config files"""
        if not self.config_dir.exists():
            return
        
        for json_file in self.config_dir.glob('*.json'):
            category = json_file.stem  # filename without .json
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    self._configs[category] = data.get('indicators', [])
            except Exception as e:
                print(f"Warning: Could not load {json_file}: {e}")
    
    def get_config(self, indicator_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific indicator.
        
        Args:
            indicator_name: Indicator name (e.g., 'RSI', 'PIVOT', 'ELDER_RAY')
        
        Returns:
            Configuration dict or None if not found
        """
        indicator_name = indicator_name.upper()
        
        for category, indicators in self._configs.items():
            for ind in indicators:
                if ind.get('name', '').upper() == indicator_name:
                    return ind
        
        return None
    
    def get_all_configs(self) -> Dict[str, List[Dict]]:
        """Get all configurations grouped by category"""
        return self._configs.copy()
    
    def get_category_configs(self, category: str) -> List[Dict]:
        """Get all indicators in a category"""
        return self._configs.get(category, [])
    
    def list_categories(self) -> List[str]:
        """List all available categories"""
        return list(self._configs.keys())
    
    def list_indicators(self) -> List[str]:
        """List all indicator names"""
        indicators = []
        for category_indicators in self._configs.values():
            for ind in category_indicators:
                indicators.append(ind.get('name', ''))
        return sorted(indicators)
    
    def get_indicator_info(self, indicator_name: str) -> Dict[str, Any]:
        """
        Get detailed information about an indicator.
        
        Returns:
            {
                'name': 'RSI',
                'display_name': 'Relative Strength Index',
                'description': '...',
                'parameters': [...],
                'outputs': [...],
                'category': 'momentum'
            }
        """
        indicator_name = indicator_name.upper()
        
        for category, indicators in self._configs.items():
            for ind in indicators:
                if ind.get('name', '').upper() == indicator_name:
                    info = ind.copy()
                    info['category'] = category
                    return info
        
        return None


# Global config loader instance
_config_loader = ConfigLoader()


def get_config(indicator_name: str) -> Dict[str, Any]:
    """Get configuration for an indicator"""
    return _config_loader.get_config(indicator_name)


def get_all_configs() -> Dict[str, List[Dict]]:
    """Get all configurations"""
    return _config_loader.get_all_configs()


def list_indicators() -> List[str]:
    """List all available indicators"""
    return _config_loader.list_indicators()


def get_indicator_info(indicator_name: str) -> Dict[str, Any]:
    """Get detailed information about an indicator"""
    return _config_loader.get_indicator_info(indicator_name)
