import { LocalStore } from "./db.js";
import { loadRules, score } from "./engine.js";
import { SyncStatus, startAutoSync, pullStatusUpdates } from "./sync.js";

const state = { rules: null, selectedFlags: new Set() };

async function init() {
  state.rules = await loadRules();
  renderComplaintOptions();
  renderFlagChips();
  await renderCaseHistory();
  startAutoSync();
  SyncStatus.subscribe(renderSyncStatus);

  // Periodically pull status updates from the server (e.g. staff review
  // outcomes) and re-render, so front-desk can see review status without
  // needing to check staff-dashboard themselves.
  setInterval(async () => {
    await pullStatusUpdates();
    await renderCaseHistory();
  }, 15000);

  document.getElementById("submit").addEventListener("click", onSubmit);
  window.addEventListener("online", () => renderSyncStatus(SyncStatus.current));
  window.addEventListener("offline", () => renderSyncStatus(SyncStatus.current));
}

function renderComplaintOptions() {
  const sel = document.getElementById("complaint");
  sel.innerHTML = Object.entries(state.rules.complaints)
    .map(([id, c]) => `<option value="${id}">${c.label}</option>`)
    .join("");
}

function renderFlagChips() {
  const wrap = document.getElementById("flags");
  wrap.innerHTML = state.rules.red_flags
    .map((f) => `<div class="chip" data-id="${f.id}">${f.label}</div>`)
    .join("");
  wrap.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      chip.classList.toggle("on");
      const id = chip.dataset.id;
      state.selectedFlags.has(id) ? state.selectedFlags.delete(id) : state.selectedFlags.add(id);
    });
  });
}

async function onSubmit() {
  const msg = document.getElementById("submitMsg");
  const token = document.getElementById("patientToken").value.trim();
  const complaintId = document.getElementById("complaint").value;

  if (!token) {
    msg.textContent = "Enter a patient token first.";
    msg.className = "msg error";
    return;
  }

  const result = score(state.rules, {
    patientToken: token,
    complaintId,
    redFlagIds: [...state.selectedFlags],
  });

  // Local-first: this write succeeds with zero network. Sync is separate and best-effort.
  await LocalStore.saveCase(result);

  msg.textContent = `Saved locally -- tier: ${result.tier_label}${result.escalate ? " (flagged for staff review)" : ""}`;
  msg.className = "msg ok";

  document.getElementById("patientToken").value = "";
  state.selectedFlags.clear();
  document.querySelectorAll(".chip.on").forEach((c) => c.classList.remove("on"));

  await renderCaseHistory();
}

async function renderCaseHistory() {
  const cases = await LocalStore.getAllCases();
  const list = document.getElementById("history");
  if (cases.length === 0) {
    list.innerHTML = `<div class="empty">No cases recorded on this device yet.</div>`;
    return;
  }
  list.innerHTML = cases
    .slice(0, 20)
    .map((c) => {
      let statusLabel;
      if (c.status === "pending_review") statusLabel = "awaiting staff review";
      else if (c.status === "confirmed") statusLabel = `confirmed${c.reviewed_by ? " by " + c.reviewed_by : ""}`;
      else if (c.status === "downgraded") statusLabel = `downgraded${c.reviewed_by ? " by " + c.reviewed_by : ""}`;
      else statusLabel = "routed";

      return `
      <div class="case-row">
        <span class="badge tier-${c.tier}">${c.tier_label}</span>
        <span class="token">${c.patient_token}</span>
        <span class="dept">${c.department}</span>
        <span class="status">${statusLabel}</span>
      </div>`;
    })
    .join("");
}

function renderSyncStatus(s) {
  const el = document.getElementById("syncStatus");
  const dot = document.getElementById("syncDot");
  const labels = {
    offline: "Offline -- cases saved on this device, will sync when connected",
    syncing: "Syncing…",
    synced: "All cases synced",
    partial: `${s.pendingCount} case(s) waiting to sync`,
  };
  el.textContent = labels[s.state] || s.state;
  dot.className = "dot " + (s.state === "synced" ? "on" : "off");
}

init();