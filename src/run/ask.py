"""
CLI to ask a plain-English question and get structured trading advice.
"""

import argparse
import json
from ..agents.qa_llm import answer_question


def main():
    parser = argparse.ArgumentParser(description="Ask the trading Q&A assistant")
    parser.add_argument("--symbol", required=True, help="e.g., BTC-USD, ETH-USD")
    parser.add_argument("--q", required=True, help="Your question")
    parser.add_argument("--window", type=int, default=300, help="Time window in seconds")
    
    args = parser.parse_args()

    print(f"\n🤖 Asking about {args.symbol}...")
    print(f"❓ Question: {args.q}\n")
    
    ans = answer_question(args.q, args.symbol, window_sec=args.window)
    
    # Pretty print
    print("=" * 80)
    print(f"📊 ANSWER")
    print("=" * 80)
    print(f"\n{ans.answer}\n")
    print(f"Stance: {ans.stance.upper()}")
    print(f"Confidence: {ans.confidence_0_1 * 100:.1f}%")
    print(f"Time Horizon: {ans.time_horizon_min} minutes")
    
    if ans.suggested_action:
        print(f"\n💡 SUGGESTED ACTION:")
        print(f"   {ans.suggested_action.side.upper()} {ans.suggested_action.order_type}")
        print(f"   Amount: ${ans.suggested_action.qty_usd:.2f}")
        if ans.suggested_action.stop_bps:
            print(f"   Stop Loss: {ans.suggested_action.stop_bps} bps")
        if ans.suggested_action.take_profit_bps:
            print(f"   Take Profit: {ans.suggested_action.take_profit_bps} bps")
    
    if ans.guardrails["violations"]:
        print(f"\n⚠️  GUARDRAILS TRIGGERED:")
        for v in ans.guardrails["violations"]:
            print(f"   - {v}")
    
    print(f"\n📈 KEY METRICS:")
    for key, val in list(ans.evidence.metrics.items())[:10]:
        if isinstance(val, float):
            print(f"   {key}: {val:.4f}")
        else:
            print(f"   {key}: {val}")
    
    print("\n" + "=" * 80)
    print("\n📄 Full JSON:")
    print(json.dumps(ans.model_dump(), indent=2))


if __name__ == "__main__":
    main()

