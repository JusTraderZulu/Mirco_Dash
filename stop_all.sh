#!/bin/bash
# Stop all TEPM services

echo "🛑 Stopping TEPM Dashboard..."
echo ""

# Kill processes
pkill -f "uvicorn src.api.server" && echo "✓ API Server stopped"
pkill -f "next dev" && echo "✓ Dashboard stopped"

sleep 1

echo ""
echo "✅ All services stopped"

