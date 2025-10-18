#!/bin/bash
# TEPM Dashboard - Complete Startup Script
# This starts both API and Dashboard with one command

set -e

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

echo "🚀 Starting TEPM Trading Dashboard"
echo "==================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment found${NC}"
fi

# Activate virtual environment
source .venv/bin/activate

# Check Polygon API key
if [ ! -f "polygon_api.txt" ]; then
    echo -e "${RED}❌ polygon_api.txt not found${NC}"
    echo "Please create polygon_api.txt with your Polygon API key"
    exit 1
fi

export POLYGON_API_KEY=$(cat polygon_api.txt | tr -d '[:space:]')
echo -e "${GREEN}✓ Polygon API key loaded${NC}"

# Kill any existing processes
echo ""
echo -e "${BLUE}Cleaning up old processes...${NC}"
pkill -f "uvicorn src.api.server" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
sleep 2

# Start API Server
echo ""
echo -e "${BLUE}[1/2] Starting API Server...${NC}"
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
API_PID=$!
sleep 3

# Test API
if curl -s http://localhost:8000/health/live > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API Server running on http://localhost:8000${NC}"
else
    echo -e "${RED}❌ API Server failed to start${NC}"
    exit 1
fi

# Check for data gaps and offer backfill
echo ""
echo -e "${BLUE}Checking data coverage...${NC}"
python3 << 'PYEOF'
import requests
import sys

try:
    # Check a few key assets for data gaps
    assets_to_check = ["BTC-USD", "ETH-USD", "EUR-USD"]
    gaps_found = False
    
    for symbol in assets_to_check:
        try:
            r = requests.get(f"http://localhost:8000/data-status/{symbol}", timeout=5)
            if r.status_code == 200:
                stats = r.json().get("coverage", {})
                if stats.get("has_gap"):
                    print(f"⚠ {symbol}: Gap detected (last data: {stats.get('latest', 'never')})")
                    gaps_found = True
                elif stats.get("total_records", 0) > 0:
                    print(f"✓ {symbol}: {stats.get('total_records', 0)} records, coverage: {stats.get('coverage_hours', 0):.1f}h")
        except:
            pass
    
    if gaps_found:
        print("\n💡 Tip: Run backfill to fill gaps before starting:")
        print("   curl -X POST http://localhost:8000/backfill/BTC-USD?hours=24")
    
except Exception as e:
    print(f"Could not check data coverage (API may still be starting)")
PYEOF


# Start Dashboard
echo ""
echo -e "${BLUE}[2/2] Starting Dashboard...${NC}"
cd dashboard
npm run dev > ../logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
cd ..
sleep 5

# Test Dashboard
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Dashboard running on http://localhost:3000${NC}"
else
    echo -e "${YELLOW}⚠ Dashboard may still be loading...${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ TEPM Dashboard Ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📊 Dashboard:${NC}  http://localhost:3000"
echo -e "${BLUE}🔌 API:${NC}        http://localhost:8000"
echo ""
echo -e "${YELLOW}📝 Logs:${NC}"
echo "   API:       tail -f logs/api.log"
echo "   Dashboard: tail -f logs/dashboard.log"
echo ""
echo -e "${BLUE}🛑 To stop:${NC} ./stop_all.sh"
echo ""
echo -e "${GREEN}Open http://localhost:3000 in your browser!${NC}"
echo ""

