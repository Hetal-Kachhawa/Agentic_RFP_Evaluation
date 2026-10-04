from tools.ranking_tool import rank_suppliers
from tools.validation_tool import validate_scorecard

CRIT = [
    {"criterion_id": 1, "name": "A", "weight": 60, "max_score": 10},
    {"criterion_id": 2, "name": "B", "weight": 40, "max_score": 10},
]

def card(name, s1, s2):
    return {"supplier_name": name, "criteria": [
        {"criterion_id": 1, "name": "A", "weight": 60, "score": s1, "max_score": 10, "justification": "", "evidence": ""},
        {"criterion_id": 2, "name": "B", "weight": 40, "score": s2, "max_score": 10, "justification": "", "evidence": ""},
    ], "risks": [], "overall_summary": ""}

def sup(name, s1, s2, date="2026-01-10", exp=3):
    return {"supplier_name": name, "submission_date": date, "experience_rating": exp, "scorecard": card(name, s1, s2)}

def test_hand_calculated_values():
    out = rank_suppliers([sup("X", 8, 5), sup("Y", 6, 10)], CRIT)
    x = next(s for s in out["suppliers"] if s["supplier_name"] == "X")
    y = next(s for s in out["suppliers"] if s["supplier_name"] == "Y")
    assert x["absolute_score"] == 68.0 and y["absolute_score"] == 76.0
    assert x["ppi"] == 80.0 and y["ppi"] == 85.0
    assert out["suppliers"][0]["supplier_name"] == "Y"
    assert out["benchmarks"] == {1: 8, 2: 10}

def test_gap_is_zero_for_leader_else_negative():
    out = rank_suppliers([sup("X", 8, 5), sup("Y", 6, 10)], CRIT)
    x = next(s for s in out["suppliers"] if s["supplier_name"] == "X")
    assert x["criteria"][0]["gap"] == 0 and x["criteria"][1]["gap"] == -5

def test_tiebreak_date():
    out = rank_suppliers([sup("B", 5, 5, "2026-01-12"), sup("A", 5, 5, "2026-01-10")], CRIT)
    assert [s["supplier_name"] for s in out["suppliers"]] == ["A", "B"]

def test_tiebreak_experience():
    out = rank_suppliers([sup("A", 5, 5, exp=2), sup("B", 5, 5, exp=4)], CRIT)
    assert out["suppliers"][0]["supplier_name"] == "B"

def test_tiebreak_name():
    out = rank_suppliers([sup("Zed", 5, 5), sup("Alpha", 5, 5)], CRIT)
    assert [s["supplier_name"] for s in out["suppliers"]] == ["Alpha", "Zed"]
    assert [s["final_rank"] for s in out["suppliers"]] == [1, 2]

def test_zero_benchmark_is_safe():
    out = rank_suppliers([sup("X", 0, 5), sup("Y", 0, 5)], CRIT)
    assert all(c["relative_pct"] == 100.0 for c in out["suppliers"][0]["criteria"][:1])

def test_deterministic():
    data = [sup("X", 8, 5), sup("Y", 6, 10), sup("Z", 7, 7)]
    assert rank_suppliers(data, CRIT) == rank_suppliers(data, CRIT)

def test_validation_fixes_bad_llm_output():
    raw = '```json\n{"criteria":[{"criterion_id":1,"score":15,"justification":"x","evidence":"y"},{"criterion_id":99,"score":5}]}\n```'
    card_, warns = validate_scorecard(raw, CRIT, "X")
    assert card_["criteria"][0]["score"] == 10.0          # clipped
    assert card_["criteria"][1]["score"] == 0.0           # missing -> 0
    assert len(warns) >= 3                                # clip, unknown id, missing

def test_validation_garbage_input():
    card_, warns = validate_scorecard("sorry I cannot do that", CRIT, "X")
    assert [c["score"] for c in card_["criteria"]] == [0.0, 0.0] and warns
