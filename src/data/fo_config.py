"""
F&O Configuration - Index and Commodity settings for dynamic resolution.
"""

from typing import Dict, List

# F&O Index Configuration (NSE/BSE)
FO_INDEX_CONFIG = {
    "NIFTY": {
        "exchange": "NFO",
        "lot_size": 50,
        "strike_interval": 50,
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["W0", "W1", "W2", "W3", "W4", "M0", "M1", "M2", "Q0", "Q1", "Y0", "Y1"]
        },
        "expiry_day": {
            "weekly": "Thursday",
            "monthly": "last_thursday",
            "quarterly": "last_thursday",
            "yearly": "last_thursday"
        }
    },
    
    "SENSEX": {
        "exchange": "BFO",
        "lot_size": 10,
        "strike_interval": 100,
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["W0", "W1", "W2", "W3", "W4", "M0", "M1", "M2", "Q0", "Q1", "Y0", "Y1"]
        },
        "expiry_day": {
            "weekly": "Friday",
            "monthly": "last_friday",
            "quarterly": "last_friday",
            "yearly": "last_friday"
        }
    },
    
    "BANKNIFTY": {
        "exchange": "NFO",
        "lot_size": 15,
        "strike_interval": 100,
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2", "Q0", "Q1", "Y0", "Y1"]  # No weekly
        },
        "expiry_day": {
            "monthly": "last_wednesday",
            "quarterly": "last_wednesday",
            "yearly": "last_wednesday"
        }
    },
    
    "FINNIFTY": {
        "exchange": "NFO",
        "lot_size": 40,
        "strike_interval": 50,
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2", "Q0", "Q1", "Y0", "Y1"]  # No weekly
        },
        "expiry_day": {
            "monthly": "last_tuesday",
            "quarterly": "last_tuesday",
            "yearly": "last_tuesday"
        }
    },
    
    "MIDCPNIFTY": {
        "exchange": "NFO",
        "lot_size": 75,
        "strike_interval": 25,
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2", "Q0", "Q1"]  # No weekly, no yearly
        },
        "expiry_day": {
            "monthly": "last_monday",
            "quarterly": "last_monday"
        }
    }
}


def get_index_config(index: str) -> Dict:
    """Get configuration for an index."""
    index_upper = index.upper()
    if index_upper not in FO_INDEX_CONFIG:
        raise ValueError(f"Index {index} not configured for F&O")
    return FO_INDEX_CONFIG[index_upper]


def get_strike_interval(index: str) -> int:
    """Get strike interval for an index."""
    return get_index_config(index)["strike_interval"]


def get_lot_size(index: str) -> int:
    """Get lot size for an index."""
    return get_index_config(index)["lot_size"]


def get_exchange(index: str) -> str:
    """Get exchange for an index."""
    return get_index_config(index)["exchange"]


def get_supported_expiry_types(index: str, instrument_type: str = "options") -> List[str]:
    """Get supported expiry types for an index."""
    config = get_index_config(index)
    return config["expiry_types"].get(instrument_type, [])


# MCX Commodity Configuration
MCX_COMMODITY_CONFIG = {
    "GOLD": {
        "exchange": "MCX",
        "lot_size": 100,  # grams
        "strike_interval": 10000,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "first_friday"  # First Friday of expiry month
        },
        "unit": "grams"
    },
    
    "GOLDM": {
        "exchange": "MCX",
        "lot_size": 100,  # grams (mini)
        "strike_interval": 10000,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "first_friday"
        },
        "unit": "grams"
    },
    
    "SILVER": {
        "exchange": "MCX",
        "lot_size": 30,  # kg (30000 grams)
        "strike_interval": 25000,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "first_friday"
        },
        "unit": "kg"
    },
    
    "SILVERM": {
        "exchange": "MCX",
        "lot_size": 5,  # kg (mini)
        "strike_interval": 25000,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "first_friday"
        },
        "unit": "kg"
    },
    
    "CRUDEOIL": {
        "exchange": "MCX",
        "lot_size": 100,  # barrels
        "strike_interval": 5000,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "third_tuesday"  # Third Tuesday of expiry month
        },
        "unit": "barrels"
    },
    
    "NATURALGAS": {
        "exchange": "MCX",
        "lot_size": 1250,  # mmBtu
        "strike_interval": 5,  # Gap between strikes in rupees (e.g., 255, 260, 265, 270...)
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "last_tuesday"
        },
        "unit": "mmBtu"
    },
    
    "COPPER": {
        "exchange": "MCX",
        "lot_size": 2500,  # kg
        "strike_interval": 500,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "last_tuesday"
        },
        "unit": "kg"
    },
    
    "ZINC": {
        "exchange": "MCX",
        "lot_size": 5,  # MT (metric tons)
        "strike_interval": 250,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "last_tuesday"
        },
        "unit": "MT"
    },
    
    "LEAD": {
        "exchange": "MCX",
        "lot_size": 5,  # MT
        "strike_interval": 500,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "last_tuesday"
        },
        "unit": "MT"
    },
    
    "NICKEL": {
        "exchange": "MCX",
        "lot_size": 250,  # kg
        "strike_interval": 1000,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "last_tuesday"
        },
        "unit": "kg"
    },
    
    "ALUMINIUM": {
        "exchange": "MCX",
        "lot_size": 5,  # MT
        "strike_interval": 500,  # Gap between strikes
        "expiry_types": {
            "futures": ["M0", "M1", "M2"],
            "options": ["M0", "M1", "M2"]
        },
        "expiry_day": {
            "monthly": "last_tuesday"
        },
        "unit": "MT"
    }
}


def get_commodity_config(commodity: str) -> Dict:
    """Get configuration for a commodity."""
    commodity_upper = commodity.upper()
    if commodity_upper not in MCX_COMMODITY_CONFIG:
        raise ValueError(f"Commodity {commodity} not configured for MCX")
    return MCX_COMMODITY_CONFIG[commodity_upper]


def get_config(symbol: str) -> Dict:
    """
    Get configuration for any symbol (index or commodity).
    
    Args:
        symbol: Symbol name (e.g., NIFTY, GOLD, SILVER)
    
    Returns:
        Configuration dictionary
    """
    symbol_upper = symbol.upper()
    
    # Try index first
    if symbol_upper in FO_INDEX_CONFIG:
        return FO_INDEX_CONFIG[symbol_upper]
    
    # Try commodity
    if symbol_upper in MCX_COMMODITY_CONFIG:
        return MCX_COMMODITY_CONFIG[symbol_upper]
    
    raise ValueError(f"Symbol {symbol} not found in configuration")
