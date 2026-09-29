const authGate = document.getElementById("auth-gate");
const appEl = document.getElementById("app");
const authForm = document.getElementById("auth-form");
const authEmail = document.getElementById("auth-email");
const authPassword = document.getElementById("auth-password");
const authName = document.getElementById("auth-name");
const authTenant = document.getElementById("auth-tenant");
const authError = document.getElementById("auth-error");
const authSubmit = document.getElementById("auth-submit");
const authTitle = document.getElementById("auth-title");
const authSub = document.getElementById("auth-sub");
const nameField = document.getElementById("name-field");
const tenantField = document.getElementById("tenant-field");
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");

const transcript = document.getElementById("transcript");
const form = document.getElementById("composer");
const input = document.getElementById("message");
const sendBtn = document.getElementById("send-btn");
const clearBtn = document.getElementById("clear-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const historyList = document.getElementById("history-list");
const historyEmpty = document.getElementById("history-empty");
const historyRail = document.getElementById("history-rail");
const historyBackdrop = document.getElementById("history-backdrop");
const historyCollapseBtn = document.getElementById("history-collapse-btn");
const historyOpenBtn = document.getElementById("history-open-btn");
const chatTitle = document.getElementById("chat-title");
const connectBtn = document.getElementById("connect-btn");
const disconnectBtn = document.getElementById("disconnect-btn");
const logoutBtn = document.getElementById("logout-btn");
const errorEl = document.getElementById("error");
const statusPill = document.getElementById("status-pill");
const tenantSelect = document.getElementById("tenant-select");
const userEmailEl = document.getElementById("user-email");
const sidebar = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const sidebarCollapseBtn = document.getElementById("sidebar-collapse-btn");
const sidebarOpenBtn = document.getElementById("sidebar-open-btn");
const sidebarOpenBtnChat = document.getElementById("sidebar-open-btn-chat");

const zohoModal = document.getElementById("zoho-modal");
const zohoPanelBtn = document.getElementById("zoho-panel-btn");
const zohoForm = document.getElementById("zoho-form");
const zohoDc = document.getElementById("zoho-dc");
const zohoOrg = document.getElementById("zoho-org");
const zohoRefresh = document.getElementById("zoho-refresh");
const zohoClientId = document.getElementById("zoho-client-id");
const zohoClientSecret = document.getElementById("zoho-client-secret");
const zohoSecretHint = document.getElementById("zoho-secret-hint");
const zohoRedirectUri = document.getElementById("zoho-redirect-uri");
const zohoError = document.getElementById("zoho-error");
const zohoOk = document.getElementById("zoho-ok");
const zohoSave = document.getElementById("zoho-save");

const viewAnalytics = document.getElementById("view-analytics");
const viewChat = document.getElementById("view-chat");
const navAnalytics = document.getElementById("nav-analytics");
const navChat = document.getElementById("nav-chat");
const analyticsBody = document.getElementById("analytics-body");
const analyticsTitle = document.getElementById("analytics-title");
const analyticsPeriod = document.getElementById("analytics-period");
const refreshAnalyticsBtn = document.getElementById("refresh-analytics-btn");
const chatLayout = document.querySelector(".chat-layout");

/** Public URL prefix when behind nginx, e.g. "/clario". Empty for local root. */
const BASE = String(window.CLARIO_BASE || "").replace(/\/$/, "");

function url(path) {
  if (!path) return BASE || "/";
  if (/^https?:\/\//i.test(path)) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${BASE}${normalized}`;
}

const TOKEN_KEY = "clario.token";
const TENANT_KEY = "clario.tenantId";
const SESSION_KEY = "clario.sessionId";
const CONVO_KEY = "clario.conversationId";
const VIEW_KEY = "clario.view";
const SIDEBAR_KEY = "clario.sidebarCollapsed";
const HISTORY_KEY = "clario.historyCollapsed";

let mode = "login";
let token = localStorage.getItem(TOKEN_KEY);
let tenantId = localStorage.getItem(TENANT_KEY);
let sessionId = localStorage.getItem(SESSION_KEY);
let conversationId = localStorage.getItem(CONVO_KEY);
let currentUserEmail = "";
let zohoConnected = false;
let currentView = localStorage.getItem(VIEW_KEY) || "analytics";
let sidebarCollapsed = localStorage.getItem(SIDEBAR_KEY) === "1";
let historyCollapsed = localStorage.getItem(HISTORY_KEY) === "1";
let sidebarDrawerOpen = false;
let historyDrawerOpen = false;

function isMobileLayout() {
  return window.matchMedia("(max-width: 720px)").matches;
}

function syncPanelControls() {
  const mobile = isMobileLayout();
  const sidebarExpanded = mobile ? sidebarDrawerOpen : !sidebarCollapsed;
  const historyExpanded = mobile ? historyDrawerOpen : !historyCollapsed;

  appEl.classList.toggle("sidebar-collapsed", !mobile && sidebarCollapsed);
  appEl.classList.toggle("sidebar-open", mobile && sidebarDrawerOpen);
  if (chatLayout) {
    chatLayout.classList.toggle("history-collapsed", mobile ? !historyDrawerOpen : historyCollapsed);
    chatLayout.classList.toggle("history-open", mobile && historyDrawerOpen);
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.hidden = !(mobile && sidebarDrawerOpen);
    sidebarBackdrop.classList.toggle("is-open", mobile && sidebarDrawerOpen);
    sidebarBackdrop.setAttribute("aria-hidden", mobile && sidebarDrawerOpen ? "false" : "true");
  }
  if (historyBackdrop) {
    historyBackdrop.hidden = !(mobile && historyDrawerOpen);
    historyBackdrop.classList.toggle("is-open", mobile && historyDrawerOpen);
    historyBackdrop.setAttribute("aria-hidden", mobile && historyDrawerOpen ? "false" : "true");
  }

  const sidebarButtons = [sidebarCollapseBtn, sidebarOpenBtn, sidebarOpenBtnChat].filter(Boolean);
  for (const btn of sidebarButtons) {
    btn.setAttribute("aria-expanded", sidebarExpanded ? "true" : "false");
    const opening = btn === sidebarCollapseBtn ? false : true;
    btn.title = opening
      ? sidebarExpanded
        ? "Menu open"
        : "Open menu"
      : "Collapse menu";
  }

  if (historyCollapseBtn) {
    historyCollapseBtn.setAttribute("aria-expanded", historyExpanded ? "true" : "false");
    historyCollapseBtn.title = "Hide chats";
  }
  if (historyOpenBtn) {
    historyOpenBtn.setAttribute("aria-expanded", historyExpanded ? "true" : "false");
    historyOpenBtn.title = historyExpanded ? "Chats open" : "Show chats";
  }
}

function setSidebarCollapsed(collapsed) {
  sidebarCollapsed = Boolean(collapsed);
  localStorage.setItem(SIDEBAR_KEY, sidebarCollapsed ? "1" : "0");
  if (!isMobileLayout()) sidebarDrawerOpen = false;
  syncPanelControls();
}

function setHistoryCollapsed(collapsed) {
  historyCollapsed = Boolean(collapsed);
  localStorage.setItem(HISTORY_KEY, historyCollapsed ? "1" : "0");
  if (!isMobileLayout()) historyDrawerOpen = false;
  syncPanelControls();
}

function openSidebarDrawer() {
  sidebarDrawerOpen = true;
  if (isMobileLayout()) historyDrawerOpen = false;
  syncPanelControls();
}

function closeSidebarDrawer() {
  sidebarDrawerOpen = false;
  syncPanelControls();
}

function openHistoryDrawer() {
  historyDrawerOpen = true;
  if (isMobileLayout()) sidebarDrawerOpen = false;
  syncPanelControls();
}

function closeHistoryDrawer() {
  historyDrawerOpen = false;
  syncPanelControls();
}

function toggleSidebar() {
  if (isMobileLayout()) {
    if (sidebarDrawerOpen) closeSidebarDrawer();
    else openSidebarDrawer();
    return;
  }
  setSidebarCollapsed(!sidebarCollapsed);
}

function toggleHistory() {
  if (isMobileLayout()) {
    if (historyDrawerOpen) closeHistoryDrawer();
    else openHistoryDrawer();
    return;
  }
  setHistoryCollapsed(!historyCollapsed);
}

function showError(message) {
  errorEl.hidden = !message;
  errorEl.textContent = message || "";
}

function showAuthError(message) {
  authError.hidden = !message;
  authError.textContent = message || "";
}

function showZohoError(message) {
  zohoError.hidden = !message;
  zohoError.textContent = message || "";
  if (message) zohoOk.hidden = true;
}

function showZohoOk(message) {
  zohoOk.hidden = !message;
  zohoOk.textContent = message || "";
  if (message) zohoError.hidden = true;
}

function appendMessage(role, html) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.innerHTML = html;
  transcript.appendChild(el);
  transcript.scrollTop = transcript.scrollHeight;
  return el;
}

function authHeaders(extra = {}) {
  const headers = { ...extra };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (tenantId) headers["X-Tenant-Id"] = tenantId;
  return headers;
}

async function api(path, options = {}) {
  const res = await fetch(url(path), {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...authHeaders(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail || data);
    throw new Error(message || `HTTP ${res.status}`);
  }
  return data;
}

function setMode(next) {
  mode = next;
  tabLogin.classList.toggle("active", mode === "login");
  tabRegister.classList.toggle("active", mode === "register");
  nameField.hidden = mode !== "register";
  tenantField.hidden = mode !== "register";
  authSubmit.textContent = mode === "login" ? "Sign in" : "Create account";
  authTitle.textContent = mode === "login" ? "Welcome back" : "Create your workspace";
  authSub.textContent =
    mode === "login"
      ? "Sign in to your Clario workspace"
      : "Register and spin up an isolated Zoho workspace";
}

function setView(view) {
  currentView = view === "chat" ? "chat" : "analytics";
  localStorage.setItem(VIEW_KEY, currentView);
  viewAnalytics.hidden = currentView !== "analytics";
  viewChat.hidden = currentView !== "chat";
  navAnalytics.classList.toggle("active", currentView === "analytics");
  navChat.classList.toggle("active", currentView === "chat");
  if (isMobileLayout()) {
    closeSidebarDrawer();
    if (currentView !== "chat") closeHistoryDrawer();
  }
  if (currentView === "analytics") loadAnalytics();
  if (currentView === "chat") loadHistory();
  syncPanelControls();
}

tabLogin.addEventListener("click", () => setMode("login"));
tabRegister.addEventListener("click", () => setMode("register"));
navAnalytics.addEventListener("click", () => setView("analytics"));
navChat.addEventListener("click", () => setView("chat"));
refreshAnalyticsBtn.addEventListener("click", () => loadAnalytics(true));

sidebarCollapseBtn?.addEventListener("click", () => {
  if (isMobileLayout()) closeSidebarDrawer();
  else setSidebarCollapsed(true);
});
sidebarOpenBtn?.addEventListener("click", () => {
  if (isMobileLayout()) openSidebarDrawer();
  else setSidebarCollapsed(false);
});
sidebarOpenBtnChat?.addEventListener("click", () => {
  if (isMobileLayout()) openSidebarDrawer();
  else setSidebarCollapsed(false);
});
sidebarBackdrop?.addEventListener("click", () => closeSidebarDrawer());

historyCollapseBtn?.addEventListener("click", () => {
  if (isMobileLayout()) closeHistoryDrawer();
  else setHistoryCollapsed(true);
});
historyOpenBtn?.addEventListener("click", () => {
  if (isMobileLayout()) openHistoryDrawer();
  else setHistoryCollapsed(false);
});
historyBackdrop?.addEventListener("click", () => closeHistoryDrawer());

window.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (sidebarDrawerOpen) closeSidebarDrawer();
  if (historyDrawerOpen) closeHistoryDrawer();
});

