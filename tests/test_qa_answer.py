"""
Tests for Q&A answer validation and guardrails.
"""

import json
from src.core.schemas import QAAnswer
from src.agents.qa_llm import vet_llm_answer


def test_vet_guardrails():
    """Test that guardrails force stand-down on violations."""
    ans = {
        "answer": "test answer",
        "stance": "long",
        "time_horizon_min": 15,
        "evidence": {"metrics": {}, "context": {}},
        "suggested_action": {
            "order_type": "limit",
            "side": "buy",
            "qty_usd": 1000,
            "expiry_sec": 120
        },
        "guardrails": {"violations": [], "stand_down_reasons": []},
        "confidence_0_1": 0.6
    }
    
    # Metrics that violate thresholds
    metrics = {
        "spread_bps": 3.0,  # Exceeds max
        "ctr": 5.0,  # Exceeds threshold
        "qv_x1e4": 0.7,  # Exceeds max
        "impact_lambda": 1e-6
    }
    
    env = {
        "spread_bps_max": 2.0,
        "ctr_threshold": 4.0,
        "qv_x1e4_max": 0.6,
        "max_slippage_bps": 2.0
    }
    
    out = vet_llm_answer(ans, metrics, env)
    
    # Should force stand-down
    assert out["stance"] == "stand-down"
    assert len(out["guardrails"]["violations"]) >= 1
    assert "spread_bps" in out["guardrails"]["violations"]
    assert "ctr" in out["guardrails"]["violations"]
    assert "qv" in out["guardrails"]["violations"]
    
    # Should remove suggested action
    assert "suggested_action" not in out or out["suggested_action"] is None
    
    # Should be valid QAAnswer
    QAAnswer(**{
        **out,
        "time_horizon_min": out.get("time_horizon_min", 15),
        "evidence": {"metrics": {}, "context": {}},
        "confidence_0_1": out.get("confidence_0_1", 0.0)
    })
    
    print("✅ Guardrails test passed")


def test_qa_answer_schema():
    """Test QAAnswer schema validation."""
    valid_answer = {
        "answer": "Market conditions favor a long position",
        "stance": "long",
        "time_horizon_min": 30,
        "evidence": {
            "metrics": {"mid": 106000, "ofi": 0.3, "spread_bps": 0.5},
            "context": {"sentiment_score": 0.2, "headline_bullets": ["Positive news"]}
        },
        "suggested_action": {
            "order_type": "limit",
            "side": "buy",
            "qty_usd": 500,
            "stop_bps": 50,
            "take_profit_bps": 100,
            "expiry_sec": 300
        },
        "guardrails": {"violations": [], "stand_down_reasons": []},
        "confidence_0_1": 0.75
    }
    
    qa = QAAnswer(**valid_answer)
    assert qa.stance == "long"
    assert qa.confidence_0_1 == 0.75
    assert qa.suggested_action is not None
    
    print("✅ Schema validation test passed")


if __name__ == "__main__":
    test_vet_guardrails()
    test_qa_answer_schema()
    print("\n✅ All tests passed!")

