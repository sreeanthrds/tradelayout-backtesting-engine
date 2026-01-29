"""
Hybrid Indicator Library
========================

High-performance indicators with dual-mode operation:
1. Bulk calculation using pandas_ta (for historical data)
2. Incremental O(1) updates (for live ticks)

All indicators are aligned with the JSON configuration format.

Total Indicators: 136
- Original: 126 indicators
- New (Nov 2025): 10 indicators (Pivots, Elder Ray, AVWAP, Chart Types, Ichimoku, S/R)
"""

from .base import HybridIndicator
from .moving_averages import (
    SMAIndicator, EMAIndicator, WMAIndicator, DEMAIndicator,
    TEMAIndicator, HMAIndicator, ZLEMAIndicator, VWMAIndicator, KAMAIndicator
)
from .momentum import (
    RSIIndicator, MACDIndicator, STOCHIndicator, STOCHRSIIndicator,
    CCIIndicator, CMOIndicator, ROCIndicator, MOMIndicator,
    WILLRIndicator, PPOIndicator, TRIXIndicator, UOIndicator,
    AOIndicator, BOPIndicator, FISHERIndicator, KSTIndicator
)
from .volatility import (
    ATRIndicator, NATRIndicator, BBANDSIndicator, KCIndicator,
    DONCHIANIndicator, STDEVIndicator, VARIANCEIndicator
)
from .trend import (
    ADXIndicator, DMIndicator, SUPERTRENDIndicator, AROONIndicator,
    PSARIndicator, SLOPEIndicator, VORTEXIndicator
)
from .volume import (
    OBVIndicator, ADIndicator, ADOSCIndicator, CMFIndicator, MFIIndicator,
    PVTIndicator, VWAPIndicator, PVOIndicator, EFIIndicator, NVIIndicator, PVIIndicator
)
from .overlap import (
    ALMAIndicator, FWMAIndicator, JMAIndicator, LINREGIndicator, MIDPOINTIndicator,
    MIDPRICEIndicator, T3Indicator, TRIMAIndicator, SINWMAIndicator, PWMAIndicator,
    RMAIndicator, SWMAIndicator, VIDYAIndicator, ZLMAIndicator, HWMAIndicator
)
from .statistics import (
    ENTROPYIndicator, KURTOSISIndicator, MADIndicator, MEDIANIndicator,
    QUANTILEIndicator, SKEWIndicator, ZSCOREIndicator
)
from .performance import (
    LOGRETURNIndicator, PERCENTRETURNIndicator, DRAWDOWNIndicator
)
from .advanced_momentum import (
    APOIndicator, BIASIndicator, BRARIndicator, CFOIndicator, CGIndicator,
    COPPOCKIndicator, ERIndicator, INERTIAIndicator, KDJIndicator, PGOIndicator,
    PSLIndicator, QQEIndicator, RSXIndicator, RVGIIndicator, SMIIndicator,
    SQUEEZEIndicator, STCIndicator, TSIIndicator, CTIIndicator
)
from .advanced_trend import (
    ALLIGATORIndicator, AMATIndicator, CHOPIndicator, CKSPIndicator, DECAYIndicator,
    DPOIndicator, HTTRENDLINEIndicator, QSTICKIndicator, TTMTRENDIndicator, VHFIndicator,
    ZIGZAGIndicator
)
from .advanced_volatility import (
    ABERRATIONIndicator, ACCBANDSIndicator, ATRTSIndicator, CHANDELIEREXITIndicator, HWCIndicator,
    MASSIIndicator, RVIIndicator, THERMOIndicator, TRUERANGEIndicator, UIIndicator
)
from .advanced_volume import (
    AOBVIndicator, EOMIndicator, KVOIndicator, PVOLIndicator, PVRIndicator, TSVIndicator, VPIndicator
)
from .candles import (
    HAIndicator, CDLDOJIIndicator, CDLINSIDEIndicator, CDLPATTERNIndicator
)
from .pivots import (
    PIVOTIndicator, CPRIndicator, CAMARILLAIndicator, FIBONACCIPIVOTIndicator
)
from .elder_ray import ElderRayIndicator
from .anchored_vwap import AnchoredVWAPIndicator
from .chart_types import RenkoIndicator, HeikinAshiIndicator
from .ichimoku import IchimokuIndicator
from .support_resistance import SupportResistanceIndicator

