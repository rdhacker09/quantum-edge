#!/usr/bin/env python3
"""
🤖 Bybit AI vs Human 1v1 Trading Trading Bot
================================================
Designed for Bybit's AI & Human 1v1 Trading Trading

Trading Requirements:
- Minimum 1,000 USDT capital
- Minimum 10 trades/day
- Max recommended leverage: 15x
- Real capital, live market (MAINNET)

Usage:
    python main.py                # Run live trading
    python main.py --dry-run      # Simulate without real trades
    python main.py --debug        # Debug logging
    python main.py --backtest     # Run backtests
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
from dataclasses import dataclass
from enum import Enum

import yaml
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from pybit.unified_trading import HTTP
except ImportError:
    print("❌ Please install pybit: pip install pybit")
    sys.exit(1)


# ============================================================
# DATA STRUCTURES
# ============================================================

class Side(Enum):
    BUY = "Buy"
    SELL = "Sell"


@dataclass
class Signal:
    symbol: str
    side: Side
    confidence: float
    score: int
    reasons: List[str]
    suggested_leverage: int
    entry_price: float
    stop_loss: float
    take_profit: float


@dataclass
class Position:
    symbol: str
    side: str
    size: float
    entry_price: float
    leverage: int
    unrealized_pnl: float
    created_time: datetime


# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    def __init__(self, path: str = "config.yaml"):
        with open(path, 'r') as f:
            self._config = yaml.safe_load(f)
    
    def __getattr__(self, name):
        value = self._config.get(name, {})
        if isinstance(value, dict):
            return type('ConfigSection', (), value)()
        return value


# ============================================================
# EXCHANGE CLIENT
# ============================================================

class BybitClient:
    """Bybit API client wrapper."""
    
    def __init__(self, config: Config, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        
        # Load API credentials
        api_key = os.getenv('BYBIT_API_KEY')
        api_secret = os.getenv('BYBIT_API_SECRET')
        
        if not api_key or not api_secret:
            raise ValueError("❌ BYBIT_API_KEY and BYBIT_API_SECRET must be set in .env")
        
        # Initialize client (MAINNET for trading)
        testnet = config.exchange.network != 'mainnet'
        self.client = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        
        network_str = "TESTNET" if testnet else "🔴 MAINNET"
        self.logger.info(f"📡 Connected to Bybit {network_str}")
    
    def get_balance(self) -> float:
        """Get USDT balance."""
        try:
            result = self.client.get_wallet_balance(accountType="UNIFIED", coin="USDT")
            coins = result['result']['list'][0]['coin']
            for coin in coins:
                if coin['coin'] == 'USDT':
                    return float(coin['walletBalance'])
            return 0.0
        except Exception as e:
            self.logger.error(f"Failed to get balance: {e}")
            return 0.0
    
    def get_positions(self) -> List[Position]:
        """Get open positions."""
        positions = []
        try:
            result = self.client.get_positions(category="linear", settleCoin="USDT")
            for pos in result['result']['list']:
                if float(pos['size']) > 0:
                    positions.append(Position(
                        symbol=pos['symbol'],
                        side=pos['side'],
                        size=float(pos['size']),
                        entry_price=float(pos['avgPrice']),
                        leverage=int(pos['leverage']),
                        unrealized_pnl=float(pos['unrealisedPnl']),
                        created_time=datetime.fromtimestamp(int(pos['createdTime']) / 1000)
                    ))
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
        return positions
    
    def get_klines(self, symbol: str, interval: int, limit: int = 200) -> List[Dict]:
        """Get candlestick data."""
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
            return list(reversed(klines))  # Oldest first
        except Exception as e:
            self.logger.error(f"Failed to get klines for {symbol}: {e}")
            return []
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get current ticker."""
        try:
            result = self.client.get_tickers(category="linear", symbol=symbol)
            if result['result']['list']:
                t = result['result']['list'][0]
                return {
                    'symbol': t['symbol'],
                    'last_price': float(t['lastPrice']),
                    'bid': float(t['bid1Price']),
                    'ask': float(t['ask1Price']),
                    'volume_24h': float(t['volume24h'])
                }
        except Exception as e:
            self.logger.error(f"Failed to get ticker for {symbol}: {e}")
        return None
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would set leverage {leverage}x for {symbol}")
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
            return True  # Already set
    
    def place_order(self, symbol: str, side: Side, qty: float, 
                    stop_loss: float = None, take_profit: float = None) -> Optional[str]:
        """Place a market order."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would place {side.value} order: {symbol} qty={qty}")
            return "DRY_RUN_ORDER_ID"
        
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "side": side.value,
                "orderType": "Market",
                "qty": str(qty),
                "timeInForce": "GTC"
            }
            
            if stop_loss:
                params["stopLoss"] = str(round(stop_loss, 2))
            if take_profit:
                params["takeProfit"] = str(round(take_profit, 2))
            
            result = self.client.place_order(**params)
            order_id = result['result']['orderId']
            self.logger.info(f"✅ Order placed: {order_id}")
            return order_id
        except Exception as e:
            self.logger.error(f"❌ Failed to place order: {e}")
            return None
    
    def close_position(self, symbol: str, side: str, qty: float) -> bool:
        """Close a position."""
        close_side = Side.SELL if side == "Buy" else Side.BUY
        return self.place_order(symbol, close_side, qty) is not None


# ============================================================
# INDICATORS
# ============================================================

class Indicators:
    """Technical indicators calculator."""
    
    @staticmethod
    def sma(data: List[float], period: int) -> List[float]:
        result = [None] * (period - 1)
        for i in range(period - 1, len(data)):
            result.append(sum(data[i-period+1:i+1]) / period)
        return result
    
    @staticmethod
    def ema(data: List[float], period: int) -> List[float]:
        result = [None] * (period - 1)
        multiplier = 2 / (period + 1)
        
        # First EMA is SMA
        first_ema = sum(data[:period]) / period
        result.append(first_ema)
        
        for i in range(period, len(data)):
            ema_val = (data[i] * multiplier) + (result[-1] * (1 - multiplier))
            result.append(ema_val)
        
        return result
    
    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> List[float]:
        result = [None] * period
        
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        if len(gains) < period:
            return result
        
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
    def macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List, List, List]:
        ema_fast = Indicators.ema(closes, fast)
        ema_slow = Indicators.ema(closes, slow)
        
        macd_line = []
        for i in range(len(closes)):
            if ema_fast[i] is None or ema_slow[i] is None:
                macd_line.append(None)
            else:
                macd_line.append(ema_fast[i] - ema_slow[i])
        
        # Signal line
        valid_macd = [m for m in macd_line if m is not None]
        signal_line = [None] * (len(macd_line) - len(valid_macd))
        signal_line.extend(Indicators.ema(valid_macd, signal))
        
        # Histogram
        histogram = []
        for i in range(len(macd_line)):
            if macd_line[i] is None or signal_line[i] is None:
                histogram.append(None)
            else:
                histogram.append(macd_line[i] - signal_line[i])
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Tuple[List, List, List]:
        sma = Indicators.sma(closes, period)
        upper = []
        lower = []
        
        for i in range(len(closes)):
            if sma[i] is None:
                upper.append(None)
                lower.append(None)
            else:
                window = closes[max(0, i-period+1):i+1]
                std = np.std(window)
                upper.append(sma[i] + std_dev * std)
                lower.append(sma[i] - std_dev * std)
        
        return upper, sma, lower
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
        tr_list = [highs[0] - lows[0]]
        
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        return Indicators.sma(tr_list, period)


# ============================================================
# TRADING STRATEGY
# ============================================================

class Strategy:
    """Trading strategy for the trading."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def analyze(self, symbol: str, klines: Dict[int, List[Dict]]) -> Optional[Signal]:
        """Analyze a symbol and generate signal if conditions met."""
        
        if not klines or 5 not in klines or len(klines[5]) < 50:
            return None
        
        # Get closes for different timeframes
        closes_5m = [k['close'] for k in klines[5]]
        highs_5m = [k['high'] for k in klines[5]]
        lows_5m = [k['low'] for k in klines[5]]
        volumes_5m = [k['volume'] for k in klines[5]]
        
        current_price = closes_5m[-1]
        
        # Calculate indicators
        rsi = Indicators.rsi(closes_5m, self.config.strategy.rsi_period)
        macd_line, signal_line, histogram = Indicators.macd(
            closes_5m,
            self.config.strategy.macd_fast,
            self.config.strategy.macd_slow,
            self.config.strategy.macd_signal
        )
        bb_upper, bb_mid, bb_lower = Indicators.bollinger_bands(
            closes_5m,
            self.config.strategy.bb_period,
            self.config.strategy.bb_std
        )
        atr = Indicators.atr(highs_5m, lows_5m, closes_5m, 14)
        ema_fast = Indicators.ema(closes_5m, self.config.strategy.ema_fast)
        ema_slow = Indicators.ema(closes_5m, self.config.strategy.ema_slow)
        volume_ma = Indicators.sma(volumes_5m, self.config.strategy.volume_ma_period)
        
        # Get latest values
        latest_rsi = rsi[-1] if rsi[-1] else 50
        latest_macd = macd_line[-1] if macd_line[-1] else 0
        latest_signal = signal_line[-1] if signal_line[-1] else 0
        latest_histogram = histogram[-1] if histogram[-1] else 0
        latest_bb_upper = bb_upper[-1] if bb_upper[-1] else current_price * 1.02
        latest_bb_lower = bb_lower[-1] if bb_lower[-1] else current_price * 0.98
        latest_atr = atr[-1] if atr[-1] else current_price * 0.01
        latest_ema_fast = ema_fast[-1] if ema_fast[-1] else current_price
        latest_ema_slow = ema_slow[-1] if ema_slow[-1] else current_price
        latest_volume_ma = volume_ma[-1] if volume_ma[-1] else volumes_5m[-1]
        
        # Scoring system
        buy_score = 0
        sell_score = 0
        reasons = []
        
        # RSI
        if latest_rsi < self.config.strategy.rsi_oversold:
            buy_score += 2
            reasons.append(f"RSI oversold ({latest_rsi:.1f})")
        elif latest_rsi > self.config.strategy.rsi_overbought:
            sell_score += 2
            reasons.append(f"RSI overbought ({latest_rsi:.1f})")
        
        # MACD
        if latest_macd > latest_signal and latest_histogram > 0:
            buy_score += 1
            reasons.append("MACD bullish")
        elif latest_macd < latest_signal and latest_histogram < 0:
            sell_score += 1
            reasons.append("MACD bearish")
        
        # Bollinger Bands
        if current_price < latest_bb_lower:
            buy_score += 2
            reasons.append("Price below BB lower")
        elif current_price > latest_bb_upper:
            sell_score += 2
            reasons.append("Price above BB upper")
        
        # EMA trend
        if latest_ema_fast > latest_ema_slow:
            buy_score += 1
            reasons.append("EMA bullish")
        else:
            sell_score += 1
            reasons.append("EMA bearish")
        
        # Volume confirmation
        if volumes_5m[-1] > latest_volume_ma * self.config.strategy.volume_spike_multiplier:
            if buy_score > sell_score:
                buy_score += 1
                reasons.append("Volume spike (bullish)")
            elif sell_score > buy_score:
                sell_score += 1
                reasons.append("Volume spike (bearish)")
        
        # Determine signal
        min_score = self.config.strategy.min_signal_score
        
        if buy_score >= min_score and buy_score > sell_score:
            side = Side.BUY
            score = buy_score
            confidence = min(0.9, 0.5 + (buy_score - sell_score) * 0.1)
            stop_loss = current_price - (latest_atr * self.config.stops.atr_stop_multiplier)
            take_profit = current_price + (latest_atr * self.config.stops.atr_tp_multiplier)
        elif sell_score >= min_score and sell_score > buy_score:
            side = Side.SELL
            score = sell_score
            confidence = min(0.9, 0.5 + (sell_score - buy_score) * 0.1)
            stop_loss = current_price + (latest_atr * self.config.stops.atr_stop_multiplier)
            take_profit = current_price - (latest_atr * self.config.stops.atr_tp_multiplier)
        else:
            return None
        
        # Calculate suggested leverage based on confidence
        base_leverage = self.config.leverage.default_leverage
        max_leverage = self.config.leverage.max_leverage
        suggested_leverage = min(max_leverage, int(base_leverage + (confidence - 0.5) * 10))
        
        return Signal(
            symbol=symbol,
            side=side,
            confidence=confidence,
            score=score,
            reasons=reasons,
            suggested_leverage=suggested_leverage,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )


