#!/usr/bin/env python3
"""
🤖 Bybit AI vs Human 1v1 Trading Bot - V2 PRO
=================================================
Advanced trading bot with:
- Market regime detection
- Order flow analysis  
- ML signal enhancement
- Smart entry optimization
- Advanced position management
- WebSocket real-time data
- Trading audit trail

Trading Requirements:
- Minimum 1,000 USDT capital
- Minimum 10 trades/day  
- Max recommended leverage: 15x
- Real capital, live market (MAINNET)

Usage:
    python bot_v2.py                # Run live trading
    python bot_v2.py --dry-run      # Simulate without real trades
    python bot_v2.py --debug        # Debug logging
    python bot_v2.py --status       # Show current status
"""

import sys
import os
import argparse
import logging
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

import yaml
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from pybit.unified_trading import HTTP
except ImportError:
    print("❌ Please install pybit: pip install pybit")
    sys.exit(1)

# Import our modules
from src.market_regime import MarketRegimeDetector, MarketRegime
from src.order_flow import OrderFlowAnalyzer, OrderFlowBias
from src.smart_entry import SmartEntryOptimizer, EntryType
from src.position_manager import PositionManager
from src.ml_model import MLSignalEnhancer

# New advanced indicators (Credits: LuxAlgo, The_Caretaker - see module headers)
from src.trendline_breaks import TrendlineBreaks, BreakoutType
from src.advanced_ma import AdvancedMA, MAType, MACrossoverCalculator
from src.echo_forecast import EchoForecast, ForecastMode


# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    def __init__(self, path: str = "config.yaml"):
        config_path = Path(__file__).parent / path
        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)
    
    def __getattr__(self, name):
        value = self._config.get(name, {})
        if isinstance(value, dict):
            return type('ConfigSection', (), value)()
        return value


# ============================================================
# ENHANCED BYBIT CLIENT
# ============================================================

class BybitClient:
    """Enhanced Bybit API client."""
    
    def __init__(self, config: Config, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        
        api_key = os.getenv('BYBIT_API_KEY')
        api_secret = os.getenv('BYBIT_API_SECRET')
        
        if not api_key or not api_secret:
            if not dry_run:
                raise ValueError("❌ BYBIT_API_KEY and BYBIT_API_SECRET required")
            api_key = "dummy"
            api_secret = "dummy"
        
        testnet = config.exchange.network != 'mainnet'
        self.client = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        
        network_str = "TESTNET" if testnet else "🔴 MAINNET"
        self.logger.info(f"📡 Connected to Bybit {network_str}")
    
    def get_balance(self) -> float:
        if self.dry_run:
            return 10000.0
        try:
            result = self.client.get_wallet_balance(accountType="UNIFIED", coin="USDT")
            for coin in result['result']['list'][0]['coin']:
                if coin['coin'] == 'USDT':
                    return float(coin['walletBalance'])
        except Exception as e:
            self.logger.error(f"Failed to get balance: {e}")
        return 0.0
    
    def get_positions(self) -> List[Dict]:
        if self.dry_run:
            return []
        positions = []
        try:
            result = self.client.get_positions(category="linear", settleCoin="USDT")
            for pos in result['result']['list']:
                if float(pos['size']) > 0:
                    positions.append({
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': float(pos['size']),
                        'entry_price': float(pos['avgPrice']),
                        'leverage': int(pos['leverage']),
                        'unrealized_pnl': float(pos['unrealisedPnl']),
                        'mark_price': float(pos.get('markPrice', pos['avgPrice']))
                    })
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
        return positions
    
    def get_klines(self, symbol: str, interval: int, limit: int = 200) -> List[Dict]:
        try:
            result = self.client.get_kline(
                category="linear",
                symbol=symbol,
                interval=str(interval),
                limit=limit
            )
            klines = []
            for k in result['result']['list']:
                klines.append({
                    'timestamp': int(k[0]),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                })
            return list(reversed(klines))
        except Exception as e:
            self.logger.error(f"Failed to get klines: {e}")
            return []
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        try:
            result = self.client.get_tickers(category="linear", symbol=symbol)
            if result['result']['list']:
                t = result['result']['list'][0]
                return {
                    'symbol': t['symbol'],
                    'last_price': float(t['lastPrice']),
                    'price_24h_pct_change': float(t.get('price24hPcnt', 0)) * 100,
                    'volume_24h': float(t['volume24h']),
                    'funding_rate': float(t.get('fundingRate', 0))
                }
        except Exception as e:
            self.logger.error(f"Failed to get ticker: {e}")
        return None
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        if self.dry_run:
            return True
        try:
            self.client.set_leverage(
                category="linear",
                symbol=symbol,
                buyLeverage=str(leverage),
                sellLeverage=str(leverage)
            )
            return True
        except Exception as e:
            if "leverage not modified" not in str(e).lower():
                self.logger.error(f"Failed to set leverage: {e}")
            return True
    
    def place_order(self, symbol: str, side: str, qty: float,
                    stop_loss: float = None, take_profit: float = None,
                    reduce_only: bool = False) -> Optional[str]:
        if self.dry_run:
            self.logger.info(f"[DRY RUN] {side} {symbol} qty={qty}")
            return "DRY_RUN_ORDER"
        
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": "Market",
                "qty": str(qty),
                "timeInForce": "GTC"
            }
            
            if reduce_only:
                params["reduceOnly"] = True
            
            if stop_loss:
                params["stopLoss"] = str(round(stop_loss, 2))
            if take_profit:
                params["takeProfit"] = str(round(take_profit, 2))
            
            result = self.client.place_order(**params)
            order_id = result['result']['orderId']
            self.logger.info(f"✅ Order placed: {order_id}")
            return order_id
        except Exception as e:
            self.logger.error(f"❌ Order failed: {e}")
            return None


