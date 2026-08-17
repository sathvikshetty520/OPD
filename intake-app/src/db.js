/**
 * Local-first storage layer using IndexedDB.
 *
 * All writes land here FIRST, synchronously with the UI action, before any
 * network attempt. This is what makes the app usable with zero connectivity --
 * the network is an optional, best-effort layer on top, never a dependency
 * for recording a case.
 */

const DB_NAME = "opd_intake";
const DB_VERSION = 1;
const CASES_STORE = "cases";
const OUTBOX_STORE = "sync_outbox"; // records waiting to be pushed to server

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(CASES_STORE)) {
        const store = db.createObjectStore(CASES_STORE, { keyPath: "case_id" });
        store.createIndex("by_status", "status");
        store.createIndex("by_timestamp", "timestamp");
      }
      if (!db.objectStoreNames.contains(OUTBOX_STORE)) {
        db.createObjectStore(OUTBOX_STORE, { keyPath: "case_id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export const LocalStore = {
  /** Save a case record locally AND queue it for sync. Always succeeds offline. */
  async saveCase(caseRecord) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction([CASES_STORE, OUTBOX_STORE], "readwrite");
      tx.objectStore(CASES_STORE).put(caseRecord);
      tx.objectStore(OUTBOX_STORE).put(caseRecord);
      tx.oncomplete = () => resolve(caseRecord);
      tx.onerror = () => reject(tx.error);
    });
  },

  /** Update an existing case (e.g. staff review outcome) -- also re-queues for sync. */
  async updateCase(caseId, patch) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction([CASES_STORE, OUTBOX_STORE], "readwrite");
      const store = tx.objectStore(CASES_STORE);
      const getReq = store.get(caseId);
      getReq.onsuccess = () => {
        const existing = getReq.result;
        if (!existing) return reject(new Error("case not found: " + caseId));
        const updated = { ...existing, ...patch };
        store.put(updated);
        tx.objectStore(OUTBOX_STORE).put(updated);
        tx.oncomplete = () => resolve(updated);
      };
      getReq.onerror = () => reject(getReq.error);
    });
  },

  async getAllCases() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(CASES_STORE, "readonly");
      const req = tx.objectStore(CASES_STORE).getAll();
      req.onsuccess = () => resolve(req.result.sort((a, b) => b.timestamp.localeCompare(a.timestamp)));
      req.onerror = () => reject(req.error);
    });
  },

  async getOutbox() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(OUTBOX_STORE, "readonly");
      const req = tx.objectStore(OUTBOX_STORE).getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  },

  async clearFromOutbox(caseId) {
    return withStore(OUTBOX_STORE, "readwrite", (store) => store.delete(caseId));
  },
};
