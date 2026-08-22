import { fetchCasesFromServer, pushReviewOutcome, login, logout, getStoredSession } from "./api-client/client.js";
import { fetchCasesFromLocalDevice, updateCaseOnLocalDevice } from "./local-fallback.js";

const state = { cases: [], source: "unknown" };

function showLoginScreen() {
  document.getElementById("loginScreen").style.display = "flex";
  document.getElementById("mainScreen").style.display = "none";
}

function showMainScreen() {
  const session = getStoredSession();
  document.getElementById("loginScreen").style.display = "none";
  document.getElementById("mainScreen").style.display = "block";
  document.getElementById("whoami").textContent = session ? `Signed in as ${session.display_name}` : "";
}

async function onLogin() {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const msg = document.getElementById("loginMsg");

  if (!username || !password) {
    msg.textContent = "Enter both username and password.";
    msg.className = "msg error";
    return;
  }

  msg.textContent = "Signing in…";
  msg.className = "msg";

  const result = await login(username, password);
  if (!result.ok) {
    msg.textContent = result.reason === "unreachable"
      ? "Can't reach the server. Check it's running."
      : "Invalid username or password.";
    msg.className = "msg error";
    return;
  }

  document.getElementById("password").value = "";
  showMainScreen();
  loadCases();
}

async function onLogout() {
  await logout();
  showLoginScreen();
}

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
    const result = await pushReviewOutcome(caseId, patch);
    if (!result.ok) {
      if (result.reason === "session_expired" || result.reason === "not_logged_in") {
        showLoginScreen();
        return;
      }
      alert("Couldn't save review outcome: " + (result.reason || "unknown error"));
      return;
    }
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
        <div class="meta">${(c.status || "").replace("_", " ")}${c.reviewed_by ? " by " + c.reviewed_by : ""}</div>
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

document.getElementById("loginBtn").addEventListener("click", onLogin);
document.getElementById("password").addEventListener("keydown", (e) => {
  if (e.key === "Enter") onLogin();
});
document.getElementById("logoutBtn").addEventListener("click", onLogout);

initTabs();

// Viewing the queue doesn't require staff login (station key is enough),
// so show the dashboard immediately, but the login screen is still available
// via any 401 on a review action.
if (getStoredSession()) {
  showMainScreen();
} else {
  showMainScreen(); // queue is viewable either way; login only gates review actions
}
loadCases();
setInterval(loadCases, 15000);