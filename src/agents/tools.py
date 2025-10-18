"""
Deterministic tools for the LLM Q&A assistant.
Fetches live metrics, market context, and risk envelope.
"""

import os
import time
import httpx
from typing import Dict, Any


def get_metrics(symbol: str, window_sec: int = 300) -> Dict[str, Any]:
    """
    Fetch live microstructure metrics from the API server.
    Returns keys used by LLM for decision making.
    """
    try:
        # Fetch from our own API server
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"http://localhost:8000/microstructure/{symbol}")
            if response.status_code == 200:
                data = response.json()
                features = data.get("features", {})
                scenario = data.get("scenario", {})
                mc = data.get("monte_carlo", {})
                
                # Map to LLM expected keys
                return {
                    "mid": features.get("current_price", 0.0),
                    "spread": features.get("spread_current", 0.0),
                    "spread_bps": features.get("spread_bps", 0.0),
                    "ofi": features.get("ofi", 0.0),
                    "depth_imbalance": features.get("depth_imbalance", 0.0),
                    "microprice": features.get("microprice", 0.0),
                    "microprice_delta_bps": abs(features.get("microprice", 0.0) - features.get("current_price", 0.0)) / features.get("current_price", 1.0) * 10000,
                    "qv_x1e4": features.get("quadratic_variation", 0.0) * 10000,
                    "ctr": 0.0,  # Would need tick data
                    "refill_rate": 0.0,  # Would need order book history
                    "impact_lambda": features.get("price_impact_lambda", 0.0),
                    "tp_hit_prob": mc.get("tp_hit_prob", 0.5),
                    "sl_hit_prob": mc.get("sl_hit_prob", 0.5),
                    "upside_prob": mc.get("upside_prob", 0.5),
                    "var_5_usd": mc.get("var_5pct", 0.0),
                    "realized_vol": features.get("realized_vol", 0.0),
                    "liquidity_concentration": features.get("liquidity_concentration", 0.5),
                    "effective_spread_bps": features.get("effective_spread_bps", 0.0),
                    "market_depth_elasticity": features.get("market_depth_elasticity", 0.0),
                    "trade_count": features.get("trade_count", 0)
                }
    except Exception as e:
        print(f"Error fetching metrics: {e}")
    
    # Fallback
    return {
        "mid": 0.0, "spread": 0.0, "spread_bps": 0.0, "ofi": 0.0, "depth_imbalance": 0.0,
        "microprice": 0.0, "microprice_delta_bps": 0.0, "qv_x1e4": 0.0, "ctr": 0.0,
        "refill_rate": 0.0, "impact_lambda": 0.0, "tp_hit_prob": 0.5, "sl_hit_prob": 0.5,
        "upside_prob": 0.5, "var_5_usd": 0.0
    }


def _pplx_client():
    base_url = os.getenv("PPLX_BASE_URL", "https://api.perplexity.ai")
    api_key  = os.environ.get("PPLX_API_KEY", "")
    
    # Try to load from file if not in environment
    if not api_key:
        try:
            with open("pplx_api.txt", "r") as f:
                api_key = f.read().strip()
        except FileNotFoundError:
            pass
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    return base_url, headers


def get_context(symbol: str) -> Dict[str, Any]:
    """
    Calls Perplexity (OpenAI-compatible) to summarize last-60m token context.
    Returns: basis_bps, funding_8h_bps, sentiment_score in [-1,1], headline_bullets[]
    """
    if not os.environ.get("PPLX_API_KEY"):
        # Skip LLM call if no API key
        return {
            "basis_bps": 0.0,
            "funding_8h_bps": 0.0,
            "sentiment_score": 0.0,
            "headline_bullets": []
        }
    
    base_url, headers = _pplx_client()
    model = os.getenv("PPLX_MODEL", "sonar")

    prompt = f"""
You are a crypto market context summarizer.
Task: For {symbol}, produce a compact JSON with fields:
- "sentiment_score": float in [-1,1] (aggregate of last 60 minutes, conservative),
- "headline_bullets": array of <=5 short bullets of notable drivers in last 60 minutes.
If insufficient info, set sentiment_score=0 and bullets=[].
Return JSON only.
    """.strip()

    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "return_citations": False,
        "return_images": False
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{base_url}/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Perplexity API error: {e}")
        content = '{"sentiment_score":0,"headline_bullets":[]}'

    # Merge context
    ctx = {"basis_bps": 0.0, "funding_8h_bps": 0.0, "sentiment_score": 0.0, "headline_bullets": []}
    try:
        import json
        ctx_llm = json.loads(content)
        ctx.update({k: ctx_llm.get(k, ctx[k]) for k in ctx.keys() if k in ctx_llm})
    except Exception:
        pass
    return ctx


def get_risk_envelope() -> Dict[str, Any]:
    """Get risk management parameters from environment."""
    return {
        "max_risk_per_trade_usd": float(os.getenv("MAX_RISK_PER_TRADE_USD", "500")),
        "daily_var_5_limit_usd": float(os.getenv("DAILY_VAR5_LIMIT_USD", "5000")),
        "max_slippage_bps": float(os.getenv("MAX_SLIPPAGE_BPS", "2.0")),
        "ctr_threshold": float(os.getenv("CTR_THRESHOLD", "4.0")),
        "spoofing_index_threshold": float(os.getenv("SPOOFING_INDEX_THRESHOLD", "0.7")),
        "qv_x1e4_max": float(os.getenv("QV_X1E4_MAX", "0.6")),
        "spread_bps_max": float(os.getenv("SPREAD_BPS_MAX", "2.0"))
    }

