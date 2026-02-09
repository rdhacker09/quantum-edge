"""
🎯 Market Regime Detection
==========================
Identifies market conditions to adapt strategy:
- TRENDING_UP: Strong bullish momentum
- TRENDING_DOWN: Strong bearish momentum  
- RANGING: Sideways consolidation
- VOLATILE: High volatility, choppy
- BREAKOUT: Potential breakout forming
"""

import numpy as np
from enum import Enum
from typing import List, Dict, Tuple
from dataclasses import dataclass


class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    BREAKOUT = "breakout"


@dataclass
class RegimeAnalysis:
    regime: MarketRegime
    confidence: float
    trend_strength: float
    volatility: float
    adx: float
    recommendations: Dict


class MarketRegimeDetector:
    """Detects current market regime for strategy adaptation."""
    
    def __init__(self):
        self.lookback = 50
    
    def calculate_adx(self, highs: List[float], lows: List[float], 
                      closes: List[float], period: int = 14) -> Tuple[float, float, float]:
        """Calculate ADX, +DI, -DI."""
        if len(closes) < period + 1:
            return 25.0, 25.0, 25.0
        
        plus_dm = []
        minus_dm = []
        tr_list = []
        
        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)
            
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        # Smooth with Wilder's method
        def wilder_smooth(data, period):
            result = [sum(data[:period])]
            for i in range(period, len(data)):
                result.append(result[-1] - (result[-1] / period) + data[i])
            return result
        
        if len(tr_list) < period:
            return 25.0, 25.0, 25.0
            
        atr = wilder_smooth(tr_list, period)
        plus_dm_smooth = wilder_smooth(plus_dm, period)
        minus_dm_smooth = wilder_smooth(minus_dm, period)
        
        # Calculate +DI and -DI
        plus_di = [(pdm / atr_val * 100) if atr_val > 0 else 0 
                   for pdm, atr_val in zip(plus_dm_smooth, atr)]
        minus_di = [(mdm / atr_val * 100) if atr_val > 0 else 0 
                    for mdm, atr_val in zip(minus_dm_smooth, atr)]
        
        # Calculate DX and ADX
        dx = []
        for pdi, mdi in zip(plus_di, minus_di):
            if pdi + mdi > 0:
                dx.append(abs(pdi - mdi) / (pdi + mdi) * 100)
            else:
                dx.append(0)
        
        if len(dx) < period:
            return 25.0, plus_di[-1] if plus_di else 25.0, minus_di[-1] if minus_di else 25.0
            
        adx = wilder_smooth(dx, period)
        
        return adx[-1], plus_di[-1], minus_di[-1]
    
    def calculate_volatility(self, closes: List[float], period: int = 20) -> float:
        """Calculate normalized volatility (ATR / price)."""
        if len(closes) < period:
            return 0.02
        
        returns = np.diff(closes[-period:]) / closes[-period:-1]
        return np.std(returns) * np.sqrt(period)
    
    def detect_consolidation(self, highs: List[float], lows: List[float], 
                            lookback: int = 20) -> Tuple[bool, float, float]:
        """Detect if price is in consolidation (range)."""
        if len(highs) < lookback:
            return False, 0, 0
        
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        
        range_high = max(recent_highs)
        range_low = min(recent_lows)
        range_size = (range_high - range_low) / range_low
        
        # Consolidation if range < 5% and price bouncing within
        is_consolidating = range_size < 0.05
        
        return is_consolidating, range_low, range_high
    
    def detect_breakout_potential(self, closes: List[float], volumes: List[float],
                                  highs: List[float], lows: List[float]) -> Tuple[bool, str]:
        """Detect if breakout is forming."""
        if len(closes) < 30:
            return False, ""
        
        is_consolidating, range_low, range_high = self.detect_consolidation(highs, lows)
        
        if not is_consolidating:
            return False, ""
        
        current_price = closes[-1]
        avg_volume = np.mean(volumes[-20:-1])
        recent_volume = volumes[-1]
        
        # Volume expansion + near range boundary
        volume_spike = recent_volume > avg_volume * 1.5
        near_resistance = current_price > range_high * 0.98
        near_support = current_price < range_low * 1.02
        
        if volume_spike and near_resistance:
            return True, "bullish"
        elif volume_spike and near_support:
            return True, "bearish"
        
        return False, ""
    
    def analyze(self, highs: List[float], lows: List[float], 
                closes: List[float], volumes: List[float]) -> RegimeAnalysis:
        """Full market regime analysis."""
        
        # Calculate indicators
        adx, plus_di, minus_di = self.calculate_adx(highs, lows, closes)
        volatility = self.calculate_volatility(closes)
        is_consolidating, range_low, range_high = self.detect_consolidation(highs, lows)
        breakout_forming, breakout_direction = self.detect_breakout_potential(
            closes, volumes, highs, lows
        )
        
        # Trend strength from DI difference
        trend_strength = abs(plus_di - minus_di) / 100
        
        # Determine regime
        if breakout_forming:
            regime = MarketRegime.BREAKOUT
            confidence = 0.7
        elif volatility > 0.04:  # High volatility
            regime = MarketRegime.VOLATILE
            confidence = 0.8
        elif adx > 25:  # Strong trend
            if plus_di > minus_di:
                regime = MarketRegime.TRENDING_UP
            else:
                regime = MarketRegime.TRENDING_DOWN
            confidence = min(0.9, adx / 40)
        elif is_consolidating or adx < 20:
            regime = MarketRegime.RANGING
            confidence = 0.75
        else:
            regime = MarketRegime.RANGING
            confidence = 0.5
        
        # Generate recommendations
        recommendations = self._get_recommendations(regime, volatility, adx)
        
        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility=volatility,
            adx=adx,
            recommendations=recommendations
        )
    
    def _get_recommendations(self, regime: MarketRegime, 
                            volatility: float, adx: float) -> Dict:
        """Get trading recommendations based on regime."""
        
        recs = {
            "strategy": "",
            "leverage_multiplier": 1.0,
            "position_size_multiplier": 1.0,
            "entry_timing": "immediate",
            "preferred_indicators": []
        }
        
        if regime == MarketRegime.TRENDING_UP:
            recs["strategy"] = "trend_following_long"
            recs["leverage_multiplier"] = 1.2
            recs["position_size_multiplier"] = 1.1
            recs["entry_timing"] = "pullback"
            recs["preferred_indicators"] = ["ema", "macd", "supertrend"]
            
        elif regime == MarketRegime.TRENDING_DOWN:
            recs["strategy"] = "trend_following_short"
            recs["leverage_multiplier"] = 1.2
            recs["position_size_multiplier"] = 1.1
            recs["entry_timing"] = "pullback"
            recs["preferred_indicators"] = ["ema", "macd", "supertrend"]
            
        elif regime == MarketRegime.RANGING:
            recs["strategy"] = "mean_reversion"
            recs["leverage_multiplier"] = 0.8
            recs["position_size_multiplier"] = 0.9
            recs["entry_timing"] = "immediate"
            recs["preferred_indicators"] = ["rsi", "bollinger", "stochastic"]
            
        elif regime == MarketRegime.VOLATILE:
            recs["strategy"] = "reduced_exposure"
            recs["leverage_multiplier"] = 0.5
            recs["position_size_multiplier"] = 0.6
            recs["entry_timing"] = "limit_orders"
            recs["preferred_indicators"] = ["atr", "vwap"]
            
        elif regime == MarketRegime.BREAKOUT:
            recs["strategy"] = "breakout"
            recs["leverage_multiplier"] = 1.3
            recs["position_size_multiplier"] = 1.0
            recs["entry_timing"] = "confirmation"
            recs["preferred_indicators"] = ["volume", "momentum", "atr"]
        
        return recs
