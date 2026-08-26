/**
 * API client for the staff dashboard.
 *
 * Fetching cases uses the station key (any dashboard on a legitimate
 * station device can view the queue). Submitting a review outcome
 * (confirm/downgrade) requires a logged-in staff session token instead --
 * that's what makes reviewed_by meaningful in the audit trail.
 *
 * Falls back to reading this browser's local IndexedDB store
 * (see local-fallback.js) if the server is unreachable -- useful for a
 * single front-desk-plus-dashboard setup or testing, not a substitute for
 * real multi-station sync.
 */


const AUTH_ENDPOINT = "http://localhost:5000/api/auth";
import { SERVER_ENDPOINT, STATION_KEY } from "../config.js";

const STATION_HEADERS = {
  "Content-Type": "application/json",
  "X-Station-Key": STATION_KEY,
};

const TOKEN_STORAGE_KEY = "opd_staff_session";

export function getStoredSession() {
  const raw = localStorage.getItem(TOKEN_STORAGE_KEY);
  return raw ? JSON.parse(raw) : null;
}

function storeSession(session) {
  localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export async function login(username, password) {
  try {
    const res = await fetch(`${AUTH_ENDPOINT}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) return { ok: false };
    const data = await res.json();
    storeSession(data); // { token, username, display_name }
    return { ok: true, ...data };
  } catch (e) {
    return { ok: false, reason: "unreachable" };
  }
}

export async function logout() {
  const session = getStoredSession();
  if (session?.token) {
    try {
      await fetch(`${AUTH_ENDPOINT}/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.token}` },
      });
    } catch (e) {
      // best-effort -- clear local session regardless
    }
  }
  clearSession();
}

export async function fetchCasesFromServer() {
  if (!SERVER_ENDPOINT) {
    return { ok: false, reason: "no_server_configured", cases: [] };
  }
  try {
    const res = await fetch(`${SERVER_ENDPOINT}?since=today`, {
      headers: STATION_HEADERS,
    });
    if (!res.ok) return { ok: false, reason: `server_error_${res.status}`, cases: [] };
    const cases = await res.json();
    return { ok: true, cases };
  } catch (e) {
    return { ok: false, reason: "unreachable", cases: [] };
  }
}

export async function pushReviewOutcome(caseId, patch, expectedStatus) {
  const session = getStoredSession();
  if (!session?.token) {
    return { ok: false, reason: "not_logged_in" };
  }
  try {
    const res = await fetch(`${SERVER_ENDPOINT}/${caseId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.token}`,
      },
      body: JSON.stringify({ ...patch, expected_status: expectedStatus }),
    });
    if (res.status === 401) {
      clearSession();
      return { ok: false, reason: "session_expired" };
    }
    if (res.status === 409) {
      const body = await res.json();
      return { ok: false, reason: "conflict", message: body.message, current: body.current };
    }
    return { ok: res.ok };
  } catch (e) {
    return { ok: false, reason: "unreachable" };
  }
}

export async function fetchDuplicates(caseId) {
  try {
    const res = await fetch(`${SERVER_ENDPOINT}/${caseId}/duplicates`, {
      headers: STATION_HEADERS,
    });
    if (!res.ok) return [];
    return await res.json();
  } catch (e) {
    return [];
  }
}

export async function fetchDuplicatesBatch(caseTokens) {
  try {
    const res = await fetch(`${SERVER_ENDPOINT}/duplicates/batch`, {
      method: "POST",
      headers: STATION_HEADERS,
      body: JSON.stringify({ case_tokens: caseTokens }),
    });
    if (!res.ok) return {};
    return await res.json();
  } catch (e) {
    return {};
  }
}