__all__ = [
    'HybridIndicator',
    # Moving Averages (9)
    'SMAIndicator', 'EMAIndicator', 'WMAIndicator', 'DEMAIndicator',
    'TEMAIndicator', 'HMAIndicator', 'ZLEMAIndicator', 'VWMAIndicator', 'KAMAIndicator',
    # Momentum (16)
    'RSIIndicator', 'MACDIndicator', 'STOCHIndicator', 'STOCHRSIIndicator',
    'CCIIndicator', 'CMOIndicator', 'ROCIndicator', 'MOMIndicator',
    'WILLRIndicator', 'PPOIndicator', 'TRIXIndicator', 'UOIndicator',
    'AOIndicator', 'BOPIndicator', 'FISHERIndicator', 'KSTIndicator',
    # Volatility (7)
    'ATRIndicator', 'NATRIndicator', 'BBANDSIndicator', 'KCIndicator',
    'DONCHIANIndicator', 'STDEVIndicator', 'VARIANCEIndicator',
    # Trend (7)
    'ADXIndicator', 'DMIndicator', 'SUPERTRENDIndicator', 'AROONIndicator',
    'PSARIndicator', 'SLOPEIndicator', 'VORTEXIndicator',
    # Volume (11)
    'OBVIndicator', 'ADIndicator', 'ADOSCIndicator', 'CMFIndicator', 'MFIIndicator',
    'PVTIndicator', 'VWAPIndicator', 'PVOIndicator', 'EFIIndicator', 'NVIIndicator', 'PVIIndicator',
    # Overlap (15)
    'ALMAIndicator', 'FWMAIndicator', 'JMAIndicator', 'LINREGIndicator', 'MIDPOINTIndicator',
    'MIDPRICEIndicator', 'T3Indicator', 'TRIMAIndicator', 'SINWMAIndicator', 'PWMAIndicator',
    'RMAIndicator', 'SWMAIndicator', 'VIDYAIndicator', 'ZLMAIndicator', 'HWMAIndicator',
    # Statistics (7)
    'ENTROPYIndicator', 'KURTOSISIndicator', 'MADIndicator', 'MEDIANIndicator',
    'QUANTILEIndicator', 'SKEWIndicator', 'ZSCOREIndicator',
    # Performance (3)
    'LOGRETURNIndicator', 'PERCENTRETURNIndicator', 'DRAWDOWNIndicator',
    # Advanced Momentum (19)
    'APOIndicator', 'BIASIndicator', 'BRARIndicator', 'CFOIndicator', 'CGIndicator',
    'COPPOCKIndicator', 'ERIndicator', 'INERTIAIndicator', 'KDJIndicator', 'PGOIndicator',
    'PSLIndicator', 'QQEIndicator', 'RSXIndicator', 'RVGIIndicator', 'SMIIndicator',
    'SQUEEZEIndicator', 'STCIndicator', 'TSIIndicator', 'CTIIndicator',
    # Advanced Trend (11)
    'ALLIGATORIndicator', 'AMATIndicator', 'CHOPIndicator', 'CKSPIndicator', 'DECAYIndicator',
    'DPOIndicator', 'HTTRENDLINEIndicator', 'QSTICKIndicator', 'TTMTRENDIndicator', 'VHFIndicator',
    'ZIGZAGIndicator',
    # Advanced Volatility (10)
    'ABERRATIONIndicator', 'ACCBANDSIndicator', 'ATRTSIndicator', 'CHANDELIEREXITIndicator', 'HWCIndicator',
    'MASSIIndicator', 'RVIIndicator', 'THERMOIndicator', 'TRUERANGEIndicator', 'UIIndicator',
    # Advanced Volume (7)
    'AOBVIndicator', 'EOMIndicator', 'KVOIndicator', 'PVOLIndicator', 'PVRIndicator', 'TSVIndicator', 'VPIndicator',
    # Candles (4)
    'HAIndicator', 'CDLDOJIIndicator', 'CDLINSIDEIndicator', 'CDLPATTERNIndicator',
    # Pivots (4)
    'PIVOTIndicator', 'CPRIndicator', 'CAMARILLAIndicator', 'FIBONACCIPIVOTIndicator',
    # Elder Ray (1)
    'ElderRayIndicator',
    # Anchored VWAP (1)
    'AnchoredVWAPIndicator',
    # Chart Types (2)
    'RenkoIndicator', 'HeikinAshiIndicator',
    # Ichimoku (1)
    'IchimokuIndicator',
    # Support & Resistance (1)
    'SupportResistanceIndicator',
]
