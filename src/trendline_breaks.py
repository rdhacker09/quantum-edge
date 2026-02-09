"""
📈 Trendlines with Breaks
=========================
Python implementation of automatic trendline detection with breakout signals.

Original PineScript by LuxAlgo
https://www.tradingview.com/script/...
License: Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
https://creativecommons.org/licenses/by-nc-sa/4.0/
© LuxAlgo

Ported to Python for QuantumEdge Trading Bot
Credits preserved as required by license.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class BreakoutType(Enum):
    NONE = "none"
    BULLISH = "bullish"  # Price broke DOWN trendline upward
    BEARISH = "bearish"  # Price broke UP trendline downward


class SlopeMethod(Enum):
    ATR = "atr"
    STDEV = "stdev"
    LINREG = "linreg"


@dataclass
class TrendlineSignal:
    breakout: BreakoutType
    upper_trendline: float
    lower_trendline: float
    slope_upper: float
    slope_lower: float
    pivot_high: Optional[float]
    pivot_low: Optional[float]
    confidence: float


class TrendlineBreaks:
    """
    Automatic Trendline Detection with Breakout Signals
    
    Original concept by LuxAlgo (TradingView)
    Python implementation for algorithmic trading
    
    Detects swing highs/lows, draws dynamic trendlines,
    and signals when price breaks through them.
    """
    
    def __init__(self, length: int = 14, slope_mult: float = 1.0, 
                 calc_method: SlopeMethod = SlopeMethod.ATR):
        """
        Initialize Trendline Breaks detector.
        
        Args:
            length: Swing detection lookback period (default: 14)
            slope_mult: Slope multiplier for trendline angle (default: 1.0)
            calc_method: Method for calculating slope (ATR, STDEV, LINREG)
        """
        self.length = length
        self.slope_mult = slope_mult
        self.calc_method = calc_method
        
        # State variables
        self.upper = 0.0
        self.lower = 0.0
        self.slope_ph = 0.0
        self.slope_pl = 0.0
        self.upos = 0
        self.dnos = 0
    
    def _pivot_high(self, highs: List[float], index: int) -> Optional[float]:
        """Detect pivot high at given index."""
        if index < self.length or index >= len(highs) - self.length:
            return None
        
        pivot_val = highs[index]
        
        # Check if it's higher than surrounding bars
        for i in range(1, self.length + 1):
            if highs[index - i] >= pivot_val or highs[index + i] >= pivot_val:
                return None
        
        return pivot_val
    
    def _pivot_low(self, lows: List[float], index: int) -> Optional[float]:
        """Detect pivot low at given index."""
        if index < self.length or index >= len(lows) - self.length:
            return None
        
        pivot_val = lows[index]
        
        # Check if it's lower than surrounding bars
        for i in range(1, self.length + 1):
            if lows[index - i] <= pivot_val or lows[index + i] <= pivot_val:
                return None
        
        return pivot_val
    
    def _calculate_atr(self, highs: List[float], lows: List[float], 
                       closes: List[float], period: int) -> float:
        """Calculate Average True Range."""
        if len(closes) < period + 1:
            return 0.0
        
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        if len(tr_list) < period:
            return np.mean(tr_list) if tr_list else 0.0
        
        return np.mean(tr_list[-period:])
    
    def _calculate_stdev(self, closes: List[float], period: int) -> float:
        """Calculate standard deviation."""
        if len(closes) < period:
            return 0.0
        return np.std(closes[-period:])
    
    def _calculate_linreg_slope(self, closes: List[float], period: int) -> float:
        """Calculate linear regression slope."""
        if len(closes) < period:
            return 0.0
        
        y = closes[-period:]
        x = list(range(period))
        
        n = period
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(xi ** 2 for xi in x)
        
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 0.0
        
        slope = abs((n * sum_xy - sum_x * sum_y) / denominator) / 2
        return slope
    
    def _calculate_slope(self, highs: List[float], lows: List[float], 
                         closes: List[float]) -> float:
        """Calculate trendline slope based on selected method."""
        if self.calc_method == SlopeMethod.ATR:
            atr = self._calculate_atr(highs, lows, closes, self.length)
            return (atr / self.length) * self.slope_mult
        elif self.calc_method == SlopeMethod.STDEV:
            stdev = self._calculate_stdev(closes, self.length)
            return (stdev / self.length) * self.slope_mult
        else:  # LINREG
            return self._calculate_linreg_slope(closes, self.length) * self.slope_mult
    
    def analyze(self, highs: List[float], lows: List[float], 
                closes: List[float]) -> TrendlineSignal:
        """
        Analyze price data for trendline breakouts.
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            
        Returns:
            TrendlineSignal with breakout info and trendline levels
        """
        if len(closes) < self.length * 2 + 1:
            return TrendlineSignal(
                breakout=BreakoutType.NONE,
                upper_trendline=0,
                lower_trendline=0,
                slope_upper=0,
                slope_lower=0,
                pivot_high=None,
                pivot_low=None,
                confidence=0
            )
        
        # Current bar index (analyzing the latest complete bar)
        idx = len(closes) - self.length - 1
        
        # Detect pivots
        ph = self._pivot_high(highs, idx)
        pl = self._pivot_low(lows, idx)
        
        # Calculate slope
        slope = self._calculate_slope(highs, lows, closes)
        
        # Update slopes on new pivots
        if ph is not None:
            self.slope_ph = slope
        if pl is not None:
            self.slope_pl = slope
        
        # Update trendlines
        if ph is not None:
            self.upper = ph
        else:
            self.upper = self.upper - self.slope_ph if self.upper > 0 else closes[-1]
        
        if pl is not None:
            self.lower = pl
        else:
            self.lower = self.lower + self.slope_pl if self.lower > 0 else closes[-1]
        
        # Current price
        current_close = closes[-1]
        
        # Calculate trendline values at current bar
        upper_at_current = self.upper - self.slope_ph * self.length
        lower_at_current = self.lower + self.slope_pl * self.length
        
        # Previous position states
        prev_upos = self.upos
        prev_dnos = self.dnos
        
        # Update position states
        if ph is not None:
            self.upos = 0
        elif current_close > upper_at_current:
            self.upos = 1
        
        if pl is not None:
            self.dnos = 0
        elif current_close < lower_at_current:
            self.dnos = 1
        
        # Detect breakouts
        breakout = BreakoutType.NONE
        confidence = 0.0
        
        # Bullish breakout: price crosses above down trendline
        if self.upos > prev_upos:
            breakout = BreakoutType.BULLISH
            # Confidence based on how far above trendline
            if upper_at_current > 0:
                confidence = min(0.95, 0.6 + (current_close - upper_at_current) / upper_at_current * 10)
        
        # Bearish breakout: price crosses below up trendline
        if self.dnos > prev_dnos:
            breakout = BreakoutType.BEARISH
            # Confidence based on how far below trendline
            if lower_at_current > 0:
                confidence = min(0.95, 0.6 + (lower_at_current - current_close) / lower_at_current * 10)
        
        return TrendlineSignal(
            breakout=breakout,
            upper_trendline=upper_at_current,
            lower_trendline=lower_at_current,
            slope_upper=self.slope_ph,
            slope_lower=self.slope_pl,
            pivot_high=ph,
            pivot_low=pl,
            confidence=confidence
        )
    
    def reset(self):
        """Reset state variables."""
        self.upper = 0.0
        self.lower = 0.0
        self.slope_ph = 0.0
        self.slope_pl = 0.0
        self.upos = 0
        self.dnos = 0
