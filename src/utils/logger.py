import json
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path

# Path to config and log file
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'logging_config.json')
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')

# Use single log file (cleared at startup to save disk space)
LOG_FILE = os.path.join(LOG_DIR, 'backtest.log')

# Ensure log directory exists
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

# Clear log file at startup to avoid wasting disk space
# (Later can be enhanced with log rotation/archival strategy)
if os.path.exists(LOG_FILE):
    open(LOG_FILE, 'w').close()  # Truncate file

# Default config (if file missing)
DEFAULT_CONFIG = {
    "DEBUG": True,
    "INFO": True,
    "WARNING": True,
    "ERROR": True,
    "CRITICAL": True,
    "PER_TICK_LOG": False,
    "NODE_EXEC_LOG": False,
    "UTILITY_LOG": False,
    "ORDER_LOG": False
}

# Load config
try:
    with open(CONFIG_PATH, 'r') as f:
        LOG_LEVELS_ENABLED = json.load(f)
except Exception as e:
    # This is a logger initialization error, so we can't use handle_exception here
    # Just use basic logging to avoid circular imports
    print(f"Warning: Could not load logger config from {CONFIG_PATH}: {e}")
    LOG_LEVELS_ENABLED = DEFAULT_CONFIG


# Custom formatter to include file name and line number
class CustomFormatter(logging.Formatter):
    def format(self, record):
        record.filename = record.pathname.split(os.sep)[-1]
        record.lineno = record.lineno
        return super().format(record)


LOG_FORMAT = '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Set up logger
logger = logging.getLogger('app_logger')
logger.setLevel(logging.DEBUG)  # Always log everything, filter in handlers

# File handler - only create if logging is enabled
# Use append mode (file already cleared at startup)
if os.environ.get('ENABLE_BACKTEST_LOGGING', 'true').lower() != 'false':
    file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    file_handler.setFormatter(CustomFormatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(file_handler)


# Level check helper
def _should_log(level: str) -> bool:
    # Check if logging is globally disabled via environment variable
    if os.environ.get('ENABLE_BACKTEST_LOGGING', 'true').lower() == 'false':
        return False
    return LOG_LEVELS_ENABLED.get(level.upper(), True)


# Logging functions
def log_debug(msg, *args, **kwargs):
    if _should_log('DEBUG'):
        logger.debug(msg, *args, **kwargs)


def log_info(msg, *args, **kwargs):
    if _should_log('INFO'):
        logger.info(msg, *args, **kwargs)


def log_warning(msg, *args, **kwargs):
    if _should_log('WARNING'):
        logger.warning(msg, *args, **kwargs)


def log_error(msg, *args, exc_info=False, **kwargs):
    if _should_log('ERROR'):
        if exc_info:
            logger.error(msg + '\n' + traceback.format_exc(), *args, **kwargs)
        else:
            logger.error(msg, *args, **kwargs)


def log_critical(msg, *args, exc_info=False, **kwargs):
    if _should_log('CRITICAL'):
        if exc_info:
            logger.critical(msg + '\n' + traceback.format_exc(), *args, **kwargs)
        else:
            logger.critical(msg, *args, **kwargs)


def is_per_tick_log_enabled():
    return LOG_LEVELS_ENABLED.get("PER_TICK_LOG", False)


def is_node_exec_log_enabled():
    return LOG_LEVELS_ENABLED.get("NODE_EXEC_LOG", False)


def is_utility_log_enabled():
    return LOG_LEVELS_ENABLED.get("UTILITY_LOG", False)


def is_order_log_enabled():
    return LOG_LEVELS_ENABLED.get("ORDER_LOG", False)
