"""
Sync endpoint + central audit store.

Endpoints match what intake-app/src/sync.js and staff-dashboard/src/api-client/client.js
already expect:
  POST   /api/cases          -- a station pushes a new/updated case
  GET    /api/cases?since=today  -- dashboard fetches current cases
  PATCH  /api/cases/<id>      -- staff review outcome

Auth: a simple per-station API key header (X-Station-Key). This is a
minimum-viable stand-in -- NOT how staff identity/login should work long
term (see README's "known gaps").
"""

import datetime
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

import db

app = Flask(__name__)
CORS(app)  # allow intake-app/staff-dashboard (different origin) to call this

db.init_db()

# Minimal station auth: a fixed set of allowed keys, set via env var.
# e.g. STATION_KEYS="frontdesk1:key-abc,frontdesk2:key-def"
STATION_KEYS = dict(
    pair.split(":") for pair in os.environ.get("STATION_KEYS", "default:dev-key").split(",")
)


def authenticate(req) -> str | None:
    key = req.headers.get("X-Station-Key")
    for station_id, valid_key in STATION_KEYS.items():
        if key == valid_key:
            return station_id
    return None


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
    since_date = None
    if since == "today":
        since_date = datetime.date.today().isoformat()
    cases = db.list_cases(since_date)
    return jsonify(cases)


@app.route("/api/cases/<case_id>", methods=["PATCH"])
def update_case(case_id):
    station_id = authenticate(request)
    if not station_id:
        return jsonify({"error": "unauthorized"}), 401

    patch = request.get_json(force=True)
    updated = db.patch_case(case_id, patch)
    if updated is None:
        return jsonify({"error": "case not found"}), 404
    return jsonify(db.row_to_dict(updated))


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)