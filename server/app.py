"""
Sync endpoint + central audit store.

Endpoints match what intake-app/src/sync.js and staff-dashboard/src/api-client/client.js
expect:
  POST   /api/cases              -- a station pushes a new/updated case
  GET    /api/cases?since=today  -- dashboard fetches current cases
  PATCH  /api/cases/<id>         -- staff review outcome (requires staff login)
  POST   /api/auth/login         -- staff login, returns a session token
  POST   /api/auth/logout        -- invalidate a session token
  GET    /api/health             -- health check

Two separate auth mechanisms:
  - Station key (X-Station-Key header): proves a device is a legitimate
    intake/dashboard station. Used for POST/GET /api/cases.
  - Staff session token (Authorization: Bearer <token>): proves a specific
    logged-in staff member. Used for PATCH /api/cases/<id> so review actions
    are attributable to a real person, not just "some station."

Secrets (STATION_KEYS, FLASK_SECRET_KEY, FLASK_DEBUG) are read from a local
.env file (see .env.example for the template) rather than hardcoded here.
.env itself is gitignored.
"""

import datetime
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

import db
import auth

load_dotenv()  # reads .env in this directory

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "insecure-default-do-not-use-in-production")
CORS(app)

db.init_db()



DEBUG_MODE = os.environ.get("FLASK_DEBUG", "false").lower() == "true"


def authenticate(req) -> str | None:
    """Station-level auth. Checks the X-Station-Key header against per-device credentials in the DB."""
    key = req.headers.get("X-Station-Key")
    if not key:
        return None
    return db.find_station_by_key(key)


def authenticate_staff(req) -> str | None:
    """Staff-level auth. Returns username if Authorization: Bearer <token> is a valid, unexpired session."""
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        return None
    session = db.get_session(token)
    if not session or auth.is_expired(session["expires_at"]):
        return None
    return session["username"]


@app.route("/api/cases", methods=["POST"])
def receive_case():
    station_id = authenticate(request)
    if not station_id:
        return jsonify({"error": "unauthorized"}), 401

    case = request.get_json(force=True)
    required = ("case_id", "patient_token", "tier", "timestamp")
    if not all(k in case for k in required):
        return jsonify({"error": "missing required fields"}), 400

    received_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.upsert_case(case, station_id, received_at)
    return jsonify({"ok": True, "case_id": case["case_id"]}), 201


@app.route("/api/cases", methods=["GET"])
def get_cases():
    station_id = authenticate(request)
    if not station_id:
        return jsonify({"error": "unauthorized"}), 401

    since = request.args.get("since")
    hours = None
    if since == "today" or since == "recent":
        hours = 48  # rolling 48-hour window, plus all pending cases regardless of age
    cases = db.list_cases(hours)
    return jsonify(cases)


@app.route("/api/cases/<case_id>", methods=["PATCH"])
def update_case(case_id):
    username = authenticate_staff(request)
    if not username:
        return jsonify({"error": "staff login required"}), 401

    patch = request.get_json(force=True)
    expected_status = patch.pop("expected_status", None)
    patch["reviewed_by"] = username

    updated, conflict = db.patch_case(case_id, patch, expected_status)

    if conflict is not None:
        return jsonify({
            "error": "conflict",
            "message": f"Already reviewed by {conflict.get('reviewed_by', 'someone else')}",
            "current": conflict,
        }), 409

    if updated is None:
        return jsonify({"error": "case not found"}), 404

    return jsonify(updated)


@app.route("/api/auth/login", methods=["POST"])
def login():
    body = request.get_json(force=True)
    username = body.get("username")
    password = body.get("password")
    user = db.get_user(username) if username else None

    if not user or not auth.verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401

    token = auth.new_token()
    db.create_session(token, username, auth.session_expiry())
    return jsonify({
        "token": token,
        "username": username,
        "display_name": user["display_name"],
    })


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        db.delete_session(token)
    return jsonify({"ok": True})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/api/cases/<case_id>/duplicates", methods=["GET", "OPTIONS"])
def get_duplicates(case_id):
    if request.method == "OPTIONS":
        return "", 200

    station_id = authenticate(request)
    if not station_id:
        return jsonify({"error": "unauthorized"}), 401

    with db.get_conn() as conn:
        row = conn.execute("SELECT patient_token FROM cases WHERE case_id=?", (case_id,)).fetchone()
    if not row:
        return jsonify({"error": "case not found"}), 404

    dupes = db.find_possible_duplicates(row["patient_token"], case_id)
    return jsonify(dupes)

@app.route("/api/cases/duplicates/batch", methods=["POST"])
def get_duplicates_batch():
    station_id = authenticate(request)
    if not station_id:
        return jsonify({"error": "unauthorized"}), 401

    body = request.get_json(force=True)
    case_tokens = body.get("case_tokens", {})  # { case_id: patient_token, ... }

    if not case_tokens:
        return jsonify({})

    tokens = list(set(case_tokens.values()))
    counts = db.find_duplicate_counts(tokens, case_tokens)
    return jsonify(counts)

if __name__ == "__main__":
    if DEBUG_MODE:
        print("WARNING: running with FLASK_DEBUG=true -- do not use this in any real deployment.")
    app.run(host="0.0.0.0", port=5000, debug=DEBUG_MODE)



