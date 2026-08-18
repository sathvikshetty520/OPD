/**
 * API client for the staff dashboard.
 *
 * The real source of truth for a multi-station hospital is the central
 * server (see /server in the repo root) -- it's what reconciles cases from
 * every intake station. This client talks to that server, and falls back
 * gracefully if it's unreachable (mirrors the pattern in intake-app/src/sync.js).
 *
 * Until the server has real staff auth, the dashboard falls back to reading
 * this browser's own local IndexedDB store (see local-fallback.js) -- useful
 * for a single front-desk-plus-dashboard setup on one device, or for testing,
 * but it is NOT a substitute for the real multi-station sync.
 */

const SERVER_ENDPOINT = "http://localhost:5000/api/cases";
const STATION_KEY = "dev-key"; // must match a key in the server's STATION_KEYS env var

const AUTH_HEADERS = {
  "Content-Type": "application/json",
  "X-Station-Key": STATION_KEY,
};

export async function fetchCasesFromServer() {
  if (!SERVER_ENDPOINT) {
    return { ok: false, reason: "no_server_configured", cases: [] };
  }
  try {
    const res = await fetch(`${SERVER_ENDPOINT}?since=today`, {
      headers: AUTH_HEADERS,
    });
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
      headers: AUTH_HEADERS,
      body: JSON.stringify(patch),
    });
    return { ok: res.ok };
  } catch (e) {
    return { ok: false, reason: "unreachable" };
  }
}