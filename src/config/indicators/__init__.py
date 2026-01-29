"""
Indicator Configuration Loader
Loads all indicator configurations from JSON files organized by category.
"""
import json
import os
from pathlib import Path
from typing import Dict, List

# Get the directory containing this file
INDICATORS_DIR = Path(__file__).parent


def load_all_indicators() -> Dict[str, List[Dict]]:
    """
    Load all indicator configurations from JSON files.
    
    Returns:
        Dict with structure:
        {
            "Moving Averages": [...],
            "Momentum Indicators": [...],
            "Volatility Indicators": [...],
            "Trend Indicators": [...],
            "Volume Indicators": [...]
        }
    """
    all_indicators = {}
    
    # Find all JSON files in the indicators directory
    json_files = list(INDICATORS_DIR.glob("*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                category = data.get('category', 'Other')
                indicators = data.get('indicators', [])
                
                if category in all_indicators:
                    all_indicators[category].extend(indicators)
                else:
                    all_indicators[category] = indicators
                    
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
    
    return all_indicators


def load_indicators_flat() -> List[Dict]:
    """
    Load all indicators as a flat list (no categories).
    
    Returns:
        List of all indicator configurations
    """
    all_indicators = load_all_indicators()
    flat_list = []
    
    for category, indicators in all_indicators.items():
        flat_list.extend(indicators)
    
    return flat_list


def get_indicator_by_name(name: str) -> Dict:
    """
    Get a specific indicator configuration by name.
    
    Args:
        name: Indicator name (e.g., 'EMA', 'RSI')
    
    Returns:
        Indicator configuration dict or None if not found
    """
    indicators = load_indicators_flat()
    
    for indicator in indicators:
        if indicator.get('name') == name:
            return indicator
    
    return None


def get_indicator_names() -> List[str]:
    """
    Get list of all available indicator names.
    
    Returns:
        List of indicator names
    """
    indicators = load_indicators_flat()
    return [ind.get('name') for ind in indicators if ind.get('name')]


# For backward compatibility with old code
def get_indicators_json() -> Dict:
    """
    Get indicators in the old format (for backward compatibility).
    
    Returns:
        {"indicators": [...]}
    """
    return {"indicators": load_indicators_flat()}


if __name__ == "__main__":
    # Test the loader
    print("Loading indicators...")
    all_indicators = load_all_indicators()
    
    print(f"\nFound {len(all_indicators)} categories:")
    for category, indicators in all_indicators.items():
        print(f"  - {category}: {len(indicators)} indicators")
    
    print(f"\nTotal indicators: {len(load_indicators_flat())}")
    print(f"\nAvailable indicators: {', '.join(get_indicator_names())}")
