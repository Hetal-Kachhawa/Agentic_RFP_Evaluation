import os
from db.database import get_conn, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    weight REAL NOT NULL,
    max_score INTEGER NOT NULL DEFAULT 10,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS supplier_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfp_run_id TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    submission_date TEXT,
    experience_rating REAL,
    absolute_score REAL,
    ppi REAL,
    final_rank INTEGER,
    result_json TEXT,
    FOREIGN KEY (rfp_run_id) REFERENCES rfp_runs(rfp_run_id)
);
"""

SEED = [
    (1, "Technical Capability", "Architecture, integrations, scalability, technical fit", 30, 10, 1),
    (2, "Implementation Plan", "Timeline, milestones, staffing, risk plan", 20, 10, 1),
    (3, "Commercial Value", "Pricing clarity, total cost, assumptions", 20, 10, 1),
    (4, "Security & Compliance", "Controls, certifications, privacy, auditability", 20, 10, 1),
    (5, "Support & Experience", "Support model, similar projects, references", 10, 10, 1),
]


def init_db():
    """Safe to call on every app start: creates tables, seeds only if empty."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO evaluation_criteria VALUES (?, ?, ?, ?, ?, ?)", SEED
            )


if __name__ == "__main__":
    init_db()
    print("Database ready at", DB_PATH)
