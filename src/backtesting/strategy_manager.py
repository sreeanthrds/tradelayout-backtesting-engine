"""
Strategy Manager
================

Handles strategy loading and parsing from Supabase.
Extracts timeframes, indicators, and symbols from strategy configuration.
"""

import logging
import json
from typing import Optional

from src.adapters.supabase_adapter import SupabaseStrategyAdapter
from src.utils.logger import logger
from src.backtesting.strategy_metadata import StrategyMetadata
from src.backtesting.strategy_metadata_builder import StrategyMetadataBuilder

logger = logging.getLogger(__name__)


class StrategyManager:
    """
    Manages strategy loading and parsing.
    
    Responsibilities:
    - Load strategy from Supabase
    - Parse strategy configuration
    - Extract timeframes, indicators, symbols
    """
    
    def __init__(self):
        """Initialize strategy manager."""
        self.adapter = SupabaseStrategyAdapter()
        self.metadata_builder = StrategyMetadataBuilder()
        logger.info("📋 Strategy Manager initialized")
    
    def load_strategy(
        self,
        strategy_id: str,
        user_id: Optional[str] = None,
        broker_connection_id: Optional[str] = None
    ) -> StrategyMetadata:
        """
        Load and parse strategy from Supabase with comprehensive metadata extraction.
        
        Architecture: user_id is optional - if not provided, it's fetched from strategy record.
        This ensures single source of truth (strategy record in database).
        
        Args:
            strategy_id: Strategy ID
            user_id: Optional user ID (fetched from strategy if not provided)
            broker_connection_id: Optional broker connection ID (for live trading)
        
        Returns:
            StrategyMetadata object with all strategy information
        """
        logger.info(f"📥 Loading strategy: {strategy_id}")
        
        # Load raw config from Supabase
        raw_config = self.adapter.get_strategy(strategy_id=strategy_id, user_id=user_id)
        
        # Save to file for debugging
        try:
            with open('/tmp/strategy_full_config.json', 'w') as f:
                json.dump(raw_config, f, indent=2, default=str)
            logger.info("📄 Strategy config saved to: /tmp/strategy_full_config.json")
        except Exception as e:
            logger.warning(f"Could not save strategy config: {e}")
        
        # Extract user_id from strategy record if not provided
        if not user_id:
            user_id = raw_config.get('user_id')
            if not user_id:
                raise ValueError(f"user_id not found in strategy record {strategy_id}")
            logger.info(f"   User ID from strategy: {user_id}")
        
        # Build comprehensive metadata (single source of truth)
        metadata = self.metadata_builder.build(
            strategy_config=raw_config,
            strategy_id=strategy_id,
            user_id=user_id,
            broker_connection_id=broker_connection_id
        )
        
        # Print comprehensive summary
        metadata.print_summary()
        
        return metadata
