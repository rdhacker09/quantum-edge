# QuantumEdge Trading Strategy

## Overview

QuantumEdge is an advanced algorithmic trading system designed for USDT Perpetual Futures on Bybit. The bot combines traditional technical analysis with machine learning signal enhancement and real-time market microstructure analysis.

---

## Core Strategy Components

### 1. Multi-Indicator Signal Generation

The system uses a confluence-based approach, requiring multiple indicators to align before generating a trade signal:

**Primary Indicators:**
- **RSI (14)** - Identifies oversold (<30) and overbought (>70) conditions
- **MACD (12, 26, 9)** - Detects momentum shifts and trend direction
- **Bollinger Bands (20, 2σ)** - Measures volatility and mean reversion opportunities
- **EMA Stack (9, 21, 50)** - Confirms trend direction and strength
- **Supertrend (10, 3)** - Provides dynamic support/resistance and trend confirmation
- **Volume Profile** - Identifies high-volume nodes and value areas
- **VWAP** - Intraday fair value reference

**Signal Scoring:**
Each indicator contributes points to a scoring system. A minimum score of 5 is required, with the winning direction needing at least 2 points more than the opposite direction.

### 2. Market Regime Detection

The bot adapts its strategy based on current market conditions:

| Regime | Detection Method | Strategy Adaptation |
|--------|------------------|---------------------|
| Trending Up | ADX > 25, +DI > -DI | Trend following, pullback entries |
| Trending Down | ADX > 25, -DI > +DI | Trend following, bounce entries |
| Ranging | ADX < 20, consolidation | Mean reversion, range trading |
| Volatile | High ATR, choppy price | Reduced position sizes, wider stops |
| Breakout | Volume spike + range boundary | Momentum entries on confirmation |

### 3. Order Flow Analysis

Real-time market microstructure data is incorporated:

- **Funding Rate** - Contrarian signal when extreme (>0.1% or <-0.1%)
- **Open Interest Changes** - Confirms new money entering positions
- **Long/Short Ratio** - Identifies crowded trades for contrarian opportunities

### 4. ML Signal Enhancement

A machine learning layer enhances base signals:

- Feature extraction from 12 market variables
- Gradient Boosting classifier for win probability
- Confidence adjustment based on historical pattern matching
- Self-improving model that learns from trade outcomes

---

## Risk Management

### Position Sizing
- **Fixed margin per trade: $150 USDT**
- Dynamic leverage: 5x-15x based on signal confidence
- Risk per trade: ~1-2% of capital

### Position Limits
- **Maximum concurrent positions: 4-6**
- Diversified across different asset categories
- No more than 2 positions in correlated assets

### Stop Loss & Take Profit
- ATR-based stops: 2x ATR from entry
- Multiple take profit levels:
  - TP1: 1.5x ATR (close 40%)
  - TP2: 2.5x ATR (close 30%)
  - TP3: 4x ATR (close 30%)
- Trailing stop activation: After first TP hit
- Auto break-even: After 1.5% profit

### Leverage Control
- Default: 8x leverage
- Maximum: 15x (competition limit)
- Dynamic reduction in volatile conditions

### Daily Safeguards
- Maximum daily drawdown: 8% (trading pauses)
- Minimum trades per day: 12 (ensures activity)
- Session-aware sizing (reduced during low-liquidity hours)

---

## Trading Pairs

Diversified selection across market cap and volatility:

**Large Cap (High Liquidity):**
- BTCUSDT
- ETHUSDT
- BNBUSDT
- XRPUSDT

**Mid Cap (Higher Volatility):**
- SOLUSDT
- ADAUSDT
- AVAXUSDT
- DOTUSDT
- LINKUSDT
- MATICUSDT

**High Momentum:**
- DOGEUSDT
- SHIBUSDT
- PEPEUSDT
- SUIUSDT
- APTUSDT
- ARBUSDT
- OPUSDT

**DeFi & Layer 2:**
- UNIUSDT
- AABORUSDT
- LDOUSDT

---

## Technology Stack

- **Language:** Python 3.12
- **Exchange API:** pybit (Bybit Unified Trading API)
- **ML Framework:** scikit-learn
- **Data Processing:** NumPy, Pandas
- **Real-time Data:** WebSocket connections

---

## AI Integration

The bot is fully autonomous with AI decision-making at every level:

1. **Signal Generation** - AI analyzes multiple timeframes and indicators
2. **Confidence Scoring** - ML model predicts trade success probability
3. **Position Management** - Automated partial exits and trailing stops
4. **Risk Adjustment** - Dynamic sizing based on market conditions
5. **Self-Improvement** - Model retrains on new trade outcomes

---

## Compliance

- Meets minimum 10 trades/day requirement
- Respects maximum 15x leverage limit
- Full audit trail maintained in logs
- Code publicly available on GitHub

---

## GitHub Repository

**Public Repository:** https://github.com/rdhacker09/bybit-1v1-bot

Daily code updates will be pushed to maintain transparency and demonstrate AI participation.

---

*QuantumEdge - Where Quantum Computing Meets Trading Edge*
