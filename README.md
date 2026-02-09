# 🤖 Bybit AI vs Human 1v1 Competition Bot - V2 PRO

Advanced trading bot designed specifically for Bybit's AI & Human 1v1 Trading Competition.

## 🏆 Competition Requirements Met
- ✅ Minimum 1,000 USDT capital
- ✅ Minimum 10 trades/day (configured for 12+)
- ✅ Max 15x leverage enforced
- ✅ Real capital, MAINNET only
- ✅ Full audit trail

## 🚀 Features

### Core
- **Multi-Indicator Strategy**: RSI, MACD, Bollinger Bands, EMAs, Supertrend
- **Market Regime Detection**: Adapts to trending/ranging/volatile conditions
- **Order Flow Analysis**: Funding rates, open interest, long/short ratio
- **ML Signal Enhancement**: Machine learning confidence scoring

### Risk Management
- Dynamic position sizing based on ATR and confidence
- Partial take profits (40% / 30% / 30%)
- Trailing stops with auto break-even
- Max daily drawdown protection
- Portfolio-wide risk monitoring

### Smart Execution
- Session-aware trading (optimal hours)
- Pullback entries in trends
- Breakout confirmation
- Volume spike detection

## 📦 Installation

```bash
cd /root/clawd/tools/bybit-1v1-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit config
cp .env.example .env
nano .env  # Add your API keys
```

## 🔧 Configuration

Edit `config.yaml` for:
- Trading pairs
- Risk parameters
- Leverage limits
- Strategy settings

## 🎮 Usage

```bash
# Activate venv first
cd /root/clawd/tools/bybit-1v1-bot
source venv/bin/activate

# Dry run (no real trades) - TEST FIRST!
python bot_v2.py --dry-run

# Live trading
python bot_v2.py

# Debug mode
python bot_v2.py --debug

# Check status
python bot_v2.py --status

# Run in background with nohup
nohup python bot_v2.py > bot.out 2>&1 &
```

## 📊 Monitoring

Trade logs are saved to `logs/trades_YYYYMMDD.json`

Bot activity logs: `logs/bot_YYYYMMDD.log`

## ⚠️ Risk Warning

This bot trades with REAL money on MAINNET. 

**NEVER**:
- Risk more than you can afford to lose
- Run without testing in dry-run mode first
- Share your API keys

**ALWAYS**:
- Start with minimum capital
- Monitor the bot regularly
- Have a manual intervention plan

## 🏗️ Architecture

```
bybit-1v1-bot/
├── bot_v2.py           # Main bot (V2 PRO)
├── main.py             # Original bot (V1)
├── config.yaml         # Configuration
├── src/
│   ├── market_regime.py    # Regime detection
│   ├── order_flow.py       # Order flow analysis
│   ├── smart_entry.py      # Entry optimization
│   ├── position_manager.py # Position management
│   ├── ml_model.py         # ML enhancement
│   └── websocket_client.py # Real-time data
├── logs/               # Trade & activity logs
├── models/             # ML model storage
└── data/               # Historical data
```

## 🎯 Strategy Overview

1. **Signal Generation**
   - Multi-timeframe analysis (5m, 15m, 1h)
   - Indicator confluence scoring
   - Market regime awareness

2. **Signal Enhancement**
   - Order flow bias check
   - ML confidence adjustment
   - Session timing factor

3. **Execution**
   - Smart entry timing
   - Dynamic leverage
   - ATR-based stops

4. **Position Management**
   - Partial take profits
   - Trailing stops
   - Break-even protection

## 📈 Performance Tracking

The bot tracks:
- Win rate
- Average R:R
- Daily P&L
- Max drawdown
- Sharpe ratio (in logs)

## 🔄 Updates

Check for updates:
```bash
cd /root/clawd/tools/bybit-1v1-bot
git pull
```

---

Built for winning 🏆 Good luck in the competition!
