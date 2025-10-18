"""
OpenAI-compatible client for Perplexity LLM Q&A assistant.
Enforces guardrails and returns structured QAAnswer.
"""

import os
import json
import httpx
from typing import Dict, Any
from pydantic import ValidationError
from ..core.schemas import QAAnswer
from .tools import get_metrics, get_context, get_risk_envelope


def _pplx_call(messages: list, model: str, temperature: float = 0.1) -> str:
    """Call Perplexity API (OpenAI-compatible)."""
    base_url = os.getenv("PPLX_BASE_URL", "https://api.perplexity.ai")
    api_key  = os.environ.get("PPLX_API_KEY", "")
    
    # Try to load from file if not in environment
    if not api_key:
        try:
            with open("pplx_api.txt", "r") as f:
                api_key = f.read().strip()
        except FileNotFoundError:
            pass
    
    if not api_key:
        raise ValueError("PPLX_API_KEY environment variable not set and pplx_api.txt not found")
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "return_citations": False,
        "return_images": False
    }
    
    with httpx.Client(timeout=45.0) as client:
        r = client.post(f"{base_url}/chat/completions", headers=headers, json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


SYSTEM = """You are a conservative intraday trading assistant for cryptocurrency markets.

RULES:
1) You MUST base answers on live metrics and context fetched by tools (the caller supplies them).
2) Respect guardrails: if any breach occurs, stance="stand-down", no suggested_action.
3) Prefer neutral/stand-down if confidence < 0.55.
4) Order type rules:
   - market only if spread_bps<0.6 AND impact small AND OFI confirms
   - else limit/post_only
5) Output STRICT JSON conforming to QAAnswer schema:
   {
     "answer": "plain English explanation",
     "stance": "long" | "short" | "neutral" | "stand-down",
     "time_horizon_min": <integer minutes>,
     "evidence": {"metrics": {...}, "context": {...}},
     "suggested_action": {...} or null,
     "guardrails": {"violations": [], "stand_down_reasons": []},
     "confidence_0_1": <float 0-1>
   }

No prose outside JSON. Be conservative."""


def vet_llm_answer(ans: Dict[str, Any], metrics: Dict[str, Any], env: Dict[str, Any]) -> Dict[str, Any]:
    """
    Post-process LLM answer to enforce hard guardrails.
    Forces stand-down if risk thresholds are breached.
    """
    reasons = []
    
    # Check spread
    if metrics.get("spread_bps", 0) > env["spread_bps_max"]:
        reasons.append("spread_bps")
    
    # Check CTR
    if metrics.get("ctr", 0) > env["ctr_threshold"]:
        reasons.append("ctr")
    
    # Check QV
    if metrics.get("qv_x1e4", 0) > env["qv_x1e4_max"]:
        reasons.append("qv")
    
    # Check slippage if action is suggested
    sa = ans.get("suggested_action")
    if sa:
        est_slip_bps = (metrics.get("impact_lambda", 0) * sa.get("qty_usd", 0)) * 1e4
        if est_slip_bps > env["max_slippage_bps"]:
            reasons.append("slippage")
    
    # Force stand-down if violations
    if reasons:
        ans["stance"] = "stand-down"
        ans.pop("suggested_action", None)
        ans.setdefault("guardrails", {"violations": [], "stand_down_reasons": []})
        ans["guardrails"]["violations"] = reasons
        ans["guardrails"]["stand_down_reasons"] = reasons
    
    return ans


def answer_question(question: str, symbol: str, window_sec: int = 300) -> QAAnswer:
    """
    Answer a trading question using LLM with live market data.
    
    Args:
        question: User's question
        symbol: Asset symbol (e.g., "BTC-USD")
        window_sec: Time window for metrics
        
    Returns:
        QAAnswer with stance, evidence, and optional action
    """
    model = os.getenv("PPLX_MODEL", "sonar")
    
    # Fetch live data
    metrics = get_metrics(symbol, window_sec=window_sec)
    context = get_context(symbol)
    env     = get_risk_envelope()

    user_prompt = {
        "role": "user",
        "content": f"""Question: {question}

Symbol: {symbol}

Live Metrics (JSON):
{json.dumps(metrics, indent=2)}

Market Context (JSON):
{json.dumps(context, indent=2)}

Risk Envelope (JSON):
{json.dumps(env, indent=2)}

Return QAAnswer JSON only. Be conservative - prefer stand-down if uncertain."""
    }

    try:
        content = _pplx_call(
            messages=[{"role": "system", "content": SYSTEM}, user_prompt],
            model=model,
            temperature=0.1
        )
    except Exception as e:
        # Fallback if Perplexity fails
        print(f"LLM call failed: {e}")
        ans_dict = {
            "answer": f"LLM service unavailable. Based on current metrics: Price ${metrics.get('mid', 0):.2f}, OFI {metrics.get('ofi', 0):.3f}, Vol {metrics.get('realized_vol', 0)*100:.1f}%. Standing down due to system error.",
            "stance": "stand-down",
            "time_horizon_min": 15,
            "evidence": {"metrics": metrics, "context": context},
            "guardrails": {"violations": ["llm_error"], "stand_down_reasons": ["llm_error"]},
            "confidence_0_1": 0.0
        }
        return QAAnswer(**ans_dict)

    # Parse LLM response
    try:
        # Try to extract JSON from response (in case LLM added prose)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        ans_dict = json.loads(content)
        
        # Ensure required fields with defaults
        ans_dict.setdefault("answer", content[:200])
        ans_dict.setdefault("stance", "neutral")
        ans_dict.setdefault("time_horizon_min", 15)
        ans_dict.setdefault("evidence", {"metrics": metrics, "context": context})
        ans_dict.setdefault("guardrails", {"violations": [], "stand_down_reasons": []})
        ans_dict.setdefault("confidence_0_1", 0.5)
        
    except Exception as e:
        print(f"Failed to parse LLM response: {e}")
        print(f"Raw response: {content[:300]}")
        ans_dict = {
            "answer": content[:500] if content else "Insufficient or malformed response. Standing down.",
            "stance": "stand-down",
            "time_horizon_min": 15,
            "evidence": {"metrics": metrics, "context": context},
            "guardrails": {"violations": ["parse_error"], "stand_down_reasons": ["parse_error"]},
            "confidence_0_1": 0.0
        }

    # Apply guardrails vetting
    ans_dict = vet_llm_answer(ans_dict, metrics, env)
    
    # Ensure evidence is present
    if "evidence" not in ans_dict:
        ans_dict["evidence"] = {"metrics": metrics, "context": context}
    
    # Validate and return
    try:
        return QAAnswer(**ans_dict)
    except ValidationError as e:
        print(f"Validation failed: {e}")
        # Final fallback to safe stand-down
        safe = {
            "answer": "Validation failed; standing down for safety.",
            "stance": "stand-down",
            "time_horizon_min": 15,
            "evidence": {"metrics": metrics, "context": context},
            "guardrails": {"violations": ["validation_error"], "stand_down_reasons": ["validation_error"]},
            "confidence_0_1": 0.0
        }
        return QAAnswer(**safe)

