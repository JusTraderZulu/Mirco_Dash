#!/bin/bash
# Backfill historical data for key assets before starting trading session

echo "🔄 Backfilling Historical Data"
echo "=============================="
echo ""

# Assets to backfill
ASSETS=("BTC-USD" "ETH-USD" "EUR-USD" "SOL-USD" "GBP-USD")
HOURS=24  # How far back to fill

echo "Backfilling last ${HOURS} hours for ${#ASSETS[@]} assets..."
echo ""

for symbol in "${ASSETS[@]}"; do
    echo -n "📊 $symbol: "
    result=$(curl -s -X POST "http://localhost:8000/backfill/${symbol}?hours=${HOURS}")
    
    # Parse result
    status=$(echo "$result" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('backfill_result', {}).get('status', 'unknown'))" 2>/dev/null)
    
    if [ "$status" == "success" ]; then
        count=$(echo "$result" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('backfill_result', {}).get('backfilled_count', 0))" 2>/dev/null)
        echo "✅ Filled $count records"
    elif [ "$status" == "no_gap" ]; then
        echo "✓ Up to date"
    else
        echo "⚠ $status"
    fi
done

echo ""
echo "✅ Backfill complete!"
echo ""

