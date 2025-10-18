# 🚀 TEPM Analytics Dashboard

**Professional Microstructure Trading Analysis Platform**

Real-time market microstructure analysis for crypto and forex with AI-powered insights. Built for intraday traders who need institutional-grade data and signals.

![Dashboard](https://img.shields.io/badge/Status-Production%20Ready-success)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Next.js](https://img.shields.io/badge/Next.js-15.5-black)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

### 📊 **Multi-Asset Support**
- **💱 7 Forex Pairs** - EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, NZD/USD, USD/CHF
- **₿ 12 Cryptocurrencies** - BTC, ETH, SOL, DOGE, XRP, ADA, AVAX, MATIC, and more
- **Level 2 Data** for forex (real bid/ask spreads)
- **Live Trade Data** for crypto

### 📈 **Advanced Microstructure Metrics**
- Order Flow Imbalance (OFI)
- Bid-Ask Spread Analysis
- Liquidity Concentration
- Price Impact Coefficients
- Depth Imbalance
- Aggressive/Passive Ratios
- Realized Volatility
- Microprice Estimation

### ⏰ **Time-Based Intelligence**
- Automatic timeframe classification (Scalp/Intraday/Swing)
- Expected time to TP/SL
- Recommended holding periods
- Signal freshness tracking
- Exit condition monitoring

### 🤖 **AI Trading Assistant**
- Natural language queries
- Context-aware analysis (25+ metrics)
- Professional trading insights
- Actionable recommendations
- Powered by Perplexity AI

### 💾 **Historical Data Management**
- Automatic timestamped storage
- Gap detection and backfill
- Time-series database
- Historical analysis ready

---

## 🚀 Quick Start

### 1️⃣ Installation

```bash
# Clone repository
git clone <your-repo-url>
cd Mircostructure\ Bot

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install dashboard dependencies
cd dashboard
npm install
cd ..

# Add API keys
echo "YOUR_POLYGON_API_KEY" > polygon_api.txt
echo "YOUR_PERPLEXITY_API_KEY" > pplx_api.txt  # Optional
```

### 2️⃣ Start Trading

```bash
# Start everything (one command!)
./start_all.sh

# Open browser
open http://localhost:3000

# Optional: Backfill historical data
./backfill_data.sh
```

### 3️⃣ Stop When Done

```bash
./stop_all.sh
```

---

## 📖 Documentation

- **[QUICK_START.md](QUICK_START.md)** - Detailed setup guide
- **[TRADING_WORKFLOW.md](TRADING_WORKFLOW.md)** - How to use for trading
- **API Documentation** - http://localhost:8000/docs (when running)

---

## 🎯 Dashboard Overview

### **Three Main Tabs:**

#### 1. Overview
- Quick market snapshot
- Trading bias and confidence
- Entry/TP/SL levels with timing
- Key metrics at a glance

#### 2. Advanced Analytics  
- Complete microstructure breakdown
- All 25+ calculated metrics
- Monte Carlo probability analysis
- Detailed market depth data

#### 3. AI Assistant
- Ask trading questions
- Get professional insights
- Context includes all metrics + timing
- Stance recommendations

---

## 🏗️ Architecture

```
┌─────────────────┐
│   Dashboard     │  Next.js 15 + React 19
│  (localhost:3000)│  TypeScript + Tailwind
└────────┬────────┘
         │ HTTP
         ↓
┌─────────────────┐
│   FastAPI       │  Python 3.11+
│  (localhost:8000)│  REST API
└────────┬────────┘
         │
    ┌────┴────┬─────────┐
    ↓         ↓         ↓
┌────────┐ ┌──────┐ ┌─────────┐
│Polygon │ │SQLite│ │Perplexity│
│  API   │ │  DB  │ │   AI    │
└────────┘ └──────┘ └─────────┘
```

---

## 📊 Use Cases

### **Intraday Trading**
- Pre-trade analysis with microstructure signals
- Entry timing optimization
- Exit condition monitoring
- Real-time risk assessment

### **Signal Generation**
- OFI-based directional bias
- Confidence-weighted signals
- Timeframe-appropriate levels
- Probability-adjusted sizing

### **Research & Analysis**
- Compare assets (crypto vs forex)
- Liquidity studies
- Spread analysis
- Historical pattern recognition

---

## 🔑 API Keys Required

### **Polygon.io** (Required)
- Get free key: https://polygon.io
- 100 API calls/minute on free tier
- Supports crypto trades + forex Level 2

### **Perplexity AI** (Optional)
- Get key: https://www.perplexity.ai
- Only needed for AI Assistant feature
- Dashboard works without it

---

## 📁 Project Structure

```
Mircostructure Bot/
├── start_all.sh              # 🚀 Main startup script
├── stop_all.sh               # 🛑 Clean shutdown
├── backfill_data.sh          # 🔄 Fill historical gaps
│
├── src/                      # Backend Python code
│   ├── api/
│   │   └── server.py         # FastAPI REST API
│   ├── data/
│   │   ├── metrics_cache.py  # Time-series storage
│   │   └── historical_cache.py # Backfill system
│   ├── agents/
│   │   └── tools.py          # AI analysis tools
│   └── core/
│       └── *.py              # Core system
│
├── dashboard/                # Frontend Next.js app
│   ├── src/
│   │   ├── app/
│   │   │   └── page.tsx      # Main dashboard
│   │   └── components/
│   │       ├── OverviewDashboard.tsx
│   │       ├── MicrostructureDashboard.tsx
│   │       ├── AssetSelector.tsx
│   │       ├── AnalysisQuery.tsx
│   │       └── SystemControl.tsx
│   └── package.json
│
├── data/                     # SQLite databases (auto-generated)
├── logs/                     # Application logs (auto-generated)
│
├── README.md                 # This file
├── QUICK_START.md            # Setup guide
└── TRADING_WORKFLOW.md       # Trading guide
```

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python API framework
- **SQLite** - Lightweight time-series database
- **httpx** - Async HTTP client for Polygon
- **NumPy** - Numerical calculations
- **Pydantic** - Data validation

### Frontend
- **Next.js 15** - React framework with Turbopack
- **React 19** - UI library
- **TypeScript** - Type safety
- **Tailwind CSS 4** - Styling
- **Lucide Icons** - UI icons
- **Recharts** - Data visualization

### Data Sources
- **Polygon.io** - Market data (trades + Level 2 quotes)
- **Perplexity AI** - LLM analysis (optional)

---

## 🎓 Key Concepts

### **Order Flow Imbalance (OFI)**
Measures buy vs sell pressure by analyzing trade flow. Positive = buying pressure, Negative = selling pressure.

### **Microstructure Analysis**
Studies the mechanics of price formation - spreads, depth, impact, liquidity - to understand true market conditions beyond just price.

### **Level 2 Data**
Bid/ask quotes showing actual market depth (available for forex). More accurate than trade-based estimates.

### **Time-to-Target**
Statistical estimate of when price is likely to reach TP/SL based on current volatility and momentum.

---

## 🔧 Commands

```bash
# Start dashboard
./start_all.sh

# Stop dashboard
./stop_all.sh

# Backfill historical data
./backfill_data.sh

# Check specific asset coverage
curl http://localhost:8000/data-status/BTC-USD

# View API docs
open http://localhost:8000/docs

# Check logs
tail -f logs/api.log
tail -f logs/dashboard.log
```

---

## 📝 Environment Variables

Create these files in the project root:

```bash
# polygon_api.txt
YOUR_POLYGON_API_KEY

# pplx_api.txt (optional)
YOUR_PERPLEXITY_API_KEY
```

---

## 🤝 Contributing

This is a personal trading system. Feel free to fork and customize for your needs.

---

## ⚠️ Disclaimer

**This software is for educational and research purposes only.**

- Not financial advice
- Past performance doesn't guarantee future results
- Cryptocurrency and forex trading involves substantial risk
- Only trade with capital you can afford to lose
- Always do your own research

---

## 📞 Support

- Check logs in `logs/` directory
- API documentation: http://localhost:8000/docs
- Restart system: `./stop_all.sh && ./start_all.sh`

---

## 📄 License

MIT License - See LICENSE file for details

---

**Built for serious intraday traders who value data quality and professional analysis.** 📊🚀

---

## 🎯 Quick Links

- **Dashboard**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health/live