# ============================================================
# ENHANCED INDICATORS
# ============================================================

class Indicators:
    """Technical indicators."""
    
    @staticmethod
    def ema(data: List[float], period: int) -> List[float]:
        if len(data) < period:
            return [data[0]] * len(data)
        
        result = [sum(data[:period]) / period]
        multiplier = 2 / (period + 1)
        
        for i in range(period, len(data)):
            ema = (data[i] * multiplier) + (result[-1] * (1 - multiplier))
            result.append(ema)
        
        return [None] * (period - 1) + result
    
    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> List[float]:
        if len(closes) < period + 1:
            return [50] * len(closes)
        
        result = [None] * period
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(closes)):
            if avg_loss == 0:
                result.append(100)
            else:
                rs = avg_gain / avg_loss
                result.append(100 - (100 / (1 + rs)))
            
            if i < len(gains):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        return result
    
    @staticmethod
    def macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
        ema_fast = Indicators.ema(closes, fast)
        ema_slow = Indicators.ema(closes, slow)
        
        macd_line = []
        for i in range(len(closes)):
            if ema_fast[i] is None or ema_slow[i] is None:
                macd_line.append(None)
            else:
                macd_line.append(ema_fast[i] - ema_slow[i])
        
        valid_macd = [m for m in macd_line if m is not None]
        signal_ema = Indicators.ema(valid_macd, signal) if len(valid_macd) > signal else [0]
        
        signal_line = [None] * (len(macd_line) - len(signal_ema)) + signal_ema
        
        histogram = []
        for m, s in zip(macd_line, signal_line):
            if m is None or s is None:
                histogram.append(None)
            else:
                histogram.append(m - s)
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(closes: List[float], period: int = 20, std: float = 2.0):
        if len(closes) < period:
            return [closes[-1]] * len(closes), [closes[-1]] * len(closes), [closes[-1]] * len(closes)
        
        upper, middle, lower = [], [], []
        
        for i in range(len(closes)):
            if i < period - 1:
                upper.append(None)
                middle.append(None)
                lower.append(None)
            else:
                window = closes[i-period+1:i+1]
                sma = sum(window) / period
                std_dev = np.std(window)
                
                middle.append(sma)
                upper.append(sma + std * std_dev)
                lower.append(sma - std * std_dev)
        
        return upper, middle, lower
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
        if len(closes) < 2:
            return [0]
        
        tr_list = [highs[0] - lows[0]]
        
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        # Simple moving average of TR
        atr = [None] * (period - 1)
        for i in range(period - 1, len(tr_list)):
            atr.append(sum(tr_list[i-period+1:i+1]) / period)
        
        return atr
    
    @staticmethod
    def supertrend(highs: List[float], lows: List[float], closes: List[float], 
                   period: int = 10, multiplier: float = 3.0) -> Tuple[List, List]:
        """Supertrend indicator."""
        atr = Indicators.atr(highs, lows, closes, period)
        
        supertrend = [None] * len(closes)
        direction = [None] * len(closes)  # 1 = bullish, -1 = bearish
        
        for i in range(period, len(closes)):
            if atr[i] is None:
                continue
            
            basic_upper = (highs[i] + lows[i]) / 2 + multiplier * atr[i]
            basic_lower = (highs[i] + lows[i]) / 2 - multiplier * atr[i]
            
            if supertrend[i-1] is None:
                supertrend[i] = basic_upper
                direction[i] = -1
                continue
            
            if direction[i-1] == 1:  # Was bullish
                if closes[i] > supertrend[i-1]:
                    supertrend[i] = max(basic_lower, supertrend[i-1])
                    direction[i] = 1
                else:
                    supertrend[i] = basic_upper
                    direction[i] = -1
            else:  # Was bearish
                if closes[i] < supertrend[i-1]:
                    supertrend[i] = min(basic_upper, supertrend[i-1])
                    direction[i] = -1
                else:
                    supertrend[i] = basic_lower
                    direction[i] = 1
        
        return supertrend, direction


