import json, math, re
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError


class LLMCriterionResult(BaseModel):
    criterion_id: int
    score: float
    max_score: Optional[float] = None
    justification: str = ""
    evidence: str = ""


class LLMScorecard(BaseModel):
    """Schema we ask the LLM to follow (also used by the agent in Step 6)."""
    supplier_name: str = ""
    criteria: List[LLMCriterionResult] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    overall_summary: str = ""


def _parse_json(raw):
    """Accepts a dict or a string (possibly with ```json fences or extra text)."""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("LLM output is neither dict nor string")
    text = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM output")
    return json.loads(text[start:end + 1])


def validate_scorecard(raw, active_criteria, supplier_name):
    """
    Returns (normalized_scorecard, warnings).
    - one entry for EVERY active criterion (missing -> score 0, flagged)
    - score clipped to [0, max_score from DB]
    - unknown / duplicate / malformed entries ignored with a warning
    """
    warnings = []
    try:
        data = _parse_json(raw)
    except Exception as e:
        warnings.append(f"[{supplier_name}] Could not parse LLM JSON ({e}). All criteria set to 0.")
        data = {}

    # Validate each criterion item separately so one bad item doesn't kill the rest
    valid_items = {}
    for item in data.get("criteria", []) if isinstance(data.get("criteria"), list) else []:
        try:
            parsed = LLMCriterionResult.model_validate(item)
        except ValidationError:
            warnings.append(f"[{supplier_name}] Malformed criterion entry ignored: {str(item)[:80]}")
            continue
        if parsed.criterion_id in valid_items:
            warnings.append(f"[{supplier_name}] Duplicate result for criterion {parsed.criterion_id}; first one kept.")
            continue
        valid_items[parsed.criterion_id] = parsed

    active_ids = {c["criterion_id"] for c in active_criteria}
    for cid in valid_items:
        if cid not in active_ids:
            warnings.append(f"[{supplier_name}] Unknown criterion_id {cid} ignored.")

    normalized = []
    for c in active_criteria:
        cid, max_score = c["criterion_id"], c["max_score"]
        item = valid_items.get(cid)
        filled = False
        if item is None:
            warnings.append(f"[{supplier_name}] Missing result for '{c['name']}'. Score set to 0.")
            score, justification, evidence, filled = 0.0, "No result returned by the model.", "", True
        else:
            score, justification, evidence = item.score, item.justification, item.evidence
            if not math.isfinite(score):
                warnings.append(f"[{supplier_name}] Non-finite score for '{c['name']}'. Set to 0.")
                score = 0.0
            if score < 0 or score > max_score:
                clipped = min(max(score, 0.0), float(max_score))
                warnings.append(f"[{supplier_name}] Score {score} for '{c['name']}' outside 0-{max_score}. Clipped to {clipped}.")
                score = clipped
            if not evidence.strip():
                warnings.append(f"[{supplier_name}] No evidence given for '{c['name']}'.")
        normalized.append({
            "criterion_id": cid, "name": c["name"], "weight": c["weight"],
            "score": float(score), "max_score": float(max_score),
            "justification": justification, "evidence": evidence, "filled_default": filled,
        })

    risks = data.get("risks", []) if isinstance(data.get("risks"), list) else []
    scorecard = {
        "supplier_name": supplier_name,
        "criteria": normalized,
        "risks": [str(r) for r in risks],
        "overall_summary": str(data.get("overall_summary", "")),
    }
    return scorecard, warnings
