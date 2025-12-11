"""
Strategy Metadata Builder - Extract comprehensive metadata from strategy config.

This module builds a complete StrategyMetadata object from a strategy configuration,
capturing ALL information in one pass:
- Symbols and timeframes
- Indicators per timeframe
- Option patterns from entry nodes
- Broker mappings (if provided)

Author: UniTrader Team
Created: 2024-11-21
"""

import re
from typing import Dict, List, Set, Any, Optional
from src.backtesting.strategy_metadata import (
    StrategyMetadata,
    IndicatorMetadata,
    InstrumentConfig,
    OptionPatternMetadata,
    BrokerMetadata
)
from src.utils.logger import log_info, log_debug, log_warning


class StrategyMetadataBuilder:
    """
    Build comprehensive strategy metadata from configuration.
    
    Extracts:
    1. Instrument configs (symbol-timeframe-indicators binding)
    2. Option patterns from entry nodes
    3. Broker mappings (if provided)
    4. Node and edge configuration
    """
    
    # Known indicator functions
    INDICATOR_FUNCTIONS = {
        'RSI', 'EMA', 'SMA', 'MACD', 'BB', 'ATR', 'VWAP', 
        'ADX', 'STOCH', 'CCI', 'MFI', 'OBV', 'WILLR',
        'BBANDS', 'DEMA', 'TEMA', 'KAMA', 'MAMA', 'SAR',
        'STOCHRSI', 'AROON', 'AROONOSC', 'BOP', 'CMO'
    }
    
    # Option expiry codes
    EXPIRY_CODES = {'W0', 'W1', 'W2', 'W3', 'M0', 'M1', 'M2', 'M3'}
    
    # Strike codes (regex pattern)
    STRIKE_PATTERN = re.compile(r'(ATM|OTM|ITM)(\d+)?')
    
    def __init__(self):
        """Initialize metadata builder."""
        pass
    
    def build(
        self,
        strategy_config: Dict[str, Any],
        strategy_id: str,
        user_id: str,
        broker_connection_id: Optional[str] = None
    ) -> StrategyMetadata:
        """
        Build comprehensive strategy metadata.
        
        Args:
            strategy_config: Strategy configuration dictionary
            strategy_id: Strategy ID
            user_id: User ID
            broker_connection_id: Optional broker connection ID (for live trading)
        
        Returns:
            StrategyMetadata object with all information
        """
        log_info(f"🔨 Building metadata for strategy: {strategy_id}")
        
        # Initialize metadata
        metadata = StrategyMetadata(
            strategy_id=strategy_id,
            user_id=user_id,
            strategy_name=strategy_config.get('strategy_name', 'Unnamed'),
            config=strategy_config,
            nodes=strategy_config.get('nodes', []),
            edges=strategy_config.get('edges', [])
        )
        
        # Extract symbols and timeframes with indicators
        self._extract_symbols_and_timeframes(strategy_config, metadata)
        
        # Extract option patterns from entry nodes
        self._extract_option_patterns(strategy_config, metadata)
        
        # Extract broker mappings (if provided)
        if broker_connection_id:
            self._extract_broker_mappings(broker_connection_id, metadata)
        
        log_info(f"✅ Metadata built:")
        log_info(f"   Instrument Configs: {len(metadata.instrument_configs)}")
        log_info(f"   Unique Symbols: {len(metadata.get_symbols())}")
        log_info(f"   Unique Timeframes: {len(metadata.get_timeframes())}")
        log_info(f"   Total Indicators: {len(metadata.get_all_indicators())}")
        log_info(f"   Option Patterns: {len(metadata.option_patterns)}")
        log_info(f"   Cache Keys: {len(metadata.get_cache_keys())}")
        
        return metadata
    
    def _extract_symbols_and_timeframes(
        self,
        strategy_config: Dict[str, Any],
        metadata: StrategyMetadata
    ):
        """
        Extract instrument configs (symbol-timeframe-indicators binding) from config.
        
        Data is located in StartNode.data.tradingInstrumentConfig and supportingInstrumentConfig.
        """
        nodes = strategy_config.get('nodes', [])
        
        # Find StartNode
        start_node = None
        for node in nodes:
            if node.get('type') == 'startNode':
                start_node = node
                break
        
        if not start_node:
            log_warning("⚠️ No StartNode found in strategy")
            return
        
        node_data = start_node.get('data', {})
        
        # Process Trading Instrument (TI)
        ti_config = node_data.get('tradingInstrumentConfig', {})
        if ti_config:
            self._process_instrument_config(ti_config, metadata, 'TI')
        
        # Process Supporting Instrument (SI) if enabled
        if node_data.get('supportingInstrumentEnabled', False):
            si_config = node_data.get('supportingInstrumentConfig', {})
            if si_config:
                self._process_instrument_config(si_config, metadata, 'SI')
    
    def _process_instrument_config(
        self,
        inst_config: Dict[str, Any],
        metadata: StrategyMetadata,
        alias: str
    ):
        """
        Process a single instrument configuration (TI or SI).
        Creates InstrumentConfig objects that bind symbol-timeframe-indicators together.
        """
        symbol = inst_config.get('symbol')
        if not symbol:
            log_warning(f"⚠️ No symbol found for instrument {alias}")
            return
        
        log_debug(f"   Processing symbol: {symbol} (alias: {alias})")
        
        # Process each timeframe for this symbol
        timeframes = inst_config.get('timeframes', [])
        for tf_obj in timeframes:
            if not isinstance(tf_obj, dict):
                continue
            
            timeframe = tf_obj.get('timeframe')
            if not timeframe:
                continue
            
            # Collect indicators for this symbol-timeframe pair
            indicators = set()
            
            # Process indicators (dict format: {indicator_id: indicator_config})
            indicators_dict = tf_obj.get('indicators', {})
            for ind_id, ind_config in indicators_dict.items():
                if not isinstance(ind_config, dict):
                    continue
                
                # Supabase format uses 'indicator_name' not 'type'
                ind_type = ind_config.get('indicator_name')
                if not ind_type:
                    continue
                
                # Build params from indicator config with intelligent mapping
                ind_params = self._map_indicator_params(ind_type, ind_config)
                
                # Generate indicator key (matches DataManager format)
                ind_key = self._generate_indicator_key(ind_type, ind_params)
                
                # Create indicator metadata
                # Use ind_id (database ID like 'rsi_1764509210372') as the key
                # This will be mapped to ind_key (generated key like 'rsi(14,close)') in DataManager
                ind_meta = IndicatorMetadata(
                    name=ind_type,
                    params=ind_params,
                    key=ind_id  # Use database ID, not generated key
                )
                
                indicators.add(ind_meta)
                log_debug(f"      {symbol}:{timeframe}: {ind_key}")
            
            # Create InstrumentConfig that binds symbol-timeframe-indicators
            inst_config_obj = InstrumentConfig(
                symbol=symbol,
                timeframe=timeframe,
                indicators=indicators
            )
            
            # Add to metadata dictionary (key = "SYMBOL:TIMEFRAME")
            config_key = inst_config_obj.get_key()
            metadata.instrument_configs[config_key] = inst_config_obj
            log_debug(f"   ✅ Created config: {config_key} with {len(indicators)} indicators")
    
    def _map_indicator_params(self, ind_type: str, ind_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map indicator parameters from strategy config to ta_hybrid expected format.
        
        Different indicators expect different parameter names:
        - Most indicators (EMA, SMA, RSI, etc.) use 'length'
        - MACD uses 'fast', 'slow', 'signal'
        - Some use 'timeperiod' directly
        
        Args:
            ind_type: Indicator type (e.g., 'ema', 'rsi', 'macd')
            ind_config: Raw indicator config from strategy JSON
        
        Returns:
            Mapped parameters dictionary
        """
        ind_params = {}
        ind_type_lower = ind_type.lower()
        
        # Map 'field' to 'price_field' (universal)
        if 'field' in ind_config:
            ind_params['price_field'] = ind_config['field']
        
        # Handle timeperiod mapping based on indicator type
        if 'timeperiod' in ind_config:
            timeperiod = ind_config['timeperiod']
            
            # MACD and similar multi-period indicators
            if ind_type_lower in ['macd']:
                # For MACD, timeperiod could mean fast period
                # Check if fast/slow/signal are already provided
                if 'fast' not in ind_config:
                    ind_params['fast'] = timeperiod
                if 'slow' not in ind_config:
                    ind_params['slow'] = timeperiod * 2  # Common default
                if 'signal' not in ind_config:
                    ind_params['signal'] = 9  # Standard default
            
            # Stochastic indicators (use k, d, smooth_k)
            elif ind_type_lower in ['stoch', 'stochrsi']:
                if 'k' not in ind_config:
                    ind_params['k'] = timeperiod
            
            # ATR and volatility indicators
            elif ind_type_lower in ['atr', 'natr']:
                ind_params['length'] = timeperiod
            
            # Bollinger Bands
            elif ind_type_lower in ['bbands']:
                ind_params['length'] = timeperiod
                if 'std_dev' not in ind_config and 'nbdevup' not in ind_config:
                    ind_params['std_dev'] = 2  # Standard default
            
            # Most indicators (EMA, SMA, RSI, etc.) use 'length'
            else:
                ind_params['length'] = timeperiod
        
        # Copy other params directly (they might be specific overrides)
        excluded_keys = ['indicator_name', 'display_name', 'timeperiod', 'field']
        for key, value in ind_config.items():
            if key not in excluded_keys and key not in ind_params:
                ind_params[key] = value
        
        return ind_params
    
    def _generate_indicator_key(self, ind_type: str, params: Dict[str, Any]) -> str:
        """
        Generate indicator key matching DataManager format.
        
        Examples:
            - EMA(21, close) -> ema(21,close)
            - RSI(14) -> rsi(14)
        """
        ind_type_lower = ind_type.lower()
        
        # Extract key parameters (common ones)
        param_parts = []
        
        # Handle MACD specially (fast, slow, signal)
        if ind_type_lower == 'macd':
            if 'fast' in params:
                param_parts.append(str(params['fast']))
            if 'slow' in params:
                param_parts.append(str(params['slow']))
            if 'signal' in params:
                param_parts.append(str(params['signal']))
        else:
            # Period/Length for most indicators
            if 'period' in params:
                param_parts.append(str(params['period']))
            elif 'length' in params:
                param_parts.append(str(params['length']))
        
        # Price field (for MAs)
        if 'price_field' in params:
            param_parts.append(params['price_field'])
        elif 'field' in params:
            param_parts.append(params['field'])
        
        # Build key
        if param_parts:
            return f"{ind_type_lower}({','.join(param_parts)})"
        else:
            return ind_type_lower
    
    def _extract_option_patterns(
        self,
        strategy_config: Dict[str, Any],
        metadata: StrategyMetadata
    ):
        """
        Extract option patterns from entry nodes.
        
        Option details are in: node.data.positions[].optionDetails
        """
        nodes = strategy_config.get('nodes', [])
        
        # Get underlying symbol from StartNode (trading instrument)
        underlying_symbol = None
        for node in nodes:
            if node.get('type') == 'startNode':
                node_data = node.get('data', {})
                ti_config = node_data.get('tradingInstrumentConfig', {})
                underlying_symbol = ti_config.get('symbol')
                break
        
        if not underlying_symbol:
            log_warning("⚠️ No trading instrument symbol found - cannot extract option patterns")
            return
        
        for node in nodes:
            node_type = node.get('type')
            node_id = node.get('id')
            
            # Only process entry nodes
            if node_type != 'entryNode':
                continue
            
            node_data = node.get('data', {})
            
            # Process each position in the entry node
            # Note: instrument field is optional - positions can exist without it
            positions = node_data.get('positions', [])
            if not positions:
                continue
            for position in positions:
                if not isinstance(position, dict):
                    continue
                
                option_details = position.get('optionDetails')
                if not option_details:
                    # Not an option position, skip
                    continue
                
                # Extract option details
                expiry_code = option_details.get('expiry')
                strike_code = option_details.get('strikeType')
                option_type = option_details.get('optionType')
                
                if not expiry_code or not strike_code or not option_type:
                    log_warning(f"⚠️ Incomplete option details in node {node_id}")
                    continue
                
                # Validate
                if expiry_code not in self.EXPIRY_CODES:
                    log_warning(f"⚠️ Unknown expiry code: {expiry_code} in node {node_id}")
                    continue
                
                if option_type not in ['CE', 'PE']:
                    log_warning(f"⚠️ Invalid option type: {option_type} in node {node_id}")
                    continue
                
                # Validate strike code
                if not self.STRIKE_PATTERN.match(strike_code):
                    log_warning(f"⚠️ Invalid strike code: {strike_code} in node {node_id}")
                    continue
                
                # Create option pattern metadata
                pattern = OptionPatternMetadata(
                    node_id=node_id,
                    underlying=underlying_symbol,
                    expiry_code=expiry_code,
                    strike_code=strike_code,
                    option_type=option_type
                )
                
                metadata.option_patterns.add(pattern)
                log_debug(f"   Option pattern: {pattern.get_pattern_key()} (node: {node_id})")
    
    def _extract_broker_mappings(
        self,
        broker_connection_id: str,
        metadata: StrategyMetadata
    ):
        """
        Extract broker-specific mappings.
        
        For live trading, this will:
        1. Load broker connection details from Supabase
        2. Get symbol tokens for all symbols
        3. Pre-load option tokens for all patterns
        
        For backtesting, this is skipped.
        
        Args:
            broker_connection_id: Broker connection ID from Supabase
            metadata: StrategyMetadata to populate
        """
        log_debug(f"   Loading broker mappings for connection: {broker_connection_id}")
        
        # TODO: Implement when adding live trading support
        # This will:
        # 1. Query supabase.broker_connections table
        # 2. Get broker_name, account_id
        # 3. Load symbol master and create token mappings
        # 4. Pre-load option token mappings for all patterns
        
        # For now, create empty broker metadata
        metadata.broker = BrokerMetadata(
            broker_connection_id=broker_connection_id,
            broker_name='Unknown',
            account_id='Unknown'
        )
        
        log_debug("   ⚠️ Broker token mapping not yet implemented (placeholder created)")
