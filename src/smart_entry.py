"""
🎯 Smart Entry System
=====================
Optimizes entry timing:
- Pullback entries in trends
- Breakout confirmation
- Liquidity-aware entries
- Session timing optimization
"""

import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import numpy as np


class EntryType(Enum):
    IMMEDIATE = "immediate"
    PULLBACK = "pullback"
    BREAKOUT_CONFIRM = "breakout_confirm"
    LIMIT_ORDER = "limit_order"
    SCALE_IN = "scale_in"


@dataclass
class EntryPlan:
    entry_type: EntryType
    suggested_price: float
    price_tolerance: float  # How far from suggested to still enter
    wait_candles: int  # How many candles to wait
    scale_levels: List[Tuple[float, float]]  # [(price, size_pct), ...]
    reason: str
    urgency: float  # 0-1


class SmartEntryOptimizer:
    """Optimizes trade entry timing."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Optimal trading sessions (UTC)
        self.optimal_sessions = {
            "asia": (0, 8),      # 00:00 - 08:00 UTC
            "europe": (8, 16),   # 08:00 - 16:00 UTC
            "us": (13, 21),      # 13:00 - 21:00 UTC (overlap with Europe)
        }
    
    def get_session_multiplier(self) -> Tuple[float, str]:
        """Get position size multiplier based on current session."""
        hour = datetime.now(timezone.utc).hour
        
        # US/Europe overlap is most liquid
        if 13 <= hour <= 16:
            return 1.2, "US/EU overlap - high liquidity"
        # Europe session
        elif 8 <= hour <= 13:
            return 1.0, "Europe session"
        # US session
        elif 16 <= hour <= 21:
            return 1.0, "US session"
        # Asia session
        elif 0 <= hour <= 8:
            return 0.8, "Asia session - lower liquidity"
        # Off hours
        else:
            return 0.6, "Off-peak hours"
    
    def calculate_pullback_level(self, closes: List[float], highs: List[float],
                                  lows: List[float], side: str) -> float:
        """Calculate ideal pullback entry level."""
        if len(closes) < 20:
            return closes[-1]
        
        current = closes[-1]
        
        # Calculate recent swing points
        recent_highs = highs[-10:]
        recent_lows = lows[-10:]
        
        if side == "Buy":
            # For longs, wait for pullback to support
            # Use 38.2% Fib from recent low to current
            recent_low = min(recent_lows)
            recent_high = max(recent_highs)
            fib_382 = recent_high - (recent_high - recent_low) * 0.382
            
            # Also consider EMA as dynamic support
            ema_20 = self._calculate_ema(closes, 20)[-1]
            
            # Use the higher of the two (more conservative)
            pullback_level = max(fib_382, ema_20)
            return pullback_level
        else:
            # For shorts, wait for bounce to resistance
            recent_low = min(recent_lows)
            recent_high = max(recent_highs)
            fib_382 = recent_low + (recent_high - recent_low) * 0.382
            
            ema_20 = self._calculate_ema(closes, 20)[-1]
            
            pullback_level = min(fib_382, ema_20)
            return pullback_level
    
    def _calculate_ema(self, data: List[float], period: int) -> List[float]:
        """Simple EMA calculation."""
        result = [data[0]]
        multiplier = 2 / (period + 1)
        for i in range(1, len(data)):
            ema = (data[i] * multiplier) + (result[-1] * (1 - multiplier))
            result.append(ema)
        return result
    
    def calculate_breakout_confirmation(self, closes: List[float], 
                                        volumes: List[float],
                                        breakout_level: float,
                                        side: str) -> Tuple[bool, str]:
        """Check if breakout is confirmed."""
        if len(closes) < 5:
            return False, "Insufficient data"
        
        current = closes[-1]
        avg_volume = np.mean(volumes[-20:-1])
        current_volume = volumes[-1]
        
        # Breakout criteria
        price_beyond = (current > breakout_level * 1.005 if side == "Buy" 
                       else current < breakout_level * 0.995)
        volume_confirm = current_volume > avg_volume * 1.3
        
        # Check for multiple closes beyond level
        closes_beyond = sum(1 for c in closes[-3:] if 
                          (c > breakout_level if side == "Buy" else c < breakout_level))
        
        if price_beyond and volume_confirm and closes_beyond >= 2:
            return True, "Strong breakout confirmation"
        elif price_beyond and closes_beyond >= 2:
            return True, "Breakout confirmed (watch for volume)"
        elif price_beyond:
            return False, "Awaiting confirmation (need more closes)"
        
        return False, "No breakout yet"
    
    def should_scale_in(self, current_price: float, entry_price: float,
                       atr: float, side: str) -> Tuple[bool, float]:
        """Determine if we should add to position."""
        
        price_diff = current_price - entry_price if side == "Buy" else entry_price - current_price
        atr_moves = price_diff / atr
        
        # Scale in after 1 ATR move in our favor
        if atr_moves >= 1.0:
            # Add 50% at 1 ATR, 30% at 2 ATR
            if atr_moves >= 2.0:
                return True, 0.30
            return True, 0.50
        
        return False, 0
    
    def plan_entry(self, symbol: str, side: str, signal_strength: float,
                   closes: List[float], highs: List[float], lows: List[float],
                   volumes: List[float], regime: str = "ranging") -> EntryPlan:
        """Create optimized entry plan."""
        
        current_price = closes[-1]
        session_mult, session_note = self.get_session_multiplier()
        
        # Default immediate entry
        if signal_strength > 0.85:
            # Very strong signal - enter now
            return EntryPlan(
                entry_type=EntryType.IMMEDIATE,
                suggested_price=current_price,
                price_tolerance=0.002,
                wait_candles=0,
                scale_levels=[],
                reason=f"Strong signal ({signal_strength:.0%}) - immediate entry. {session_note}",
                urgency=0.9
            )
        
        # Trending market - use pullback entry
        if regime in ["trending_up", "trending_down"]:
            pullback_price = self.calculate_pullback_level(closes, highs, lows, side)
            distance_pct = abs(pullback_price - current_price) / current_price
            
            if distance_pct < 0.005:
                # Already at pullback level
                return EntryPlan(
                    entry_type=EntryType.IMMEDIATE,
                    suggested_price=current_price,
                    price_tolerance=0.003,
                    wait_candles=0,
                    scale_levels=[],
                    reason=f"At pullback level - enter now. {session_note}",
                    urgency=0.8
                )
            else:
                return EntryPlan(
                    entry_type=EntryType.PULLBACK,
                    suggested_price=pullback_price,
                    price_tolerance=0.005,
                    wait_candles=10,  # Wait up to 10 candles
                    scale_levels=[(pullback_price, 0.7), (pullback_price * 0.995 if side == "Buy" else pullback_price * 1.005, 0.3)],
                    reason=f"Wait for pullback to {pullback_price:.2f} ({distance_pct:.1%} from current). {session_note}",
                    urgency=0.5
                )
        
        # Breakout regime
        if regime == "breakout":
            return EntryPlan(
                entry_type=EntryType.BREAKOUT_CONFIRM,
                suggested_price=current_price,
                price_tolerance=0.003,
                wait_candles=3,  # Wait for confirmation
                scale_levels=[(current_price, 0.5), (current_price * 1.01 if side == "Buy" else current_price * 0.99, 0.5)],
                reason=f"Breakout forming - enter on confirmation. {session_note}",
                urgency=0.6
            )
        
        # Volatile regime - use limit orders
        if regime == "volatile":
            # Place limit order at better price
            limit_price = current_price * 0.995 if side == "Buy" else current_price * 1.005
            return EntryPlan(
                entry_type=EntryType.LIMIT_ORDER,
                suggested_price=limit_price,
                price_tolerance=0.003,
                wait_candles=15,
                scale_levels=[],
                reason=f"High volatility - limit order at {limit_price:.2f}. {session_note}",
                urgency=0.4
            )
        
        # Default ranging market - scale in
        return EntryPlan(
            entry_type=EntryType.SCALE_IN,
            suggested_price=current_price,
            price_tolerance=0.004,
            wait_candles=0,
            scale_levels=[(current_price, 0.5), (current_price * 0.99 if side == "Buy" else current_price * 1.01, 0.3), (current_price * 0.98 if side == "Buy" else current_price * 1.02, 0.2)],
            reason=f"Ranging market - scale in entry. {session_note}",
            urgency=0.6
        )
