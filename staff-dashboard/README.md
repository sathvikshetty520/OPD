# staff-dashboard

Escalation queue and case log for on-duty staff. Same no-build, no-framework
approach as `intake-app`.

## Data source: server-first, local fallback

`src/app.js` tries the central server first
(`src/api-client/client.js`, pointed at `http://localhost:5000/api/cases`
with an `X-Station-Key` auth header). If the server is unreachable or
returns an error, it falls back to `src/local-fallback.js`, which reads the
**same IndexedDB database (`opd_intake`) that intake-app writes to on this
device**.

This means:

- **With the server running**: the dashboard shows cases from every station
  that has synced, not just this device. This is the real, intended mode.
- **Without the server running** (or unreachable): falls back to showing
  only cases entered on this exact browser/device -- useful for local
  testing or a single-workstation setup, but not sufficient for a real
  multi-station hospital.

## Running it

Run `/server` first (see its own instructions), then:
cd staff-dashboard
python -m http.server 8001

Or, to test the full stack together, serve the whole repo root instead so
intake-app and staff-dashboard share one origin (needed for the local
IndexedDB fallback to work correctly -- it's scoped per-origin). See the
top-level README for the recommended combined setup.

## What's real vs. not

- Escalation queue, all-cases view, review actions (confirm/downgrade),
  polling every 15s -- all implemented and tested against both the server
  and the local IndexedDB fallback.
- Server connectivity -- live and working locally (`localhost:5000`). Not
  yet tested against a real deployed server or multiple real stations.
- Auth -- a single shared station key (`X-Station-Key: dev-key`), not real
  staff login. Review actions (confirm/downgrade) have no identity attached
  to who performed them beyond this shared key.