# 🤖 Advanced Crypto Trading Bot

Automated trading bot for Bybit USDT Perpetuals with multi-indicator strategy and ML enhancement.

## 🚀 Features

### Core Strategy
- **Multi-Indicator Analysis**: RSI, MACD, Bollinger Bands, EMAs, Supertrend
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
# Clone repo
git clone https://github.com/rdhacker09/bybit-1v1-bot.git
cd bybit-1v1-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
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
# Activate venv
source venv/bin/activate

# Dry run (simulation)
python bot_v2.py --dry-run

# Live trading
python bot_v2.py

# Debug mode
python bot_v2.py --debug

# Check status
python bot_v2.py --status

# Run in background
nohup python bot_v2.py > bot.out 2>&1 &
```

## 📊 Monitoring

- Trade logs: `logs/trades_YYYYMMDD.json`
- Bot activity: `logs/bot_YYYYMMDD.log`

## 🏗️ Architecture

```
├── bot_v2.py              # Main bot
├── config.yaml            # Configuration
├── src/
│   ├── market_regime.py   # Regime detection
│   ├── order_flow.py      # Order flow analysis
│   ├── smart_entry.py     # Entry optimization
│   ├── position_manager.py# Position management
│   ├── ml_model.py        # ML enhancement
│   └── websocket_client.py# Real-time data
└── logs/                  # Trade & activity logs
```

## ⚠️ Disclaimer

This bot trades with real money. Use at your own risk.

- Never risk more than you can afford to lose
- Always test in dry-run mode first
- Monitor regularly
- Past performance ≠ future results

## 📄 License

MIT