# ============================================================
# MAIN BOT
# ============================================================

class TradingBot:
    """Main trading trading bot."""
    
    def __init__(self, config: Config, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        
        self.client = BybitClient(config, dry_run)
        self.strategy = Strategy(config)
        
        self.trades_today = 0
        self.last_trade_date = None
        self.running = False
    
    def _reset_daily_counter(self):
        """Reset daily trade counter."""
        today = datetime.now().date()
        if self.last_trade_date != today:
            self.trades_today = 0
            self.last_trade_date = today
    
    def _calculate_position_size(self, signal: Signal, balance: float) -> float:
        """Calculate position size based on risk."""
        risk_amount = balance * (self.config.risk.base_risk_pct / 100)
        
        # Calculate size based on stop loss distance
        sl_distance = abs(signal.entry_price - signal.stop_loss)
        sl_pct = sl_distance / signal.entry_price
        
        if sl_pct == 0:
            return 0
        
        # Position size = Risk Amount / (SL% * Leverage)
        size_usdt = risk_amount / sl_pct
        
        # Apply max position limit
        max_position = balance * (self.config.risk.max_position_pct / 100)
        size_usdt = min(size_usdt, max_position)
        
        # Convert to quantity
        qty = size_usdt / signal.entry_price
        
        return round(qty, 3)
    
    def _log_trade(self, signal: Signal, qty: float, balance: float):
        """Log trade for trading audit."""
        log_dir = Path(__file__).parent / "logs"
        log_file = log_dir / f"trades_{datetime.now().strftime('%Y%m%d')}.json"
        
        trade_log = {
            "timestamp": datetime.now().isoformat(),
            "symbol": signal.symbol,
            "side": signal.side.value,
            "quantity": qty,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "leverage": signal.suggested_leverage,
            "confidence": signal.confidence,
            "score": signal.score,
            "reasons": signal.reasons,
            "balance_before": balance
        }
        
        # Append to log file
        logs = []
        if log_file.exists():
            with open(log_file, 'r') as f:
                logs = json.load(f)
        logs.append(trade_log)
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
    
    def run_cycle(self):
        """Run one trading cycle."""
        self._reset_daily_counter()
        
        # Get balance
        balance = self.client.get_balance()
        if balance < self.config.risk.min_capital:
            self.logger.warning(f"⚠️ Balance ({balance:.2f}) below minimum ({self.config.risk.min_capital})")
        
        # Get positions
        positions = self.client.get_positions()
        open_symbols = [p.symbol for p in positions]
        
        self.logger.info(f"💰 Balance: {balance:.2f} USDT | Positions: {len(positions)} | Trades today: {self.trades_today}")
        
        # Check each symbol
        for symbol in self.config.trading.symbols:
            if symbol in open_symbols:
                continue
            
            if len(positions) >= self.config.trading.max_open_positions:
                break
            
            # Get klines for all timeframes
            klines = {}
            for tf in self.config.trading.timeframes:
                klines[tf] = self.client.get_klines(symbol, tf, 200)
            
            # Analyze
            signal = self.strategy.analyze(symbol, klines)
            
            if signal and signal.confidence >= self.config.strategy.min_confidence:
                self.logger.info(f"📊 Signal: {symbol} {signal.side.value} | Conf: {signal.confidence:.2f} | Score: {signal.score}")
                self.logger.info(f"   Reasons: {', '.join(signal.reasons)}")
                
                # Calculate position size
                qty = self._calculate_position_size(signal, balance)
                
                if qty > 0:
                    # Set leverage
                    self.client.set_leverage(symbol, signal.suggested_leverage)
                    
                    # Place order
                    order_id = self.client.place_order(
                        symbol=symbol,
                        side=signal.side,
                        qty=qty,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit
                    )
                    
                    if order_id:
                        self.trades_today += 1
                        self._log_trade(signal, qty, balance)
                        self.logger.info(f"✅ Trade #{self.trades_today} executed: {symbol} {signal.side.value}")
        
        # Check if we need more trades for trading minimum
        remaining_trades = self.config.trading.min_trades_per_day - self.trades_today
        if remaining_trades > 0:
            self.logger.info(f"📈 Need {remaining_trades} more trades to meet daily minimum")
    
    def start(self):
        """Start the bot."""
        self.running = True
        
        self.logger.info("=" * 50)
        self.logger.info("🤖 BYBIT AI vs HUMAN 1v1 COMPETITION BOT")
        self.logger.info("=" * 50)
        self.logger.info(f"🔴 Mode: {'DRY RUN' if self.dry_run else 'LIVE TRADING'}")
        self.logger.info(f"📊 Symbols: {', '.join(self.config.trading.symbols)}")
        self.logger.info(f"⚡ Max Leverage: {self.config.leverage.max_leverage}x")
        self.logger.info(f"🎯 Min trades/day: {self.config.trading.min_trades_per_day}")
        self.logger.info("=" * 50)
        
        while self.running:
            try:
                self.run_cycle()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                self.logger.info("🛑 Stopping bot...")
                self.running = False
            except Exception as e:
                self.logger.error(f"❌ Error: {e}")
                time.sleep(30)
    
    def stop(self):
        """Stop the bot."""
        self.running = False


# ============================================================
# MAIN
# ============================================================

def setup_logging(level: str = "INFO"):
    """Setup logging."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    
    file_handler = logging.FileHandler(
        log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(formatter)
    
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))
    root.addHandler(console)
    root.addHandler(file_handler)


def main():
    parser = argparse.ArgumentParser(description="Bybit 1v1 Trading Bot")
    parser.add_argument("--dry-run", action="store_true", help="Run without placing real orders")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    args = parser.parse_args()
    
    # Load environment
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    # Setup
    setup_logging("DEBUG" if args.debug else "INFO")
    config = Config(args.config)
    
    # Run bot
    bot = TradingBot(config, dry_run=args.dry_run)
    bot.start()


if __name__ == "__main__":
    main()
