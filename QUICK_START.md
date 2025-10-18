# 🚀 TEPM Trading Dashboard - Quick Start Guide

## One-Command Startup

### 1️⃣ First Time Setup (One Time Only)

```bash
# Clone or navigate to project
cd "Mircostructure Bot"

# Create virtual environment
python3 -m venv .venv

# Install dependencies
source .venv/bin/activate
pip install -r requirements.txt

# Install dashboard dependencies
cd dashboard
npm install
cd ..

# Add your Polygon API key
echo "YOUR_POLYGON_API_KEY" > polygon_api.txt

# Optional: Add Perplexity API key for AI assistant
echo "YOUR_PPLX_API_KEY" > pplx_api.txt
```

### 2️⃣ Start Dashboard (Every Time)

```bash
./start_all.sh
```

That's it! The script will:
- ✅ Start API server (port 8000)
- ✅ Start Dashboard (port 3000)
- ✅ Check health of both services
- ✅ Show you the URLs

### 3️⃣ Open Dashboard

Open your browser to: **http://localhost:3000**

---

## 🎯 Using the Dashboard

### System Control Panel

At the top of the dashboard, you'll see:
- **🟢 API Connected** - Backend is running
- **🟢 Live Data** - Receiving real-time market data
- **Refresh Status** button - Check connection

### Tabs

1. **Overview** 
   - Quick metrics & trading signals
   - Entry/TP/SL levels
   - Expected timing

2. **Advanced Analytics**
   - Complete microstructure breakdown
   - All 25+ metrics
   - Detailed analysis

3. **AI Assistant**
   - Ask trading questions
   - Get professional insights
   - Context-aware analysis

### Asset Selection

Choose from 15+ cryptocurrencies:
- **BTC-USD**, **ETH-USD**, **SOL-USD**, **DOGE-USD**
- **XRP-USD**, **ADA-USD**, **AVAX-USD**, **MATIC-USD**
- **And more...**

---

## 🛑 Stop Dashboard

```bash
./stop_all.sh
```

---

## 📊 What You Get

### Real-Time Metrics
- ✅ **Order Flow Imbalance (OFI)** - Buy/sell pressure
- ✅ **Spread Analysis** - Liquidity conditions
- ✅ **Volatility Regime** - Risk assessment
- ✅ **Price Impact** - Execution cost estimates
- ✅ **Time-to-Target** - When to expect TP/SL
- ✅ **Signal Freshness** - Data age tracking

### Trading Intelligence
- ✅ **Bias Detection** - Long/Short/Neutral
- ✅ **Confidence Levels** - How strong the signal is
- ✅ **Timeframe Classification** - Scalp/Intraday/Swing
- ✅ **Risk Quantification** - VaR and volatility
- ✅ **Probability Analysis** - TP/SL hit chances

### AI Insights
- ✅ **Natural Language Queries** - Ask anything
- ✅ **Context-Aware** - Knows all your metrics
- ✅ **Professional Analysis** - Institutional-grade
- ✅ **Actionable Recommendations** - What to do now

---

## 🔧 Troubleshooting

### Dashboard won't start?

**Check if ports are in use:**
```bash
lsof -i :8000  # API port
lsof -i :3000  # Dashboard port
```

**Kill existing processes:**
```bash
./stop_all.sh
```

### API shows offline?

**Check API logs:**
```bash
tail -f logs/api.log
```

**Manually test API:**
```bash
curl http://localhost:8000/health/live
```

### No data for an asset?

**Test Polygon connection:**
```bash
curl "https://api.polygon.io/v3/trades/X:BTCUSD?limit=1" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## 📁 Project Structure

```
Mircostructure Bot/
├── start_all.sh          # 🚀 ONE-COMMAND STARTUP
├── stop_all.sh           # Stop all services
├── src/
│   └── api/
│       └── server.py     # Backend API (FastAPI)
├── dashboard/
│   └── src/
│       ├── app/
│       │   └── page.tsx  # Main dashboard
│       └── components/   # Dashboard components
├── logs/                 # Service logs
├── data/                 # Data cache
└── polygon_api.txt       # Your API key
```

---

## 🎓 Trading Workflow

### 1. Check Dashboard Status
- Verify **🟢 API Connected** and **🟢 Live Data**

### 2. Select Asset
- Choose crypto from dropdown
- Wait for metrics to load (~2-3 seconds)

### 3. Analyze Overview
- Check **Bias** (Long/Short/Neutral)
- Note **Confidence** level
- See **Timeframe** (Scalp/Intraday/Swing)
- Review **Expected TP Time**

### 4. Review Microstructure
- Check **OFI** for order flow direction
- Verify **Spread** for liquidity
- Check **Volatility** for risk
- Monitor **Signal Age** (should be fresh)

### 5. Use AI Assistant
- Ask: "Should I enter now?"
- Ask: "What's the risk?"
- Ask: "When should I exit?"

### 6. Execute on Coinbase
- Use recommended Entry/TP/SL levels
- Set position size based on volatility
- Monitor dashboard for exit signals

### 7. Monitor Position
- Watch **OFI** for flips
- Check **Liquidity** stays good
- Exit if signal becomes stale (>30 min)
- Take profit at target or time limit

---

## ⚡ Pro Tips

1. **Best Assets to Start:** BTC, ETH, SOL
2. **Refresh Frequency:** Dashboard auto-refreshes every 30s
3. **Signal Validity:** Signals are good for ~30 minutes
4. **Time Estimates:** Add 20-30% buffer to expected TP times
5. **Volatility:** Higher vol = wider stops needed
6. **OFI Flips:** Strong exit signal - consider closing
7. **Data Span:** Prefer <60s data windows for freshness

---

## 🌐 Cloud Deployment (Future)

To run 24/7, you'll deploy to:
- **DigitalOcean / AWS / Heroku** for backend
- **Vercel / Netlify** for dashboard frontend
- **PostgreSQL** for persistent data
- **Redis** for caching

For now, run locally and start when you need to trade!

---

## 📞 Support

- Check logs: `logs/api.log` and `logs/dashboard.log`
- Restart: `./stop_all.sh && ./start_all.sh`
- Test API: `curl http://localhost:8000/health/live`

---

**Happy Trading! 📈🚀**

