"""
Additive Strike Subscription Manager

Manages option contract subscriptions with additive-only logic.
Never unsubscribes - only adds new strikes as market moves.
"""

from typing import Set, List, Tuple
from datetime import datetime


class AdditiveStrikeManager:
    """
    Manages dynamic option strike subscriptions with additive-only logic.
    
    Key Features:
    - Additive-only (never unsubscribe)
    - Triggers on 50-point movements for NIFTY
    - Maintains 16 OTM + 16 ITM window
    - Tracks all subscription events
    """
    
    def __init__(
        self,
        underlying: str = "NIFTY",
        strike_interval: int = 50,
        num_otm: int = 16,
        num_itm: int = 16
    ):
        self.underlying = underlying
        self.strike_interval = strike_interval
        self.num_otm = num_otm
        self.num_itm = num_itm
        
        self.subscribed_strikes: Set[int] = set()
        self.last_subscription_spot: float = None
        self.subscription_events: List[dict] = []
    
    def calculate_atm_strike(self, spot: float) -> int:
        """Calculate ATM strike from spot price."""
        return round(spot / self.strike_interval) * self.strike_interval
    
    def calculate_strike_window(self, spot: float) -> List[int]:
        """
        Calculate 16 ITM + ATM + 16 OTM strikes around current spot.
        
        For NIFTY:
        - ITM: 16 strikes BELOW ATM (lower strikes)
        - ATM: Rounded to nearest 50
        - OTM: 16 strikes ABOVE ATM (higher strikes)
        
        Example: spot=25,800 → ATM=25,800
        - ITM: 25,000, 25,050, ..., 25,750 (16 strikes)
        - ATM: 25,800
        - OTM: 25,850, 25,900, ..., 26,600 (16 strikes)
        """
        atm = self.calculate_atm_strike(spot)
        
        # ITM strikes (below ATM for both CALL and PUT perspective)
        itm = [atm - (i * self.strike_interval) for i in range(1, self.num_itm + 1)]
        
        # OTM strikes (above ATM)
        otm = [atm + (i * self.strike_interval) for i in range(1, self.num_otm + 1)]
        
        # Return sorted: lowest to highest
        return sorted(itm) + [atm] + sorted(otm)
    
    def subscribe_initial(self, spot: float, timestamp: datetime = None) -> List[int]:
        """Subscribe to initial strikes at 9:15 AM."""
        strikes = self.calculate_strike_window(spot)
        self.subscribed_strikes.update(strikes)
        self.last_subscription_spot = spot
        
        self.subscription_events.append({
            'timestamp': timestamp or datetime.now(),
            'spot': spot,
            'action': 'initial',
            'strikes_added': strikes,
            'total': len(self.subscribed_strikes)
        })
        
        return strikes
    
    def check_and_add_strikes(
        self, 
        current_spot: float, 
        timestamp: datetime = None
    ) -> List[int]:
        """Check if need to add new strikes. Returns list of new strikes added."""
        
        # Check if moved 50+ points
        if self.last_subscription_spot is None:
            return []
        
        if abs(current_spot - self.last_subscription_spot) < self.strike_interval:
            return []
        
        # Calculate current window
        current_window = set(self.calculate_strike_window(current_spot))
        
        # Find new strikes not yet subscribed
        new_strikes = current_window - self.subscribed_strikes
        
        if not new_strikes:
            self.last_subscription_spot = current_spot
            return []
        
        # Add new strikes
        self.subscribed_strikes.update(new_strikes)
        self.last_subscription_spot = current_spot
        
        self.subscription_events.append({
            'timestamp': timestamp or datetime.now(),
            'spot': current_spot,
            'action': 'add',
            'strikes_added': sorted(new_strikes),
            'total': len(self.subscribed_strikes)
        })
        
        return sorted(new_strikes)
    
    def get_all_strikes(self) -> List[int]:
        """Get all subscribed strikes."""
        return sorted(self.subscribed_strikes)
    
    def get_strike_range(self) -> Tuple[int, int]:
        """Get min and max strikes."""
        if not self.subscribed_strikes:
            return None, None
        return min(self.subscribed_strikes), max(self.subscribed_strikes)
    
    def print_summary(self):
        """Print subscription summary."""
        min_s, max_s = self.get_strike_range()
        print(f"\n📊 {self.underlying} Strike Subscription Summary:")
        print(f"   Total Strikes: {len(self.subscribed_strikes)}")
        print(f"   Range: {min_s} to {max_s}")
        print(f"   Events: {len(self.subscription_events)}")


# Example usage
if __name__ == "__main__":
    manager = AdditiveStrikeManager()
    
    # 9:15 AM - Initial
    strikes = manager.subscribe_initial(25800)
    print(f"Initial: {len(strikes)} strikes ({min(strikes)} to {max(strikes)})")
    
    # 10:00 AM - +50
    new = manager.check_and_add_strikes(25850)
    if new:
        print(f"Added: {new}")
    
    # 10:30 AM - +100
    new = manager.check_and_add_strikes(25900)
    if new:
        print(f"Added: {new}")
    
    manager.print_summary()
