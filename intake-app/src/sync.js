/**
 * Sync layer: pushes locally-saved cases to the server (best-effort), and
 * separately pulls back status updates for cases this device already knows
 * about -- so front-desk staff can see when a case has been reviewed,
 * without needing to check staff-dashboard themselves.
 *
 * Contract: neither direction ever blocks or fails the local save. Both are
 * purely additive on top of IndexedDB, which remains the source of truth
 * for this device when offline.
 */

import { LocalStore } from "./db.js";

import { SYNC_ENDPOINT, STATION_KEY } from "./config.js";

const STATION_HEADERS = {
  "Content-Type": "application/json",
  "X-Station-Key": STATION_KEY,
};

export const SyncStatus = {
  listeners: new Set(),
  current: { state: "offline", pendingCount: 0, lastSyncedAt: null },

  subscribe(fn) {
    this.listeners.add(fn);
    fn(this.current);
    return () => this.listeners.delete(fn);
  },

  update(patch) {
    this.current = { ...this.current, ...patch };
    for (const fn of this.listeners) fn(this.current);
  },
};

async function pushOne(caseRecord) {
  if (!SYNC_ENDPOINT) throw new Error("no sync endpoint configured");
  const res = await fetch(SYNC_ENDPOINT, {
    method: "POST",
    headers: STATION_HEADERS,
    body: JSON.stringify(caseRecord),
  });
  if (!res.ok) throw new Error("sync push failed: " + res.status);
}

/** Attempt to flush the outbox (local -> server). */
export async function trySync() {
  const outbox = await LocalStore.getOutbox();
  SyncStatus.update({ pendingCount: outbox.length });

  if (outbox.length === 0) {
    SyncStatus.update({ state: navigator.onLine ? "synced" : "offline" });
    return;
  }

  if (!navigator.onLine || !SYNC_ENDPOINT) {
    SyncStatus.update({ state: "offline" });
    return;
  }

  SyncStatus.update({ state: "syncing" });
  let succeeded = 0;
  for (const record of outbox) {
    try {
      await pushOne(record);
      await LocalStore.clearFromOutbox(record.case_id);
      succeeded++;
    } catch (e) {
      break; // stop on first failure, leave remaining queued, retry later
    }
  }

  const remaining = await LocalStore.getOutbox();
  SyncStatus.update({
    state: remaining.length === 0 ? "synced" : "partial",
    pendingCount: remaining.length,
    lastSyncedAt: succeeded > 0 ? new Date().toISOString() : SyncStatus.current.lastSyncedAt,
  });
}

/**
 * Pull status updates (server -> local). For every case this device has
 * locally, check if the server's status/reviewed_by differs, and if so,
 * update the local copy so the UI reflects it.
 */
export async function pullStatusUpdates() {
  if (!SYNC_ENDPOINT || !navigator.onLine) return;

  let serverCases;
  try {
    const res = await fetch(SYNC_ENDPOINT, { headers: STATION_HEADERS });
    if (!res.ok) return;
    serverCases = await res.json();
  } catch (e) {
    return; // best-effort, silently skip this cycle
  }

  const serverByCaseId = new Map(serverCases.map((c) => [c.case_id, c]));
  const localCases = await LocalStore.getAllCases();

  for (const local of localCases) {
    const remote = serverByCaseId.get(local.case_id);
    if (!remote) continue;
    const changed = remote.status !== local.status || remote.reviewed_by !== local.reviewed_by;
    if (changed) {
      await LocalStore.applyRemoteStatus(local.case_id, {
        status: remote.status,
        reviewed_by: remote.reviewed_by,
        reviewed_at: remote.reviewed_at,
      });
    }
  }
}

export function startAutoSync(intervalMs = 15000) {
  trySync();
  pullStatusUpdates();
  window.addEventListener("online", () => {
    trySync();
    pullStatusUpdates();
  });
  return setInterval(() => {
    trySync();
    pullStatusUpdates();
  }, intervalMs);
}