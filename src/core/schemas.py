"""
Pydantic schemas for TEPM Analytics Dashboard.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Literal, Optional, Union

ActionDecision = Literal["ENTER_LONG","ENTER_SHORT","SCALE_IN","REDUCE","CLOSE","HEDGE_SPOT_WITH_FUT","REMOVE_HEDGE","HOLD"]
Stance = Literal["long","short","neutral","stand-down"]

class SuggestedAction(BaseModel):
    order_type: Literal["limit","market","post_only","ioc"]
    side: Literal["buy","sell"]
    qty_usd: float
    stop_bps: Optional[float] = None
    take_profit_bps: Optional[float] = None
    expiry_sec: int

class Evidence(BaseModel):
    metrics: Dict[str, float]
    context: Dict[str, Union[float, str, List[str]]]

class QAAnswer(BaseModel):
    answer: str
    stance: Stance
    time_horizon_min: int
    evidence: Evidence
    suggested_action: Optional[SuggestedAction] = None
    guardrails: Dict[str, List[str]] = Field(default_factory=lambda: {"violations": [], "stand_down_reasons": []})
    confidence_0_1: float

