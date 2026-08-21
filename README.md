# OPD triage assist — project scaffold

Status: **early prototype, working end-to-end locally**. Engine, intake-app,
staff-dashboard, and server (with staff auth and two-way status sync) are
all implemented and tested together. Not yet clinically reviewed or
deployment-ready — see "Before any real deployment" below.

## What's actually implemented

- `protocol/rules.yaml` — the triage rules (tiers, red flags, complaint ->
  department routing). Single source of truth for both the Python and JS
  engines. **Not clinically reviewed yet** — see `status: draft` in the file.

- `engine/triage_engine.py` — loads rules.yaml, scores a structured intake
  into a tier + department + list of matched rule IDs. Pure logic, no UI, no
  LLM calls. Unrecognized complaints always route to human review rather
  than guessing.
- `engine/audit.py` — append-only local JSONL audit log.
- `engine/tests/test_triage_engine.py` — pins every red flag and routing
  rule to a concrete test case.

- `intake-app/` — offline-first front-desk client.
  - `src/db.js` — IndexedDB local storage. Every case saves here first, with
    zero network dependency.
  - `src/engine.js` — JS port of the Python triage engine, same rules source.
  - `src/sync.js` — two-way sync with the server:
    - **push**: queues locally-saved cases and pushes them to the server
      (station-key authenticated), retrying on the next cycle if offline.
    - **pull**: periodically checks the server for status updates on cases
      this device already knows about, so front-desk can see "confirmed by
      nurse1" / "downgraded" without needing to check staff-dashboard.
  - No framework, no build step.

- `staff-dashboard/` — escalation queue + all-cases log. Fetches from the
  server (station-key authenticated) with a local-IndexedDB fallback for
  single-device use. Review actions (confirm/downgrade) require a logged-in
  staff session (see Auth below) and are recorded with `reviewed_by`.

- `server/` — Flask + SQLite central store.
  - `POST /api/cases`, `GET /api/cases` — station-key authenticated
  - `PATCH /api/cases/<id>` — staff-session authenticated, records
    `reviewed_by` with the real staff username
  - `POST /api/auth/login`, `POST /api/auth/logout` — staff session tokens
  - `GET /api/health`
  - `server/create_user.py` — CLI script to seed staff accounts

## Running everything together

Three terminals, in this order:

**1. Central server**

cd server
python -m pip install -r requirements.txt
python create_user.py <username> <password> "<Display Name>" # first time only
python app.py

Runs on `http://localhost:5000`. Creates `server/data/cases.db` on first run
(gitignored — local runtime data, not source).

**2. Static file server for the two web apps**

cd opd-triage
python -m http.server 8000


**3. Open in browser**
- `http://localhost:8000/intake-app/`
- `http://localhost:8000/staff-dashboard/`

## Testing the full loop

1. In intake-app: submit a case with a red flag checked. Status bar should
   say "Synced just now."
2. In staff-dashboard: refresh, find the case in the Escalation queue, sign
   in if prompted, click "Confirm emergency" or "Downgrade."
3. Back in intake-app: wait ~15s (or refresh) — the case's status in "Cases
   recorded on this device" should update to reflect the review outcome and
   who reviewed it.

## Auth (two separate layers)

- **Station key** (`X-Station-Key` header) — proves a device is a
  legitimate hospital station. Used for submitting and reading cases. Set
  via the server's `STATION_KEYS` env var (defaults to `default:dev-key`).
  Both `intake-app/src/sync.js` and
  `staff-dashboard/src/api-client/client.js` currently hardcode
  `"dev-key"` — fine for local dev, needs to move to per-station config
  before real deployment.
- **Staff session** (`Authorization: Bearer <token>`) — proves a specific
  logged-in person. Required only for `PATCH /api/cases/<id>` (confirming
  or downgrading a case). Obtained via `POST /api/auth/login`. Sessions
  expire after 12 hours.

## Engine tests

cd engine
python -m pip install -r requirements.txt
python -m pytest tests\


## Why this shape

`engine/` has zero UI dependencies on purpose — the same scoring logic
should serve a front-desk kiosk, a future SMS-based intake, or a phone
triage line without duplicating rule logic anywhere. `protocol/rules.yaml`
is kept out of code entirely so a clinician can review and version it
without touching software. `server/` exists purely to reconcile cases and
review outcomes across multiple intake stations — a single-station setup
can run entirely without it, falling back to local IndexedDB.

## Known gaps / before any real deployment

1. Clinical sign-off on `protocol/rules.yaml` — nothing here should touch a
   real patient until this happens.
2. Station keys and staff credentials are hardcoded dev defaults — move to
   real per-station config before deployment.
3. `GET /api/cases` defaults to `since=today` — a shift crossing midnight
   currently won't see earlier pending cases in the dashboard's default
   view. Worth revisiting the cutoff logic.
4. Move off the Flask dev server (`python app.py`) to a production WSGI
   server before any non-local deployment.
5. Handle multi-station conflicts (two stations offline simultaneously,
   overlapping patient tokens, syncing later).
6. `docs/architecture.md` is not written yet.