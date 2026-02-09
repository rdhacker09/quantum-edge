"""
🏦 Smart Money Concepts (SMC)
=============================
Python implementation of institutional trading concepts.

Original PineScript by LuxAlgo
https://www.tradingview.com/script/CnB3fSph-Smart-Money-Concepts-SMC-LuxAlgo/
License: Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
https://creativecommons.org/licenses/by-nc-sa/4.0/
© LuxAlgo

Smart Money Concepts include:
- Market Structure (BOS/CHoCH)
- Order Blocks (institutional entry zones)
- Fair Value Gaps (imbalance areas)
- Equal Highs/Lows
- Premium/Discount Zones

Ported to Python for QuantumEdge Trading Bot
Credits preserved as required by license.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class StructureType(Enum):
    NONE = "none"
    BOS_BULLISH = "bos_bullish"      # Break of Structure - Bullish
    BOS_BEARISH = "bos_bearish"      # Break of Structure - Bearish
    CHOCH_BULLISH = "choch_bullish"  # Change of Character - Bullish (trend reversal)
    CHOCH_BEARISH = "choch_bearish"  # Change of Character - Bearish (trend reversal)


class OrderBlockType(Enum):
    NONE = "none"
    BULLISH = "bullish"  # Demand zone - expect price to bounce up
    BEARISH = "bearish"  # Supply zone - expect price to bounce down


class TrendDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class SwingPoint:
    index: int
    price: float
    is_high: bool  # True = swing high, False = swing low
    timestamp: Optional[datetime] = None


@dataclass
class OrderBlock:
    type: OrderBlockType
    top: float
    bottom: float
    start_index: int
    end_index: int
    volume: float = 0.0
    strength: float = 0.0  # 0-1 based on move after OB
    mitigated: bool = False
    
    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class FairValueGap:
    type: str  # "bullish" or "bearish"
    top: float
    bottom: float
    index: int
    filled: bool = False
    
    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class SMCAnalysis:
    # Market Structure
    trend: TrendDirection
    structure_signal: StructureType
    swing_high: Optional[float]
    swing_low: Optional[float]
    
    # Order Blocks
    bullish_obs: List[OrderBlock]
    bearish_obs: List[OrderBlock]
    nearest_bullish_ob: Optional[OrderBlock]
    nearest_bearish_ob: Optional[OrderBlock]
    
    # Fair Value Gaps
    bullish_fvgs: List[FairValueGap]
    bearish_fvgs: List[FairValueGap]
    
    # Zones
    premium_zone: Tuple[float, float]  # (bottom, top) - overbought
    discount_zone: Tuple[float, float]  # (bottom, top) - oversold
    equilibrium: float  # 50% level
    
    # Equal Highs/Lows
    equal_highs: List[float]
    equal_lows: List[float]
    
    # Trading signals
    in_discount: bool  # Good for longs
    in_premium: bool   # Good for shorts
    at_order_block: Optional[OrderBlockType]
    signal_strength: float  # 0-1


class SmartMoneyConcepts:
    """
    Smart Money Concepts (SMC) Indicator
    
    Original concept by LuxAlgo (TradingView)
    Based on ICT (Inner Circle Trader) methodology
    
    Identifies institutional trading patterns:
    - Where big money enters (Order Blocks)
    - Market structure shifts (BOS/CHoCH)
    - Price imbalances (Fair Value Gaps)
    """
    
    def __init__(self, swing_length: int = 10, ob_count: int = 5, 
                 fvg_threshold: float = 0.0, eq_threshold: float = 0.001):
        """
        Initialize SMC detector.
        
        Args:
            swing_length: Bars to look back for swing detection
            ob_count: Max order blocks to track
            fvg_threshold: Min size for FVG (0 = auto)
            eq_threshold: Tolerance for equal highs/lows (0.1%)
        """
        self.swing_length = swing_length
        self.ob_count = ob_count
        self.fvg_threshold = fvg_threshold
        self.eq_threshold = eq_threshold
        
        # State
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        self.order_blocks: List[OrderBlock] = []
        self.fvgs: List[FairValueGap] = []
        self.trend = TrendDirection.NEUTRAL
        self.last_structure = StructureType.NONE
    
    def _detect_swing_high(self, highs: List[float], index: int) -> bool:
        """Detect if index is a swing high."""
        if index < self.swing_length or index >= len(highs) - self.swing_length:
            return False
        
        pivot = highs[index]
        for i in range(1, self.swing_length + 1):
            if highs[index - i] >= pivot or highs[index + i] >= pivot:
                return False
        return True
    
    def _detect_swing_low(self, lows: List[float], index: int) -> bool:
        """Detect if index is a swing low."""
        if index < self.swing_length or index >= len(lows) - self.swing_length:
            return False
        
        pivot = lows[index]
        for i in range(1, self.swing_length + 1):
            if lows[index - i] <= pivot or lows[index + i] <= pivot:
                return False
        return True
    
    def _update_swing_points(self, highs: List[float], lows: List[float]):
        """Update swing highs and lows."""
        # Check recent bars for new swing points
        for i in range(max(0, len(highs) - self.swing_length * 3), 
                       len(highs) - self.swing_length):
            
            # Check for swing high
            if self._detect_swing_high(highs, i):
                # Check if already recorded
                if not any(sp.index == i for sp in self.swing_highs):
                    self.swing_highs.append(SwingPoint(
                        index=i, price=highs[i], is_high=True
                    ))
            
            # Check for swing low
            if self._detect_swing_low(lows, i):
                if not any(sp.index == i for sp in self.swing_lows):
                    self.swing_lows.append(SwingPoint(
                        index=i, price=lows[i], is_high=False
                    ))
        
        # Keep only recent swing points
        max_swings = 20
        self.swing_highs = sorted(self.swing_highs, key=lambda x: x.index)[-max_swings:]
        self.swing_lows = sorted(self.swing_lows, key=lambda x: x.index)[-max_swings:]
    
    def _detect_market_structure(self, highs: List[float], lows: List[float], 
                                  closes: List[float]) -> StructureType:
        """Detect BOS and CHoCH."""
        if len(self.swing_highs) < 2 or len(self.swing_lows) < 2:
            return StructureType.NONE
        
        current_close = closes[-1]
        prev_swing_high = self.swing_highs[-1].price if self.swing_highs else None
        prev_swing_low = self.swing_lows[-1].price if self.swing_lows else None
        
        prev_trend = self.trend
        
        # Break of Structure
        if prev_swing_high and current_close > prev_swing_high:
            if prev_trend == TrendDirection.BEARISH:
                self.trend = TrendDirection.BULLISH
                return StructureType.CHOCH_BULLISH  # Trend reversal!
            else:
                self.trend = TrendDirection.BULLISH
                return StructureType.BOS_BULLISH  # Trend continuation
        
        if prev_swing_low and current_close < prev_swing_low:
            if prev_trend == TrendDirection.BULLISH:
                self.trend = TrendDirection.BEARISH
                return StructureType.CHOCH_BEARISH  # Trend reversal!
            else:
                self.trend = TrendDirection.BEARISH
                return StructureType.BOS_BEARISH  # Trend continuation
        
        return StructureType.NONE
    
    def _detect_order_blocks(self, opens: List[float], highs: List[float], 
                             lows: List[float], closes: List[float],
                             volumes: List[float]):
        """Detect order blocks (institutional entry zones)."""
        if len(closes) < 5:
            return
        
        # Look for bullish order block (last down candle before up move)
        for i in range(len(closes) - 4, max(0, len(closes) - 20), -1):
            # Bearish candle followed by strong bullish move
            if closes[i] < opens[i]:  # Down candle
                # Check if followed by bullish move
                future_high = max(highs[i+1:min(i+4, len(highs))])
                move_size = (future_high - highs[i]) / highs[i]
                
                if move_size > 0.005:  # 0.5% move
                    ob = OrderBlock(
                        type=OrderBlockType.BULLISH,
                        top=highs[i],
                        bottom=lows[i],
                        start_index=i,
                        end_index=i,
                        volume=volumes[i] if i < len(volumes) else 0,
                        strength=min(1.0, move_size * 50)
                    )
                    
                    # Check if not already added
                    if not any(existing.start_index == i and 
                              existing.type == OrderBlockType.BULLISH 
                              for existing in self.order_blocks):
                        self.order_blocks.append(ob)
                        break
        
        # Look for bearish order block (last up candle before down move)
        for i in range(len(closes) - 4, max(0, len(closes) - 20), -1):
            # Bullish candle followed by strong bearish move
            if closes[i] > opens[i]:  # Up candle
                # Check if followed by bearish move
                future_low = min(lows[i+1:min(i+4, len(lows))])
                move_size = (lows[i] - future_low) / lows[i]
                
                if move_size > 0.005:  # 0.5% move
                    ob = OrderBlock(
                        type=OrderBlockType.BEARISH,
                        top=highs[i],
                        bottom=lows[i],
                        start_index=i,
                        end_index=i,
                        volume=volumes[i] if i < len(volumes) else 0,
                        strength=min(1.0, move_size * 50)
                    )
                    
                    if not any(existing.start_index == i and 
                              existing.type == OrderBlockType.BEARISH 
                              for existing in self.order_blocks):
                        self.order_blocks.append(ob)
                        break
        
        # Check for mitigated order blocks
        current_price = closes[-1]
        for ob in self.order_blocks:
            if not ob.mitigated:
                if ob.type == OrderBlockType.BULLISH and current_price < ob.bottom:
                    ob.mitigated = True
                elif ob.type == OrderBlockType.BEARISH and current_price > ob.top:
                    ob.mitigated = True
        
        # Keep only recent non-mitigated order blocks
        self.order_blocks = [ob for ob in self.order_blocks if not ob.mitigated]
        self.order_blocks = sorted(self.order_blocks, key=lambda x: x.start_index)[-self.ob_count * 2:]
    
    def _detect_fvg(self, highs: List[float], lows: List[float], closes: List[float]):
        """Detect Fair Value Gaps (imbalances)."""
        if len(closes) < 3:
            return
        
        # Check last few bars for FVG
        for i in range(len(closes) - 3, max(0, len(closes) - 10), -1):
            # Bullish FVG: gap between candle 1 high and candle 3 low
            if lows[i + 2] > highs[i]:
                gap_size = lows[i + 2] - highs[i]
                if gap_size > closes[i] * (self.fvg_threshold or 0.001):
                    fvg = FairValueGap(
                        type="bullish",
                        top=lows[i + 2],
                        bottom=highs[i],
                        index=i + 1
                    )
                    if not any(f.index == fvg.index and f.type == "bullish" for f in self.fvgs):
                        self.fvgs.append(fvg)
            
            # Bearish FVG: gap between candle 1 low and candle 3 high
            if highs[i + 2] < lows[i]:
                gap_size = lows[i] - highs[i + 2]
                if gap_size > closes[i] * (self.fvg_threshold or 0.001):
                    fvg = FairValueGap(
                        type="bearish",
                        top=lows[i],
                        bottom=highs[i + 2],
                        index=i + 1
                    )
                    if not any(f.index == fvg.index and f.type == "bearish" for f in self.fvgs):
                        self.fvgs.append(fvg)
        
        # Check for filled FVGs
        current_price = closes[-1]
        for fvg in self.fvgs:
            if not fvg.filled:
                if fvg.type == "bullish" and current_price <= fvg.bottom:
                    fvg.filled = True
                elif fvg.type == "bearish" and current_price >= fvg.top:
                    fvg.filled = True
        
        # Keep only recent unfilled FVGs
        self.fvgs = [f for f in self.fvgs if not f.filled][-10:]
    
    def _detect_equal_levels(self, highs: List[float], lows: List[float]) -> Tuple[List[float], List[float]]:
        """Detect equal highs and lows (potential reversal zones)."""
        equal_highs = []
        equal_lows = []
        
        recent_highs = highs[-50:] if len(highs) > 50 else highs
        recent_lows = lows[-50:] if len(lows) > 50 else lows
        
        # Find equal highs
        for i, h1 in enumerate(recent_highs):
            for j, h2 in enumerate(recent_highs[i+5:], i+5):
                if abs(h1 - h2) / h1 < self.eq_threshold:
                    avg = (h1 + h2) / 2
                    if avg not in equal_highs:
                        equal_highs.append(avg)
        
        # Find equal lows
        for i, l1 in enumerate(recent_lows):
            for j, l2 in enumerate(recent_lows[i+5:], i+5):
                if abs(l1 - l2) / l1 < self.eq_threshold:
                    avg = (l1 + l2) / 2
                    if avg not in equal_lows:
                        equal_lows.append(avg)
        
        return equal_highs[-5:], equal_lows[-5:]
    
    def _calculate_zones(self, highs: List[float], lows: List[float]) -> Tuple[Tuple, Tuple, float]:
        """Calculate premium/discount zones."""
        lookback = min(50, len(highs))
        range_high = max(highs[-lookback:])
        range_low = min(lows[-lookback:])
        range_size = range_high - range_low
        
        equilibrium = (range_high + range_low) / 2
        
        # Premium zone (top 30%)
        premium_zone = (range_high - range_size * 0.3, range_high)
        
        # Discount zone (bottom 30%)
        discount_zone = (range_low, range_low + range_size * 0.3)
        
        return premium_zone, discount_zone, equilibrium
    
    def analyze(self, opens: List[float], highs: List[float], 
                lows: List[float], closes: List[float],
                volumes: List[float] = None) -> SMCAnalysis:
        """
        Full Smart Money Concepts analysis.
        
        Args:
            opens: Open prices
            highs: High prices
            lows: Low prices
            closes: Close prices
            volumes: Volume (optional)
            
        Returns:
            SMCAnalysis with all SMC components
        """
        if len(closes) < self.swing_length * 2:
            return self._empty_analysis()
        
        volumes = volumes or [0] * len(closes)
        current_price = closes[-1]
        
        # Update swing points
        self._update_swing_points(highs, lows)
        
        # Detect market structure
        structure_signal = self._detect_market_structure(highs, lows, closes)
        
        # Detect order blocks
        self._detect_order_blocks(opens, highs, lows, closes, volumes)
        
        # Detect FVGs
        self._detect_fvg(highs, lows, closes)
        
        # Detect equal highs/lows
        equal_highs, equal_lows = self._detect_equal_levels(highs, lows)
        
        # Calculate zones
        premium_zone, discount_zone, equilibrium = self._calculate_zones(highs, lows)
        
        # Separate bullish/bearish OBs
        bullish_obs = [ob for ob in self.order_blocks if ob.type == OrderBlockType.BULLISH]
        bearish_obs = [ob for ob in self.order_blocks if ob.type == OrderBlockType.BEARISH]
        
        # Find nearest order blocks to current price
        nearest_bullish = None
        nearest_bearish = None
        
        for ob in bullish_obs:
            if ob.top <= current_price:  # Below current price
                if nearest_bullish is None or ob.top > nearest_bullish.top:
                    nearest_bullish = ob
        
        for ob in bearish_obs:
            if ob.bottom >= current_price:  # Above current price
                if nearest_bearish is None or ob.bottom < nearest_bearish.bottom:
                    nearest_bearish = ob
        
        # Check if at order block
        at_ob = None
        for ob in self.order_blocks:
            if ob.bottom <= current_price <= ob.top:
                at_ob = ob.type
                break
        
        # Separate FVGs
        bullish_fvgs = [f for f in self.fvgs if f.type == "bullish"]
        bearish_fvgs = [f for f in self.fvgs if f.type == "bearish"]
        
        # Calculate signal strength
        signal_strength = self._calculate_signal_strength(
            current_price, structure_signal, bullish_obs, bearish_obs,
            premium_zone, discount_zone, at_ob
        )
        
        return SMCAnalysis(
            trend=self.trend,
            structure_signal=structure_signal,
            swing_high=self.swing_highs[-1].price if self.swing_highs else None,
            swing_low=self.swing_lows[-1].price if self.swing_lows else None,
            bullish_obs=bullish_obs,
            bearish_obs=bearish_obs,
            nearest_bullish_ob=nearest_bullish,
            nearest_bearish_ob=nearest_bearish,
            bullish_fvgs=bullish_fvgs,
            bearish_fvgs=bearish_fvgs,
            premium_zone=premium_zone,
            discount_zone=discount_zone,
            equilibrium=equilibrium,
            equal_highs=equal_highs,
            equal_lows=equal_lows,
            in_discount=discount_zone[0] <= current_price <= discount_zone[1],
            in_premium=premium_zone[0] <= current_price <= premium_zone[1],
            at_order_block=at_ob,
            signal_strength=signal_strength
        )
    
    def _calculate_signal_strength(self, price: float, structure: StructureType,
                                   bullish_obs: List, bearish_obs: List,
                                   premium: Tuple, discount: Tuple,
                                   at_ob: Optional[OrderBlockType]) -> float:
        """Calculate overall signal strength."""
        strength = 0.0
        
        # Structure signal
        if structure in [StructureType.BOS_BULLISH, StructureType.BOS_BEARISH]:
            strength += 0.2
        elif structure in [StructureType.CHOCH_BULLISH, StructureType.CHOCH_BEARISH]:
            strength += 0.4  # CHoCH is stronger
        
        # At order block
        if at_ob:
            strength += 0.3
        
        # In discount/premium
        if discount[0] <= price <= discount[1]:
            strength += 0.2
        elif premium[0] <= price <= premium[1]:
            strength += 0.2
        
        # Near order block
        for ob in bullish_obs + bearish_obs:
            distance = abs(price - ob.mid) / price
            if distance < 0.01:  # Within 1%
                strength += 0.1
                break
        
        return min(1.0, strength)
    
    def _empty_analysis(self) -> SMCAnalysis:
        """Return empty analysis."""
        return SMCAnalysis(
            trend=TrendDirection.NEUTRAL,
            structure_signal=StructureType.NONE,
            swing_high=None,
            swing_low=None,
            bullish_obs=[],
            bearish_obs=[],
            nearest_bullish_ob=None,
            nearest_bearish_ob=None,
            bullish_fvgs=[],
            bearish_fvgs=[],
            premium_zone=(0, 0),
            discount_zone=(0, 0),
            equilibrium=0,
            equal_highs=[],
            equal_lows=[],
            in_discount=False,
            in_premium=False,
            at_order_block=None,
            signal_strength=0
        )
    
    def get_trade_bias(self) -> Tuple[str, float]:
        """Get current trade bias based on SMC analysis."""
        if self.trend == TrendDirection.BULLISH:
            return "long", 0.7
        elif self.trend == TrendDirection.BEARISH:
            return "short", 0.7
        return "neutral", 0.5
