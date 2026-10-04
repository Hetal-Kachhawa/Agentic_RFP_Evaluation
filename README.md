

# Agentic RFP Evaluation & Supplier Ranking

An AI-assisted Streamlit app that reads supplier RFP proposals (PDF), scores them against configurable criteria stored in SQLite, benchmarks suppliers against their peers, and produces an explainable leaderboard.

**The LLM judges proposal content only. Python does all arithmetic, benchmarking, tie-breaks and ranking.**

- **Live app:** https://agenticrfpevaluation-zah5tpbyp4ja8caq4mcays.streamlit.app/
- **Demo video:** 

## Tech stack
Streamlit, SQLite, LangGraph (orchestration), LangChain + Cohere `command-r-plus-08-2024` (evaluation), Pydantic (validation), PyMuPDF (PDF text), pytest.

## Architecture

```
Setup -> Input -> Batch -> Evaluate -> Validate -> Score -> Benchmark -> Rank -> Persist -> Present
```

| Component | File | Role |
|---|---|---|
| Orchestrator (LangGraph) | `agents/orchestrator.py` | Runs the workflow: setup, evaluate, rank, persist |
| Evaluation Agent | `agents/evaluation_agent.py` | Prompts the LLM to return JSON scores with evidence for one supplier |
| Document Tool | `tools/document_tool.py` | Extracts text from PDFs |
| Validation Tool | `tools/validation_tool.py` | Parses JSON, fills missing criteria, clips scores, records warnings |
| Ranking Tool | `tools/ranking_tool.py` | Deterministic scores, benchmarks, PPI, tie-breaks, ranks (no LLM) |
| Database | `db/` | Schema, seed criteria, read/write helpers |
| UI | `app.py` | Streamlit screens |

The LLM is called in only one place (the evaluate node). Max scores and weights always come from the database, never from the LLM.

## Formulas
- **Absolute weighted score** = sum of (score / max_score) x weight
- **Criterion benchmark** = highest valid score for that criterion across all suppliers
- **Criterion gap** = supplier score - benchmark (0 for the leader, otherwise negative)
- **Relative %** = (supplier score / benchmark) x 100. If the benchmark is 0, relative % is set to 100 (nobody scored on that criterion, so nobody is behind)
- **PPI (Peer Performance Index)** = weighted average of relative % across criteria
- **Tie-break order:** higher PPI, then earlier submission date, then higher experience rating, then supplier name ascending. Ranks 1, 2, 3... are assigned only after this sort. Scores are rounded to 2 decimals before sorting.

## Validation rules
Missing criteria get score 0 and a warning. Scores outside 0 to max_score are clipped with a warning. Unknown, duplicate or malformed entries are ignored with a warning. Unparseable output sets all scores to 0. If active weights do not total 100, they are normalised.

## Database (SQLite)
`evaluation_criteria`, `rfp_runs`, `supplier_results` (full result stored as JSON per supplier under one `rfp_run_id`). The database is created and seeded automatically on startup. To change criteria, edit the `evaluation_criteria` table (weight, max_score, is_active); no code changes are needed.

## Setup
```bash
git clone https://github.com/<USERNAME>/Agentic_RFP_Evaluation.git
cd Agentic_RFP_Evaluation
pip install -r requirements.txt
export COHERE_API_KEY="your-key"     # Windows: set COHERE_API_KEY=your-key
streamlit run app.py
```
On Streamlit Community Cloud, add `COHERE_API_KEY` under Settings, Secrets. Run tests with `python -m pytest -q tests`.

## Synthetic data
`data/sample_rfps/` contains four fictional proposals (Apex Systems, BrightPath Tech, NexaWorks, Orbit Digital), each with different prices, timelines, strengths and gaps. No real supplier data is used.

## Sample output
`sample_output/run_export.json` is the exported result of one completed run.

## Screenshots
| | |
|---|---|
| Criteria | ![Criteria](screenshots/1_criteria.png) |
| Input and evaluation | ![Input](screenshots/2_input_running.png) |
| Leaderboard | ![Leaderboard](screenshots/3_leaderboard.png) |
| Detailed scorecard | ![Scorecard](screenshots/4_scorecard.png) |
| Run details | ![Run details](screenshots/5_run_details.png) |
| Validation error (duplicate names) | ![Error](screenshots/6_error_duplicate_names.png) |

## Assumptions and limitations
- Submission date and experience rating (1 to 5) are entered by the user at upload time and are used only for tie-breaking.
- Scoring uses temperature 0, but LLM scores can still vary slightly between runs. Formulas and ordering are deterministic once scorecards are validated.
- The Cohere free trial key is rate-limited. If a 429 error appears, wait a minute and retry; affected suppliers are skipped and listed under Errors.
- Text-based PDFs only (scanned image PDFs are flagged). Text is truncated at 30,000 characters.
- Suppliers are evaluated one at a time.
- Streamlit Cloud storage is temporary, so the database resets on restart and is recreated automatically.
