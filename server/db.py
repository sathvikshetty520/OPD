import sqlite3
import json
import datetime
from pathlib import Path
from contextlib import contextmanager

import auth 
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
    received_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_timestamp ON cases(timestamp);
"""

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

SCHEMA_STATIONS = """
CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL,
    device_name TEXT,
    created_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0
);
"""

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.executescript(SCHEMA_USERS)
        conn.executescript(SCHEMA_STATIONS)

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# ---------------- Cases ----------------

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
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not existing:
            return None, None

        if expected_status is not None and existing["status"] != expected_status:
            return None, row_to_dict(existing)

        fields, values = [], []
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
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))

def row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["matched_rules"] = json.loads(d["matched_rules"] or "[]")
    d["escalate"] = bool(d["escalate"])
    return d

# ---------------- Users/Sessions ----------------

def create_user(username: str, password_hash: str, display_name: str, role: str = "staff"):
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

# ---------------- Stations ----------------

def create_station(station_id: str, key_hash: str, device_name: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO stations (station_id, key_hash, device_name, created_at, revoked) VALUES (?, ?, ?, ?, 0)",
            (station_id, key_hash, device_name, datetime.datetime.now(datetime.timezone.utc).isoformat()),
        )

def get_all_stations():
    with get_conn() as conn:
        rows = conn.execute("SELECT station_id, device_name, created_at, revoked FROM stations").fetchall()
        return [dict(r) for r in rows]

def find_station_by_key(key: str):
    """Checks the given raw key against every non-revoked station's hash. Returns station_id or None."""
    with get_conn() as conn:
        rows = conn.execute("SELECT station_id, key_hash FROM stations WHERE revoked = 0").fetchall()
    for row in rows:
        if auth.verify_password(key, row["key_hash"]):  # assumes you have an auth module
            return row["station_id"]
    return None

def revoke_station(station_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE stations SET revoked = 1 WHERE station_id = ?", (station_id,))

# ---------------- Duplicate Checks ----------------

def find_possible_duplicates(patient_token: str, exclude_case_id: str, window_minutes: int = 60):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cases WHERE patient_token=? AND case_id != ? ORDER BY timestamp DESC LIMIT 10",
            (patient_token, exclude_case_id),
        ).fetchall()
    return [row_to_dict(r) for r in rows]

def find_duplicate_counts(patient_tokens: list[str], exclude_case_ids: dict[str, str]):
    if not patient_tokens:
        return {}
    with get_conn() as conn:
        placeholders = ",".join("?" * len(patient_tokens))
        rows = conn.execute(
            f"SELECT case_id, patient_token FROM cases WHERE patient_token IN ({placeholders})",
            patient_tokens,
        ).fetchall()
    by_token: dict[str, list[str]] = {}
    for row in rows:
        by_token.setdefault(row["patient_token"], []).append(row["case_id"])
    result = {}
    for case_id, token in exclude_case_ids.items():
        matches = by_token.get(token, [])
        result[case_id] = len([m for m in matches if m != case_id])
    return result
