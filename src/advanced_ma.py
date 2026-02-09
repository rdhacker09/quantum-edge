"""
📊 Advanced Moving Averages & Crossover System
==============================================
Python implementation of advanced MA types and crossover price calculations.

Inspired by CT Moving Average Crossover Indicator
Original PineScript by The_Caretaker
License: Mozilla Public License 2.0
https://mozilla.org/MPL/2.0/
© The_Caretaker

Includes:
- Hull Moving Average (HMA) - Alan Hull
- Least Squares Moving Average (LSMA)
- Weighted Moving Average (WMA)
- Crossover price calculations

Ported to Python for QuantumEdge Trading Bot
Credits preserved as required by license.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class MAType(Enum):
    SMA = "SMA"    # Simple Moving Average
    EMA = "EMA"    # Exponential Moving Average
    WMA = "WMA"    # Weighted Moving Average
    HMA = "HMA"    # Hull Moving Average
    LSMA = "LSMA"  # Least Squares Moving Average
    RMA = "RMA"    # Relative Moving Average (Wilder's)


@dataclass 
class MACrossoverSignal:
    fast_ma: float
    slow_ma: float
    crossover_price: float  # Price needed to trigger crossover
    is_bullish_cross: bool  # True if fast > slow
    distance_to_cross: float  # How far current price is from crossover
    cross_direction: str  # "above" or "below" needed to cross


class AdvancedMA:
    """
    Advanced Moving Average Calculator
    
    Implements multiple MA types including HMA for faster trend detection
    and crossover price calculations for smarter entries.
    
    HMA formula by Alan Hull:
    HMA = WMA(2*WMA(n/2) − WMA(n)), sqrt(n))
    """
    
    @staticmethod
    def sma(data: List[float], period: int) -> List[float]:
        """Simple Moving Average."""
        if len(data) < period:
            return [data[-1]] * len(data)
        
        result = [None] * (period - 1)
        for i in range(period - 1, len(data)):
            result.append(sum(data[i-period+1:i+1]) / period)
        return result
    
    @staticmethod
    def ema(data: List[float], period: int) -> List[float]:
        """Exponential Moving Average."""
        if len(data) < period:
            return [data[-1]] * len(data)
        
        multiplier = 2 / (period + 1)
        result = [sum(data[:period]) / period]
        
        for i in range(period, len(data)):
            ema_val = (data[i] * multiplier) + (result[-1] * (1 - multiplier))
            result.append(ema_val)
        
        return [None] * (period - 1) + result
    
    @staticmethod
    def rma(data: List[float], period: int) -> List[float]:
        """
        Relative Moving Average (Wilder's Smoothing)
        Used in RSI, ATR calculations.
        """
        if len(data) < period:
            return [data[-1]] * len(data)
        
        alpha = 1 / period
        result = [sum(data[:period]) / period]
        
        for i in range(period, len(data)):
            rma_val = alpha * data[i] + (1 - alpha) * result[-1]
            result.append(rma_val)
        
        return [None] * (period - 1) + result
    
    @staticmethod
    def wma(data: List[float], period: int) -> List[float]:
        """
        Weighted Moving Average
        Gives more weight to recent prices.
        """
        if len(data) < period:
            return [data[-1]] * len(data)
        
        result = [None] * (period - 1)
        weights = list(range(1, period + 1))
        weight_sum = sum(weights)
        
        for i in range(period - 1, len(data)):
            window = data[i-period+1:i+1]
            weighted_sum = sum(w * p for w, p in zip(weights, window))
            result.append(weighted_sum / weight_sum)
        
        return result
    
    @staticmethod
    def hma(data: List[float], period: int) -> List[float]:
        """
        Hull Moving Average
        By Alan Hull - reduces lag significantly.
        
        Formula: HMA = WMA(2*WMA(n/2) − WMA(n), sqrt(n))
        """
        if len(data) < period:
            return [data[-1]] * len(data)
        
        half_period = max(1, period // 2)
        sqrt_period = max(1, int(np.sqrt(period)))
        
        # Calculate WMA of half period
        wma_half = AdvancedMA.wma(data, half_period)
        
        # Calculate WMA of full period
        wma_full = AdvancedMA.wma(data, period)
        
        # Calculate 2*WMA(half) - WMA(full)
        diff = []
        for i in range(len(data)):
            if wma_half[i] is None or wma_full[i] is None:
                diff.append(None)
            else:
                diff.append(2 * wma_half[i] - wma_full[i])
        
        # Filter out None values for final WMA
        valid_diff = [d for d in diff if d is not None]
        if len(valid_diff) < sqrt_period:
            return [data[-1]] * len(data)
        
        # Calculate final HMA
        hma_final = AdvancedMA.wma(valid_diff, sqrt_period)
        
        # Pad with None to match original length
        padding = len(data) - len(hma_final)
        return [None] * padding + hma_final
    
    @staticmethod
    def lsma(data: List[float], period: int) -> List[float]:
        """
        Least Squares Moving Average (Linear Regression)
        Fits a line to the data and returns endpoint.
        """
        if len(data) < period:
            return [data[-1]] * len(data)
        
        result = [None] * (period - 1)
        
        for i in range(period - 1, len(data)):
            window = data[i-period+1:i+1]
            x = np.arange(period)
            
            # Linear regression
            n = period
            sum_x = np.sum(x)
            sum_y = np.sum(window)
            sum_xy = np.sum(x * np.array(window))
            sum_x2 = np.sum(x ** 2)
            
            denominator = n * sum_x2 - sum_x ** 2
            if denominator == 0:
                result.append(window[-1])
                continue
            
            slope = (n * sum_xy - sum_x * sum_y) / denominator
            intercept = (sum_y - slope * sum_x) / n
            
            # Value at the end of the line
            result.append(intercept + slope * (period - 1))
        
        return result
    
    @staticmethod
    def calculate(data: List[float], period: int, ma_type: MAType) -> List[float]:
        """Calculate any MA type."""
        if ma_type == MAType.SMA:
            return AdvancedMA.sma(data, period)
        elif ma_type == MAType.EMA:
            return AdvancedMA.ema(data, period)
        elif ma_type == MAType.WMA:
            return AdvancedMA.wma(data, period)
        elif ma_type == MAType.HMA:
            return AdvancedMA.hma(data, period)
        elif ma_type == MAType.LSMA:
            return AdvancedMA.lsma(data, period)
        elif ma_type == MAType.RMA:
            return AdvancedMA.rma(data, period)
        else:
            return AdvancedMA.sma(data, period)


class MACrossoverCalculator:
    """
    Calculate exact price needed to trigger MA crossover.
    
    Based on CT Moving Average Crossover Indicator by The_Caretaker
    Useful for setting limit orders at optimal entry points.
    """
    
    @staticmethod
    def _sma_sma_cross(prices: List[float], period1: int, period2: int) -> float:
        """Calculate crossover price between two SMAs."""
        if len(prices) < max(period1, period2):
            return 0.0
        
        sum1 = sum(prices[-(period1-1):]) if period1 > 1 else 0
        sum2 = sum(prices[-(period2-1):]) if period2 > 1 else 0
        
        if period1 == period2:
            return 0.0
        
        cross_price = (sum1 * period2 - sum2 * period1) / (period1 - period2)
        return max(0, cross_price)
    
    @staticmethod
    def _ema_ema_cross(prev_ema1: float, prev_ema2: float, 
                       period1: int, period2: int) -> float:
        """Calculate crossover price between two EMAs."""
        alpha1 = 2 / (period1 + 1)
        alpha2 = 2 / (period2 + 1)
        
        if alpha1 == alpha2:
            return 0.0
        
        cross_price = ((1 - alpha2) * prev_ema2 - (1 - alpha1) * prev_ema1) / (alpha1 - alpha2)
        return max(0, cross_price)
    
    @staticmethod
    def _sma_ema_cross(prices: List[float], sma_period: int, 
                       prev_ema: float, ema_period: int) -> float:
        """Calculate crossover price between SMA and EMA."""
        if len(prices) < sma_period:
            return 0.0
        
        alpha = 2 / (ema_period + 1)
        prev_sum = sum(prices[-(sma_period-1):]) if sma_period > 1 else 0
        
        denominator = 1 - sma_period * alpha
        if denominator == 0:
            return 0.0
        
        cross_price = (sma_period * (1 - alpha) * prev_ema - prev_sum) / denominator
        return max(0, cross_price)
    
    @staticmethod
    def calculate_crossover_price(prices: List[float], 
                                   fast_period: int, fast_type: MAType,
                                   slow_period: int, slow_type: MAType,
                                   fast_ma_current: float = None,
                                   slow_ma_current: float = None) -> MACrossoverSignal:
        """
        Calculate the price needed for MA crossover.
        
        Args:
            prices: Historical prices
            fast_period: Fast MA period
            fast_type: Fast MA type
            slow_period: Slow MA period
            slow_type: Slow MA type
            fast_ma_current: Current fast MA value (optional)
            slow_ma_current: Current slow MA value (optional)
            
        Returns:
            MACrossoverSignal with crossover details
        """
        if len(prices) < max(fast_period, slow_period) + 1:
            return MACrossoverSignal(
                fast_ma=0, slow_ma=0, crossover_price=0,
                is_bullish_cross=False, distance_to_cross=0,
                cross_direction="none"
            )
        
        # Calculate current MAs if not provided
        if fast_ma_current is None:
            fast_ma_list = AdvancedMA.calculate(prices, fast_period, fast_type)
            fast_ma_current = fast_ma_list[-1] or prices[-1]
        
        if slow_ma_current is None:
            slow_ma_list = AdvancedMA.calculate(prices, slow_period, slow_type)
            slow_ma_current = slow_ma_list[-1] or prices[-1]
        
        # Get previous MA values
        fast_ma_prev_list = AdvancedMA.calculate(prices[:-1], fast_period, fast_type)
        slow_ma_prev_list = AdvancedMA.calculate(prices[:-1], slow_period, slow_type)
        
        fast_ma_prev = fast_ma_prev_list[-1] if fast_ma_prev_list[-1] else prices[-2]
        slow_ma_prev = slow_ma_prev_list[-1] if slow_ma_prev_list[-1] else prices[-2]
        
        # Calculate crossover price based on MA types
        crossover_price = 0.0
        
        if fast_type == MAType.SMA and slow_type == MAType.SMA:
            crossover_price = MACrossoverCalculator._sma_sma_cross(
                prices[:-1], fast_period, slow_period
            )
        elif fast_type == MAType.EMA and slow_type == MAType.EMA:
            crossover_price = MACrossoverCalculator._ema_ema_cross(
                fast_ma_prev, slow_ma_prev, fast_period, slow_period
            )
        elif fast_type == MAType.SMA and slow_type == MAType.EMA:
            crossover_price = MACrossoverCalculator._sma_ema_cross(
                prices[:-1], fast_period, slow_ma_prev, slow_period
            )
        elif fast_type == MAType.EMA and slow_type == MAType.SMA:
            crossover_price = MACrossoverCalculator._sma_ema_cross(
                prices[:-1], slow_period, fast_ma_prev, fast_period
            )
        else:
            # For other combinations, estimate based on current values
            if fast_ma_current != slow_ma_current:
                # Simple linear interpolation estimate
                crossover_price = (fast_ma_current + slow_ma_current) / 2
        
        # Determine current state and direction needed
        is_bullish = fast_ma_current > slow_ma_current
        current_price = prices[-1]
        
        if crossover_price > 0:
            if is_bullish:
                cross_direction = "below"  # Need to close below to cross bearish
                distance = current_price - crossover_price
            else:
                cross_direction = "above"  # Need to close above to cross bullish
                distance = crossover_price - current_price
        else:
            cross_direction = "none"
            distance = 0
        
        return MACrossoverSignal(
            fast_ma=fast_ma_current,
            slow_ma=slow_ma_current,
            crossover_price=crossover_price,
            is_bullish_cross=is_bullish,
            distance_to_cross=distance,
            cross_direction=cross_direction
        )
