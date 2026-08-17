# staff-dashboard

Escalation queue and case log for on-duty staff. Same no-build, no-framework
approach as `intake-app`.

## Data source: server-first, local fallback

`src/app.js` tries the central server first (`src/api-client/client.js`). That
server doesn't exist yet (`SERVER_ENDPOINT` is `null` in that file, same
pattern as `intake-app/src/sync.js`), so right now it always falls through to
`src/local-fallback.js`, which reads the **same IndexedDB database
(`opd_intake`) that intake-app writes to**.

This means, as shipped:

- **Works today, single device**: serve `intake-app` and `staff-dashboard`
  from the same origin (e.g. both under one `python3 -m http.server`), submit
  a case in intake-app, see it appear here. Good for local testing and small
  single-workstation setups.
- **Not yet sufficient for a real multi-station hospital**: each front-desk
  station has its own separate IndexedDB. This dashboard only sees whichever
  single browser/device it's running on until `/server` exists to reconcile
  cases across stations. That's a real gap, not a demo shortcut — building
  `/server` is the next step to close it.

## Running it

```
cd staff-dashboard
python3 -m http.server 8001
```
Open `http://localhost:8001`. For the local-fallback data to show anything,
run `intake-app` from the **same origin** (same host + port) at some point
first, since IndexedDB is scoped per-origin — a dashboard on port 8001 cannot
see an intake-app database written from port 8000. Practically: serve both
folders under one server root, or point `local-fallback.js`'s `DB_NAME` setup
at a shared origin once you wire up real hosting.

## What's real vs. not

- Escalation queue, all-cases view, review actions (confirm/downgrade),
  polling every 15s — all implemented and wired to actual IndexedDB reads/writes.
- Server connectivity — client code is written and ready, but has never run
  against a real backend, because `/server` doesn't exist.
- Auth — none. Any staff member can review any case with no identity attached
  beyond whatever review action they clicked.
