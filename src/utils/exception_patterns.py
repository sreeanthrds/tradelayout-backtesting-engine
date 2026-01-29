"""
Exception Handling Patterns for Live Trading Engine
Provides standardized patterns for handling different types of exceptions
"""

from typing import Any, Dict, Optional, Callable
from .error_handler import handle_exception

def handle_condition_evaluation_error(error: Exception, context: str, condition: Any, 
                                    default_return: bool = False) -> bool:
    """
    Handle errors in condition evaluation (expected to return False on error)
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
        condition: The condition being evaluated
        default_return: Value to return on error (usually False for conditions)
        
    Returns:
        bool: The default_return value
    """
    handle_exception(error, context, {
        "condition": str(condition)[:200] if condition else "None",
        "default_return": default_return,
        "error_type": "condition_evaluation"
    }, is_critical=False, continue_execution=True)
    return default_return

def handle_data_processing_error(error: Exception, context: str, data_info: Dict[str, Any], 
                               default_return: Any = None) -> Any:
    """
    Handle errors in data processing (expected to return None or default on error)
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
        data_info: Information about the data being processed
        default_return: Value to return on error
        
    Returns:
        Any: The default_return value
    """
    handle_exception(error, context, {
        "data_info": data_info,
        "default_return": default_return,
        "error_type": "data_processing"
    }, is_critical=False, continue_execution=True)
    return default_return

def handle_network_error(error: Exception, context: str, network_info: Dict[str, Any], 
                        default_return: Any = None) -> Any:
    """
    Handle network-related errors (may be critical for live trading)
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
        network_info: Information about the network operation
        default_return: Value to return on error
        
    Returns:
        Any: The default_return value
    """
    is_critical = "websocket" in context.lower() or "api" in context.lower()
    handle_exception(error, context, {
        "network_info": network_info,
        "default_return": default_return,
        "error_type": "network",
        "is_critical": is_critical
    }, is_critical=is_critical, continue_execution=True)
    return default_return

def handle_calculation_error(error: Exception, context: str, calculation_info: Dict[str, Any], 
                           default_return: Any = None) -> Any:
    """
    Handle calculation errors (usually non-critical)
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
        calculation_info: Information about the calculation
        default_return: Value to return on error
        
    Returns:
        Any: The default_return value
    """
    handle_exception(error, context, {
        "calculation_info": calculation_info,
        "default_return": default_return,
        "error_type": "calculation"
    }, is_critical=False, continue_execution=True)
    return default_return

def handle_validation_error(error: Exception, context: str, validation_info: Dict[str, Any], 
                          default_return: Any = None) -> Any:
    """
    Handle validation errors (usually non-critical)
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
        validation_info: Information about the validation
        default_return: Value to return on error
        
    Returns:
        Any: The default_return value
    """
    handle_exception(error, context, {
        "validation_info": validation_info,
        "default_return": default_return,
        "error_type": "validation"
    }, is_critical=False, continue_execution=True)
    return default_return

def safe_condition_evaluation(func: Callable, context: str, condition: Any, 
                             default_return: bool = False, *args, **kwargs) -> bool:
    """
    Safely evaluate a condition with proper error handling
    
    Args:
        func: Function to execute
        context: Context name for error logging
        condition: The condition being evaluated
        default_return: Value to return on error
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function
        
    Returns:
        bool: Function result or default_return if error occurred
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return handle_condition_evaluation_error(e, context, condition, default_return)

def safe_data_processing(func: Callable, context: str, data_info: Dict[str, Any], 
                        default_return: Any = None, *args, **kwargs) -> Any:
    """
    Safely process data with proper error handling
    
    Args:
        func: Function to execute
        context: Context name for error logging
        data_info: Information about the data being processed
        default_return: Value to return on error
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function
        
    Returns:
        Any: Function result or default_return if error occurred
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        return handle_data_processing_error(e, context, data_info, default_return)
