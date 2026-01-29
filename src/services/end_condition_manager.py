"""
End Condition Manager Service
==============================

Service for evaluating strategy-level end conditions.

Responsibilities:
- Evaluate time-based exit conditions (market close, specific time)
- Evaluate performance-based exit conditions (daily P&L targets/limits)
- Evaluate alert notification conditions
- Check if all nodes are inactive

Does NOT execute exits - only evaluates conditions!
Exit execution is handled by StartNode._trigger_exit_node()
"""

import traceback
from datetime import datetime, time
from typing import Dict, Any, Tuple, Optional

from src.config.market_timings import get_session_times, detect_exchange_from_symbol
from src.utils.logger import log_debug, log_info, log_warning, log_error


class EndConditionManager:
    """
    Service for evaluating strategy-level end conditions.
    
    This service is stateless and only evaluates conditions.
    It does NOT execute exits or modify strategy state.
    """
    
    def __init__(self):
        """Initialize end condition manager."""
        pass
    
    def check_end_conditions(
        self,
        context: Dict[str, Any],
        end_conditions: Dict[str, Any],
        current_timestamp: datetime,
        current_tick: Dict[str, Any],
        symbol: str = None
    ) -> Dict[str, Any]:
        """
        Check all end conditions and return result.
        
        Args:
            context: Execution context
            end_conditions: End conditions config from strategy
            current_timestamp: Current timestamp
            current_tick: Current tick data
            symbol: Trading symbol (for exchange detection)
            
        Returns:
            {
                'should_end': bool,
                'reason': str,
                'condition_type': str
            }
        """
        # If already ended, don't check again
        if context.get('strategy_ended', False):
            return {'should_end': True, 'reason': 'Strategy already ended'}
        
        if current_tick is None or current_timestamp is None:
            return {'should_end': False, 'reason': 'No tick data available'}
        
        if not end_conditions:
            return {'should_end': False, 'reason': 'No end conditions configured'}
        
        # Evaluate each end condition based on its type
        for condition_name, condition_config in end_conditions.items():
            try:
                result = {'satisfied': False, 'should_end': False}
                
                # Time-based exit
                if condition_name == 'timeBasedExit':
                    result = self.evaluate_time_based_exit(
                        condition_config,
                        current_timestamp,
                        symbol
                    )
                    if result and result.get('satisfied', False):
                        return {
                            'should_end': True,
                            'reason': 'Time-based exit triggered',
                            'condition_type': 'timeBasedExit',
                            'details': result
                        }
                
                # Performance-based exit (daily P&L)
                if condition_name == 'performanceBasedExit':
                    result, which_triggered = self.evaluate_performance_based_exit(
                        condition_config,
                        context
                    )
                    if result and result.get('satisfied', False):
                        if which_triggered == 'profit':
                            reason = 'Daily profit target reached'
                        elif which_triggered == 'loss':
                            reason = 'Daily loss limit reached'
                        else:
                            reason = 'Performance-based exit triggered'
                        
                        return {
                            'should_end': True,
                            'reason': reason,
                            'condition_type': 'performanceBasedExit',
                            'details': result,
                            'which_triggered': which_triggered
                        }
                
                # Alert notification (doesn't end strategy)
                if condition_name == 'alertNotification':
                    result = self.evaluate_alert_notification(condition_config, context)
                    # Alert notifications don't end the strategy
                    if result and result.get('satisfied', False):
                        log_info(f"  📢 Alert notification triggered: {result.get('description')}")
                
                # Check if this condition should end the strategy
                if result.get('should_end', False):
                    return result
            
            except Exception as e:
                log_error(f"  ❌ Error evaluating end condition {condition_name}: {e}")
                traceback.print_exc()
                raise  # Fail fast
        
        return {'should_end': False, 'reason': 'No end conditions met'}
    
    def evaluate_time_based_exit(
        self,
        condition_config: Dict[str, Any],
        current_timestamp: datetime,
        symbol: str = None
    ) -> Dict[str, Any]:
        """
        Evaluate time-based exit condition.
        
        Checks:
        - Exit at market close (with minutes before close)
        - Exit at specific time
        
        Args:
            condition_config: Time-based exit configuration
            current_timestamp: Current timestamp
            symbol: Symbol for exchange detection
            
        Returns:
            {
                'satisfied': bool,
                'type': 'time_based_exit',
                'description': str,
                'current_time': str,
                'exit_time': str
            }
        """
        try:
            # Check if exit at market close is enabled
            if condition_config.get('exitAtMarketClose', False):
                # Get market-specific close time (15:30 for NSE, 23:30 for MCX)
                exchange = detect_exchange_from_symbol(symbol) if symbol else None
                _, market_close_time = get_session_times(exchange, symbol)
                
                current_time = current_timestamp.time()
                minutes_before_close = condition_config.get('minutesBeforeClose', 5)
                
                # Calculate exit time properly
                # Convert market close time to total minutes since midnight
                market_close_minutes = market_close_time.hour * 60 + market_close_time.minute
                exit_minutes = market_close_minutes - minutes_before_close
                
                # Convert back to hours and minutes
                exit_hours = exit_minutes // 60
                exit_minutes_remainder = exit_minutes % 60
                
                exit_time = time(exit_hours, exit_minutes_remainder)
                
                satisfied = current_time >= exit_time
                
                return {
                    'satisfied': satisfied,
                    'type': 'time_based_exit',
                    'description': f'Exit {minutes_before_close} minutes before market close',
                    'current_time': str(current_time),
                    'exit_time': str(exit_time),
                    'market_close_time': str(market_close_time)
                }
            
            # Check specific exit time
            exit_time_str = condition_config.get('exitTime', '')
            if exit_time_str:
                try:
                    exit_time = time.fromisoformat(exit_time_str)
                    current_time = current_timestamp.time()
                    satisfied = current_time >= exit_time
                    
                    return {
                        'satisfied': satisfied,
                        'type': 'time_based_exit',
                        'description': f'Exit at {exit_time_str}',
                        'current_time': str(current_time),
                        'exit_time': str(exit_time)
                    }
                except ValueError:
                    log_warning(f"Invalid exit time format: {exit_time_str}")
            
            return {
                'satisfied': False,
                'type': 'time_based_exit',
                'description': 'Time-based exit not configured'
            }
        
        except Exception as e:
            log_error(f"Error evaluating time-based exit: {e}")
            return {
                'satisfied': False,
                'type': 'time_based_exit',
                'description': f'Error: {str(e)}'
            }
    
    def evaluate_performance_based_exit(
        self,
        condition_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Evaluate performance-based exit condition (daily P&L).
        
        Checks:
        - Daily profit target reached
        - Daily loss limit reached
        
        Args:
            condition_config: Performance-based exit configuration
            context: Execution context (for GPS access)
            
        Returns:
            (result_dict, which_triggered)
            result_dict: {
                'satisfied': bool,
                'type': 'performance_based_exit',
                'description': str,
                'current_pnl': float,
                'target_amount': float
            }
            which_triggered: 'profit' | 'loss' | None
        """
        try:
            daily_pnl_config = condition_config.get('dailyPnLTarget', {})
            if not daily_pnl_config.get('enabled', False):
                return {
                    'satisfied': False,
                    'type': 'performance_based_exit',
                    'description': 'Performance-based exit not enabled'
                }, None
            
            # Get GPS from context manager
            context_manager = context.get('context_manager')
            if not context_manager:
                return {
                    'satisfied': False,
                    'type': 'performance_based_exit',
                    'description': 'No context manager available'
                }, None
            
            gps = context_manager.get_gps()
            open_positions = gps.get_open_positions()
            closed_positions = gps.get_closed_positions()
            
            # Get current price from tick
            current_tick = context.get('current_tick', {})
            current_price = current_tick.get('ltp') or current_tick.get('close')
            
            # Calculate realised P&L (from closed positions)
            realised_pnl = 0.0
            for pos in closed_positions.values():
                entry_price = pos.get('entry_price', 0)
                exit_price = pos.get('exit_price', 0)
                quantity = pos.get('quantity', 0)
                multiplier = pos.get('position_config', {}).get('multiplier', 1)
                side = pos.get('entry', {}).get('side', 'buy')
                
                if side == 'buy':
                    pnl = (exit_price - entry_price) * quantity * multiplier
                else:
                    pnl = (entry_price - exit_price) * quantity * multiplier
                
                realised_pnl += pnl
            
            # Calculate unrealised P&L (from open positions)
            unrealised_pnl = 0.0
            for pos in open_positions.values():
                entry_price = pos.get('entry_price', 0)
                quantity = pos.get('quantity', 0)
                multiplier = pos.get('position_config', {}).get('multiplier', 1)
                side = pos.get('entry', {}).get('side', 'buy')
                
                if current_price is not None:
                    if side == 'buy':
                        pnl = (current_price - entry_price) * quantity * multiplier
                    else:
                        pnl = (entry_price - current_price) * quantity * multiplier
                    unrealised_pnl += pnl
            
            total_pnl = realised_pnl + unrealised_pnl
            
            target_amount = daily_pnl_config.get('targetAmount', 0)
            target_type = daily_pnl_config.get('targetType', 'absolute')
            initial_capital = daily_pnl_config.get('initialCapital', None)
            
            satisfied = False
            which_triggered = None
            
            # Check profit target and loss limit
            if target_type == 'absolute':
                if total_pnl >= target_amount:
                    satisfied = True
                    which_triggered = 'profit'
                elif total_pnl <= -abs(target_amount):
                    satisfied = True
                    which_triggered = 'loss'
            elif target_type == 'percentage' and initial_capital:
                pct = (total_pnl / initial_capital) * 100
                pct_target = target_amount
                if pct >= pct_target:
                    satisfied = True
                    which_triggered = 'profit'
                elif pct <= -abs(pct_target):
                    satisfied = True
                    which_triggered = 'loss'
            
            desc = f"Performance-based exit: {'Profit target reached' if which_triggered == 'profit' else 'Loss limit reached' if which_triggered == 'loss' else 'Not triggered'} (P&L: {total_pnl:.2f})"
            
            return {
                'satisfied': satisfied,
                'type': 'performance_based_exit',
                'description': desc,
                'current_pnl': total_pnl,
                'realised_pnl': realised_pnl,
                'unrealised_pnl': unrealised_pnl,
                'target_amount': target_amount,
                'target_type': target_type,
                'initial_capital': initial_capital
            }, which_triggered
        
        except Exception as e:
            log_error(f"Error evaluating performance-based exit: {e}")
            return {
                'satisfied': False,
                'type': 'performance_based_exit',
                'description': f'Error: {str(e)}'
            }, None
    
    def evaluate_alert_notification(
        self,
        condition_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate alert notification condition.
        
        Args:
            condition_config: Alert notification configuration
            context: Execution context
            
        Returns:
            {
                'satisfied': bool,
                'type': 'alert_notification',
                'description': str
            }
        """
        try:
            enabled = condition_config.get('enabled', False)
            
            if not enabled:
                return {
                    'satisfied': False,
                    'type': 'alert_notification',
                    'description': 'Alert notification not enabled'
                }
            
            # TODO: Implement alert notification logic
            # This could trigger alerts based on various conditions
            
            return {
                'satisfied': False,
                'type': 'alert_notification',
                'description': 'Alert notification enabled but not triggered'
            }
        
        except Exception as e:
            log_error(f"Error evaluating alert notification: {e}")
            return {
                'satisfied': False,
                'type': 'alert_notification',
                'description': f'Error: {str(e)}'
            }
    
    def check_all_nodes_inactive(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if all nodes in the strategy are inactive.
        
        Args:
            context: Execution context containing node statuses
            
        Returns:
            {
                'satisfied': bool,
                'type': 'all_nodes_inactive',
                'description': str,
                'active_nodes': int,
                'total_nodes': int
            }
        """
        try:
            # Get node statuses from context
            node_statuses = context.get('node_statuses', {})
            
            if not node_statuses:
                return {
                    'satisfied': False,
                    'type': 'all_nodes_inactive',
                    'description': 'No node statuses available',
                    'active_nodes': 0,
                    'total_nodes': 0
                }
            
            # Count active and total nodes
            active_nodes = sum(1 for status in node_statuses.values() if status.get('active', False))
            total_nodes = len(node_statuses)
            
            # Check if all nodes are inactive (excluding the start node which should always be active)
            start_nodes = [node_id for node_id, status in node_statuses.items()
                          if status.get('node_type') == 'StartNode']
            
            # Exclude start nodes from the inactive check
            non_start_nodes = {node_id: status for node_id, status in node_statuses.items()
                              if status.get('node_type') != 'StartNode'}
            
            active_non_start_nodes = sum(1 for status in non_start_nodes.values()
                                        if status.get('active', False))
            total_non_start_nodes = len(non_start_nodes)
            
            # Strategy should end if all non-start nodes are inactive
            satisfied = total_non_start_nodes > 0 and active_non_start_nodes == 0
            
            return {
                'satisfied': satisfied,
                'type': 'all_nodes_inactive',
                'description': f'All non-start nodes inactive ({active_non_start_nodes}/{total_non_start_nodes})',
                'active_nodes': active_nodes,
                'total_nodes': total_nodes,
                'active_non_start_nodes': active_non_start_nodes,
                'total_non_start_nodes': total_non_start_nodes,
                'start_nodes': start_nodes
            }
        
        except Exception as e:
            log_error(f"Error checking all nodes inactive: {e}")
            return {
                'satisfied': False,
                'type': 'all_nodes_inactive',
                'description': f'Error: {str(e)}',
                'active_nodes': 0,
                'total_nodes': 0
            }