window.addEventListener("resize", () => {
  if (!isMobileLayout()) {
    sidebarDrawerOpen = false;
    historyDrawerOpen = false;
  }
  syncPanelControls();
});

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showAuthError("");
  try {
    const body =
      mode === "login"
        ? { email: authEmail.value, password: authPassword.value }
        : {
            email: authEmail.value,
            password: authPassword.value,
            full_name: authName.value,
            tenant_name: authTenant.value || undefined,
          };
    const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
    const data = await api(path, { method: "POST", body: JSON.stringify(body) });
    token = data.access_token;
    tenantId = data.tenant_id;
    currentUserEmail = data.email || authEmail.value;
    localStorage.setItem(TOKEN_KEY, token);
    if (tenantId) localStorage.setItem(TENANT_KEY, tenantId);
    await enterApp();
  } catch (err) {
    showAuthError(err.message);
  }
});

function openZohoModal() {
  zohoModal.hidden = false;
  showZohoError("");
  showZohoOk("");
  zohoRefresh.value = "";
  zohoClientSecret.value = "";
}

function fillZohoForm(zoho) {
  if (!zoho) return;
  if (zoho.data_center) zohoDc.value = zoho.data_center;
  zohoOrg.value = zoho.organization_id || "";
  zohoClientId.value = zoho.client_id || "";
  if (zoho.redirect_uri) zohoRedirectUri.textContent = zoho.redirect_uri;
  if (zoho.client_secret_configured) {
    zohoSecretHint.hidden = false;
    zohoSecretHint.textContent = `Secret saved (${zoho.client_secret_masked || "••••"}). Leave blank to keep it.`;
  } else if (zoho.uses_platform_oauth_app) {
    zohoSecretHint.hidden = false;
    zohoSecretHint.textContent =
      "Using platform Zoho app from server .env. Add this workspace’s own Client ID + Secret to isolate orgs.";
  } else {
    zohoSecretHint.hidden = false;
    zohoSecretHint.textContent =
      "Paste Client ID and Secret from this organization’s Zoho API Console (Server-based app).";
  }
}

