from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from db.init_db import init_db
from db.database import (get_active_criteria, create_run, update_run_status,
                         save_supplier_result)
from tools.document_tool import extract_text
from tools.validation_tool import validate_scorecard
from tools.ranking_tool import rank_suppliers
from agents.evaluation_agent import evaluate_supplier


class RFPState(TypedDict, total=False):
    suppliers_input: List[Dict[str, Any]]   # name, date, experience, pdf_bytes, filename
    api_key: str
    criteria: List[Dict[str, Any]]
    run_id: str
    evaluated: List[Dict[str, Any]]
    ranking: Dict[str, Any]
    warnings: List[str]
    errors: List[str]


def node_setup(state):
    init_db()
    criteria = get_active_criteria()
    if not criteria:
        raise ValueError("No active criteria found in the database.")
    run_id = create_run()
    warnings = list(state.get("warnings", []))
    total = sum(c["weight"] for c in criteria)
    if abs(total - 100) > 0.01:
        warnings.append(f"Active criteria weights total {total}, not 100.")
    return {"criteria": criteria, "run_id": run_id, "warnings": warnings,
            "evaluated": [], "errors": []}


def node_evaluate_all(state):
    """For each supplier: extract text (tool) -> LLM score (agent) -> validate (tool)."""
    criteria = state["criteria"]
    warnings = list(state["warnings"])
    errors = list(state["errors"])
    evaluated = []

    for s in state["suppliers_input"]:
        name = s["supplier_name"]
        doc = extract_text(s["pdf_bytes"], s.get("filename", name))
        warnings.extend(doc["warnings"])
        if not doc["text"].strip():
            errors.append(f"[{name}] No text could be extracted. Supplier skipped.")
            continue
        try:
            raw = evaluate_supplier(name, doc["text"], criteria, api_key=state.get("api_key"))
        except Exception as e:
            errors.append(f"[{name}] LLM call failed: {e}. Supplier skipped.")
            continue
        scorecard, v_warnings = validate_scorecard(raw, criteria, name)
        warnings.extend(v_warnings)
        evaluated.append({
            "supplier_name": name,
            "submission_date": s["submission_date"],
            "experience_rating": s["experience_rating"],
            "scorecard": scorecard,
        })
    return {"evaluated": evaluated, "warnings": warnings, "errors": errors}


def node_rank(state):
    if not state["evaluated"]:
        return {"ranking": {}, "errors": state["errors"] + ["No suppliers could be evaluated."]}
    ranking = rank_suppliers(state["evaluated"], state["criteria"])
    return {"ranking": ranking, "warnings": state["warnings"] + ranking["warnings"]}


def node_persist(state):
    run_id = state["run_id"]
    if not state.get("ranking"):
        update_run_status(run_id, "FAILED")
        return {}
    for r in state["ranking"]["suppliers"]:
        save_supplier_result(run_id, r)
    update_run_status(run_id, "COMPLETED")
    return {}


def build_graph():
    g = StateGraph(RFPState)
    g.add_node("setup", node_setup)
    g.add_node("evaluate", node_evaluate_all)
    g.add_node("rank", node_rank)
    g.add_node("persist", node_persist)
    g.set_entry_point("setup")
    g.add_edge("setup", "evaluate")
    g.add_edge("evaluate", "rank")
    g.add_edge("rank", "persist")
    g.add_edge("persist", END)
    return g.compile()


def run_workflow(suppliers_input, api_key=None):
    """Entry point used by the Streamlit app. Returns a single result dict."""
    final = build_graph().invoke({"suppliers_input": suppliers_input, "api_key": api_key,
                                  "warnings": [], "errors": []})
    ranking = final.get("ranking", {})
    return {
        "rfp_run_id": final["run_id"],
        "criteria": final["criteria"],
        "suppliers": ranking.get("suppliers", []),
        "benchmarks": ranking.get("benchmarks", {}),
        "tie_break_notes": ranking.get("tie_break_notes", []),
        "warnings": final.get("warnings", []),
        "errors": final.get("errors", []),
    }
