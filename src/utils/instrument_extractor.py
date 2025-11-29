"""
Instrument Extractor
Extracts instruments from strategy config and fetches tokens from broker
"""

from typing import Dict, List, Any
from src.utils.logger import log_info, log_warning, log_error


def extract_and_fetch_instruments(
    strategy_config: Dict[str, Any],
    broker_adapter
) -> List[Dict[str, Any]]:
    """
    Extract instruments from strategy config and fetch tokens from broker
    
    Args:
        strategy_config: Strategy configuration JSON
        broker_adapter: Broker adapter to fetch tokens
        
    Returns:
        List of instrument dicts with: symbol, token, exchange, type, timeframes
    """
    instruments = []
    
    # Find startNode
    start_node = None
    for node in strategy_config.get('nodes', []):
        if node.get('type') == 'startNode':
            start_node = node.get('data', {})
            break
    
    if not start_node:
        error_msg = "startNode not found in strategy config"
        log_error(f"[InstrumentExtractor] {error_msg}")
        from src.utils.error_handler import handle_exception
        handle_exception(
            ValueError(error_msg),
            "instrument_extractor_no_start_node",
            {
                "strategy_id": strategy_config.get('id'),
                "strategy_name": strategy_config.get('name'),
                "nodes_count": len(strategy_config.get('nodes', []))
            },
            is_critical=True,
            continue_execution=False
        )
        return instruments
    
    # Extract Trading Instrument (TI)
    tic = start_node.get('tradingInstrumentConfig', {})
    if tic:
        base_symbol = tic.get('symbol')
        # Check exchange at both levels (UI saves at data.exchange, but config may have it at tradingInstrumentConfig.exchange)
        exchange = tic.get('exchange') or start_node.get('exchange', 'NSE')  # Default to NSE
        
        # Check if TI is futures or spot
        ti_type = tic.get('type', 'stock')  # Default to stock/spot
        ti_instrument_config = start_node.get('tradingInstrument', {})
        if ti_instrument_config.get('type') == 'futures':
            ti_type = 'futures'
        
        # For futures, construct dynamic symbol with expiry
        if ti_type == 'futures':
            # Get expiry from config (default to M0 - current month)
            expiry = tic.get('expiry', 'M0')
            symbol = f"{base_symbol}:{expiry}:FUT"
            log_info(f"[InstrumentExtractor] TI is FUTURES: {symbol}")
        else:
            # Spot/stock - use base symbol
            symbol = base_symbol
        
        # Extract timeframes
        timeframes = []
        for tf in tic.get('timeframes', []):
            tf_id = tf.get('timeframe') or tf.get('id')
            if tf_id:
                timeframes.append(tf_id)
        
        if symbol and timeframes:
            # Check if token is already provided in config
            provided_token = tic.get('symbolToken')
            
            if provided_token:
                # Use provided token
                instruments.append({
                    'symbol': symbol,
                    'token': provided_token,
                    'exchange': exchange,
                    'type': 'TI',
                    'timeframes': timeframes,
                    'is_futures': ti_type == 'futures'
                })
                
                log_info(f"[InstrumentExtractor] TI: {symbol} (token: {provided_token}, exchange: {exchange}) [PROVIDED]")
            else:
                # For futures, we need to resolve the dynamic symbol first
                token = None
                resolved_symbol = symbol
                
                if ti_type == 'futures':
                    # For futures, fetch instruments from AngelOne scrip master
                    log_info(f"[InstrumentExtractor] Futures detected: {symbol}")
                    
                    try:
                        from datetime import datetime
                        from src.data.fo_dynamic_resolver import FODynamicResolver
                        from src.data.instrument_ltp_store import InstrumentLTPStore
                        import requests
                        import pandas as pd
                        
                        # Fetch instruments from AngelOne scrip master URL
                        log_info(f"[InstrumentExtractor] Fetching instruments from AngelOne scrip master...")
                        url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
                        response = requests.get(url, timeout=10)
                        instruments_df = pd.DataFrame(response.json())
                        instruments_df.columns = [c.lower() for c in instruments_df.columns]
                        log_info(f"[InstrumentExtractor] Loaded {len(instruments_df)} instruments")
                        
                        # Create instrument store from DataFrame
                        inst_store = InstrumentLTPStore()
                        instruments_list = instruments_df.to_dict('records')
                        inst_store.load_instrument_master(instruments_list)
                        
                        resolver = FODynamicResolver(inst_store)
                        # Resolve to universal format: NATURALGAS:2025-10-28:FUT
                        resolved_universal = resolver.resolve(symbol, {}, datetime.now().date())
                        log_info(f"[InstrumentExtractor] Resolved: {symbol} → {resolved_universal}")
                        
                        # Convert to AngelOne format: NATURALGAS28OCT25FUT
                        if hasattr(broker_adapter, '_convert_universal_to_angelone'):
                            angelone_symbol = broker_adapter._convert_universal_to_angelone(resolved_universal)
                            log_info(f"[InstrumentExtractor] AngelOne symbol: {angelone_symbol}")
                            
                            # Search for the actual futures contract in instruments
                            matches = instruments_df[instruments_df['symbol'] == angelone_symbol]
                            
                            if not matches.empty:
                                inst_row = matches.iloc[0]
                                token = str(inst_row.get('token', ''))
                                actual_exchange = inst_row.get('exch_seg', exchange)
                                
                                instruments.append({
                                    'symbol': angelone_symbol,  # Use actual futures contract for subscription
                                    'token': token,
                                    'exchange': actual_exchange,
                                    'type': 'TI',
                                    'timeframes': timeframes,
                                    'is_futures': True,
                                    'futures_symbol': symbol,
                                    'base_symbol': base_symbol,
                                    'resolved_symbol': resolved_universal
                                })
                                
                                log_info(f"[InstrumentExtractor] TI FUTURES: {angelone_symbol} (token: {token}, exchange: {actual_exchange})")
                            else:
                                log_warning(f"[InstrumentExtractor] Could not find futures contract: {angelone_symbol}")
                        else:
                            log_warning(f"[InstrumentExtractor] _convert_universal_to_angelone method not available")
                    except Exception as e:
                        log_warning(f"[InstrumentExtractor] Could not resolve futures: {e}")
                        import traceback
                        log_warning(f"[InstrumentExtractor] Traceback: {traceback.format_exc()}")
                else:
                    # Try to get spot index token using DataFrame filter
                    if hasattr(broker_adapter, 'instrument_finder'):
                        token = broker_adapter.instrument_finder.get_spot_index_token(symbol, exchange)
                    
                    if token:
                        # Found spot index token
                        instruments.append({
                            'symbol': symbol,
                            'token': token,
                            'exchange': exchange,
                            'type': 'TI',
                            'timeframes': timeframes,
                            'is_futures': False
                        })
                        
                        log_info(f"[InstrumentExtractor] TI: {symbol} (token: {token}, exchange: {exchange}) [SPOT INDEX]")
                    else:
                        # Fallback: search instrument
                        instrument_data = broker_adapter.search_instrument(symbol, exchange)
                        
                        if instrument_data:
                            token = instrument_data.get('symboltoken')
                            actual_exchange = instrument_data.get('exchange', exchange)
                            
                            instruments.append({
                                'symbol': symbol,
                                'token': token,
                                'exchange': actual_exchange,
                                'type': 'TI',
                                'timeframes': timeframes,
                                'is_futures': False
                            })
                            
                            log_info(f"[InstrumentExtractor] TI: {symbol} (token: {token}, exchange: {actual_exchange})")
                        else:
                            error_msg = f"Could not find TI instrument: {symbol}"
                            log_error(f"[InstrumentExtractor] {error_msg}")
                            from src.utils.error_handler import handle_exception
                            handle_exception(
                                ValueError(error_msg),
                                "instrument_extractor_ti_not_found",
                                {
                                    "symbol": symbol,
                                    "exchange": exchange,
                                    "timeframes": timeframes,
                                    "has_instrument_finder": hasattr(broker_adapter, 'instrument_finder')
                                },
                                is_critical=True,
                                continue_execution=False
                            )
    
    # Extract Supporting Instrument (SI)
    sic = start_node.get('supportingInstrumentConfig', {})
    if sic and start_node.get('supportingInstrumentEnabled', False):
        symbol = sic.get('symbol')
        # Check exchange at both levels (same as TI)
        exchange = sic.get('exchange') or start_node.get('exchange', 'NSE')
        
        # Extract timeframes
        timeframes = []
        for tf in sic.get('timeframes', []):
            tf_id = tf.get('timeframe') or tf.get('id')
            if tf_id:
                timeframes.append(tf_id)
        
        if symbol and timeframes:
            # Try to get spot index token using DataFrame filter
            token = None
            if hasattr(broker_adapter, 'instrument_finder'):
                token = broker_adapter.instrument_finder.get_spot_index_token(symbol, exchange)
            
            if token:
                # Found spot index token
                instruments.append({
                    'symbol': symbol,
                    'token': token,
                    'exchange': exchange,
                    'type': 'SI',
                    'timeframes': timeframes
                })
                
                log_info(f"[InstrumentExtractor] SI: {symbol} (token: {token}, exchange: {exchange}) [SPOT INDEX]")
            else:
                # Fallback: search instrument
                instrument_data = broker_adapter.search_instrument(symbol, exchange)
                
                if instrument_data:
                    token = instrument_data.get('symboltoken')
                    actual_exchange = instrument_data.get('exchange', exchange)
                    
                    instruments.append({
                        'symbol': symbol,
                        'token': token,
                        'exchange': actual_exchange,
                        'type': 'SI',
                        'timeframes': timeframes
                    })
                    
                    log_info(f"[InstrumentExtractor] SI: {symbol} (token: {token}, exchange: {actual_exchange})")
                else:
                    error_msg = f"Could not find SI instrument: {symbol}"
                    log_error(f"[InstrumentExtractor] {error_msg}")
                    from src.utils.error_handler import handle_exception
                    handle_exception(
                        ValueError(error_msg),
                        "instrument_extractor_si_not_found",
                        {
                            "symbol": symbol,
                            "exchange": exchange,
                            "timeframes": timeframes,
                            "has_instrument_finder": hasattr(broker_adapter, 'instrument_finder')
                        },
                        is_critical=True,
                        continue_execution=False
                    )
    
    log_info(f"[InstrumentExtractor] Extracted {len(instruments)} instruments")
    
    return instruments


def get_subscription_list(instruments: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Convert instruments list to WebSocket subscription format
    
    Args:
        instruments: List of instrument dicts
        
    Returns:
        List of subscription dicts with exchange and token
    """
    subscription_list = []
    
    for instrument in instruments:
        subscription_list.append({
            'exchange': instrument['exchange'],
            'token': instrument['token']
        })
    
    return subscription_list
