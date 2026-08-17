# OPD triage assist — project scaffold

Status: **early prototype**. The `engine/` module is real, tested, working code.
Everything else is scaffolded structure, not yet built.

## What's actually implemented

- `protocol/rules.yaml` — the triage rules (tiers, red flags, complaint -> department
  routing). This is the single source of truth. **Not clinically reviewed yet** —
  see `status: draft` in the file itself.
- `engine/triage_engine.py` — loads rules.yaml, scores a structured intake into a
  tier + department + list of matched rule IDs. Pure logic, no UI, no LLM calls.
  Unrecognized complaints always route to human review rather than guessing.
- `engine/audit.py` — append-only local JSONL audit log. Local-first so it works
  offline; a sync process would tail this file when connectivity returns.
- `engine/tests/test_triage_engine.py` — pins every red flag and routing rule to a
  concrete test case, so a future rules.yaml edit that silently breaks a red flag
  gets caught.

Run it:
```
cd engine
pip install -r requirements.txt
pytest tests/
python triage_engine.py   # runs one demo case, prints the audit record
```

## What's scaffolded but not built

- `intake-app/` — **implemented.** Offline-first front-desk client: IndexedDB local
  storage (`src/db.js`), a JS port of the triage engine (`src/engine.js`), and a
  best-effort sync layer (`src/sync.js`) that queues locally until a real server
  exists. No framework, no build step — see `intake-app/README.md` for how to run
  it. Not yet wired to a real server (`/server` is still empty) or to any auth.
- `staff-dashboard/` — **implemented.** Escalation queue + all-cases log, server-first
  with a local-IndexedDB fallback (`src/api-client/client.js`, `src/local-fallback.js`).
  Works today for single-device testing; needs `/server` before it works across multiple
  front-desk stations. See `staff-dashboard/README.md`.
- `server/` — sync endpoint, central audit store, auth. Only needed once multiple
  intake stations need to reconcile with each other and with a central record.
  Not built yet — both `intake-app` and `staff-dashboard` are already written
  against the endpoint this should expose.
- `docs/architecture.md` — not written yet.

## Why this shape

`engine/` has zero UI dependencies on purpose — the same scoring logic should serve
a front-desk kiosk, a future SMS-based intake, or a phone triage line without
duplicating rule logic anywhere. `protocol/rules.yaml` is kept out of code entirely
so a clinician can review and version it without touching software.

## Before any real deployment

1. Clinical sign-off on `protocol/rules.yaml` (see `open items` in the docx protocol
   draft) — nothing here should touch a real patient until that happens.
2. Real local-first storage in `intake-app/` (this scaffold has none yet).
3. Staff identity/auth before any override or review action is trusted.
