"""
Utility functions for run configuration management.
"""
from typing import Dict, Any


# Define the fields that uniquely identify a trading strategy
STRATEGY_IDENTIFYING_FIELDS = [
    "instrument_name",
    "way",
    "point_type",
    "point_strategy_key",
    "point_position",
    "exit_strategy_key",
]


def extract_strategy_config(full_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the identifying fields from a full run configuration.
    
    These fields define the trading strategy and are used to detect
    duplicate configurations.
    
    Args:
        full_config: The complete run configuration dictionary
    
    Returns:
        Dictionary containing only the strategy-identifying fields
    """
    strategy_config = {}
    
    for field in STRATEGY_IDENTIFYING_FIELDS:
        if field in full_config:
            value = full_config[field]
            # Convert enum objects to their string values for consistent comparison
            if hasattr(value, 'value'):
                strategy_config[field] = value.value
            else:
                strategy_config[field] = str(value) if value is not None else None
    
    return strategy_config


def normalize_strategy_config(strategy_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize strategy config for consistent comparison.
    Ensures all values are strings and sorted by key.
    
    Args:
        strategy_config: The strategy configuration to normalize
    
    Returns:
        Normalized strategy configuration
    """
    normalized = {}
    for key in sorted(strategy_config.keys()):
        value = strategy_config[key]
        if hasattr(value, 'value'):
            normalized[key] = str(value.value)
        else:
            normalized[key] = str(value) if value is not None else None
    
    return normalized
