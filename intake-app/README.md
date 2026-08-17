# intake-app

Front-desk offline-first intake client. No build step, no framework, no
external dependencies -- plain HTML/CSS/JS modules, so it runs by opening
`index.html` in any modern browser or serving the folder statically.

## Why it's offline-first

- Every submitted case is written to **IndexedDB immediately** (`src/db.js`).
  This succeeds with zero network access -- that's the whole point for a
  low-connectivity hospital.
- `src/sync.js` is a separate, best-effort layer that tries to push queued
  cases to a server when one exists and the device is online. It never blocks
  or fails the local save. Right now `SYNC_ENDPOINT` is `null` because
  `/server` isn't built yet -- cases will queue locally indefinitely until you
  point it at a real endpoint.
- `src/engine.js` is a JS port of `engine/triage_engine.py`, reading the same
  `protocol/rules.yaml` (exported to `src/rules.json` -- see below). Keeping
  the same rules source avoids the two engines silently drifting apart.

## Running it

Any static file server works, e.g.:
```
cd intake-app
python3 -m http.server 8000
```
Then open `http://localhost:8000`. (Opening `index.html` directly via
`file://` will NOT work -- ES module imports and IndexedDB both require a
real origin, i.e. an http server.)

## Regenerating rules.json after editing protocol/rules.yaml

```
cd engine
python3 -c "
import yaml, json
with open('../protocol/rules.yaml') as f:
    rules = yaml.safe_load(f)
with open('../intake-app/src/rules.json', 'w') as f:
    json.dump(rules, f, indent=2)
"
```
This should eventually become a build step (or the app fetches rules.yaml
directly via a tiny YAML parser) rather than a manual command -- noted as a
follow-up.

## Known gaps

- No auth -- any device can submit as any "station."
- No conflict resolution if the same patient token is somehow used twice
  across two offline stations before they sync.
- `server/` doesn't exist yet, so nothing here has actually synced
  end-to-end against a real backend -- only the local half is proven.
