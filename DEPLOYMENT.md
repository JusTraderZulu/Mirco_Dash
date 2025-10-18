# 🌐 TEPM Dashboard - Deployment Guide

## Overview

The TEPM dashboard consists of **two parts** that need separate deployment:

1. **Frontend (Dashboard)** → Deploy to **Vercel** (Easy & Free!)
2. **Backend (API)** → Deploy to **DigitalOcean/Railway/Render** (Requires server)

---

## 🎨 Part 1: Deploy Frontend to Vercel

### Prerequisites
- GitHub account
- Vercel account (free): https://vercel.com

### Option A: Deploy via Vercel Dashboard (Easiest)

1. **Go to Vercel:**
   - Visit https://vercel.com
   - Click "Add New Project"
   - Import from GitHub: `JusTraderZulu/Mirco_Dash`

2. **Configure Build Settings:**
   ```
   Framework Preset: Next.js
   Root Directory: dashboard
   Build Command: npm run build
   Output Directory: .next
   Install Command: npm install
   ```

3. **Environment Variables:**
   ```
   NEXT_PUBLIC_API_URL=https://your-api-domain.com
   ```
   (We'll set this after deploying the backend)

4. **Deploy!**
   - Click "Deploy"
   - Wait 2-3 minutes
   - Get URL: `https://mirco-dash.vercel.app`

### Option B: Deploy via CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy from dashboard directory
cd dashboard
vercel --prod

# Follow prompts:
# - Link to existing project: No
# - Project name: mirco-dash
# - Root directory: ./
# - Build settings: Default (Next.js)
```

---

## 🔧 Part 2: Deploy Backend API

### Options (Choose One):

#### **Option 1: Railway (Easiest for Python)**

1. **Create account:** https://railway.app
2. **New Project → Deploy from GitHub**
3. **Select repository:** `Mirco_Dash`
4. **Configure:**
   ```
   Root Directory: /
   Start Command: uvicorn src.api.server:app --host 0.0.0.0 --port $PORT
   ```

5. **Add Environment Variables:**
   ```
   POLYGON_API_KEY=your_key
   PPLX_API_KEY=your_key
   PORT=8000
   ```

6. **Deploy!**
   - Get URL: `https://your-app.up.railway.app`

#### **Option 2: Render**

1. **Create account:** https://render.com
2. **New Web Service**
3. **Connect GitHub:** `Mirco_Dash`
4. **Configure:**
   ```
   Name: tepm-api
   Root Directory: /
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn src.api.server:app --host 0.0.0.0 --port $PORT
   ```

5. **Add Environment Variables:**
   ```
   POLYGON_API_KEY=your_key
   PPLX_API_KEY=your_key
   PYTHON_VERSION=3.11
   ```

#### **Option 3: DigitalOcean App Platform**

1. **Create account:** https://www.digitalocean.com
2. **Create App → GitHub**
3. **Select repo and configure**
4. **Estimated cost:** $5-10/month

---

## 🔗 Part 3: Connect Frontend to Backend

### Update Frontend Environment

Once backend is deployed, update Vercel environment variable:

```bash
# In Vercel Dashboard:
# Settings → Environment Variables → Add

NEXT_PUBLIC_API_URL=https://your-api.up.railway.app
```

Or update the frontend code directly:

**dashboard/src/app/page.tsx:**
```typescript
// Replace localhost with your API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Use in fetch calls:
fetch(`${API_URL}/microstructure/${symbol}`)
```

**Redeploy Vercel** after changing environment variables.

---

## 📊 Current Limitation: Backend Must Run Somewhere

### **Problem:**
- Frontend (Vercel): ✅ Static, can be deployed easily
- Backend (API): ❌ Needs a server running 24/7

### **Solutions:**

#### **Short-term (For Sharing):**

**Option 1: Local Backend + Ngrok (Quick Demo)**
```bash
# Terminal 1: Start your local backend
./start_all.sh

# Terminal 2: Expose via ngrok
ngrok http 8000

# You get: https://abc123.ngrok.io
# Share this URL for demos
```

Update Vercel:
```
NEXT_PUBLIC_API_URL=https://abc123.ngrok.io
```

**Pros:** Free, instant  
**Cons:** Only works when your computer is on, URL changes

#### **Option 2: Deploy Backend to Railway (Best)**
```bash
# Railway gives you a permanent URL
https://tepm-api.up.railway.app

# Set in Vercel
NEXT_PUBLIC_API_URL=https://tepm-api.up.railway.app
```

**Pros:** 24/7 uptime, permanent URL  
**Cons:** $5-10/month

---

## 🚀 Recommended Deployment Path

### **For Professional Use:**

```
1. Deploy Backend → Railway ($5/month)
   ↓
2. Get permanent API URL
   ↓
3. Update frontend environment variable
   ↓
4. Deploy Frontend → Vercel (FREE!)
   ↓
5. Share: https://mirco-dash.vercel.app ✨
```

### **For Quick Demos:**

```
1. Run backend locally
   ↓
2. Expose with ngrok (free)
   ↓
3. Update Vercel temporarily
   ↓
4. Share: https://mirco-dash.vercel.app
   (Works while your laptop is on)
```

---

## 🎯 Full Production Setup

### **Step-by-Step:**

#### 1. Deploy Backend to Railway

```bash
# In Railway Dashboard:
1. New Project
2. Deploy from GitHub
3. Select: Mirco_Dash
4. Add env vars:
   POLYGON_API_KEY=xxx
   PPLX_API_KEY=xxx
5. Deploy

# Get URL: https://tepm-api.up.railway.app
```

#### 2. Update Dashboard for Production

Create `dashboard/.env.production`:
```bash
NEXT_PUBLIC_API_URL=https://tepm-api.up.railway.app
```

Or set in Vercel:
```
Settings → Environment Variables
NEXT_PUBLIC_API_URL=https://tepm-api.up.railway.app
```

#### 3. Deploy Dashboard to Vercel

```bash
cd dashboard
vercel --prod

# Or via Vercel Dashboard:
# Import from GitHub → Auto-deploy
```

#### 4. Update Code to Use Environment Variable

**dashboard/src/components/OverviewDashboard.tsx** (line 68-70):
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const fetchData = async () => {
  try {
    const response = await fetch(`${API_URL}/microstructure/${symbol}`);
    // ...
```

Do this for all components:
- OverviewDashboard.tsx
- MicrostructureDashboard.tsx
- AnalysisQuery.tsx
- SystemControl.tsx
- page.tsx (AssetSelector)

---

## 💡 Quick Deploy Script

Want me to create an update that:
1. Adds `NEXT_PUBLIC_API_URL` environment variable support
2. Creates a `dashboard/.env.local.example`
3. Makes the dashboard work with both local and remote API
4. Adds deploy instructions to README

---

## 💰 Cost Breakdown

### **Free Tier (Demo/Personal):**
- Frontend (Vercel): **FREE** ✅
- Backend (ngrok): **FREE** (when laptop on)
- Database: **Local SQLite** - FREE
- **Total: $0/month**

### **Professional (24/7):**
- Frontend (Vercel): **FREE** ✅
- Backend (Railway): **$5-10/month**
- Database: **Included with Railway**
- **Total: $5-10/month**

### **Enterprise (High Traffic):**
- Frontend (Vercel Pro): **$20/month**
- Backend (DigitalOcean): **$10-20/month**
- Database (PostgreSQL): **$15/month**
- **Total: $45-55/month**

---

## 🎯 What to Do Now?

**Choose your deployment strategy:**

**A. Just pushed to GitHub (Done! ✅)**
- Code is safe and backed up
- Others can clone and run locally

**B. Deploy for sharing (15 minutes)**
- Deploy backend to Railway
- Deploy frontend to Vercel
- Share URL with anyone

**C. Professional deployment (30 minutes)**
- Railway backend + PostgreSQL
- Vercel frontend + custom domain
- Production monitoring

**Want me to help set up option B or C?** Let me know and I'll:
1. Update dashboard to use environment variables
2. Create deployment configs
3. Provide step-by-step Railway + Vercel guide

