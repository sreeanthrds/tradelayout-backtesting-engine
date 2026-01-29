#!/usr/bin/env python3
"""
Supabase Adapter for Live Trading Engine
Handles strategy fetching and management from Supabase database
"""

import os
from datetime import datetime
from typing import Dict, List, Any

try:
    from supabase import create_client, Client
except ImportError:
    # log_info("⚠️  Supabase client not installed. Run: pip install supabase")
    Client = None

from src.utils.logger import log_debug, log_info, log_warning, log_error, log_critical, is_order_log_enabled


class SupabaseStrategyAdapter:
    """
    Adapter for fetching and managing strategies from Supabase database.
    Converts database format to engine-compatible format.
    """

    def __init__(self, url: str = None, key: str = None):
        """
        Initialize Supabase adapter.
        
        Args:
            url: Supabase URL (defaults to environment variable)
            key: Supabase service role key (defaults to environment variable)
        """
        self.url = url or os.getenv('SUPABASE_URL')
        self.key = key or os.getenv('SUPABASE_SERVICE_ROLE_KEY')

        if not self.url or not self.key:
            raise ValueError("Supabase URL and key must be provided or set in environment variables")

        if Client is None:
            raise ImportError("Supabase client not installed. Run: pip install supabase")

        self.supabase: Client = create_client(self.url, self.key)
        # log_info(f"✅ Supabase adapter initialized: {self.url}")

    def get_strategy(self, strategy_id: str, user_id: str = None) -> Dict[str, Any]:
        """
        Fetch specific strategy from Supabase.
        
        Args:
            strategy_id: Strategy UUID
            user_id: User UUID (optional - if None, fetches by strategy_id only)
            
        Returns:
            Strategy data in engine-compatible format
            
        Raises:
            ValueError: If strategy not found
        """
        try:
            # Build query
            query = self.supabase.table("strategies").select("*").eq("id", strategy_id)
            
            # Add user_id filter only if provided
            if user_id is not None:
                query = query.eq("user_id", user_id)
            
            response = query.execute()

            if not response.data:
                if user_id:
                    raise ValueError(f"Strategy {strategy_id} not found for user {user_id}")
                else:
                    raise ValueError(f"Strategy {strategy_id} not found")

            strategy_data = response.data[0]
            log_info(f"✅ Strategy fetched: {strategy_data.get('name', 'Unknown')}")

            # Convert database format to engine format
            return self._convert_db_to_engine_format(strategy_data)

        except Exception as e:
            from src.utils.error_handler import handle_exception
            handle_exception(
                e,
                "supabase_adapter_get_strategy",
                {
                    "strategy_id": strategy_id,
                    "user_id": user_id
                },
                is_critical=True,
                continue_execution=False
            )
            raise RuntimeError(f"Failed to fetch strategy from database: {e}") from e

    def get_user_strategies(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all strategies for a user.
        
        Args:
            user_id: User UUID
            
        Returns:
            List of strategy summaries
        """
        try:
            response = self.supabase.table("strategies").select(
                "id, name, description, status, created_at, updated_at, version"
            ).eq("user_id", user_id).order("created_at", desc=True).execute()

            strategies = response.data
            # log_info(f"✅ Found {len(strategies)} strategies for user {user_id}")

            return strategies

        except Exception as e:
            log_error(f"❌ Error fetching user strategies: {e}", exc_info=True)
            raise

    def create_strategy(self, user_id: str, name: str, description: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new strategy in Supabase.
        
        Args:
            user_id: User UUID
            name: Strategy name
            description: Strategy description
            config: Strategy configuration (engine format)
            
        Returns:
            Created strategy data
        """
        try:
            strategy_data = {
                "user_id": user_id,
                "name": name,
                "description": description,
                "config": config,
                "status": "active",
                "version": 1
            }

            response = self.supabase.table("strategies").insert(strategy_data).execute()

            if not response.data:
                raise ValueError("Failed to create strategy")

            created_strategy = response.data[0]
            # log_info(f"✅ Strategy created: {created_strategy['name']} (ID: {created_strategy['id']})")

            return created_strategy

        except Exception as e:
            log_error(f"❌ Error creating strategy: {e}", exc_info=True)
            raise

    def update_strategy(self, strategy_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing strategy.
        
        Args:
            strategy_id: Strategy UUID
            user_id: User UUID
            updates: Fields to update
            
        Returns:
            Updated strategy data
        """
        try:
            # Add updated_at timestamp
            updates['updated_at'] = datetime.now().isoformat()

            response = self.supabase.table("strategies").update(updates).eq("id", strategy_id).eq("user_id",
                                                                                                  user_id).execute()

            if not response.data:
                raise ValueError(f"Strategy {strategy_id} not found or update failed")

            updated_strategy = response.data[0]
            # log_info(f"✅ Strategy updated: {updated_strategy['name']}")

            return updated_strategy

        except Exception as e:
            log_error(f"❌ Error updating strategy: {e}", exc_info=True)
            raise

    def delete_strategy(self, strategy_id: str, user_id: str) -> bool:
        """
        Delete a strategy.
        
        Args:
            strategy_id: Strategy UUID
            user_id: User UUID
            
        Returns:
            True if deleted successfully
        """
        try:
            response = self.supabase.table("strategies").delete().eq("id", strategy_id).eq("user_id", user_id).execute()

            if response.data:
                # log_info(f"✅ Strategy deleted: {strategy_id}")
                return True
            else:
                log_warning(f"⚠️  Strategy {strategy_id} not found or already deleted")
                return False

        except Exception as e:
            log_error(f"❌ Error deleting strategy: {e}", exc_info=True)
            raise

    def save_execution_result(self, strategy_id: str, user_id: str, execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save strategy execution results.
        
        Args:
            strategy_id: Strategy UUID
            user_id: User UUID
            execution_data: Execution results (GPS data, performance metrics)
            
        Returns:
            Saved execution record
        """
        try:
            execution_record = {
                "strategy_id": strategy_id,
                "user_id": user_id,
                "execution_type": execution_data.get("execution_type", "backtest"),
                "start_time": execution_data.get("start_time"),
                "end_time": execution_data.get("end_time"),
                "status": execution_data.get("status", "completed"),
                "results": execution_data.get("results", {}),
                "created_at": datetime.now().isoformat()
            }

            response = self.supabase.table("strategy_executions").insert(execution_record).execute()

            if not response.data:
                raise ValueError("Failed to save execution result")

            saved_record = response.data[0]
            # log_info(f"✅ Execution result saved: {saved_record['id']}")

            return saved_record

        except Exception as e:
            log_error(f"❌ Error saving execution result: {e}", exc_info=True)
            raise

    def _convert_db_to_engine_format(self, db_strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert database strategy format to engine format.
        
        Args:
            db_strategy: Strategy data from database
            
        Returns:
            Strategy data in engine format
            
        Raises:
            ValueError: If strategy configuration is empty or invalid
        """
        # Strategy JSON may be stored under 'strategy' (preferred) or 'config'
        config = db_strategy.get('strategy') or db_strategy.get('config')
        
        if not config:
            raise ValueError(
                f"Strategy '{db_strategy.get('name')}' (ID: {db_strategy.get('id')}) has no configuration. "
                f"Please configure the strategy in the database before running."
            )
        
        # Parse JSON if it's a string
        if isinstance(config, str):
            import json
            config = json.loads(config)
            
        # Validate that config has required fields
        if not isinstance(config, dict) or not config.get('nodes'):
            raise ValueError(
                f"Strategy '{db_strategy.get('name')}' (ID: {db_strategy.get('id')}) has invalid configuration. "
                f"Configuration must contain 'nodes' array."
            )

        # Apply timeframe ID translation before processing
        translated_config = translate_timeframe_ids(config)
        
        # Process edges to populate parent-child relationships in nodes
        translated_config = self._process_edges(translated_config)

        # Add metadata from database
        engine_strategy = {
            'strategy_id': db_strategy['id'],
            'user_id': db_strategy.get('user_id'),  # Add user_id from database
            'strategy_name': db_strategy['name'],
            'name': db_strategy['name'],  # Also add 'name' for convenience
            'strategy_description': db_strategy.get('description', ''),
            'strategy_status': db_strategy.get('status', 'active'),
            'strategy_version': db_strategy.get('version', 1),
            'created_at': db_strategy.get('created_at'),
            'updated_at': db_strategy.get('updated_at'),
            **translated_config  # Include all config fields with translated timeframeId values
        }

        return engine_strategy
    
    def _process_edges(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process edges array and populate parents/children in nodes.
        
        Args:
            config: Strategy configuration with edges array
            
        Returns:
            Config with nodes having parents and children populated
        """
        edges = config.get('edges', [])
        nodes = config.get('nodes', [])
        
        # Create node lookup
        node_map = {node['id']: node for node in nodes}
        
        # Initialize parents and children arrays for all nodes
        for node in nodes:
            if 'parents' not in node:
                node['parents'] = []
            if 'children' not in node:
                node['children'] = []
        
        # Process edges to populate parent-child relationships
        for edge in edges:
            source_id = edge.get('source')
            target_id = edge.get('target')
            
            if source_id and target_id:
                # Add target as child of source
                if source_id in node_map:
                    if target_id not in node_map[source_id]['children']:
                        node_map[source_id]['children'].append(target_id)
                
                # Add source as parent of target
                if target_id in node_map:
                    if source_id not in node_map[target_id]['parents']:
                        node_map[target_id]['parents'].append(source_id)
        
        log_debug(f"✅ Processed {len(edges)} edges into parent-child relationships")
        
        return config

    def test_connection(self) -> bool:
        """
        Test Supabase connection.
        
        Returns:
            True if connection successful
        """
        try:
            # Try a simple query to test connection
            response = self.supabase.table("strategies").select("count", count="exact").limit(1).execute()
            # log_info("✅ Supabase connection test successful")
            return True
        except Exception as e:
            log_error(f"❌ Supabase connection test failed: {e}", exc_info=True)
            return False


# Convenience functions for backward compatibility
def get_user_strategies(user_id: str, url: str = None, key: str = None) -> List[Dict[str, Any]]:
    """Get all strategies for a user."""
    adapter = SupabaseStrategyAdapter(url, key)
    return adapter.get_user_strategies(user_id)


def get_strategy(strategy_id: str, user_id: str, url: str = None, key: str = None) -> Dict[str, Any]:
    """Get specific strategy."""
    adapter = SupabaseStrategyAdapter(url, key)
    return adapter.get_strategy(strategy_id, user_id)


def translate_timeframe_ids(strategy_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate UUID timeframeId values to their corresponding timeframe values using string replacement.
    
    Args:
        strategy_config: Strategy configuration dictionary
        
    Returns:
        Strategy configuration with translated timeframeId values
    """
    try:
        import json
        
        # Step 1: Create mapping dictionary from tradingInstrumentConfig and supportingInstrumentConfig
        timeframe_mapping = {}
        
        # Extract from tradingInstrumentConfig (check multiple possible locations)
        def extract_timeframes_from_config(config, path=""):
            """Recursively extract timeframes from config"""
            if isinstance(config, dict):
                # Check direct location
                if 'tradingInstrumentConfig' in config:
                    timeframes = config['tradingInstrumentConfig'].get('timeframes', [])
                    for tf in timeframes:
                        if 'id' in tf and 'timeframe' in tf:
                            timeframe_mapping[tf['id']] = tf['timeframe']
                            log_debug(f"Found timeframe mapping: {tf['id']} → {tf['timeframe']} at {path}/tradingInstrumentConfig")
                
                if 'supportingInstrumentConfig' in config:
                    timeframes = config['supportingInstrumentConfig'].get('timeframes', [])
                    for tf in timeframes:
                        if 'id' in tf and 'timeframe' in tf:
                            timeframe_mapping[tf['id']] = tf['timeframe']
                            log_debug(f"Found timeframe mapping: {tf['id']} → {tf['timeframe']} at {path}/supportingInstrumentConfig")
                
                # Recursively check nested structures
                for key, value in config.items():
                    if isinstance(value, (dict, list)):
                        extract_timeframes_from_config(value, f"{path}/{key}")
            elif isinstance(config, list):
                for i, item in enumerate(config):
                    extract_timeframes_from_config(item, f"{path}[{i}]")
        
        # Extract timeframes from the entire config structure
        extract_timeframes_from_config(strategy_config, "root")
        
        # If no mappings found, return original config
        if not timeframe_mapping:
            log_debug("No timeframe mappings found, returning original config")
            return strategy_config
        
        # Step 2: Convert strategy to string, replace ALL UUID occurrences, convert back to dict
        strategy_str = json.dumps(strategy_config)
        
        # Replace ALL occurrences of each UUID with its respective timeframe
        for tid, tf in timeframe_mapping.items():
            strategy_str = strategy_str.replace(tid, tf)
        
        # Convert back to dictionary
        translated_config = json.loads(strategy_str)
        
        log_debug(f"✅ Timeframe IDs translated: {len(timeframe_mapping)} mappings applied")
        return translated_config
        
    except Exception as e:
        log_warning(f"⚠️  Error translating timeframe IDs: {e}")
        return strategy_config
