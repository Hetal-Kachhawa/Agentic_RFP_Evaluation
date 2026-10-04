import sqlite3, json, os, uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rfp.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_active_criteria():
    """Always reads fresh from the DB, so weight changes apply without code changes."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT criterion_id, name, description, weight, max_score
               FROM evaluation_criteria WHERE is_active = 1
               ORDER BY criterion_id"""
        ).fetchall()
    return [dict(r) for r in rows]


def create_run():
    run_id = "RUN-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO rfp_runs (rfp_run_id, created_at, status) VALUES (?, ?, ?)",
            (run_id, datetime.now().isoformat(timespec="seconds"), "RUNNING"),
        )
    return run_id


def update_run_status(run_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE rfp_runs SET status = ? WHERE rfp_run_id = ?", (status, run_id))


def save_supplier_result(run_id, r):
    """r = dict with supplier_name, submission_date, experience_rating,
    absolute_score, ppi, final_rank and any extra detail."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO supplier_results
               (rfp_run_id, supplier_name, submission_date, experience_rating,
                absolute_score, ppi, final_rank, result_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, r["supplier_name"], r["submission_date"], r["experience_rating"],
             r["absolute_score"], r["ppi"], r["final_rank"], json.dumps(r)),
        )


def get_run_results(run_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT result_json FROM supplier_results WHERE rfp_run_id = ? ORDER BY final_rank",
            (run_id,),
        ).fetchall()
    return [json.loads(r["result_json"]) for r in rows]