function closeZohoModal() {
  zohoModal.hidden = true;
}

zohoPanelBtn.addEventListener("click", openZohoModal);
document.querySelectorAll("[data-close-zoho]").forEach((el) => {
  el.addEventListener("click", closeZohoModal);
});

async function enterApp() {
  authGate.hidden = true;
  appEl.hidden = false;
  syncPanelControls();
  const me = await api("/api/me");
  currentUserEmail = me.email || currentUserEmail;
  userEmailEl.textContent = currentUserEmail || "";
  tenantSelect.innerHTML = "";
  for (const tenant of me.tenants) {
    const opt = document.createElement("option");
    opt.value = tenant.id;
    opt.textContent = tenant.name;
    if (tenant.id === tenantId) opt.selected = true;
    tenantSelect.appendChild(opt);
  }
  if (!tenantId && me.tenants[0]) {
    tenantId = me.tenants[0].id;
    localStorage.setItem(TENANT_KEY, tenantId);
    tenantSelect.value = tenantId;
  }
  await loadStatus();
  setView(currentView);
  if (conversationId && currentView === "chat") {
    openConversation(conversationId).catch(() => startNewChat());
  } else if (!transcript.querySelector(".msg")) {
    appendMessage(
      "system",
      "Ask a question grounded in this workspace’s Zoho Books data. Open <strong>Zoho Books</strong> in the sidebar to connect."
    );
  }
}

