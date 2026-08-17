/**
 * API client for the staff dashboard.
 *
 * The real source of truth for a multi-station hospital is the central
 * server (see /server in the repo root) -- it's what reconciles cases from
 * every intake station. That server doesn't exist yet, so this client is
 * written against the endpoint it WILL expose, and fails gracefully when
 * that endpoint isn't there (mirrors the pattern in intake-app/src/sync.js).
 *
 * Until /server exists, the dashboard falls back to reading this browser's
 * own local IndexedDB store (see local-fallback.js) -- useful for a single
 * front-desk-plus-dashboard setup on one device, or for testing, but it is
 * NOT a substitute for the real multi-station sync once the server exists.
 */

const SERVER_ENDPOINT = null; // e.g. "https://hospital-server.local/api/cases"

export async function fetchCasesFromServer() {
  if (!SERVER_ENDPOINT) {
    return { ok: false, reason: "no_server_configured", cases: [] };
  }
  try {
    const res = await fetch(`${SERVER_ENDPOINT}?since=today`);
    if (!res.ok) return { ok: false, reason: `server_error_${res.status}`, cases: [] };
    const cases = await res.json();
    return { ok: true, cases };
  } catch (e) {
    return { ok: false, reason: "unreachable", cases: [] };
  }
}

export async function pushReviewOutcome(caseId, patch) {
  if (!SERVER_ENDPOINT) {
    return { ok: false, reason: "no_server_configured" };
  }
  try {
    const res = await fetch(`${SERVER_ENDPOINT}/${caseId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    return { ok: res.ok };
  } catch (e) {
    return { ok: false, reason: "unreachable" };
  }
}
