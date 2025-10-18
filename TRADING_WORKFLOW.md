# 📊 TEPM Trading Dashboard - Complete Workflow

## 🎯 Philosophy

**This dashboard is designed for deliberate, informed trading - not high-frequency automation.**

- ✅ Analyze market microstructure before trading
- ✅ Make informed decisions with complete context
- ✅ Monitor positions intelligently
- ✅ Build historical context over time

---

## 🚀 Session Workflow

### **Before Trading (One-Time per Day)**

#### 1. Start the System
```bash
./start_all.sh
```

#### 2. Check Data Coverage
The startup script will show you:
```
✓ BTC-USD: 45 records, coverage: 3.2h
⚠ EUR-USD: Gap detected (last data: 8h ago)
✓ ETH-USD: 32 records, coverage: 2.1h
```

#### 3. Backfill Gaps (if needed)
```bash
# Option A: Backfill specific asset
curl -X POST http://localhost:8000/backfill/EUR-USD?hours=24

# Option B: Use the backfill script for all key assets
./backfill_data.sh
```

**Why backfill?**
- Better context for AI analysis
- See recent trends and patterns
- Understand market regime changes
- More accurate volatility calculations

---

## 💹 Trading Session

### **Step 1: Review Market (5-10 min)**

Open http://localhost:3000

**Check multiple assets:**
- EUR-USD (forex, tight spreads)
- BTC-USD (high volatility)
- ETH-USD (tech momentum)
- SOL-USD (alt action)

**Look for:**
- ✅ Strong bias (>60% confidence)
- ✅ Fresh signal (< 5 min old)
- ✅ Good liquidity (concentration > 99%)
- ✅ Clear OFI direction
- ✅ Appropriate timeframe for your style

### **Step 2: Deep Dive on Candidate (3-5 min)**

**Overview Tab:**
```
Price: $107,337
Bias: LONG (52% confidence)
OFI: 0.692 (buy pressure)
Timeframe: INTRADAY
Expected TP: 53 minutes
Hold Period: 37-79 min
```

**Advanced Analytics Tab:**
- Check all 25+ metrics
- Verify spread is tight
- Check volatility regime
- Review Monte Carlo probabilities

**AI Assistant Tab:**
Ask specific questions:
```
"Should I enter a long position on BTC now?"
"What's the downside risk?"
"How confident is this signal?"
"What could invalidate this trade?"
```

### **Step 3: Execute on Coinbase (2-3 min)**

**Set up trade:**
```
Entry: Use recommended level
TP: Set at recommended TP
SL: Set at recommended SL
Size: Based on volatility & your risk
```

**Record trade:**
- Entry time
- Expected TP time (e.g., +53 min = 3:45 PM)
- Exit conditions (OFI flip, time limit)

### **Step 4: Monitor Position**

**Every 10-15 minutes, check dashboard:**

**Quick Check (30 seconds):**
- Is OFI still positive? (or negative for short)
- Has bias flipped?
- Is signal still fresh?

**Detailed Check (2-3 minutes):**
- Review updated metrics
- Check if volatility increased
- Verify liquidity still good

**Exit Triggers:**
1. ✅ **TP hit** - Take profit
2. ❌ **SL hit** - Accept loss
3. ⏰ **Time limit** - Max hold period reached
4. 🔄 **OFI flip** - Order flow reversed
5. ⚠️ **Spread widened** - Liquidity dried up

---

## ⏱️ Timing & Refresh Strategy

### **Dashboard Refresh:**
- **Auto-refresh**: Every 5 minutes
- **Manual refresh**: Click button anytime
- **API fetch**: ~2-3 seconds per asset

### **Signal Validity:**
- **Fresh**: < 5 minutes old (use it!)
- **Stale**: 5-15 minutes (review before using)
- **Old**: > 15 minutes (refresh first)

### **Position Monitoring:**
```
Entry → Check @10min → Check @20min → Check @30min → Decision

If TP not hit by expected time + 50%:
→ Consider exiting
```

---

## 📊 Historical Data Strategy

### **Database Builds Over Time:**

**Session 1 (Today 2-4 PM):**
```
BTC: 24 records (2 hours)
EUR: 18 records (2 hours)
```

**Session 2 (Tomorrow 2-4 PM):**
```
Before backfill:
  BTC: 24 records (gap from 4 PM yesterday to 2 PM today)
  
After backfill:
  BTC: 1,464 records (24 hours continuous!)
  
Add new live data:
  BTC: 1,488 records (24h + 2h today)
```