tenantSelect.addEventListener("change", async () => {
  tenantId = tenantSelect.value;
  localStorage.setItem(TENANT_KEY, tenantId);
  sessionId = null;
  conversationId = null;
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(CONVO_KEY);
  transcript.innerHTML = "";
  appendMessage("system", "Switched workspace. Ask a question grounded in this tenant’s Zoho Books data.");
  await loadStatus();
  if (currentView === "analytics") await loadAnalytics(true);
  else await loadHistory();
});

function formatHistoryDate(iso) {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

async function loadHistory() {
  if (!token || !tenantId) return;
  try {
    const data = await api("/api/conversations");
    const rows = data.conversations || [];
    historyList.innerHTML = "";
    historyEmpty.hidden = rows.length > 0;
    for (const row of rows) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = row.id === conversationId ? "active" : "";
      btn.innerHTML = `<span class="htitle">${escapeHtml(row.title || "New chat")}</span>
        <span class="hmeta">${escapeHtml(formatHistoryDate(row.updated_at || row.created_at))}</span>`;
      btn.addEventListener("click", () => openConversation(row.id));
      li.appendChild(btn);
      historyList.appendChild(li);
    }
  } catch (err) {
    historyEmpty.hidden = false;
    historyEmpty.textContent = err.message || "Could not load history.";
  }
}

