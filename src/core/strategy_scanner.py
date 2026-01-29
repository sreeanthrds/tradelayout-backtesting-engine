"""
Strategy Scanner - Extract dependencies from strategy configuration.

This module scans strategy configurations to extract:
1. Indicators used in conditions (entry, exit, alerts)
2. Option requirements from entry nodes
3. Symbols and timeframes used

Author: UniTrader Team
Created: 2024-11-12
"""

import re
from typing import Dict, List, Set, Tuple, Any
from src.utils.logger import log_info, log_warning, log_debug


class StrategyScanner:
    """
    Scan strategy configuration to extract dependencies.
    
    Extracts:
    1. Indicators used in conditions
    2. Option requirements from entry nodes
    3. Symbols and timeframes used
    """
    
    # Known indicator functions
    INDICATOR_FUNCTIONS = {
        'RSI', 'EMA', 'SMA', 'MACD', 'BB', 'ATR', 'VWAP', 
        'ADX', 'STOCH', 'CCI', 'MFI', 'OBV', 'WILLR',
        'BBANDS', 'DEMA', 'TEMA', 'KAMA', 'MAMA', 'SAR',
        'STOCHRSI', 'AROON', 'AROONOSC', 'BOP', 'CMO'
    }
    
    # Price functions (not indicators)
    PRICE_FUNCTIONS = {
        'CLOSE', 'OPEN', 'HIGH', 'LOW', 'VOLUME',
        'LTP', 'PREV_HIGH', 'PREV_LOW', 'PREV_CLOSE'
    }
    
    def __init__(self):
        """Initialize strategy scanner."""
        pass
    
    def scan_indicators(self, strategy_config: Dict[str, Any]) -> Dict[Tuple[str, str], Set[str]]:
        """
        Scan strategy for all indicators used.
        
        Args:
            strategy_config: Strategy configuration dictionary
        
        Returns:
            Dictionary mapping (symbol, timeframe) to set of indicators
            Example: {
                ('NIFTY', '1m'): {'RSI_14', 'EMA_20'},
                ('NIFTY', '5m'): {'MACD_12_26_9'}
            }
        """
        log_info("🔍 Scanning strategy for indicators...")

        indicators: Dict[Tuple[str, str], Set[str]] = {}

        # ------------------------------------------------------------------
        # 1) Metadata-driven indicator config (preferred)
        # ------------------------------------------------------------------
        metadata = strategy_config.get('metadata') or {}
        instruments_meta = metadata.get('instruments') or {}

        if instruments_meta:
            log_debug("   Using metadata-driven indicator config")

            for alias in ['TI', 'SI']:
                inst = instruments_meta.get(alias)
                if not isinstance(inst, dict):
                    continue

                symbol = inst.get('symbol')
                if not symbol:
                    continue

                timeframes_meta = inst.get('timeframes') or []
                for tf in timeframes_meta:
                    if not isinstance(tf, dict):
                        continue

                    timeframe = tf.get('timeframe')
                    if not timeframe:
                        continue

                    key = (symbol, timeframe)
                    if key not in indicators:
                        indicators[key] = set()

                    for ind in tf.get('indicators') or []:
                        if not isinstance(ind, dict):
                            continue

                        ind_key = ind.get('key')
                        if not ind_key:
                            name = ind.get('indicator_name')
                            params = ind.get('params') or {}
                            if not name:
                                continue
                            ind_key = self._build_indicator_key(name, params)

                        indicators[key].add(ind_key)

        # ------------------------------------------------------------------
        # 2) Fallback: controller/start node TI/SI configs (detected by data)
        # ------------------------------------------------------------------
        if not indicators:
            nodes = strategy_config.get('nodes') or []

            controller_node = None
            for node in nodes:
                data = node.get('data') or {}
                if 'tradingInstrumentConfig' in data or 'supportingInstrumentConfig' in data:
                    controller_node = node
                    break

            if controller_node:
                log_debug("   Using controller/start node TI/SI configs as indicator source")
                data = controller_node.get('data') or {}

                ti_cfg = data.get('tradingInstrumentConfig') or {}
                si_cfg = data.get('supportingInstrumentConfig') or {}

                self._extract_indicators_from_instrument_config(ti_cfg, indicators)
                self._extract_indicators_from_instrument_config(si_cfg, indicators)

        # Log summary
        total_indicators = sum(len(inds) for inds in indicators.values())
        log_info(f"✅ Found {total_indicators} unique indicators across {len(indicators)} symbol:timeframe combinations")

        for (symbol, timeframe), inds in indicators.items():
            log_debug(f"   {symbol}:{timeframe} → {', '.join(sorted(inds))}")

        return indicators
    
    def scan_option_requirements(self, strategy_config: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Scan entry nodes for option requirements.
        
        Args:
            strategy_config: Strategy configuration dictionary
        
        Returns:
            List of option requirements
            Example: [
                {'underlying': 'NIFTY', 'strike_type': 'ATM', 'option_type': 'CE', 'expiry_code': 'W0'},
                {'underlying': 'NIFTY', 'strike_type': 'OTM5', 'option_type': 'PE', 'expiry_code': 'W0'}
            ]
        """
        log_info("🔍 Scanning strategy for option requirements...")

        metadata = strategy_config.get('metadata') or {}
        patterns = metadata.get('option_entry_patterns') or []
        instruments_meta = metadata.get('instruments') or {}

        option_requirements: List[Dict[str, str]] = []

        # First try metadata patterns (if they exist)
        for p in patterns:
            if not isinstance(p, dict):
                continue

            pattern = p.get('pattern')
            if not pattern:
                continue

            underlying_alias = p.get('underlying_alias', 'TI')
            inst_meta = instruments_meta.get(underlying_alias) or {}
            underlying_symbol = inst_meta.get('symbol')
            entry_node_id = p.get('entry_node_id')
            vpi = p.get('vpi')

            option_requirements.append(
                {
                    'pattern': pattern,
                    'underlying_alias': underlying_alias,
                    'underlying_symbol': underlying_symbol,
                    'entry_node_id': entry_node_id,
                    'vpi': vpi,
                }
            )

            log_debug(
                f"      → Option requirement pattern: {pattern} "
                f"(alias={underlying_alias}, symbol={underlying_symbol}, entry={entry_node_id}, vpi={vpi})"
            )

        # If no metadata patterns, scan entry nodes directly
        if not option_requirements:
            nodes = strategy_config.get('nodes', [])
            for node in nodes:
                if node.get('type') != 'entryNode':
                    continue
                
                entry_id = node.get('id')
                data = node.get('data', {})
                positions = data.get('positions', [])
                
                for pos in positions:
                    opt_details = pos.get('optionDetails', {})
                    if not opt_details:
                        continue
                    
                    expiry = opt_details.get('expiry')
                    strike_type = opt_details.get('strikeType')
                    option_type = opt_details.get('optionType')
                    
                    if expiry and strike_type and option_type:
                        # Build pattern: TI:W0:ATM:CE
                        underlying_alias = 'TI'  # Default to TI
                        pattern = f"{underlying_alias}:{expiry}:{strike_type}:{option_type}"
                        
                        # Try to get underlying symbol from metadata or infer from indicators
                        inst_meta = instruments_meta.get(underlying_alias) or {}
                        underlying_symbol = inst_meta.get('symbol')
                        
                        # If not in metadata, infer from strategy's trading instrument
                        if not underlying_symbol:
                            # Check if we have indicator data to infer the symbol
                            raw_indicators = self.scan_indicators(strategy_config)
                            if raw_indicators:
                                # Use the first symbol found in indicators
                                underlying_symbol = list(raw_indicators.keys())[0][0]
                            else:
                                underlying_symbol = 'NIFTY'  # Final fallback
                        
                        option_requirements.append({
                            'pattern': pattern,
                            'underlying_alias': underlying_alias,
                            'underlying_symbol': underlying_symbol,
                            'entry_node_id': entry_id,
                            'vpi': pos.get('vpi'),
                            'expiry': expiry,
                            'strike_type': strike_type,
                            'option_type': option_type
                        })
                        
                        log_debug(
                            f"      → Option from entry node {entry_id}: {pattern}"
                        )

        log_info(f"✅ Found {len(option_requirements)} option requirements")

        return option_requirements
    
    def scan_symbols_and_timeframes(self, strategy_config: Dict[str, Any]) -> Dict[str, Set[str]]:
        """
        Scan strategy for all symbols and timeframes used.
        
        Args:
            strategy_config: Strategy configuration dictionary
        
        Returns:
            Dictionary mapping symbol to set of timeframes
            Example: {
                'NIFTY': {'1m', '5m'},
                'BANKNIFTY': {'1m'}
            }
        """
        symbols_timeframes = {}
        
        # Get from indicators
        indicators = self.scan_indicators(strategy_config)
        for (symbol, timeframe), _ in indicators.items():
            if symbol not in symbols_timeframes:
                symbols_timeframes[symbol] = set()
            symbols_timeframes[symbol].add(timeframe)
        
        return symbols_timeframes
    
    def scan_multiple_strategies(self, strategy_ids: List[str]) -> Dict[str, Any]:
        """
        Scan multiple strategies and consolidate their requirements.
        
        Args:
            strategy_ids: List of strategy IDs to scan
        
        Returns:
            Consolidated requirements in the format:
            {
                'instruments': ['NIFTY', 'BANKNIFTY', ...],
                'timeframes': ['NIFTY:1m', 'NIFTY:3m', 'BANKNIFTY:1m', ...],
                'indicators': {
                    'NIFTY': {
                        '1m': [{'name': 'EMA', 'params': {'length': 21}}, ...],
                        '3m': [{'name': 'RSI', 'params': {'length': 14}}, ...]
                    },
                    'BANKNIFTY': { ... }
                },
                'options': {
                    'NIFTY': ['TI:W0:ATM:CE', 'TI:W0:ATM:PE', ...],
                    'BANKNIFTY': [...]
                },
                'strategies': [('user_id', 'strategy_id'), ...]
            }
        """
        from src.adapters.supabase_adapter import SupabaseStrategyAdapter
        
        log_info(f"📋 Scanning {len(strategy_ids)} strategies for consolidated requirements...")
        
        adapter = SupabaseStrategyAdapter()
        
        all_instruments = set()
        all_timeframes = set()  # Store as "SYMBOL:TF" pairs
        all_indicators = {}  # {symbol: {timeframe: [indicators]}}
        all_option_patterns = {}  # {symbol: [patterns]}
        user_strategies = []  # [(user_id, strategy_id), ...]
        
        for strategy_id in strategy_ids:
            try:
                log_info(f"🔍 Scanning strategy: {strategy_id}")
                
                # Get strategy from database (with user_id)
                raw_config = adapter.get_strategy(strategy_id=strategy_id, user_id=None)
                user_id = raw_config.get('user_id')
                
                if not user_id:
                    log_warning(f"  ⚠️  Could not read user_id from strategy {strategy_id}, skipping")
                    continue
                
                log_info(f"  👤 User ID: {user_id}")
                user_strategies.append((user_id, strategy_id))
                
                # Scan this strategy
                scan_result = self.scan_strategy(raw_config)
                
                # Extract instruments from indicators
                for symbol in scan_result.get('indicators', {}).keys():
                    all_instruments.add(symbol)
                
                # Extract from option requirements
                for symbol in scan_result.get('option_requirements', {}).keys():
                    all_instruments.add(symbol)
                
                # Collect timeframes as "SYMBOL:TF" pairs
                indicators = scan_result.get('indicators', {})
                for symbol, tf_dict in indicators.items():
                    for tf in tf_dict.keys():
                        all_timeframes.add(f"{symbol}:{tf}")
                        
                        # Merge indicators
                        if symbol not in all_indicators:
                            all_indicators[symbol] = {}
                        if tf not in all_indicators[symbol]:
                            all_indicators[symbol][tf] = []
                        all_indicators[symbol][tf].extend(tf_dict[tf])
                
                # Collect option patterns
                option_reqs = scan_result.get('option_requirements', {})
                for symbol, patterns in option_reqs.items():
                    if symbol not in all_option_patterns:
                        all_option_patterns[symbol] = []
                    all_option_patterns[symbol].extend(patterns)
                
                log_info(f"  ✅ Scanned successfully")
                
            except Exception as e:
                log_warning(f"  ❌ Error scanning strategy {strategy_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Build final consolidated result
        result = {
            'instruments': sorted(list(all_instruments)),
            'timeframes': sorted(list(all_timeframes)),
            'indicators': all_indicators,
            'options': all_option_patterns,
            'strategies': user_strategies
        }
        
        log_info(f"✅ Consolidated scan complete:")
        log_info(f"   Total Strategies: {len(user_strategies)}")
        log_info(f"   Instruments: {result['instruments']}")
        log_info(f"   Timeframes: {result['timeframes']}")
        log_info(f"   Indicators: {len(all_indicators)} symbols")
        log_info(f"   Option Requirements: {len(all_option_patterns)} symbols")
        
        return result
    
    def scan_each(self, strategy_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Scan multiple strategies and return separate metadata for each.
        
        Args:
            strategy_ids: List of strategy IDs to scan
            
        Returns:
            Dictionary with strategy_id as key and metadata as value
            Example:
            {
                'strategy1_id': {
                    'user_id': 'user123',
                    'name': 'My Strategy',
                    'instruments': ['NIFTY'],
                    'timeframes': ['NIFTY:1m', 'NIFTY:3m'],
                    'indicators': {
                        'NIFTY': {
                            '1m': [{'name': 'EMA', 'params': {...}}]
                        }
                    },
                    'options': {
                        'NIFTY': ['TI:W0:ATM:CE']
                    }
                },
                'strategy2_id': {...}
            }
        """
        from src.adapters.supabase_adapter import SupabaseStrategyAdapter
        
        log_info(f"📋 Scanning {len(strategy_ids)} strategies individually...")
        
        adapter = SupabaseStrategyAdapter()
        result = {}
        
        for strategy_id in strategy_ids:
            try:
                log_info(f"🔍 Scanning strategy: {strategy_id}")
                
                # Get strategy from database
                raw_config = adapter.get_strategy(strategy_id=strategy_id, user_id=None)
                user_id = raw_config.get('user_id')
                strategy_name = raw_config.get('name', 'Unknown')
                
                if not user_id:
                    log_warning(f"  ⚠️  Could not read user_id from strategy {strategy_id}, skipping")
                    continue
                
                log_info(f"  👤 User ID: {user_id}")
                log_info(f"  📝 Strategy Name: {strategy_name}")
                
                # Scan this strategy
                scan_result = self.scan_strategy(raw_config)
                
                # Get instruments from scan result
                instruments = set()
                for symbol in scan_result.get('indicators', {}).keys():
                    instruments.add(symbol)
                for symbol in scan_result.get('option_requirements', {}).keys():
                    instruments.add(symbol)
                
                # Build timeframes with symbol prefix (SYMBOL:TF format)
                timeframes = set()
                for symbol, tf_dict in scan_result.get('indicators', {}).items():
                    for tf in tf_dict.keys():
                        timeframes.add(f"{symbol}:{tf}")
                
                # Build metadata for this strategy
                result[strategy_id] = {
                    'user_id': user_id,
                    'name': strategy_name,
                    'instruments': sorted(list(instruments)),
                    'timeframes': sorted(list(timeframes)),
                    'indicators': scan_result.get('indicators', {}),
                    'options': scan_result.get('option_requirements', {})
                }
                
                log_info(f"  ✅ Scanned successfully")
                
            except Exception as e:
                log_warning(f"  ❌ Error scanning strategy {strategy_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        log_info(f"📋 Individual scan complete: {len(result)} strategies")
        
        return result
    
    def scan_strategy(self, strategy_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive strategy scan that extracts all requirements.
        
        Args:
            strategy_config: Strategy configuration dictionary
        
        Returns:
            Dictionary containing:
            {
                'timeframes': ['1m', '5m', ...],
                'indicators': {
                    'NIFTY': {
                        '1m': [{'name': 'RSI', 'params': {'length': 14}}, ...],
                        '5m': [...]
                    }
                },
                'option_requirements': {
                    'NIFTY': ['TI:W0:ATM:CE', 'TI:W0:ATM:PE', ...]
                }
            }
        """
        log_info("📋 Comprehensive strategy scan starting...")
        
        # Get raw indicator scan results {(symbol, tf): {'RSI_14', 'EMA_20'}}
        raw_indicators = self.scan_indicators(strategy_config)
        
        # Get option requirements
        option_reqs = self.scan_option_requirements(strategy_config)
        
        # Convert indicators to desired format
        all_timeframes = set()
        indicators_by_symbol = {}
        
        for (symbol, timeframe), indicator_keys in raw_indicators.items():
            all_timeframes.add(timeframe)
            
            if symbol not in indicators_by_symbol:
                indicators_by_symbol[symbol] = {}
            
            if timeframe not in indicators_by_symbol[symbol]:
                indicators_by_symbol[symbol][timeframe] = []
            
            # Parse each indicator key
            # Format: 'MACD:fast=12:signal=9:slow=26' or 'RSI:length=14:price_field=close'
            for ind_key in indicator_keys:
                # Split by ':' to separate name and params
                parts = ind_key.split(':')
                if len(parts) >= 1:
                    name = parts[0]
                    params = {}
                    
                    # Parse remaining parts as key=value pairs
                    for i in range(1, len(parts)):
                        if '=' in parts[i]:
                            key, value = parts[i].split('=', 1)
                            # Try to convert to int if possible
                            try:
                                params[key] = int(value)
                            except ValueError:
                                params[key] = value
                        else:
                            # If no '=', use as generic param
                            params[f'param{i}'] = parts[i]
                    
                    indicators_by_symbol[symbol][timeframe].append({
                        'name': name,
                        'params': params
                    })
        
        # Convert option requirements to per-symbol format
        options_by_symbol = {}
        for opt_req in option_reqs:
            pattern = opt_req.get('pattern', '')
            if pattern:
                # Use underlying_symbol if available, otherwise map from pattern
                actual_symbol = opt_req.get('underlying_symbol')
                
                if not actual_symbol:
                    # Fallback: Extract underlying from pattern (e.g., 'TI:W0:ATM:CE' → 'TI')
                    underlying = pattern.split(':')[0] if ':' in pattern else 'TI'
                    
                    # Map TI/SI to actual symbol if available
                    metadata = strategy_config.get('metadata', {})
                    instruments = metadata.get('instruments', {})
                    
                    actual_symbol = 'NIFTY'  # Default
                    if underlying in instruments:
                        actual_symbol = instruments[underlying].get('symbol', actual_symbol)
                
                if actual_symbol not in options_by_symbol:
                    options_by_symbol[actual_symbol] = []
                
                options_by_symbol[actual_symbol].append(pattern)
        
        result = {
            'timeframes': sorted(all_timeframes),
            'indicators': indicators_by_symbol,
            'option_requirements': options_by_symbol
        }
        
        log_info(f"✅ Strategy scan complete:")
        log_info(f"   Timeframes: {result['timeframes']}")
        log_info(f"   Instruments with indicators: {list(indicators_by_symbol.keys())}")
        log_info(f"   Instruments with options: {list(options_by_symbol.keys())}")
        
        return result
    
    def _extract_indicators_from_expression(self, expression: str) -> Dict[Tuple[str, str], Set[str]]:
        """
        Extract indicators from condition expression.
        
        Args:
            expression: Condition expression string
        
        Returns:
            Dictionary mapping (symbol, timeframe) to set of indicators
        
        Examples:
            "RSI(TI, 1m, 14) > 70" → {('TI', '1m'): {'RSI_14'}}
            "EMA(TI, 5m, 20) > CLOSE(TI, 5m)" → {('TI', '5m'): {'EMA_20'}}
            "MACD(TI, 1m, 12, 26, 9) > 0" → {('TI', '1m'): {'MACD_12_26_9'}}
        """
        indicators = {}
        
        if not expression:
            return indicators
        
        # Regex pattern to match function calls
        # Pattern: FUNCTION_NAME(symbol, timeframe, params...)
        pattern = r'(\w+)\(([^,]+),\s*["\']?([^,\)]+)["\']?(?:,\s*([^)]+))?\)'
        
        matches = re.findall(pattern, expression)
        
        for match in matches:
            func_name = match[0].upper()
            symbol = match[1].strip()
            timeframe = match[2].strip().strip("'\"")
            params = match[3].strip() if len(match) > 3 and match[3] else ''
            
            # Check if it's an indicator (not a price function)
            if func_name in self.INDICATOR_FUNCTIONS:
                key = (symbol, timeframe)
                if key not in indicators:
                    indicators[key] = set()
                
                # Create indicator key
                if params:
                    # Clean up params: remove spaces, quotes
                    clean_params = params.replace(' ', '').replace("'", "").replace('"', '')
                    indicator_key = f"{func_name}_{clean_params}"
                else:
                    indicator_key = func_name
                
                indicators[key].add(indicator_key)
        
        return indicators

    def _build_indicator_key(self, name: str, params: Dict[str, Any]) -> str:
        """Build a unified indicator key from name and parameter dict.

        Example output: "EMA:timeperiod=21".
        Non-parameter/meta fields like indicator_name/display_name are ignored.
        """
        indicator_name = str(name).upper()

        if not params:
            return indicator_name

        # Exclude meta keys that aren't part of TA params
        excluded_keys = {"indicator_name", "display_name", "id"}

        parts = []
        for key in sorted(params.keys()):
            if key in excluded_keys:
                continue
            value = params[key]
            parts.append(f"{key}={value}")

        if not parts:
            return indicator_name

        return f"{indicator_name}:{':'.join(parts)}"

    def build_metadata_if_missing(self, strategy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure strategy_config has a metadata block.

        If metadata exists but lacks instruments/option_entry_patterns, this will
        augment it while preserving existing fields (e.g. created/lastModified).
        If metadata is missing entirely, it will be created.
        """
        metadata = strategy_config.get("metadata") or {}

        nodes = strategy_config.get("nodes") or []

        controller_node = None
        for node in nodes:
            if node.get("id") == "strategy-controller":
                controller_node = node
                break

        instruments_meta: Dict[str, Any] = {}

        if controller_node:
            data = controller_node.get("data") or {}
            ti_cfg = data.get("tradingInstrumentConfig") or {}
            si_cfg = data.get("supportingInstrumentConfig") or {}

            # Trading Instrument → TI
            if ti_cfg.get("symbol"):
                instruments_meta["TI"] = self._build_instrument_meta_from_config(ti_cfg)

            # Supporting Instrument → SI
            if si_cfg.get("symbol"):
                instruments_meta["SI"] = self._build_instrument_meta_from_config(si_cfg)

        option_entry_patterns = self._build_option_entry_patterns_from_nodes(nodes)

        # Merge into existing metadata (do not drop created/lastModified, etc.)
        metadata.setdefault("instruments", instruments_meta)
        # If instruments already present but empty, overwrite with freshly built
        if not metadata["instruments"] and instruments_meta:
            metadata["instruments"] = instruments_meta

        metadata.setdefault("option_entry_patterns", option_entry_patterns)
        if not metadata["option_entry_patterns"] and option_entry_patterns:
            metadata["option_entry_patterns"] = option_entry_patterns

        strategy_config["metadata"] = metadata

        return strategy_config

    def _extract_indicators_from_instrument_config(
        self,
        instrument_config: Dict[str, Any],
        target: Dict[Tuple[str, str], Set[str]],
    ) -> None:
        """Extract indicators from a single instrument config (TI or SI).

        Expected structure:
            {
                "symbol": "NIFTY",
                "timeframes": [
                    {
                        "timeframe": "1m",
                        "indicators": {
                            "EMA_xxx": {
                                "indicator_name": "EMA",
                                "timeperiod": 21,
                                ...
                            }
                        }
                    },
                    ...
                ]
            }
        """
        if not instrument_config:
            return

        symbol = instrument_config.get("symbol") if isinstance(instrument_config, dict) else None
        if not symbol:
            return

        timeframes = instrument_config.get("timeframes") or []
        for tf in timeframes:
            if not isinstance(tf, dict):
                continue

            timeframe = tf.get("timeframe")
            if not timeframe:
                continue

            indicators_cfg = tf.get("indicators") or {}
            if not isinstance(indicators_cfg, dict) or not indicators_cfg:
                continue

            key = (symbol, timeframe)
            if key not in target:
                target[key] = set()

            for ind_cfg in indicators_cfg.values():
                if not isinstance(ind_cfg, dict):
                    continue

                name = ind_cfg.get("indicator_name")
                if not name:
                    continue

                indicator_key = self._build_indicator_key(name, ind_cfg)
                target[key].add(indicator_key)

    def _build_instrument_meta_from_config(self, inst_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Convert tradingInstrumentConfig/supportingInstrumentConfig into metadata shape."""
        symbol = inst_cfg.get("symbol")
        inst_type = inst_cfg.get("type")

        timeframes_meta: List[Dict[str, Any]] = []

        for tf in inst_cfg.get("timeframes") or []:
            if not isinstance(tf, Dict):
                continue

            timeframe = tf.get("timeframe")
            if not timeframe:
                continue

            indicators_meta: List[Dict[str, Any]] = []
            indicators_cfg = tf.get("indicators") or {}

            for ind_cfg in indicators_cfg.values():
                if not isinstance(ind_cfg, Dict):
                    continue

                name = ind_cfg.get("indicator_name")
                if not name:
                    continue

                params = {
                    k: v
                    for k, v in ind_cfg.items()
                    if k not in ("indicator_name", "display_name", "id")
                }

                key = self._build_indicator_key(name, params)

                indicators_meta.append(
                    {
                        "key": key,
                        "indicator_name": name,
                        "params": params,
                    }
                )

            timeframes_meta.append(
                {
                    "id": tf.get("id"),
                    "timeframe": timeframe,
                    "indicators": indicators_meta,
                }
            )

        return {
            "symbol": symbol,
            "type": inst_type,
            "timeframes": timeframes_meta,
        }

    def _build_option_entry_patterns_from_nodes(
        self, nodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Build metadata.option_entry_patterns from entry nodes using TI as underlying.

        Uses entryNode.data.positions[*].optionDetails and ignores entryNode.data.instrument.
        """
        patterns: List[Dict[str, Any]] = []

        for node in nodes:
            if node.get("type") != "entryNode":
                continue

            entry_id = node.get("id")
            data = node.get("data") or {}
            positions = data.get("positions") or []

            for pos in positions:
                if not isinstance(pos, Dict):
                    continue

                opt = pos.get("optionDetails") or {}
                expiry = opt.get("expiry")
                strike_type = opt.get("strikeType")
                option_type = opt.get("optionType")

                if not (expiry and strike_type and option_type):
                    continue

                underlying_alias = "TI"
                pattern = f"{underlying_alias}:{expiry}:{strike_type}:{option_type}"

                patterns.append(
                    {
                        "entry_node_id": entry_id,
                        "vpi": pos.get("vpi"),
                        "underlying_alias": underlying_alias,
                        "pattern": pattern,
                    }
                )

        return patterns
    
    def _merge_indicators(self, target: Dict[Tuple[str, str], Set[str]], source: Dict[Tuple[str, str], Set[str]]):
        """
        Merge source indicators into target.
        
        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from
        """
        for key, indicators in source.items():
            if key not in target:
                target[key] = set()
            target[key].update(indicators)
    
    def _is_option_instrument(self, trading_instrument: str) -> bool:
        """
        Check if trading instrument is an option.
        
        Args:
            trading_instrument: Trading instrument string
        
        Returns:
            True if option, False otherwise
        
        Examples:
            'NIFTY:W0:ATM:CE' → True
            'NIFTY:W0:OTM5:PE' → True
            'NIFTY' → False
            'NIFTY:FUT' → False
        """
        if not trading_instrument:
            return False
        
        # Check for explicit option marker
        if ':OPT:' in trading_instrument:
            return True
        
        # Check for dynamic option codes
        option_codes = ['ATM', 'OTM', 'ITM']
        for code in option_codes:
            if code in trading_instrument:
                return True
        
        return False
    
    def _parse_option_requirement(self, trading_instrument: str) -> Dict[str, str]:
        """
        Parse option requirement from trading instrument.
        
        Args:
            trading_instrument: Trading instrument string
        
        Returns:
            Option requirement dictionary or None if invalid
        
        Examples:
            'NIFTY:W0:ATM:CE' → {
                'underlying': 'NIFTY',
                'expiry_code': 'W0',
                'strike_type': 'ATM',
                'option_type': 'CE'
            }
            'NIFTY:W0:OTM5:PE' → {
                'underlying': 'NIFTY',
                'expiry_code': 'W0',
                'strike_type': 'OTM5',
                'option_type': 'PE'
            }
        """
        try:
            parts = trading_instrument.split(':')
            
            # Expected format: UNDERLYING:EXPIRY:STRIKE_TYPE:OPTION_TYPE
            if len(parts) >= 4:
                return {
                    'underlying': parts[0],
                    'expiry_code': parts[1],
                    'strike_type': parts[2],  # ATM, OTM5, ITM3, etc.
                    'option_type': parts[3]   # CE, PE
                }
            else:
                log_warning(f"⚠️ Invalid option format: {trading_instrument}")
                return None
        
        except Exception as e:
            log_warning(f"⚠️ Failed to parse option requirement: {trading_instrument} - {e}")
            return None


# Convenience functions
def scan_strategy_indicators(strategy_config: Dict[str, Any]) -> Dict[Tuple[str, str], Set[str]]:
    """
    Convenience function to scan strategy for indicators.
    
    Args:
        strategy_config: Strategy configuration dictionary
    
    Returns:
        Dictionary mapping (symbol, timeframe) to set of indicators
    """
    scanner = StrategyScanner()
    return scanner.scan_indicators(strategy_config)


def scan_strategy_options(strategy_config: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Convenience function to scan strategy for option requirements.
    
    Args:
        strategy_config: Strategy configuration dictionary
    
    Returns:
        List of option requirements
    """
    scanner = StrategyScanner()
    return scanner.scan_option_requirements(strategy_config)
