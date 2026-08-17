import { fetchCasesFromServer, pushReviewOutcome } from "./api-client/client.js";
import { fetchCasesFromLocalDevice, updateCaseOnLocalDevice } from "./local-fallback.js";

const state = { cases: [], source: "unknown", activeTab: "queue" };

async function loadCases() {
  const serverResult = await fetchCasesFromServer();
  if (serverResult.ok) {
    state.cases = serverResult.cases;
    state.source = "server";
  } else {
    state.cases = await fetchCasesFromLocalDevice();
    state.source = "local_device";
  }
  render();
}

async function resolveCase(caseId, outcome) {
  const patch = { status: outcome, reviewed_at: new Date().toISOString() };

  if (state.source === "server") {
    await pushReviewOutcome(caseId, patch);
  } else {
    await updateCaseOnLocalDevice(caseId, patch);
  }

  const c = state.cases.find((x) => x.case_id === caseId);
  if (c) Object.assign(c, patch);
  render();
}

function timeAgo(ts) {
  const mins = Math.max(0, Math.round((Date.now() - new Date(ts)) / 60000));
  return mins < 1 ? "just now" : mins + "m ago";
}

function caseCard(c, showActions) {
  const rules = (c.matched_rules || []).map((r) => `<div>${r}</div>`).join("");
  return `
    <div class="card case">
      <div class="row">
        <div>
          <span class="badge tier-${c.tier}">${c.tier_label || c.tier}</span>
          <span class="token">${c.patient_token}</span>
          <div class="meta">${c.department} &middot; ${timeAgo(c.timestamp)}</div>
        </div>
        <div class="meta">${(c.status || "").replace("_", " ")}</div>
      </div>
      <div class="log">${rules}</div>
      ${showActions ? `
        <div class="btns">
          <button class="primary" data-action="confirmed" data-id="${c.case_id}">Confirm emergency</button>
          <button data-action="downgraded" data-id="${c.case_id}">Downgrade after review</button>
        </div>` : ""}
    </div>`;
}

function render() {
  const pending = state.cases.filter((c) => c.status === "pending_review");
  const stats = [
    ["Pending review", pending.length, "var(--danger-tx)"],
    ["Cases today", state.cases.length, "var(--text)"],
    ["Urgent+", state.cases.filter((c) => c.tier === "urgent" || c.tier === "emergency").length, "var(--warn-tx)"],
    ["Standard/low", state.cases.filter((c) => c.tier === "standard" || c.tier === "nonurgent").length, "var(--std-tx)"],
  ];
  document.getElementById("stats").innerHTML = stats
    .map(([l, n, c]) => `<div class="stat"><div class="n" style="color:${c}">${n}</div><div class="l">${l}</div></div>`)
    .join("");

  document.getElementById("p-queue").innerHTML = pending.length
    ? pending.map((c) => caseCard(c, true)).join("")
    : `<div class="empty">No cases waiting on human review.</div>`;

  document.getElementById("p-all").innerHTML = state.cases.length
    ? state.cases.slice(0, 30).map((c) => caseCard(c, false)).join("")
    : `<div class="empty">No cases yet.</div>`;

  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => resolveCase(btn.dataset.id, btn.dataset.action));
  });

  const sourceLabel = state.source === "server"
    ? "Connected to central server"
    : "No server configured -- showing cases from this device only";
  document.getElementById("sourceStatus").textContent = sourceLabel;
  document.getElementById("sourceDot").className = "dot " + (state.source === "server" ? "on" : "");
}

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById("p-" + tab.dataset.p).classList.add("active");
    });
  });
}

initTabs();
loadCases();
setInterval(loadCases, 15000);