async function openConversation(id) {
  showError("");
  try {
    const data = await api(`/api/conversations/${encodeURIComponent(id)}`);
    conversationId = data.id;
    sessionId = data.session_id;
    localStorage.setItem(CONVO_KEY, conversationId);
    localStorage.setItem(SESSION_KEY, sessionId);
    chatTitle.textContent = data.title || "Ask Clario";
    transcript.innerHTML = "";
    const messages = data.messages || [];
    if (!messages.length) {
      appendMessage("system", "Continue this conversation, or start a new one from History.");
    }
    for (const msg of messages) {
      if (msg.role === "user") appendMessage("user", marked.parse(msg.content || ""));
      else if (msg.role === "assistant") appendMessage("agent", marked.parse(msg.content || ""));
      else appendMessage("system", escapeHtml(msg.content || ""));
    }
    await loadHistory();
    if (isMobileLayout()) closeHistoryDrawer();
  } catch (err) {
    showError(err.message);
  }
}

function startNewChat() {
  sessionId = null;
  conversationId = null;
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(CONVO_KEY);
  chatTitle.textContent = "Ask Clario";
  transcript.innerHTML = "";
  appendMessage("system", "New chat. Ask a question grounded in this workspace’s Zoho Books data.");
  showError("");
  loadHistory();
  input.focus();
}

newChatBtn.addEventListener("click", () => startNewChat());

async function loadStatus() {
  try {
    const [status, tenant] = await Promise.all([
      api("/api/status"),
      api("/api/tenants/current").catch(() => null),
    ]);
    if (tenant?.zoho) {
      fillZohoForm(tenant.zoho);
    }
    zohoConnected = Boolean(status.zoho_ready || status.organization);
    if (status.organization) {
      statusPill.textContent = `${status.organization.name} · ${status.organization.currency_code || "Zoho"}`;
      statusPill.className = "pill ok";
      zohoPanelBtn.textContent = "Zoho connected";
    } else if (status.zoho_ready) {
      statusPill.textContent = "Zoho authorized";
      statusPill.className = "pill ok";
      zohoPanelBtn.textContent = "Zoho Books";
    } else {
      statusPill.textContent = "Zoho not connected";
      statusPill.className = "pill bad";
      zohoPanelBtn.textContent = "Connect Zoho";
    }
  } catch (err) {
    zohoConnected = false;
    statusPill.textContent = "API unavailable";
    statusPill.className = "pill bad";
    if (String(err.message).includes("Not authenticated") || String(err.message).includes("Invalid token")) {
      logout();
    }
  }
}

function money(amount, currency) {
  const n = Number(amount || 0);
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency || "INR",
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `${currency || ""} ${n.toLocaleString()}`;
  }
}

