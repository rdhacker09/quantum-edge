"""
📊 Order Flow Analysis
======================
Analyzes market microstructure:
- Funding rates (sentiment)
- Open interest changes
- Long/short ratio
- Liquidation data
- Buy/sell pressure
"""

import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class OrderFlowBias(Enum):
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


@dataclass
class OrderFlowAnalysis:
    bias: OrderFlowBias
    funding_rate: float
    funding_signal: str
    oi_change_pct: float
    oi_signal: str
    long_short_ratio: float
    ratio_signal: str
    score: int  # -100 to +100
    insights: List[str]


class OrderFlowAnalyzer:
    """Analyzes order flow data for trading signals."""
    
    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger(__name__)
        self._cache = {}
        self._cache_time = {}
    
    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Get current funding rate."""
        try:
            result = self.client.client.get_tickers(category="linear", symbol=symbol)
            if result['result']['list']:
                return float(result['result']['list'][0].get('fundingRate', 0))
        except Exception as e:
            self.logger.debug(f"Failed to get funding rate: {e}")
        return None
    
    def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """Get open interest data."""
        try:
            result = self.client.client.get_open_interest(
                category="linear",
                symbol=symbol,
                intervalTime="1h",
                limit=24
            )
            if result['result']['list']:
                data = result['result']['list']
                current_oi = float(data[0]['openInterest'])
                
                # Calculate 24h change
                if len(data) >= 24:
                    oi_24h_ago = float(data[-1]['openInterest'])
                    change_pct = ((current_oi - oi_24h_ago) / oi_24h_ago) * 100
                else:
                    change_pct = 0
                
                return {
                    'current': current_oi,
                    'change_24h_pct': change_pct
                }
        except Exception as e:
            self.logger.debug(f"Failed to get OI: {e}")
        return None
    
    def get_long_short_ratio(self, symbol: str) -> Optional[float]:
        """Get long/short ratio."""
        try:
            result = self.client.client.get_long_short_ratio(
                category="linear",
                symbol=symbol,
                period="1h",
                limit=1
            )
            if result['result']['list']:
                return float(result['result']['list'][0]['buyRatio'])
        except Exception as e:
            self.logger.debug(f"Failed to get L/S ratio: {e}")
        return None
    
    def analyze_funding(self, funding_rate: float) -> Tuple[str, int]:
        """Analyze funding rate for signals."""
        if funding_rate is None:
            return "neutral", 0
        
        # Funding rate thresholds (annualized)
        if funding_rate > 0.001:  # Very positive = overleveraged longs
            return "bearish_contrarian", -20
        elif funding_rate > 0.0005:  # Positive = slight long bias
            return "slight_bearish", -10
        elif funding_rate < -0.001:  # Very negative = overleveraged shorts
            return "bullish_contrarian", 20
        elif funding_rate < -0.0005:  # Negative = slight short bias
            return "slight_bullish", 10
        else:
            return "neutral", 0
    
    def analyze_oi(self, oi_data: Optional[Dict], price_change: float) -> Tuple[str, int]:
        """Analyze open interest changes."""
        if not oi_data:
            return "neutral", 0
        
        change = oi_data['change_24h_pct']
        
        # OI + Price analysis
        if change > 10:  # OI increasing significantly
            if price_change > 0:
                return "new_longs_entering", 15  # Bullish
            else:
                return "new_shorts_entering", -15  # Bearish
        elif change < -10:  # OI decreasing
            if price_change > 0:
                return "short_covering", 10  # Bullish (shorts closing)
            else:
                return "long_liquidation", -10  # Bearish
        elif change > 5:
            return "slight_interest_increase", 5 if price_change > 0 else -5
        elif change < -5:
            return "slight_interest_decrease", -5 if price_change < 0 else 5
        
        return "neutral", 0
    
    def analyze_ls_ratio(self, ratio: Optional[float]) -> Tuple[str, int]:
        """Analyze long/short ratio."""
        if ratio is None:
            return "neutral", 0
        
        # Ratio is buy ratio (0-1)
        if ratio > 0.65:  # Too many longs
            return "crowded_long", -15
        elif ratio > 0.55:
            return "slight_long_bias", -5
        elif ratio < 0.35:  # Too many shorts
            return "crowded_short", 15
        elif ratio < 0.45:
            return "slight_short_bias", 5
        
        return "balanced", 0
    
    def analyze(self, symbol: str, price_change_24h: float = 0) -> OrderFlowAnalysis:
        """Full order flow analysis."""
        insights = []
        total_score = 0
        
        # Get data
        funding = self.get_funding_rate(symbol)
        oi_data = self.get_open_interest(symbol)
        ls_ratio = self.get_long_short_ratio(symbol)
        
        # Analyze components
        funding_signal, funding_score = self.analyze_funding(funding)
        total_score += funding_score
        
        oi_signal, oi_score = self.analyze_oi(oi_data, price_change_24h)
        total_score += oi_score
        
        ratio_signal, ratio_score = self.analyze_ls_ratio(ls_ratio)
        total_score += ratio_score
        
        # Generate insights
        if funding and abs(funding) > 0.0005:
            if funding > 0:
                insights.append(f"⚠️ High positive funding ({funding*100:.3f}%) - longs paying shorts")
            else:
                insights.append(f"💡 Negative funding ({funding*100:.3f}%) - shorts paying longs")
        
        if oi_data and abs(oi_data['change_24h_pct']) > 5:
            direction = "📈" if oi_data['change_24h_pct'] > 0 else "📉"
            insights.append(f"{direction} OI changed {oi_data['change_24h_pct']:.1f}% in 24h")
        
        if ls_ratio and (ls_ratio > 0.6 or ls_ratio < 0.4):
            if ls_ratio > 0.6:
                insights.append(f"🔴 Crowded long ({ls_ratio*100:.0f}% longs) - contrarian short signal")
            else:
                insights.append(f"🟢 Crowded short ({(1-ls_ratio)*100:.0f}% shorts) - contrarian long signal")
        
        # Determine overall bias
        if total_score >= 30:
            bias = OrderFlowBias.STRONG_BULLISH
        elif total_score >= 15:
            bias = OrderFlowBias.BULLISH
        elif total_score <= -30:
            bias = OrderFlowBias.STRONG_BEARISH
        elif total_score <= -15:
            bias = OrderFlowBias.BEARISH
        else:
            bias = OrderFlowBias.NEUTRAL
        
        return OrderFlowAnalysis(
            bias=bias,
            funding_rate=funding or 0,
            funding_signal=funding_signal,
            oi_change_pct=oi_data['change_24h_pct'] if oi_data else 0,
            oi_signal=oi_signal,
            long_short_ratio=ls_ratio or 0.5,
            ratio_signal=ratio_signal,
            score=total_score,
            insights=insights
        )
