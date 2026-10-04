from datetime import date, datetime

ROUND = 2  # scores are rounded to 2 decimals BEFORE sorting, so displayed ties are real ties


def _to_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _decided_by(a, b):
    """Which tie-break rule put supplier a above supplier b?"""
    if a["ppi"] != b["ppi"]:
        return f"higher PPI ({a['ppi']} vs {b['ppi']})"
    if a["submission_date"] != b["submission_date"]:
        return f"PPI tied; earlier submission date ({a['submission_date']} vs {b['submission_date']})"
    if a["experience_rating"] != b["experience_rating"]:
        return f"PPI and date tied; higher experience rating ({a['experience_rating']} vs {b['experience_rating']})"
    return "PPI, date and experience tied; supplier name ascending"


def rank_suppliers(suppliers, criteria):
    """
    suppliers: list of {supplier_name, submission_date, experience_rating, scorecard}
               where scorecard comes from validate_scorecard()
    criteria:  active criteria from the DB
    """
    if not suppliers or not criteria:
        raise ValueError("Need at least one supplier and one active criterion.")

    warnings = []
    total_w = sum(c["weight"] for c in criteria)
    if total_w <= 0:
        raise ValueError("Active criteria weights must be positive.")
    if abs(total_w - 100) > 0.01:
        warnings.append(f"Active weights total {total_w}, not 100. Weights were normalised to 100.")
    wnorm = {c["criterion_id"]: c["weight"] / total_w * 100 for c in criteria}

    # 1) Benchmark = highest score per criterion across all suppliers
    benchmarks = {}
    for c in criteria:
        cid = c["criterion_id"]
        benchmarks[cid] = max(
            next(x["score"] for x in s["scorecard"]["criteria"] if x["criterion_id"] == cid)
            for s in suppliers
        )

    # 2) Per-supplier metrics
    results = []
    for s in suppliers:
        rows, absolute, ppi = [], 0.0, 0.0
        for x in s["scorecard"]["criteria"]:
            cid = x["criterion_id"]
            w = wnorm[cid]
            bench = benchmarks[cid]
            gap = x["score"] - bench                       # 0 for leader, else negative
            rel = 100.0 if bench == 0 else x["score"] / bench * 100   # safe handling: all-zero criterion -> 100
            absolute += x["score"] / x["max_score"] * w
            ppi += rel * w / 100
            rows.append({
                "criterion_id": cid, "name": x["name"], "weight": round(w, 4),
                "score": x["score"], "max_score": x["max_score"],
                "benchmark": bench, "gap": round(gap, 4), "relative_pct": round(rel, ROUND),
                "justification": x["justification"], "evidence": x["evidence"],
            })
        try:
            sub_date = _to_date(s["submission_date"])
        except Exception:
            sub_date = date.max
            warnings.append(f"[{s['supplier_name']}] Invalid submission date; treated as latest possible.")
        results.append({
            "supplier_name": s["supplier_name"],
            "submission_date": sub_date.isoformat(),
            "experience_rating": float(s.get("experience_rating") or 0),
            "absolute_score": round(absolute, ROUND),
            "ppi": round(ppi, ROUND),
            "criteria": rows,
            "risks": s["scorecard"]["risks"],
            "overall_summary": s["scorecard"]["overall_summary"],
        })

    # 3) Mandatory tie-break order -> stable sort -> sequential ranks
    results.sort(key=lambda r: (-r["ppi"], r["submission_date"], -r["experience_rating"], r["supplier_name"].casefold()))
    for i, r in enumerate(results, start=1):
        r["final_rank"] = i

    notes = [f"#{a['final_rank']} {a['supplier_name']} above #{b['final_rank']} {b['supplier_name']}: {_decided_by(a, b)}"
             for a, b in zip(results, results[1:])]

    return {"suppliers": results, "benchmarks": benchmarks,
            "tie_break_notes": notes, "warnings": warnings}
