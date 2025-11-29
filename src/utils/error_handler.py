"""
Global Error Handler for the Live Trading Engine
Provides configurable error handling with detailed logging and context
"""

import logging
import traceback
from typing import Any, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)

class GlobalErrorHandler:
    """Global error handler with configurable behavior"""
    
    def __init__(self, raise_errors: bool = True, log_level: int = logging.ERROR):
        self.raise_errors = raise_errors
        self.log_level = log_level
        self.error_count = 0
        
    def handle_error(self, error: Exception, context: str, extra_data: Dict[str, Any] = None, 
                    is_critical: bool = False, continue_execution: bool = True) -> bool:
        """
        Handle an error with configurable behavior
        
        Args:
            error: The exception that occurred
            context: Context where the error occurred
            extra_data: Additional data for debugging
            is_critical: Whether this is a critical error that should stop execution
            continue_execution: Whether to continue execution after handling
            
        Returns:
            bool: True if execution should continue, False if should stop
        """
        self.error_count += 1
        
        # Prepare error message
        error_msg = f"Error in {context}: {str(error)}"
        if extra_data:
            error_msg += f" | Extra: {extra_data}"
        
        # Log the error with appropriate level
        if self.log_level <= logging.CRITICAL:
            logger.critical(error_msg, exc_info=True)
        elif self.log_level <= logging.ERROR:
            logger.error(error_msg, exc_info=True)
        elif self.log_level <= logging.WARNING:
            logger.warning(error_msg, exc_info=True)
        else:
            logger.info(error_msg, exc_info=True)
        
        # Determine if we should raise the error
        should_raise = self.raise_errors and (is_critical or not continue_execution)
        
        if should_raise:
            logger.critical(f"🚨 CRITICAL ERROR: Stopping execution due to error in {context}")
            raise error
        
        return continue_execution

# Global instance
_global_handler = GlobalErrorHandler()

def set_global_error_handler(raise_errors: bool = True, log_level: int = logging.ERROR):
    """Set global error handler configuration"""
    global _global_handler
    _global_handler = GlobalErrorHandler(raise_errors, log_level)
    logger.info(f"🔧 Global error handler configured: raise_errors={raise_errors}, log_level={log_level}")

def handle_exception(error: Exception, context: str, extra_data: Dict[str, Any] = None, 
                    is_critical: bool = False, continue_execution: bool = True) -> bool:
    """
    Handle an exception with global error handler
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
        extra_data: Additional data for debugging
        is_critical: Whether this is a critical error that should stop execution
        continue_execution: Whether to continue execution after handling
        
    Returns:
        bool: True if execution should continue, False if should stop
    """
    return _global_handler.handle_error(error, context, extra_data, is_critical, continue_execution)

def handle_async_exception(error: Exception, context: str, extra_data: Dict[str, Any] = None, 
                          is_critical: bool = False, continue_execution: bool = True) -> bool:
    """
    Handle an async exception with global error handler
    
    Args:
        error: The exception that occurred
        context: Context where the error occurred
        extra_data: Additional data for debugging
        is_critical: Whether this is a critical error that should stop execution
        continue_execution: Whether to continue execution after handling
        
    Returns:
        bool: True if execution should continue, False if should stop
    """
    return _global_handler.handle_error(error, context, extra_data, is_critical, continue_execution)

def error_handler_decorator(context: str, is_critical: bool = False, continue_execution: bool = True):
    """
    Decorator for automatic error handling
    
    Args:
        context: Context name for error logging
        is_critical: Whether errors in this function are critical
        continue_execution: Whether to continue execution after error
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handle_exception(e, context, {
                    "function": func.__name__,
                    "args": str(args)[:100] if args else "None",
                    "kwargs": str(kwargs)[:100] if kwargs else "None"
                }, is_critical, continue_execution)
                if continue_execution:
                    return None
                raise
        return wrapper
    return decorator

def safe_execute(func, context: str, default_return=None, is_critical: bool = False, 
                continue_execution: bool = True, *args, **kwargs):
    """
    Safely execute a function with error handling
    
    Args:
        func: Function to execute
        context: Context name for error logging
        default_return: Value to return if function fails and continue_execution is True
        is_critical: Whether errors in this function are critical
        continue_execution: Whether to continue execution after error
        *args: Arguments to pass to function
        **kwargs: Keyword arguments to pass to function
        
    Returns:
        Function result or default_return if error occurred
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        handle_exception(e, context, {
            "function": func.__name__ if hasattr(func, '__name__') else str(func),
            "args": str(args)[:100] if args else "None",
            "kwargs": str(kwargs)[:100] if kwargs else "None"
        }, is_critical, continue_execution)
        return default_return

def get_error_count() -> int:
    """Get total number of errors handled"""
    return _global_handler.error_count

def reset_error_count():
    """Reset error count"""
    _global_handler.error_count = 0