"""
🧠 ML Signal Enhancement
========================
Uses machine learning to enhance signal quality:
- Feature engineering
- Signal confidence scoring
- Pattern recognition
- Performance prediction
"""

import logging
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


@dataclass
class MLSignal:
    direction: str  # "long", "short", "neutral"
    confidence: float
    win_probability: float
    expected_rr: float  # Risk/reward
    features_used: List[str]


class MLSignalEnhancer:
    """ML-based signal enhancement."""
    
    def __init__(self, model_dir: str = "models"):
        self.logger = logging.getLogger(__name__)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.model = None
        self.trained = False
        self.feature_names = [
            "rsi", "rsi_slope", "macd_hist", "macd_hist_slope",
            "bb_position", "atr_pct", "volume_ratio",
            "price_vs_ema20", "price_vs_ema50", "trend_strength",
            "hour_of_day", "day_of_week"
        ]
        
        self._load_model()
    
    def _load_model(self):
        """Load saved model if exists."""
        model_path = self.model_dir / "signal_model.json"
        
        if model_path.exists() and SKLEARN_AVAILABLE:
            try:
                # For simplicity, we'll retrain on startup
                # In production, use joblib to save/load sklearn models
                self.trained = False
            except Exception as e:
                self.logger.warning(f"Could not load model: {e}")
    
    def extract_features(self, klines: List[Dict], indicators: Dict) -> np.ndarray:
        """Extract features from market data."""
        
        closes = [k['close'] for k in klines]
        volumes = [k['volume'] for k in klines]
        
        current_price = closes[-1]
        
        features = []
        
        # RSI features
        rsi = indicators.get('rsi', [50])[-1] or 50
        rsi_prev = indicators.get('rsi', [50, 50])[-2] if len(indicators.get('rsi', [])) > 1 else rsi
        features.append(rsi)
        features.append(rsi - rsi_prev)  # RSI slope
        
        # MACD features
        macd_hist = indicators.get('macd_histogram', [0])[-1] or 0
        macd_hist_prev = indicators.get('macd_histogram', [0, 0])[-2] if len(indicators.get('macd_histogram', [])) > 1 else macd_hist
        features.append(macd_hist / current_price * 10000)  # Normalized
        features.append((macd_hist - macd_hist_prev) / current_price * 10000)
        
        # Bollinger position (0-1 scale)
        bb_upper = indicators.get('bb_upper', [current_price])[-1] or current_price * 1.02
        bb_lower = indicators.get('bb_lower', [current_price])[-1] or current_price * 0.98
        bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        features.append(bb_position)
        
        # ATR percentage
        atr = indicators.get('atr', [current_price * 0.02])[-1] or current_price * 0.02
        features.append(atr / current_price * 100)
        
        # Volume ratio
        avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else volumes[-1]
        features.append(volumes[-1] / avg_volume if avg_volume > 0 else 1)
        
        # Price vs EMAs
        ema20 = indicators.get('ema20', [current_price])[-1] or current_price
        ema50 = indicators.get('ema50', [current_price])[-1] or current_price
        features.append((current_price - ema20) / ema20 * 100)
        features.append((current_price - ema50) / ema50 * 100)
        
        # Trend strength (EMA20 vs EMA50)
        features.append((ema20 - ema50) / ema50 * 100)
        
        # Time features
        from datetime import datetime
        now = datetime.utcnow()
        features.append(now.hour)
        features.append(now.weekday())
        
        return np.array(features).reshape(1, -1)
    
    def train_model(self, training_data: List[Dict]):
        """Train the ML model on historical data."""
        
        if not SKLEARN_AVAILABLE:
            self.logger.warning("sklearn not available - ML disabled")
            return
        
        if len(training_data) < 100:
            self.logger.warning("Insufficient training data")
            return
        
        X = []
        y = []
        
        for sample in training_data:
            X.append(sample['features'])
            y.append(1 if sample['outcome'] == 'win' else 0)
        
        X = np.array(X)
        y = np.array(y)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        self.model.fit(X_scaled, y)
        self.trained = True
        
        self.logger.info(f"✅ ML model trained on {len(training_data)} samples")
    
    def enhance_signal(self, klines: List[Dict], indicators: Dict,
                       base_signal: str, base_confidence: float) -> MLSignal:
        """Enhance a trading signal with ML predictions."""
        
        # Extract features
        features = self.extract_features(klines, indicators)
        
        # If model not trained, return rule-based enhancement
        if not self.trained or not SKLEARN_AVAILABLE:
            return self._rule_based_enhancement(features[0], base_signal, base_confidence)
        
        # Get ML prediction
        features_scaled = self.scaler.transform(features)
        
        # Predict probability
        proba = self.model.predict_proba(features_scaled)[0]
        win_prob = proba[1]  # Probability of winning trade
        
        # Adjust confidence based on ML
        ml_confidence = base_confidence * 0.6 + win_prob * 0.4
        
        # Estimate expected R:R based on features
        expected_rr = self._estimate_rr(features[0], base_signal)
        
        return MLSignal(
            direction=base_signal,
            confidence=ml_confidence,
            win_probability=win_prob,
            expected_rr=expected_rr,
            features_used=self.feature_names
        )
    
    def _rule_based_enhancement(self, features: np.ndarray, 
                                base_signal: str, base_confidence: float) -> MLSignal:
        """Rule-based signal enhancement when ML not available."""
        
        rsi = features[0]
        bb_position = features[4]
        volume_ratio = features[6]
        trend_strength = features[9]
        
        confidence_adjustments = 0
        
        # RSI confirmation
        if base_signal == "long" and rsi < 40:
            confidence_adjustments += 0.1
        elif base_signal == "short" and rsi > 60:
            confidence_adjustments += 0.1
        
        # BB confirmation
        if base_signal == "long" and bb_position < 0.3:
            confidence_adjustments += 0.1
        elif base_signal == "short" and bb_position > 0.7:
            confidence_adjustments += 0.1
        
        # Volume confirmation
        if volume_ratio > 1.5:
            confidence_adjustments += 0.05
        
        # Trend alignment
        if base_signal == "long" and trend_strength > 0:
            confidence_adjustments += 0.05
        elif base_signal == "short" and trend_strength < 0:
            confidence_adjustments += 0.05
        
        final_confidence = min(0.95, base_confidence + confidence_adjustments)
        win_prob = 0.5 + (final_confidence - 0.5) * 0.5  # Rough estimate
        
        return MLSignal(
            direction=base_signal,
            confidence=final_confidence,
            win_probability=win_prob,
            expected_rr=2.0,  # Default 2:1
            features_used=["rsi", "bb_position", "volume_ratio", "trend_strength"]
        )
    
    def _estimate_rr(self, features: np.ndarray, signal: str) -> float:
        """Estimate expected risk/reward ratio."""
        
        atr_pct = features[5]
        trend_strength = features[9]
        
        base_rr = 2.0
        
        # Higher ATR = potentially higher RR
        if atr_pct > 3:
            base_rr += 0.5
        
        # Trend alignment increases RR
        if (signal == "long" and trend_strength > 1) or \
           (signal == "short" and trend_strength < -1):
            base_rr += 0.5
        
        return min(4.0, base_rr)
    
    def save_trade_outcome(self, features: np.ndarray, outcome: str):
        """Save trade outcome for future training."""
        
        data_file = self.model_dir / "training_data.json"
        
        data = []
        if data_file.exists():
            with open(data_file) as f:
                data = json.load(f)
        
        data.append({
            "features": features.tolist(),
            "outcome": outcome,
            "timestamp": str(datetime.now())
        })
        
        # Keep last 1000 samples
        data = data[-1000:]
        
        with open(data_file, 'w') as f:
            json.dump(data, f)
        
        # Retrain if we have enough data
        if len(data) >= 100 and len(data) % 50 == 0:
            self.train_model(data)