### **Workflow:**

**Each Trading Day:**
```bash
# 1. Start system
./start_all.sh

# 2. Check coverage (automatic)
# Shows: ⚠ BTC-USD: Gap detected (last: 22h ago)

# 3. Backfill gaps
./backfill_data.sh

# 4. Trade with full context
# Dashboard now shows trends over 24h
```

---

## 💡 Best Practices

### **When to Refresh:**

**DON'T** refresh every 30 seconds:
- ❌ Wastes API calls
- ❌ No meaningful change
- ❌ Signal noise

**DO** refresh strategically:
- ✅ Before entering trade
- ✅ Every 10-15 min during position
- ✅ When checking exit conditions
- ✅ After major news/events

### **Backfill Strategy:**

**Daily backfill:**
```bash
# Morning before trading
./backfill_data.sh

# Fills overnight gaps
# Gives you 24h context
# Better AI analysis
```

**Long break backfill:**
```bash
# If you haven't traded in days
curl -X POST http://localhost:8000/backfill/BTC-USD?hours=168  # 1 week
```

### **Database Management:**

**Let it grow naturally:**
- Each session adds 12-48 records per asset
- Over a month: ~500-1500 records per asset
- Database size: ~5-20 MB
- No cleanup needed for months

---

## 🎓 Example Full Session

### **Monday 2:00 PM - Start Trading:**

```bash
# Terminal
./start_all.sh
# Shows: ⚠ BTC: Gap (last: 66 hours ago)

./backfill_data.sh
# Fills: 1,320 records for BTC (weekend gap)
```

**Browser:**
```
1. Open http://localhost:3000
2. System shows: 🟢 API • 🟢 Live Data
3. Select BTC-USD
4. Review: 1,320 records, 66h coverage ✓
5. Check bias: LONG (65% confidence)
6. Ask AI: "Considering 66h context, is this a good long?"
7. AI sees full weekend trend in context!
```

### **2:15 PM - Enter Trade:**
```
Execute on Coinbase:
- Long BTC at $107,337
- TP: $109,484 (expected: 53 min → 3:08 PM)
- SL: $106,263
```

### **2:25 PM - First Check:**
```
Dashboard: OFI still 0.69 ✓
Bias: LONG ✓
Signal age: 10 min (slightly stale, but holding)
```

### **2:45 PM - Monitor:**
```
Dashboard: OFI dropped to 0.12 ⚠
Manual refresh (click button)
New OFI: -0.23 (FLIPPED!) ❌
Decision: EXIT NOW
```

### **3:00 PM - Exit:**
```
Close position manually
Small profit, avoided reversal
Better decision thanks to real-time OFI
```

### **4:00 PM - Done Trading:**
```bash
./stop_all.sh
```

**Database now has:**
- BTC: 1,332 records (66h + 2h today)
- Next session will build on this!

---

## 📈 Long-Term Benefits

### **After 1 Week:**
- 5-7 trading sessions
- ~10-14 hours of data per asset
- Rich historical context
- See pattern repetitions

### **After 1 Month:**
- ~20-30 sessions
- ~40-60 hours of data
- Statistical significance
- Backtest signal accuracy

### **After 3 Months:**
- Complete dataset
- Seasonal patterns visible
- Can analyze "what worked"
- Optimize your strategy

---

## 🔧 Commands Reference

```bash
# Start everything
./start_all.sh

# Stop everything  
./stop_all.sh

# Backfill all key assets
./backfill_data.sh

# Backfill specific asset
curl -X POST http://localhost:8000/backfill/BTC-USD?hours=24

# Check data coverage
curl http://localhost:8000/data-status/BTC-USD

# Get historical data
curl http://localhost:8000/history/BTC-USD?hours=24

# Check API logs
tail -f logs/api.log
```

---

## ✨ Summary

**Your Improved Workflow:**

✅ **5-minute refresh** - Reasonable update frequency  
✅ **Manual refresh** - When you need it  
✅ **Backfill on startup** - Fill overnight gaps  
✅ **Historical context** - Better AI analysis  
✅ **Continuous database** - Builds over time  
✅ **Forex Level 2** - Professional data quality  
✅ **Multi-asset** - 19+ instruments  

**No more constant refreshing - Just smart, informed trading!** 🎯📊

