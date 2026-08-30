# OPD triage assist — project scaffold

Status: **early prototype, working end-to-end locally**. Engine, intake-app,
staff-dashboard, and server (with staff auth and two-way status sync) are
all implemented and tested together. **Not clinically reviewed — no
clinician is currently attached to this project.** Nothing here should
route or triage a real patient until that changes. See "Before any real
deployment" below.

## What's actually implemented

- `protocol/rules.yaml` — the triage rules (tiers, red flags, complaint ->
  department routing). Single source of truth for both the Python and JS
  engines. **Draft only, not clinically reviewed.** A structured review
  worksheet exists (see "Clinical review" below) for when a clinician is
  available.

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
  - Review-race protection: if two staff members act on the same case
    near-simultaneously, the second request is rejected with a conflict
    message and the queue refreshes, instead of silently overwriting.
  - Duplicate-patient warning: cases sharing the same patient token show an
    amber warning badge, in both the Escalation queue and All cases tabs,
    using the batched duplicate-check endpoint.

- `server/` — Flask + SQLite central store.
  - `POST /api/cases`, `GET /api/cases` — station-key authenticated
  - `PATCH /api/cases/<id>` — staff-session authenticated, records
    `reviewed_by` with the real staff username
  - `POST /api/auth/login`, `POST /api/auth/logout` — staff session tokens
  - `GET /api/health`
  - `server/create_user.py` — CLI script to seed staff accounts
  - `GET /api/cases/<id>/duplicates` — surfaces other cases sharing the same
    patient_token, for catching a patient accidentally logged at two stations
  - `POST /api/cases/duplicates/batch` — same check for many cases in a
    single request (`{case_id: patient_token, ...}` -> `{case_id: count, ...}`).
    Used by staff-dashboard so polling doesn't fire one request per case.

## Running everything together

Three terminals, in this order:

**0. First time only: set up config files**

cd server
copy .env.example .env          # edit .env with real values
cd ..\intake-app\src
copy config.example.js config.js   # edit config.js, STATION_KEY must match server's .env
cd ..\..\staff-dashboard\src
copy config.example.js config.js   # same STATION_KEY as above


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

## Deploying on a hospital LAN (no internet required)

For real use in a low-connectivity setting, run everything on one machine
connected to the hospital's local WiFi/network — other devices (front-desk
tablets, staff phones) connect over LAN, no internet dependency.

**1. Use a production WSGI server instead of Flask's dev server**

cd server
python -m pip install waitress
python serve.py

`serve.py` wraps the same Flask app with `waitress`, suitable for real use
(unlike `python app.py`, which is dev-only — see the startup warning it
prints). `app.py`'s own `__main__` block stays for local development.

**2. Find the server machine's LAN IP**
ipconfig

Look for "IPv4 Address" (e.g. `192.168.1.102`).

**3. Point both apps' config at that IP, not localhost**

In `intake-app/src/config.js` and `staff-dashboard/src/config.js`:
```javascript
export const SYNC_ENDPOINT = "http://192.168.1.102:5000/api/cases";   // intake-app
export const SERVER_ENDPOINT = "http://192.168.1.102:5000/api/cases"; // staff-dashboard -- note different variable name
```
**Important**: intake-app's config exports `SYNC_ENDPOINT`; staff-dashboard's
exports `SERVER_ENDPOINT`. Mixing these up (e.g. pasting one file's content
into the other) causes a silent `does not provide an export` error in the
browser console — easy mistake since the two files otherwise look identical.

**4. Serve the static apps bound to all interfaces (default behavior)**
cd opd-triage
python -m http.server 8000


**5. From another device on the same WiFi**
http://192.168.1.102:8000/intake-app/
http://192.168.1.102:8000/staff-dashboard/


**6. Windows Firewall** may prompt to allow Python through on first run from
another device — allow it, or manually add inbound rules for ports 5000 and
8000.

**Known limitations of this deployment approach**: no HTTPS (acceptable on a
closed hospital LAN with no internet exposure, but traffic isn't encrypted);
the deployment machine is a single point of failure; SQLite is fine at this
scale but not built for heavy concurrent write load.

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

## Secrets and configuration

Station keys and Flask's secret key are no longer hardcoded in source files.

- **Server**: `server/.env` (gitignored) holds `STATION_KEYS`, `FLASK_SECRET_KEY`,
  and `FLASK_DEBUG`. Copy `server/.env.example` to `server/.env` and fill in
  real values before running.
- **intake-app**: `intake-app/src/config.js` (gitignored) holds `SYNC_ENDPOINT`
  and `STATION_KEY`. Copy `intake-app/src/config.example.js` to
  `intake-app/src/config.js` and fill in a value matching the server's
  `STATION_KEYS`.
- **staff-dashboard**: same pattern — copy
  `staff-dashboard/src/config.example.js` to `staff-dashboard/src/config.js`.

All three real config files (`.env`, `config.js` in both apps) are gitignored
and must be created locally after cloning — the repo only ships the
`.example` templates.

## Case visibility window

`GET /api/cases?since=today` resolves to a **rolling 48-hour window** on
the server (not a calendar-day cutoff — a prior version used SQLite's
`date()` truncation, which silently dropped pending cases across a midnight
boundary). On top of that window, **any case still `pending_review` is
always included regardless of age** — an unreviewed escalation never
disappears from the queue just because it's older than 48 hours. Routine/
resolved cases roll off after 48 hours as expected.

## Clinical review

`docs/` — a clinical review worksheet was produced covering: missing
red-flag signs (diabetic emergency, anaphylaxis, seizure, poisoning —
none currently in rules.yaml), ambiguities in existing rules (standalone
pain-score trigger, infant fever cutoff, no age field), missing complaint
categories, and one structural question about complaint-specific vs.
universal red flags. **No clinician is currently attached to this project
to complete it.** Once one is available, their answers should be applied
to `protocol/rules.yaml` and its `status` field updated from `draft` to
`clinician_reviewed`.

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

1. **No clinical review yet** — the single largest blocker, independent of
   code quality. See "Clinical review" above.
2. LAN deployment (see "Deploying on a hospital LAN" above) works for a
   single deployment machine + multiple client devices on the same network.
   Not yet tested with HTTPS, a non-SQLite database, or genuine multi-day
   uptime under real hospital conditions.
3. Station keys are per-deployment config now (not hardcoded), but still a
   single shared key per station rather than per-device credentials with
   individual revocation.
4. `docs/architecture.md` is not written yet.