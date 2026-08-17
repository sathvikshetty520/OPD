/**
 * Local fallback source: reads the SAME IndexedDB database intake-app writes
 * to ("opd_intake"). This only sees cases entered on THIS browser/device.
 *
 * This is intentional interim behavior, not a hack: on a single-device setup
 * (one machine running both intake-app and this dashboard, e.g. a small
 * clinic with one front-desk workstation), this is a legitimate way to run
 * end-to-end with zero server. On a multi-station deployment, this fallback
 * is insufficient -- each station has its own separate IndexedDB -- which is
 * exactly why /server exists as a real requirement, not a nice-to-have.
 */

const DB_NAME = "opd_intake";
const CASES_STORE = "cases";

export async function fetchCasesFromLocalDevice() {
  return new Promise((resolve) => {
    const req = indexedDB.open(DB_NAME);
    req.onupgradeneeded = () => {
      // DB doesn't exist on this device yet (no intake-app has run here).
      req.transaction.abort();
    };
    req.onsuccess = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(CASES_STORE)) {
        resolve([]);
        return;
      }
      const tx = db.transaction(CASES_STORE, "readonly");
      const getAllReq = tx.objectStore(CASES_STORE).getAll();
      getAllReq.onsuccess = () => resolve(getAllReq.result || []);
      getAllReq.onerror = () => resolve([]);
    };
    req.onerror = () => resolve([]);
    req.onblocked = () => resolve([]);
  });
}

export async function updateCaseOnLocalDevice(caseId, patch) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME);
    req.onsuccess = () => {
      const db = req.result;
      const tx = db.transaction(CASES_STORE, "readwrite");
      const store = tx.objectStore(CASES_STORE);
      const getReq = store.get(caseId);
      getReq.onsuccess = () => {
        const existing = getReq.result;
        if (!existing) return reject(new Error("case not found: " + caseId));
        const updated = { ...existing, ...patch };
        store.put(updated);
        tx.oncomplete = () => resolve(updated);
      };
    };
    req.onerror = () => reject(req.error);
  });
}
