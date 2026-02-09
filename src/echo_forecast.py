"""
🔮 Echo Forecast - Pattern-Based Price Prediction
=================================================
Python implementation of similarity-based price forecasting.

Original PineScript by LuxAlgo
https://www.tradingview.com/script/...
License: Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
https://creativecommons.org/licenses/by-nc-sa/4.0/
© LuxAlgo

The algorithm:
1. Takes a reference window (recent price action)
2. Searches historical data for similar patterns
3. Projects future price based on what happened after similar patterns

Ported to Python for QuantumEdge Trading Bot
Credits preserved as required by license.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ForecastMode(Enum):
    SIMILARITY = "similarity"      # Find most similar pattern
    DISSIMILARITY = "dissimilarity"  # Find most different pattern (contrarian)


class ForecastConstruction(Enum):
    CUMULATIVE = "cumulative"  # Add changes cumulatively
    MEAN = "mean"              # Use mean + change
    LINREG = "linreg"          # Linear regression + change


@dataclass
class EchoForecastResult:
    forecast_prices: List[float]  # Predicted future prices
    correlation: float             # How similar the matched pattern is (-1 to 1)
    matched_offset: int           # Where in history the similar pattern was found
    confidence: float             # Forecast confidence (0-1)
    direction: str                # "bullish", "bearish", "neutral"
    expected_change_pct: float    # Expected % change


class EchoForecast:
    """
    Echo Forecast - Find similar historical patterns to predict future price.
    
    Original concept by LuxAlgo (TradingView)
    Python implementation for algorithmic trading
    
    Uses correlation analysis to find the most similar historical
    price pattern and projects future movement based on what
    happened after that pattern.
    """
    
    def __init__(self, evaluation_window: int = 50, forecast_window: int = 50,
                 mode: ForecastMode = ForecastMode.SIMILARITY,
                 construction: ForecastConstruction = ForecastConstruction.CUMULATIVE):
        """
        Initialize Echo Forecast.
        
        Args:
            evaluation_window: How far back to search for patterns (default: 50)
            forecast_window: How many bars to forecast (default: 50)
            mode: SIMILARITY (find similar) or DISSIMILARITY (find opposite)
            construction: How to build the forecast
        """
        self.evaluation_window = evaluation_window
        self.forecast_window = forecast_window
        self.mode = mode
        self.construction = construction
    
    def _calculate_correlation(self, a: List[float], b: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(a) != len(b) or len(a) < 2:
            return 0.0
        
        a_arr = np.array(a)
        b_arr = np.array(b)
        
        a_mean = np.mean(a_arr)
        b_mean = np.mean(b_arr)
        
        a_std = np.std(a_arr)
        b_std = np.std(b_arr)
        
        if a_std == 0 or b_std == 0:
            return 0.0
        
        covariance = np.mean((a_arr - a_mean) * (b_arr - b_mean))
        correlation = covariance / (a_std * b_std)
        
        return correlation
    
    def _linear_regression(self, y: List[float]) -> Tuple[float, float]:
        """Calculate linear regression slope and intercept."""
        n = len(y)
        x = np.arange(n)
        
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * np.array(y))
        sum_x2 = np.sum(x ** 2)
        
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 0.0, y[-1] if y else 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        
        return slope, intercept
    
    def forecast(self, prices: List[float]) -> EchoForecastResult:
        """
        Generate price forecast based on similar historical patterns.
        
        Args:
            prices: Historical price data (at least evaluation_window + forecast_window * 2)
            
        Returns:
            EchoForecastResult with predicted prices and metadata
        """
        min_required = self.evaluation_window + self.forecast_window * 2 + 1
        
        if len(prices) < min_required:
            return EchoForecastResult(
                forecast_prices=[prices[-1]] * self.forecast_window,
                correlation=0.0,
                matched_offset=0,
                confidence=0.0,
                direction="neutral",
                expected_change_pct=0.0
            )
        
        # Calculate price changes (differences)
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        # Reference window (most recent price action)
        ref_start = len(prices) - self.forecast_window
        reference = prices[ref_start:]
        
        # Search for best matching pattern
        best_correlation = None
        best_offset = 0
        
        for i in range(self.evaluation_window):
            # Evaluation window
            eval_start = ref_start - self.forecast_window - i
            eval_end = eval_start + self.forecast_window
            
            if eval_start < 0:
                break
            
            evaluation = prices[eval_start:eval_end]
            
            # Calculate correlation
            correlation = self._calculate_correlation(reference, evaluation)
            
            # Find best match based on mode
            if self.mode == ForecastMode.SIMILARITY:
                if best_correlation is None or correlation >= best_correlation:
                    best_correlation = correlation
                    best_offset = i
            else:  # DISSIMILARITY
                if best_correlation is None or correlation <= best_correlation:
                    best_correlation = correlation
                    best_offset = i
        
        if best_correlation is None:
            best_correlation = 0.0
        
        # Build forecast using the matched pattern
        forecast_prices = []
        current_price = prices[-1]
        
        # Get the changes that occurred after the matched pattern
        match_start = ref_start - self.forecast_window - best_offset
        
        for i in range(self.forecast_window):
            change_idx = match_start + self.forecast_window + i
            
            if change_idx < len(changes):
                change = changes[change_idx]
            else:
                change = 0
            
            if self.construction == ForecastConstruction.MEAN:
                current_price = np.mean(reference) + change
            elif self.construction == ForecastConstruction.LINREG:
                slope, intercept = self._linear_regression(reference)
                current_price = intercept + slope * (len(reference) + i) + change
            else:  # CUMULATIVE
                current_price += change
            
            forecast_prices.append(current_price)
        
        # Calculate expected change
        if forecast_prices:
            expected_change = forecast_prices[-1] - prices[-1]
            expected_change_pct = (expected_change / prices[-1]) * 100
        else:
            expected_change_pct = 0.0
        
        # Determine direction
        if expected_change_pct > 0.5:
            direction = "bullish"
        elif expected_change_pct < -0.5:
            direction = "bearish"
        else:
            direction = "neutral"
        
        # Confidence based on correlation strength
        confidence = min(0.95, abs(best_correlation) * 0.8 + 0.1)
        
        return EchoForecastResult(
            forecast_prices=forecast_prices,
            correlation=best_correlation,
            matched_offset=best_offset,
            confidence=confidence,
            direction=direction,
            expected_change_pct=expected_change_pct
        )
    
    def get_short_term_bias(self, prices: List[float], bars: int = 5) -> Tuple[str, float]:
        """
        Get short-term directional bias from forecast.
        
        Args:
            prices: Historical prices
            bars: How many bars ahead to look (default: 5)
            
        Returns:
            Tuple of (direction, confidence)
        """
        result = self.forecast(prices)
        
        if len(result.forecast_prices) < bars:
            return "neutral", 0.0
        
        short_term_change = result.forecast_prices[bars-1] - prices[-1]
        short_term_pct = (short_term_change / prices[-1]) * 100
        
        if short_term_pct > 0.3:
            return "bullish", result.confidence
        elif short_term_pct < -0.3:
            return "bearish", result.confidence
        else:
            return "neutral", result.confidence * 0.5
