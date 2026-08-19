# OPD triage assist — project scaffold

Status: **early prototype, end-to-end working locally**. Engine, intake-app,
staff-dashboard, and server are all implemented and wired together. Not yet
clinically reviewed or deployment-ready — see "Before any real deployment"
below.

## What's actually implemented

- `protocol/rules.yaml` — the triage rules (tiers, red flags, complaint ->
  department routing). Single source of truth. **Not clinically reviewed
  yet** — see `status: draft` in the file itself.
- `engine/triage_engine.py` — loads rules.yaml, scores a structured intake
  into a tier + department + list of matched rule IDs. Pure logic, no UI, no
  LLM calls. Unrecognized complaints always route to human review rather
  than guessing.
- `engine/audit.py` — append-only local JSONL audit log.
- `engine/tests/test_triage_engine.py` — pins every red flag and routing
  rule to a concrete test case.
- `intake-app/` — offline-first front-desk client. IndexedDB local storage
  (`src/db.js`), a JS port of the triage engine (`src/engine.js`), and a
  sync layer (`src/sync.js`) that now pushes to the real server. No
  framework, no build step. See `intake-app/README.md`.
- `staff-dashboard/` — escalation queue + all-cases log. Server-first
  (`src/api-client/client.js`), with a local-IndexedDB fallback
  (`src/local-fallback.js`) for single-device use or when the server is
  unreachable. See `staff-dashboard/README.md`.
- `server/` — Flask + SQLite central store. Endpoints: `POST /api/cases`,
  `GET /api/cases`, `PATCH /api/cases/<id>`, `GET /api/health`. Simple
  per-station API key auth via `X-Station-Key` header (see "Auth" below).

## Running everything together

Three terminals, in this order:

**1. Central server**

cd server
python -m pip install -r requirements.txt
python app.py

Runs on `http://localhost:5000`. Creates `server/data/cases.db` on first run
(gitignored — local runtime data, not source).

**2. Static file server for the two web apps**

cd opd-triage
python -m http.server 8000


**3. Open in browser**
- `http://localhost:8000/intake-app/`
- `http://localhost:8000/staff-dashboard/`

Both apps are hardcoded to talk to `http://localhost:5000` right now — see
"Auth" below before deploying anywhere beyond your own machine.

## Auth (current state — minimal, not production-ready)

The server checks an `X-Station-Key` header against a fixed set of keys set
via the `STATION_KEYS` environment variable (defaults to `default:dev-key`
if unset). Both `intake-app/src/sync.js` and
`staff-dashboard/src/api-client/client.js` currently send `"dev-key"`
hardcoded. This is a placeholder, not real staff identity/login — every
station shares one key, and there's no per-user audit trail on the server
side yet. Needs real auth before any real deployment.

## Engine tests

cd engine
python -m pip install -r requirements.txt
python -m pytest tests\


## Why this shape

`engine/` has zero UI dependencies on purpose — the same scoring logic
should serve a front-desk kiosk, a future SMS-based intake, or a phone
triage line without duplicating rule logic anywhere. `protocol/rules.yaml`
is kept out of code entirely so a clinician can review and version it
without touching software. `server/` exists purely to reconcile cases
across multiple intake stations — a single-station setup can run entirely
without it (see each app's local-fallback behavior).

## Before any real deployment

1. Clinical sign-off on `protocol/rules.yaml` (see "open items" in the
   protocol draft doc) — nothing here should touch a real patient until
   this happens.
2. Real staff auth on the server (replace the shared `X-Station-Key`
   placeholder with per-user login and per-review audit trail).
3. Move off the Flask dev server (`python app.py`) to a production WSGI
   server before any non-local deployment — the console warning about this
   on startup is not just boilerplate.
4. `docs/architecture.md` is not written yet.