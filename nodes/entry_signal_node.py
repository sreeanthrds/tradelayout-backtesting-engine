"""
Entry Signal Node - Evaluates entry conditions.

Checks if entry conditions are met (e.g., breakout above previous high).
If conditions met, activates children and deactivates itself.
"""

from typing import Dict, Any
import logging
from nodes.base_node import BaseNode

logger = logging.getLogger(__name__)


class EntrySignalNode(BaseNode):
    """
    Entry Signal Node - Evaluates entry conditions.
    
    Behavior:
    - Checks if entry condition is met (e.g., LTP > Previous High)
    - If met: Activates children, deactivates self
    - If not met: Stays active, waits for next tick
    """
    
    def __init__(self, node_id: str, name: str, config: Dict[str, Any]):
        """
        Initialize Entry Signal Node.
        
        Args:
            node_id: Unique node ID
            name: Display name
            config: Node configuration (entry conditions, etc.)
        """
        super().__init__(node_id, "EntrySignalNode", name)
        self.config = config
        
        # Extract configuration
        self.option_type = config.get('option_type', 'CE')  # CE or PE
        self.condition_type = config.get('condition_type', 'breakout')  # breakout, breakdown
    
    def _execute_node_logic(self, context: Dict[str, Any], node_instances: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if entry condition is met.
        
        Entry Conditions:
        - CE (CALL): LTP > Previous candle High (breakout)
        - PE (PUT): LTP < Previous candle Low (breakdown)
        
        Returns:
            Dict with logic_completed=True if condition met
        """
        # Get current tick
        current_tick = context.get('current_tick')
        if not current_tick:
            return {
                'node_id': self.id,
                'executed': False,
                'logic_completed': False,
                'reason': 'No current tick'
            }
        
        # Get previous candle
        previous_candle = context.get('previous_candle')
        if not previous_candle:
            return {
                'node_id': self.id,
                'executed': False,
                'logic_completed': False,
                'reason': 'No previous candle yet'
            }
        
        # Get current LTP
        current_ltp = current_tick.ltp
        previous_high = previous_candle['high']
        previous_low = previous_candle['low']
        
        # Check entry condition
        condition_met = False
        
        if self.option_type == 'CE':
            # CALL entry: LTP > Previous High (breakout)
            if current_ltp > previous_high:
                condition_met = True
                logger.info(f"✅ Entry Signal {self.id} (CE): Breakout detected!")
                logger.info(f"   LTP: {current_ltp:.2f} > Previous High: {previous_high:.2f}")
        
        elif self.option_type == 'PE':
            # PUT entry: LTP < Previous Low (breakdown)
            if current_ltp < previous_low:
                condition_met = True
                logger.info(f"✅ Entry Signal {self.id} (PE): Breakdown detected!")
                logger.info(f"   LTP: {current_ltp:.2f} < Previous Low: {previous_low:.2f}")
        
        if condition_met:
            # Store signal in context for entry node
            signals = context.get('signals', {})
            signals[self.id] = {
                'option_type': self.option_type,
                'spot_price': current_ltp,
                'timestamp': current_tick.timestamp
            }
            context['signals'] = signals
            
            return {
                'node_id': self.id,
                'executed': True,
                'logic_completed': True,  # ✅ Activate children, deactivate self
                'signal_emitted': True,
                'option_type': self.option_type,
                'spot_price': current_ltp
            }
        else:
            # Condition not met - stay active
            return {
                'node_id': self.id,
                'executed': True,
                'logic_completed': False,  # ✅ Stay active for next tick
                'signal_emitted': False,
                'reason': f'Condition not met (LTP: {current_ltp:.2f})'
            }