# ============================================================
# ENHANCED STRATEGY
# ============================================================

class EnhancedStrategy:
    """
    Multi-factor trading strategy with advanced indicators.
    
    Includes indicators from:
    - LuxAlgo: Trendlines with Breaks, Echo Forecast (CC BY-NC-SA 4.0)
    - The_Caretaker: Advanced MA Crossover (MPL 2.0)
    - Standard TA: RSI, MACD, BB, Supertrend
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.regime_detector = MarketRegimeDetector()
        
        # Initialize advanced indicators (Credits preserved in module headers)
        self.trendline_detector = TrendlineBreaks(length=14, slope_mult=1.0)
        self.echo_forecast = EchoForecast(evaluation_window=30, forecast_window=10)
    
    def analyze(self, symbol: str, klines: Dict[int, List[Dict]], 
                order_flow: Dict = None) -> Optional[Dict]:
        """Full analysis of a symbol."""
        
        if not klines.get(5) or len(klines[5]) < 100:
            return None
        
        k5 = klines[5]
        closes = [k['close'] for k in k5]
        highs = [k['high'] for k in k5]
        lows = [k['low'] for k in k5]
        volumes = [k['volume'] for k in k5]
        
        current_price = closes[-1]
        
        # Calculate standard indicators
        rsi = Indicators.rsi(closes, 14)
        macd_line, signal_line, histogram = Indicators.macd(closes)
        bb_upper, bb_mid, bb_lower = Indicators.bollinger_bands(closes)
        atr = Indicators.atr(highs, lows, closes, 14)
        ema9 = Indicators.ema(closes, 9)
        ema21 = Indicators.ema(closes, 21)
        ema50 = Indicators.ema(closes, 50)
        supertrend, st_direction = Indicators.supertrend(highs, lows, closes)
        
        # NEW: Hull Moving Average (faster trend detection) - Credit: Alan Hull
        hma21 = AdvancedMA.hma(closes, 21)
        
        # NEW: Trendline Breakout Detection - Credit: LuxAlgo
        trendline_signal = self.trendline_detector.analyze(highs, lows, closes)
        
        # NEW: Echo Forecast (pattern-based prediction) - Credit: LuxAlgo
        try:
            forecast_bias, forecast_conf = self.echo_forecast.get_short_term_bias(closes, bars=5)
        except:
            forecast_bias, forecast_conf = "neutral", 0.0
        
        # Get latest values
        latest = {
            'rsi': rsi[-1] or 50,
            'macd': macd_line[-1] or 0,
            'macd_signal': signal_line[-1] or 0,
            'macd_hist': histogram[-1] or 0,
            'bb_upper': bb_upper[-1] or current_price * 1.02,
            'bb_lower': bb_lower[-1] or current_price * 0.98,
            'atr': atr[-1] or current_price * 0.02,
            'ema9': ema9[-1] or current_price,
            'ema21': ema21[-1] or current_price,
            'ema50': ema50[-1] or current_price,
            'supertrend_dir': st_direction[-1] or 0,
            'volume': volumes[-1],
            'avg_volume': np.mean(volumes[-20:]),
            # NEW indicators
            'hma21': hma21[-1] or current_price,
            'trendline_breakout': trendline_signal.breakout.value,
            'trendline_upper': trendline_signal.upper_trendline,
            'trendline_lower': trendline_signal.lower_trendline,
            'forecast_bias': forecast_bias,
            'forecast_conf': forecast_conf
        }
        
        # Market regime
        regime = self.regime_detector.analyze(highs, lows, closes, volumes)
        
        # Scoring system
        long_score = 0
        short_score = 0
        reasons = []
        
        # RSI
        if latest['rsi'] < 30:
            long_score += 3
            reasons.append(f"RSI oversold ({latest['rsi']:.1f})")
        elif latest['rsi'] < 40:
            long_score += 1
        elif latest['rsi'] > 70:
            short_score += 3
            reasons.append(f"RSI overbought ({latest['rsi']:.1f})")
        elif latest['rsi'] > 60:
            short_score += 1
        
        # MACD
        if latest['macd'] > latest['macd_signal'] and latest['macd_hist'] > 0:
            long_score += 2
            if histogram[-2] and latest['macd_hist'] > histogram[-2]:
                long_score += 1
                reasons.append("MACD bullish momentum")
        elif latest['macd'] < latest['macd_signal'] and latest['macd_hist'] < 0:
            short_score += 2
            if histogram[-2] and latest['macd_hist'] < histogram[-2]:
                short_score += 1
                reasons.append("MACD bearish momentum")
        
        # Bollinger Bands
        bb_position = (current_price - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower'])
        if bb_position < 0.2:
            long_score += 2
            reasons.append(f"Near BB lower ({bb_position:.0%})")
        elif bb_position > 0.8:
            short_score += 2
            reasons.append(f"Near BB upper ({bb_position:.0%})")
        
        # EMA Stack
        if latest['ema9'] > latest['ema21'] > latest['ema50']:
            long_score += 2
            reasons.append("Bullish EMA stack")
        elif latest['ema9'] < latest['ema21'] < latest['ema50']:
            short_score += 2
            reasons.append("Bearish EMA stack")
        
        # Supertrend
        if latest['supertrend_dir'] == 1:
            long_score += 2
            reasons.append("Supertrend bullish")
        elif latest['supertrend_dir'] == -1:
            short_score += 2
            reasons.append("Supertrend bearish")
        
        # Volume confirmation
        volume_ratio = latest['volume'] / latest['avg_volume'] if latest['avg_volume'] > 0 else 1
        if volume_ratio > 1.5:
            if long_score > short_score:
                long_score += 1
            elif short_score > long_score:
                short_score += 1
            reasons.append(f"Volume spike ({volume_ratio:.1f}x)")
        
        # NEW: HMA Trend (Credit: Alan Hull) - faster than EMA
        if latest['hma21'] and current_price > latest['hma21']:
            long_score += 1
            if current_price > latest['hma21'] * 1.01:  # 1% above HMA
                long_score += 1
                reasons.append("Strong HMA bullish")
        elif latest['hma21'] and current_price < latest['hma21']:
            short_score += 1
            if current_price < latest['hma21'] * 0.99:  # 1% below HMA
                short_score += 1
                reasons.append("Strong HMA bearish")
        
        # NEW: Trendline Breakout (Credit: LuxAlgo) - high conviction signals
        if latest['trendline_breakout'] == 'bullish':
            long_score += 3  # Strong signal!
            reasons.append("🔥 Trendline BREAKOUT bullish")
        elif latest['trendline_breakout'] == 'bearish':
            short_score += 3  # Strong signal!
            reasons.append("🔥 Trendline BREAKOUT bearish")
        
        # NEW: Echo Forecast (Credit: LuxAlgo) - pattern prediction
        if latest['forecast_bias'] == 'bullish' and latest['forecast_conf'] > 0.5:
            long_score += 2
            reasons.append(f"Echo forecast bullish ({latest['forecast_conf']:.0%})")
        elif latest['forecast_bias'] == 'bearish' and latest['forecast_conf'] > 0.5:
            short_score += 2
            reasons.append(f"Echo forecast bearish ({latest['forecast_conf']:.0%})")
        
        # Order flow bias (if available)
        if order_flow:
            of_score = order_flow.get('score', 0)
            if of_score > 15:
                long_score += 2
                reasons.append(f"Order flow bullish ({of_score})")
            elif of_score < -15:
                short_score += 2
                reasons.append(f"Order flow bearish ({of_score})")
        
        # Regime adjustments
        if regime.regime == MarketRegime.TRENDING_UP:
            long_score += 2
        elif regime.regime == MarketRegime.TRENDING_DOWN:
            short_score += 2
        elif regime.regime == MarketRegime.VOLATILE:
            # Reduce scores in volatile markets
            long_score = int(long_score * 0.7)
            short_score = int(short_score * 0.7)
        
        # Generate signal
        min_score = 5
        
        if long_score >= min_score and long_score > short_score + 2:
            side = "Buy"
            score = long_score
            confidence = min(0.95, 0.5 + (long_score - short_score) * 0.05)
            stop_loss = current_price - (latest['atr'] * 2.0)
            take_profit = current_price + (latest['atr'] * 3.0)
        elif short_score >= min_score and short_score > long_score + 2:
            side = "Sell"
            score = short_score
            confidence = min(0.95, 0.5 + (short_score - long_score) * 0.05)
            stop_loss = current_price + (latest['atr'] * 2.0)
            take_profit = current_price - (latest['atr'] * 3.0)
        else:
            return None
        
        # Calculate leverage based on confidence and regime
        base_leverage = self.config.leverage.default_leverage
        max_leverage = min(15, self.config.leverage.max_leverage)
        
        regime_mult = regime.recommendations.get('leverage_multiplier', 1.0)
        suggested_leverage = min(max_leverage, int(base_leverage * regime_mult * (0.8 + confidence * 0.4)))
        
        return {
            'symbol': symbol,
            'side': side,
            'confidence': confidence,
            'score': score,
            'reasons': reasons,
            'leverage': suggested_leverage,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'atr': latest['atr'],
            'regime': regime.regime.value,
            'regime_confidence': regime.confidence,
            'indicators': latest
        }


# ============================================================
# MAIN BOT V2
# ============================================================

class TradingBotV2:
    """Advanced trading trading bot."""
    
    def __init__(self, config: Config, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        
        self.client = BybitClient(config, dry_run)
        self.strategy = EnhancedStrategy(config)
        self.order_flow = OrderFlowAnalyzer(self.client)
        self.entry_optimizer = SmartEntryOptimizer(config)
        self.position_manager = PositionManager(config, self.client)
        self.ml_enhancer = MLSignalEnhancer()
        
        self.trades_today = 0
        self.last_trade_date = None
        self.daily_pnl = 0
        self.running = False
        
        # Stats
        self.stats = {
            'signals_generated': 0,
            'trades_executed': 0,
            'trades_won': 0,
            'trades_lost': 0,
            'total_pnl': 0
        }
    
    def _reset_daily_counter(self):
        today = datetime.now().date()
        if self.last_trade_date != today:
            self.trades_today = 0
            self.daily_pnl = 0
            self.last_trade_date = today
    
    def _calculate_position_size(self, signal: Dict, balance: float) -> float:
        """Risk-based position sizing."""
        risk_pct = self.config.risk.base_risk_pct / 100
        
        # Adjust risk based on confidence
        if signal['confidence'] > 0.8:
            risk_pct *= 1.2
        elif signal['confidence'] < 0.6:
            risk_pct *= 0.8
        
        risk_amount = balance * risk_pct
        
        sl_distance = abs(signal['entry_price'] - signal['stop_loss'])
        sl_pct = sl_distance / signal['entry_price']
        
        if sl_pct == 0:
            return 0
        
        size_usdt = risk_amount / sl_pct
        max_position = balance * (self.config.risk.max_position_pct / 100)
        size_usdt = min(size_usdt, max_position)
        
        qty = size_usdt / signal['entry_price']
        return round(qty, 3)
    
    def _log_trade(self, signal: Dict, qty: float, balance: float):
        """Log trade for audit."""
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"trades_{datetime.now().strftime('%Y%m%d')}.json"
        
        trade_log = {
            "timestamp": datetime.now().isoformat(),
            "symbol": signal['symbol'],
            "side": signal['side'],
            "quantity": qty,
            "entry_price": signal['entry_price'],
            "stop_loss": signal['stop_loss'],
            "take_profit": signal['take_profit'],
            "leverage": signal['leverage'],
            "confidence": signal['confidence'],
            "score": signal['score'],
            "reasons": signal['reasons'],
            "regime": signal['regime'],
            "balance": balance,
            "dry_run": self.dry_run
        }
        
        logs = []
        if log_file.exists():
            with open(log_file) as f:
                logs = json.load(f)
        logs.append(trade_log)
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
    
    def _print_status(self, balance: float, positions: List[Dict]):
        """Print status dashboard."""
        print("\n" + "=" * 60)
        print("🤖 BYBIT AI vs HUMAN 1v1 BOT - STATUS")
        print("=" * 60)
        print(f"💰 Balance: {balance:,.2f} USDT")
        print(f"📈 Trades today: {self.trades_today}/{self.config.trading.min_trades_per_day}")
        print(f"📊 P&L today: {self.daily_pnl:+.2f} USDT")
        print(f"🎯 Mode: {'🔵 DRY RUN' if self.dry_run else '🔴 LIVE'}")
        
        if positions:
            print(f"\n📂 Open Positions ({len(positions)}):")
            for p in positions:
                pnl_emoji = "🟢" if p['unrealized_pnl'] >= 0 else "🔴"
                print(f"  {pnl_emoji} {p['symbol']} {p['side']} {p['size']} @ {p['entry_price']:.2f} | PnL: {p['unrealized_pnl']:+.2f}")
        
        print("=" * 60)
    
    def run_cycle(self):
        """Run one trading cycle."""
        self._reset_daily_counter()
        
        balance = self.client.get_balance()
        positions = self.client.get_positions()
        
        # Check drawdown
        if balance < self.config.risk.min_capital * (1 - self.config.risk.max_daily_drawdown / 100):
            self.logger.warning("⚠️ Max drawdown reached - pausing trading")
            return
        
        # Update managed positions
        for pos in positions:
            ticker = self.client.get_ticker(pos['symbol'])
            if ticker:
                actions = self.position_manager.update_position(
                    pos['symbol'], ticker['last_price']
                )
                self.position_manager.execute_actions(actions)
        
        open_symbols = [p['symbol'] for p in positions]
        
        # Analyze each symbol
        for symbol in self.config.trading.symbols:
            if symbol in open_symbols:
                continue
            
            if len(positions) >= self.config.trading.max_open_positions:
                break
            
            # Get market data
            klines = {}
            for tf in [5, 15, 60]:
                klines[tf] = self.client.get_klines(symbol, tf, 200)
            
            if not klines.get(5):
                continue
            
            # Order flow analysis
            ticker = self.client.get_ticker(symbol)
            price_change = ticker['price_24h_pct_change'] if ticker else 0
            
            try:
                of_analysis = self.order_flow.analyze(symbol, price_change)
                order_flow_data = {'score': of_analysis.score, 'insights': of_analysis.insights}
            except:
                order_flow_data = None
            
            # Strategy analysis
            signal = self.strategy.analyze(symbol, klines, order_flow_data)
            
            if signal and signal['confidence'] >= 0.55:
                self.stats['signals_generated'] += 1
                
                # ML enhancement
                indicators = signal.get('indicators', {})
                ml_signal = self.ml_enhancer.enhance_signal(
                    klines[5], 
                    {'rsi': [indicators.get('rsi', 50)],
                     'macd_histogram': [indicators.get('macd_hist', 0)],
                     'bb_upper': [indicators.get('bb_upper', 0)],
                     'bb_lower': [indicators.get('bb_lower', 0)],
                     'atr': [indicators.get('atr', 0)],
                     'ema20': [indicators.get('ema21', 0)],
                     'ema50': [indicators.get('ema50', 0)]},
                    signal['side'].lower(),
                    signal['confidence']
                )
                
                # Combine confidences
                final_confidence = (signal['confidence'] + ml_signal.confidence) / 2
                
                if final_confidence >= 0.6:
                    self.logger.info(f"\n{'='*50}")
                    self.logger.info(f"📊 SIGNAL: {symbol} {signal['side']} | Score: {signal['score']} | Conf: {final_confidence:.0%}")
                    self.logger.info(f"   Regime: {signal['regime']} | Leverage: {signal['leverage']}x")
                    self.logger.info(f"   Reasons: {', '.join(signal['reasons'])}")
                    
                    if order_flow_data and order_flow_data.get('insights'):
                        self.logger.info(f"   Order Flow: {', '.join(order_flow_data['insights'][:2])}")
                    
                    # Calculate position size
                    qty = self._calculate_position_size(signal, balance)
                    
                    if qty > 0:
                        # Set leverage
                        self.client.set_leverage(symbol, signal['leverage'])
                        
                        # Place order
                        order_id = self.client.place_order(
                            symbol=symbol,
                            side=signal['side'],
                            qty=qty,
                            stop_loss=signal['stop_loss'],
                            take_profit=signal['take_profit']
                        )
                        
                        if order_id:
                            self.trades_today += 1
                            self.stats['trades_executed'] += 1
                            
                            # Create managed position
                            self.position_manager.create_managed_position(
                                symbol=symbol,
                                side=signal['side'],
                                entry_price=signal['entry_price'],
                                size=qty,
                                leverage=signal['leverage'],
                                atr=signal['atr']
                            )
                            
                            self._log_trade(signal, qty, balance)
                            self.logger.info(f"✅ TRADE #{self.trades_today}: {symbol} {signal['side']} {qty}")
        
        # Status update
        self._print_status(balance, positions)
        
        # Warn if behind on trades
        hour = datetime.now().hour
        expected_trades = int(self.config.trading.min_trades_per_day * hour / 24)
        if self.trades_today < expected_trades - 2:
            self.logger.warning(f"⚠️ Behind schedule: {self.trades_today} trades (expected ~{expected_trades})")
    
    def start(self):
        """Start the bot."""
        self.running = True
        
        print("\n" + "🔥" * 30)
        print("🤖 BYBIT AI vs HUMAN 1v1 COMPETITION BOT V2 PRO")
        print("🔥" * 30)
        print(f"🎯 Mode: {'🔵 DRY RUN' if self.dry_run else '🔴 LIVE TRADING'}")
        print(f"📊 Symbols: {', '.join(self.config.trading.symbols)}")
        print(f"⚡ Max Leverage: {self.config.leverage.max_leverage}x")
        print(f"🎯 Min trades/day: {self.config.trading.min_trades_per_day}")
        print(f"💰 Risk per trade: {self.config.risk.base_risk_pct}%")
        print("=" * 60 + "\n")
        
        while self.running:
            try:
                self.run_cycle()
                time.sleep(30)  # Check every 30 seconds
            except KeyboardInterrupt:
                self.logger.info("\n🛑 Stopping bot...")
                self.running = False
            except Exception as e:
                self.logger.error(f"❌ Error: {e}", exc_info=True)
                time.sleep(60)
    
    def stop(self):
        self.running = False


# ============================================================
# MAIN
# ============================================================

def setup_logging(level: str = "INFO"):
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)
    
    file_handler = logging.FileHandler(
        log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(formatter)
    
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))
    root.handlers = []
    root.addHandler(console)
    root.addHandler(file_handler)


def main():
    parser = argparse.ArgumentParser(description="Bybit 1v1 Trading Bot V2")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without real trades")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--config", default="config.yaml", help="Config file")
    args = parser.parse_args()
    
    # Load .env
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    setup_logging("DEBUG" if args.debug else "INFO")
    config = Config(args.config)
    
    if args.status:
        client = BybitClient(config, dry_run=True)
        balance = client.get_balance()
        positions = client.get_positions()
        print(f"\n💰 Balance: {balance:,.2f} USDT")
        print(f"📂 Positions: {len(positions)}")
        for p in positions:
            print(f"  - {p['symbol']} {p['side']} {p['size']} @ {p['entry_price']:.2f}")
        return
    
    bot = TradingBotV2(config, dry_run=args.dry_run)
    bot.start()


if __name__ == "__main__":
    main()
