/**
 * Best-effort sync of the local outbox to a central server.
 *
 * Contract: sync NEVER blocks or fails the local recording of a case. It is
 * purely additive -- if it can't reach the server, cases simply stay queued
 * in IndexedDB's sync_outbox store until the next attempt succeeds.
 *
 * No server is implemented yet (see /server in the repo root) -- this module
 * is wired to fail gracefully against that gap so the rest of the app can be
 * built and tested now, and pointed at a real endpoint later.
 */

import { LocalStore } from "./db.js";

const SYNC_ENDPOINT = "http://localhost:5000/api/cases";

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
    headers: { "Content-Type": "application/json" ,
      "X-Station-Key": "dev-key"
    },
    body: JSON.stringify(caseRecord),
  });
  if (!res.ok) throw new Error("sync push failed: " + res.status);
}

/** Attempt to flush the outbox. Safe to call repeatedly (e.g. on an interval or online event). */
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
      // Stop on first failure -- leave remaining records queued, retry later.
      break;
    }
  }

  const remaining = await LocalStore.getOutbox();
  SyncStatus.update({
    state: remaining.length === 0 ? "synced" : "partial",
    pendingCount: remaining.length,
    lastSyncedAt: succeeded > 0 ? new Date().toISOString() : SyncStatus.current.lastSyncedAt,
  });
}

export function startAutoSync(intervalMs = 15000) {
  trySync();
  window.addEventListener("online", trySync);
  return setInterval(trySync, intervalMs);
}
