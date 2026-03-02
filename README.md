# ⚡ QuantumEdge — AI-Powered Crypto Trading Bot

> *Built by [@rd__hacker](https://x.com/rd__hacker)*

QuantumEdge is a fully autonomous trading bot for Bybit — 15 pairs, ML signal scoring, multi-TP exits, dynamic risk management. Runs 24/7.

---

## 🚀 Features

- **15 Trading Pairs** — BNB, XRP, DOGE, AVAX, LINK, ADA, SUI, PEPE, APT, ARB, OP, DOT, MATIC, XAUT, WLD
- **ML Signal Scoring** — multi-indicator confluence scoring (RSI, MACD, EMA, Bollinger, Volume)
- **Dynamic Risk Management** — 1.5% SL, multi-TP levels (1%, 2%, 3%), max 8 open positions
- **Daily Drawdown Protection** — auto-pause at 8% daily loss
- **Smart Position Sizing** — $50–$150 margin per trade, up to 15x leverage
- **Re-entry Cooldown** — 30 min per symbol after close

---

## ⚙️ Setup

```bash
git clone https://github.com/rdhacker09/quantum-edge.git
cd quantum-edge
pip install -r requirements.txt
cp .env.example .env
# Add your Bybit API keys to .env
python quantumedge.py
```

---

## 📁 Structure

```
quantumedge.py     # Main bot
config.yaml        # Trading config
STRATEGY.md        # Strategy documentation
requirements.txt   # Dependencies
test_api.py        # API connection test
```

---

## ⚠️ Disclaimer

Trading crypto involves significant risk. Use at your own discretion.
