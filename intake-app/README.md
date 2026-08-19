# intake-app

Front-desk offline-first intake client. No build step, no framework, no
external dependencies -- plain HTML/CSS/JS modules, so it runs by opening
`index.html` in any modern browser or serving the folder statically.

## Why it's offline-first

- Every submitted case is written to **IndexedDB immediately** (`src/db.js`).
  This succeeds with zero network access -- that's the whole point for a
  low-connectivity hospital.
- `src/sync.js` is a separate, best-effort layer that pushes queued cases to
  the central server (`/server`) when the device is online. It never blocks
  or fails the local save -- if the server is unreachable, cases simply stay
  queued in IndexedDB's `sync_outbox` store until the next attempt succeeds.
- `src/engine.js` is a JS port of `engine/triage_engine.py`, reading the same
  `protocol/rules.yaml` (exported to `src/rules.json` -- see below). Keeping
  the same rules source avoids the two engines silently drifting apart.

## Server connection (now live)

`SYNC_ENDPOINT` in `src/sync.js` is set to `http://localhost:5000/api/cases`
and authenticates with a hardcoded `X-Station-Key` header (`"dev-key"` by
default, must match a key in the server's `STATION_KEYS` env var). This is a
placeholder auth scheme, not real staff/station identity -- see the
top-level README's "Auth" section.

Run `/server` (see its own instructions) before testing sync -- without it
running, cases will just queue locally and the sync status bar will show
"offline," which is the correct, expected behavior in that case.

## Running it

cd intake-app
python -m http.server 8000

Then open `http://localhost:8000`. (Opening `index.html` directly via
`file://` will NOT work -- ES module imports and IndexedDB both require a
real origin, i.e. an http server.)

Note: if you're running the full stack (server + both web apps), serve this
folder as part of the whole repo root instead (see top-level README) so
intake-app and staff-dashboard share one origin.

## Regenerating rules.json after editing protocol/rules.yaml

## Regenerating rules.json after editing protocol/rules.yaml

cd engine
python3 -c "
import yaml, json
with open('../protocol/rules.yaml') as f:
rules = yaml.safe_load(f)
with open('../intake-app/src/rules.json', 'w') as f:
json.dump(rules, f, indent=2)
"
This should eventually become a build step (or the app fetches rules.yaml
directly via a tiny YAML parser) rather than a manual command -- noted as a
follow-up.

## Known gaps

- Auth is a single shared station key, not real per-station or per-user
  identity -- see top-level README.
- No conflict resolution if the same patient token is somehow used twice
  across two offline stations before they sync.
- Server connection is live and tested locally, but has not been tested
  against a real multi-station, multi-network deployment.