function formatDelta(change) {
  if (!change) return { text: "vs prior period", cls: "flat" };
  const pct = change.change_percent;
  if (pct === null || pct === undefined) {
    return { text: "no prior baseline", cls: "flat" };
  }
  const n = Number(pct);
  const sign = n > 0 ? "+" : "";
  const cls = n > 0 ? "up" : n < 0 ? "down" : "flat";
  return { text: `${sign}${n}% vs prior`, cls };
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function loadAnalytics(force) {
  if (!force && analyticsBody.dataset.loaded === tenantId && zohoConnected) return;

  if (!zohoConnected) {
    analyticsTitle.textContent = "Business overview";
    analyticsPeriod.textContent = "Connect Zoho Books to load live metrics";
    analyticsBody.innerHTML =
      '<p class="muted analytics-empty">Connect Zoho Books for this workspace to see sales, expenses, receivables, and signals.</p>';
    analyticsBody.dataset.loaded = "";
    return;
  }

  analyticsBody.innerHTML = '<p class="muted analytics-empty">Loading analytics from Zoho Books…</p>';
  try {
    const data = await api("/api/analytics/overview");
    renderAnalytics(data);
    analyticsBody.dataset.loaded = tenantId;
  } catch (err) {
    analyticsBody.innerHTML = `<p class="error analytics-empty">${escapeHtml(err.message)}</p>`;
    analyticsBody.dataset.loaded = "";
  }
}

function renderAnalytics(data) {
  const currency = data.currency || "INR";
  const salesDelta = formatDelta(data.sales_change);
  const expenseDelta = formatDelta(data.expense_change);
  analyticsTitle.textContent = data.organization_name || "Business overview";
  analyticsPeriod.textContent = `${data.current_period_start} → ${data.current_period_end} · ${currency}`;

  const customers = (data.top_customers || [])
    .slice(0, 5)
    .map(
      (c) => `<li>
        <div>
          <div class="name">${escapeHtml(c.customer || "Unknown")}</div>
          <div class="meta">${c.invoice_count || 0} invoices${c.share_percent != null ? ` · ${c.share_percent}%` : ""}</div>
        </div>
        <div class="amount">${escapeHtml(money(c.sales, currency))}</div>
      </li>`
    )
    .join("");

  const signals = (data.signals || [])
    .map((s) => {
      const sev = (s.severity || "").toLowerCase();
      const cls = sev.includes("high") || sev.includes("alert") ? "alert" : sev.includes("warn") ? "warn" : "";
      return `<li class="signal ${cls}">
        <div class="sig-name">${escapeHtml(s.name || sev || "Signal")}</div>
        <p>${escapeHtml(s.observation || "")}</p>
      </li>`;
    })
    .join("");

  analyticsBody.innerHTML = `
    <div class="metric-row">
      <div class="metric">
        <span class="label">Sales</span>
        <div class="value">${escapeHtml(money(data.sales?.total_sales, currency))}</div>
        <div class="delta ${salesDelta.cls}">${escapeHtml(salesDelta.text)}</div>
        <div class="hint">${data.sales?.invoice_count || 0} invoices</div>
      </div>
      <div class="metric">
        <span class="label">Expenses</span>
        <div class="value">${escapeHtml(money(data.expenses?.total_expenses, currency))}</div>
        <div class="delta ${expenseDelta.cls}">${escapeHtml(expenseDelta.text)}</div>
        <div class="hint">${data.expenses?.expense_count || 0} expenses</div>
      </div>
      <div class="metric">
        <span class="label">Outstanding</span>
        <div class="value">${escapeHtml(money(data.receivables?.outstanding, currency))}</div>
        <div class="hint">${data.receivables?.invoice_count || 0} open invoices</div>
      </div>
      <div class="metric">
        <span class="label">Overdue</span>
        <div class="value">${escapeHtml(money(data.receivables?.overdue, currency))}</div>
        <div class="hint">${data.receivables?.overdue_count || 0} overdue</div>
      </div>
    </div>
    <div class="analytics-grid">
      <div class="panel-block">
        <h3>Top customers</h3>
        ${customers ? `<ul class="rank-list">${customers}</ul>` : `<p class="muted small">No customer sales in this period.</p>`}
      </div>
      <div class="panel-block">
        <h3>Signals</h3>
        ${signals ? `<ul class="signal-list">${signals}</ul>` : `<p class="muted small">No material signals right now.</p>`}
      </div>
    </div>
  `;
}

zohoForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showZohoError("");
  showZohoOk("");
  zohoSave.disabled = true;
  try {
    const body = {
      data_center: zohoDc.value,
      organization_id: zohoOrg.value.trim(),
      client_id: zohoClientId.value.trim(),
      client_secret: zohoClientSecret.value.trim(),
      refresh_token: zohoRefresh.value.trim(),
    };
    const data = await api("/api/tenants/current/zoho/settings", {
      method: "POST",
      body: JSON.stringify(body),
    });
    zohoRefresh.value = "";
    zohoClientSecret.value = "";
    fillZohoForm(data.zoho);
    showZohoOk(
      body.refresh_token
        ? "Zoho credentials saved and verified for this workspace."
        : "Workspace Zoho settings saved. Use Connect with Zoho to authorize."
    );
    await loadStatus();
    if (currentView === "analytics") await loadAnalytics(true);
  } catch (err) {
    showZohoError(err.message);
  } finally {
    zohoSave.disabled = false;
  }
});

