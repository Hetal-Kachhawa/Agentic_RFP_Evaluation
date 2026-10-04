import os, json
from datetime import date
import pandas as pd
import streamlit as st

from db.init_db import init_db
from db.database import get_active_criteria
from agents.orchestrator import run_workflow

st.set_page_config(page_title="Agentic RFP Evaluator", page_icon="📄", layout="wide")
init_db()  # creates + seeds the database if it doesn't exist (needed on Streamlit Cloud)


def get_api_key():
    try:
        key = st.secrets["COHERE_API_KEY"]
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("COHERE_API_KEY")


def guess_name(filename):
    base = os.path.splitext(filename)[0]
    for sep in ["—", "–", " - "]:
        if sep in base:
            return base.split(sep)[0].strip()
    return base.strip()


st.title("📄 Agentic RFP Evaluation & Supplier Ranking")
st.caption("LLM judges proposal content. Python does all scoring, benchmarking, tie-breaks and ranking.")

tab_criteria, tab_input, tab_board, tab_score, tab_run = st.tabs(
    ["1. Criteria", "2. Supplier Input", "3. Leaderboard", "4. Detailed Scorecard", "5. Run Details"]
)

# ---------------- Criteria ----------------
with tab_criteria:
    criteria = get_active_criteria()
    total = sum(c["weight"] for c in criteria)
    st.subheader("Active evaluation criteria")
    st.dataframe(
        pd.DataFrame(criteria).rename(columns={
            "criterion_id": "ID", "name": "Criterion", "description": "What the LLM inspects",
            "weight": "Weight (%)", "max_score": "Max score"}),
        use_container_width=True, hide_index=True)
    st.metric("Total weight", f"{total:g}%")
    if abs(total - 100) > 0.01:
        st.warning("Active weights do not total 100%. They will be normalised during ranking.")

# ---------------- Supplier input ----------------
with tab_input:
    st.subheader("Upload supplier proposals")
    files = st.file_uploader("Supplier RFP PDFs", type=["pdf"], accept_multiple_files=True)

    entries = []
    for i, f in enumerate(files or []):
        st.markdown(f"**{f.name}**")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Supplier name", value=guess_name(f.name), key=f"name_{i}_{f.name}")
        sub = c2.date_input("Submission date", value=date.today(), key=f"date_{i}_{f.name}")
        exp = c3.slider("Historical experience rating (1-5)", 1, 5, 3, key=f"exp_{i}_{f.name}")
        entries.append({"name": name, "date": sub, "exp": exp, "file": f})

    def validate_inputs():
        problems = []
        if not entries:
            problems.append("Upload at least one supplier PDF.")
        names = [e["name"].strip().casefold() for e in entries]
        if any(not n for n in names):
            problems.append("Every supplier needs a name.")
        if len(set(names)) != len(names):
            problems.append("Supplier names must be unique.")
        if not get_api_key():
            problems.append("COHERE_API_KEY is not configured.")
        if not get_active_criteria():
            problems.append("No active criteria in the database.")
        return problems

    problems = validate_inputs() if entries else []
    for p in problems:
        st.error(p)

    if st.button("🚀 Evaluate suppliers", type="primary", disabled=not entries):
        problems = validate_inputs()
        if problems:
            st.error("Fix the issues above before evaluating.")
        else:
            inputs = [{
                "supplier_name": e["name"].strip(),
                "submission_date": e["date"].isoformat(),
                "experience_rating": e["exp"],
                "pdf_bytes": e["file"].getvalue(),
                "filename": e["file"].name,
            } for e in entries]
            with st.spinner("Reading proposals and scoring... this can take a minute."):
                st.session_state["result"] = run_workflow(inputs, api_key=get_api_key())
            res = st.session_state["result"]
            if res["suppliers"]:
                st.success(f"Done. Run ID: {res['rfp_run_id']}. Open the Leaderboard tab.")
            else:
                st.error("No supplier could be evaluated. See Run Details for errors.")

result = st.session_state.get("result")

# ---------------- Leaderboard ----------------
with tab_board:
    if not result or not result["suppliers"]:
        st.info("Run an evaluation first.")
    else:
        st.subheader("Final leaderboard")
        df = pd.DataFrame([{
            "Rank": s["final_rank"], "Supplier": s["supplier_name"],
            "Absolute score": s["absolute_score"], "PPI": s["ppi"],
            "Submission date": s["submission_date"], "Experience rating": s["experience_rating"],
        } for s in result["suppliers"]])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.bar_chart(df.set_index("Supplier")[["PPI"]])

# ---------------- Detailed scorecard ----------------
with tab_score:
    if not result or not result["suppliers"]:
        st.info("Run an evaluation first.")
    else:
        names = [s["supplier_name"] for s in result["suppliers"]]
        choice = st.selectbox("Supplier", names)
        s = next(x for x in result["suppliers"] if x["supplier_name"] == choice)
        m1, m2, m3 = st.columns(3)
        m1.metric("Rank", f"#{s['final_rank']}")
        m2.metric("Absolute score", s["absolute_score"])
        m3.metric("PPI", s["ppi"])

        st.dataframe(pd.DataFrame([{
            "Criterion": c["name"], "Weight (%)": c["weight"],
            "Score": f"{c['score']:g}/{c['max_score']:g}", "Benchmark": c["benchmark"],
            "Gap": c["gap"], "Relative %": c["relative_pct"],
        } for c in s["criteria"]]), use_container_width=True, hide_index=True)

        st.markdown("#### Justification and evidence")
        for c in s["criteria"]:
            with st.expander(f"{c['name']}: {c['score']:g}/{c['max_score']:g}"):
                st.markdown(f"**Justification:** {c['justification']}")
                st.markdown(f"**Evidence:** {c['evidence'] or '_none provided_'}")
        if s["risks"]:
            st.markdown("#### Risks")
            for r in s["risks"]:
                st.write(f"- {r}")
        st.markdown("#### Summary")
        st.write(s["overall_summary"])

# ---------------- Run details ----------------
with tab_run:
    if not result:
        st.info("Run an evaluation first.")
    else:
        st.subheader("Run details")
        st.code(result["rfp_run_id"], language=None)
        st.markdown("**Tie-break explanation**")
        for n in result["tie_break_notes"] or ["Only one supplier, no tie-breaks needed."]:
            st.write(f"- {n}")
        if result["errors"]:
            st.markdown("**Errors**")
            for e in result["errors"]:
                st.error(e)
        st.markdown("**Warnings**")
        if result["warnings"]:
            for w in result["warnings"]:
                st.warning(w)
        else:
            st.write("None")
        st.download_button(
            "⬇️ Download complete result (JSON)",
            data=json.dumps(result, indent=2, default=str),
            file_name=f"{result['rfp_run_id']}.json", mime="application/json")
