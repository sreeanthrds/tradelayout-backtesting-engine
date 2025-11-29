from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class UnifiedSymbol:
    base_symbol: str
    asset_class: str  # "INDEX" or "STOCK"
    instrument_type: str  # "SPOT", "FUT", "OPT"
    expiry: Optional[date] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None  # "CE" or "PE" for options

    def to_universal_string(self) -> str:
        if self.instrument_type == "SPOT":
            return self.base_symbol

        if not self.expiry:
            raise ValueError("expiry is required for non-SPOT instruments")

        expiry_str = self.expiry.strftime("%Y-%m-%d")

        if self.instrument_type == "FUT":
            return f"{self.base_symbol}:{expiry_str}:FUT"

        if self.instrument_type == "OPT":
            if self.strike is None or not self.option_type:
                raise ValueError("strike and option_type are required for options")
            strike_str = ("%g" % self.strike)
            return f"{self.base_symbol}:{expiry_str}:OPT:{strike_str}:{self.option_type}"

        raise ValueError(f"Unsupported instrument_type: {self.instrument_type}")

    @staticmethod
    def from_universal_string(symbol: str, asset_class: Optional[str] = None) -> "UnifiedSymbol":
        if ":" not in symbol:
            return UnifiedSymbol(
                base_symbol=symbol,
                asset_class=asset_class or "INDEX",
                instrument_type="SPOT",
            )

        parts = symbol.split(":")

        if len(parts) == 3 and parts[2] == "FUT":
            base_symbol, expiry_str, _ = parts
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            return UnifiedSymbol(
                base_symbol=base_symbol,
                asset_class=asset_class or "INDEX",
                instrument_type="FUT",
                expiry=expiry,
            )

        if len(parts) == 5 and parts[2] == "OPT":
            base_symbol, expiry_str, _, strike_str, option_type = parts
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            strike = float(strike_str)
            return UnifiedSymbol(
                base_symbol=base_symbol,
                asset_class=asset_class or "INDEX",
                instrument_type="OPT",
                expiry=expiry,
                strike=strike,
                option_type=option_type,
            )

        raise ValueError(f"Unsupported universal symbol format: {symbol}")
