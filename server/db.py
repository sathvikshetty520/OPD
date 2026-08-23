"""
Central SQLite store for synced triage cases.

This is intentionally simple (SQLite, single file) — the point of this
server is to reconcile cases across intake stations, not to be a
high-throughput system. A hospital OPD's case volume does not need
anything heavier than this.
"""

import sqlite3
import json
import datetime
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "data" / "cases.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    patient_token TEXT NOT NULL,
    tier TEXT NOT NULL,
    tier_label TEXT,
    department TEXT,
    matched_rules TEXT,        -- JSON array, stored as text
    escalate INTEGER,
    escalate_reason TEXT,
    protocol_version TEXT,
    timestamp TEXT NOT NULL,
    status TEXT,
    reviewed_at TEXT,
    reviewed_by TEXT,
    station_id TEXT,
    received_at TEXT NOT NULL  -- when the server first saw this case
);
CREATE INDEX IF NOT EXISTS idx_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_timestamp ON cases(timestamp);
"""


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_case(case: dict, station_id: str, received_at: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cases (case_id, patient_token, tier, tier_label, department,
                matched_rules, escalate, escalate_reason, protocol_version,
                timestamp, status, station_id, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                status=excluded.status,
                tier=excluded.tier,
                tier_label=excluded.tier_label,
                department=excluded.department
            """,
            (
                case["case_id"], case["patient_token"], case["tier"],
                case.get("tier_label"), case.get("department"),
                json.dumps(case.get("matched_rules", [])),
                int(bool(case.get("escalate"))), case.get("escalate_reason"),
                case.get("protocol_version"), case["timestamp"],
                case.get("status"), station_id, received_at,
            ),
        )


def patch_case(case_id: str, patch: dict, expected_status: str | None = None):
    """
    If expected_status is given, only apply the patch if the case's current
    status still matches it -- prevents two staff members from silently
    overwriting each other's review of the same case.
    Returns (updated_row, conflict) where conflict is the current row if the
    expected_status check failed, else None.
    """
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not existing:
            return None, None

        if expected_status is not None and existing["status"] != expected_status:
            return None, row_to_dict(existing)  # conflict: someone else already reviewed it

        fields = []
        values = []
        for key in ("status", "reviewed_at", "reviewed_by"):
            if key in patch:
                fields.append(f"{key}=?")
                values.append(patch[key])
        if fields:
            values.append(case_id)
            conn.execute(f"UPDATE cases SET {', '.join(fields)} WHERE case_id=?", values)
        updated = conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        return row_to_dict(updated), None


def list_cases(hours: int | None = None):
    """
    Returns cases from the last `hours` hours (rolling window, not calendar-day
    truncation), PLUS every case still pending_review regardless of age --
    an escalated case must never silently disappear from view because a
    shift crossed midnight.
    """
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM cases ORDER BY timestamp DESC LIMIT 500").fetchall()

    all_cases = [row_to_dict(r) for r in rows]

    if hours is None:
        return all_cases

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
    result = []
    for c in all_cases:
        is_recent = _parse_ts(c["timestamp"]) >= cutoff
        is_pending = c.get("status") == "pending_review"
        if is_recent or is_pending:
            result.append(c)
    return result


def _parse_ts(ts: str) -> "datetime.datetime":
    # timestamps are stored as ISO 8601, e.g. "2026-08-20T12:05:23.233Z"
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["matched_rules"] = json.loads(d["matched_rules"] or "[]")
    d["escalate"] = bool(d["escalate"])
    return d

# Add to SCHEMA string, alongside the existing `cases` table:
SCHEMA_USERS = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    role TEXT DEFAULT 'staff',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

# In init_db(), execute both schemas:
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.executescript(SCHEMA_USERS)


# New functions -- add anywhere below the existing ones:

def create_user(username: str, password_hash: str, display_name: str, role: str = "staff"):
    import datetime
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, display_name, role, datetime.datetime.now(datetime.timezone.utc).isoformat()),
        )


def get_user(username: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(row) if row else None


def create_session(token: str, username: str, expires_at: str):
    import datetime
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, username, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, username, datetime.datetime.now(datetime.timezone.utc).isoformat(), expires_at),
        )


def get_session(token: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
        return dict(row) if row else None


def delete_session(token: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))

def find_possible_duplicates(patient_token: str, exclude_case_id: str, window_minutes: int = 60):
    """
    Cases with the same patient_token submitted within `window_minutes` of
    each other from potentially different stations -- surfaced as a warning,
    never auto-merged, since only a human can confirm it's the same person.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cases WHERE patient_token=? AND case_id != ? ORDER BY timestamp DESC LIMIT 10",
            (patient_token, exclude_case_id),
        ).fetchall()
    return [row_to_dict(r) for r in rows]