connectBtn.addEventListener("click", async () => {
  showZohoError("");
  try {
    await api("/api/tenants/current/zoho/settings", {
      method: "POST",
      body: JSON.stringify({
        data_center: zohoDc.value,
        organization_id: zohoOrg.value.trim(),
        client_id: zohoClientId.value.trim(),
        client_secret: zohoClientSecret.value.trim(),
        refresh_token: "",
      }),
    });
    zohoClientSecret.value = "";
    const data = await api("/api/oauth/zoho/start?redirect_after=" + encodeURIComponent(BASE || "/"));
    window.location.href = data.authorization_url;
  } catch (err) {
    showZohoError(err.message);
  }
});

disconnectBtn.addEventListener("click", async () => {
  showZohoError("");
  try {
    await api("/api/tenants/current/zoho", { method: "DELETE" });
    showZohoOk("Disconnected Zoho for this workspace.");
    await loadStatus();
    if (currentView === "analytics") await loadAnalytics(true);
  } catch (err) {
    showZohoError(err.message);
  }
});

logoutBtn.addEventListener("click", () => logout());

function logout() {
  token = null;
  tenantId = null;
  sessionId = null;
  conversationId = null;
  zohoConnected = false;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TENANT_KEY);
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(CONVO_KEY);
  appEl.hidden = true;
  authGate.hidden = false;
  closeZohoModal();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  showError("");
  appendMessage("user", marked.parse(message));
  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;
  const loading = appendMessage("system", "Retrieving Zoho Books data…");
  try {
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        session_id: sessionId,
        conversation_id: conversationId,
      }),
    });
    loading.remove();
    sessionId = data.session_id;
    conversationId = data.conversation_id;
    localStorage.setItem(SESSION_KEY, sessionId);
    localStorage.setItem(CONVO_KEY, conversationId);
    appendMessage("agent", marked.parse(data.answer || ""));
    chatTitle.textContent = chatTitle.textContent === "Ask Clario" ? "Ask Clario" : chatTitle.textContent;
    await loadHistory();
    if (conversationId) {
      // Refresh title from list after first user message names the thread.
      const active = historyList.querySelector("button.active .htitle");
      if (active && active.textContent) chatTitle.textContent = active.textContent;
    }
  } catch (err) {
    loading.remove();
    showError(err.message);
    appendMessage("system", err.message);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

clearBtn.addEventListener("click", async () => {
  if (conversationId) {
    try {
      await api(`/api/conversations/${encodeURIComponent(conversationId)}`, { method: "DELETE" });
    } catch {
      /* ignore */
    }
  } else if (sessionId) {
    try {
      await api(`/api/chat/clear?session_id=${encodeURIComponent(sessionId)}`, { method: "POST" });
    } catch {
      /* ignore */
    }
  }
  startNewChat();
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
});

if (token) {
  enterApp().catch(() => logout());
} else {
  syncPanelControls();
}
