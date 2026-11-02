/* App shell: boots the store, seeds demo data on first launch, handles login and sessions, renders the
   sidebar / top bar and routes to the views according to the role matrix. */
import { store, todayISO } from "./store.js";
import * as repo from "./repo.js";
import * as auth from "./auth.js";
import { needsSeed, seedDemo, DEMO_USERS } from "./seed.js";
import { t, setLang, getLang, LANGS } from "./i18n.js";
import { icon } from "./icons.js";
import { esc, initials, money, logoSrc, hasLogo, toast, fmtDate, field, input, btn, notice, errorMessage, closeModal } from "./ui.js";
import { navigate, onRoute, parseRoute } from "./router.js";
import * as dashboard from "./views/dashboard.js";
import * as patients from "./views/patients.js";
import * as appointments from "./views/appointments.js";
import * as queue from "./views/queue.js";
import * as consultations from "./views/consultations.js";
import * as prescriptions from "./views/prescriptions.js";
import * as billing from "./views/billing.js";
import * as inventory from "./views/inventory.js";
import * as reports from "./views/reports.js";
import * as settings from "./views/settings.js";

const CFG = window.CML_CONFIG || {};
const F = CFG.features || {};
const NAV = [
  ["dashboard", "dashboard", "layout-dashboard"],
  ["appointments", "appointments", "calendar"],
  ["patients", "patients", "users"],
  ["queue", "queue", "ticket"],
  ["consultations", "consultations", "stethoscope"],
  ["prescriptions", "prescriptions", "file-text"],
  ["billing", "billing", "credit-card"],
  ["inventory", "inventory", "package", F.inventory !== false],
  ["reports", "reports", "bar-chart", F.reports !== false],
  ["settings", "settings", "settings"],
].filter((n) => n[3] !== false);
const VIEWS = { dashboard, patients, appointments, queue, consultations, prescriptions, billing, inventory, reports, settings };
const BOTTOM = ["dashboard", "appointments", "patients", "queue"];

export const app = {
  store, repo, auth, t, navigate, icon, money,
  ui: {},           // per-view transient state (filters, pages, open forms)
  user: null,
  params: {},
  get page() { return parseRoute().page; },
  get settings() { return store.settings; },
  refresh() { route(parseRoute()); },
  setLanguage(l) { setLang(l); try { localStorage.setItem(`${CFG.storageKey || "cml"}:lang`, l); } catch { /* ignore */ } if (app.user) { renderShell(); route(parseRoute()); } else renderLogin(); },
  signOut(expired = false) { if (app.user) auth.logout(app.user.session_token, app.user); app.user = null; app.ui = {}; closeModal(true); showLogin(expired); },
  canView: (m) => auth.canView(app.user, m),
  canEdit: (m) => auth.canEdit(app.user, m),
  isAdmin: () => auth.isAdmin(app.user),
  isDoctor: () => auth.isDoctor(app.user),
  allowedNav: () => NAV.filter((n) => auth.canView(app.user, n[0])),
  rerenderShell: () => renderShell(),
};

// ------------------------------------------------------------ theme
function applyTheme() {
  const th = CFG.theme || {}; const root = document.documentElement.style;
  if (th.primary) root.setProperty("--primary", th.primary); if (th.primaryDark) root.setProperty("--primary-dark", th.primaryDark);
  if (th.navy) { root.setProperty("--navy", th.navy); root.setProperty("--text", th.navy); } if (th.background) root.setProperty("--bg", th.background);
  document.querySelector('meta[name="theme-color"]').setAttribute("content", th.primary || "#087F8C");
  document.title = store.settings.clinic_name ? `${store.settings.clinic_name} - ${CFG.productName || "Clinic Management Lite"}` : (CFG.productName || "Clinic Management Lite");
}
const logoHTML = (size = 40) => hasLogo() ? `<img src="${logoSrc()}" alt="" style="width:${size}px;height:${size}px"/>` : `<span class="mark" style="width:${size}px;height:${size}px">${icon("hospital", Math.round(size * 0.55))}</span>`;

// ------------------------------------------------------------ login
function showLogin(expired = false) {
  document.getElementById("app").hidden = true;
  app.loginFlash = expired ? t("session_expired") : "";
  renderLogin();
  document.getElementById("login").hidden = false;
}
function renderLogin() {
  const s = store.settings; const el = document.getElementById("login");
  const demo = s.demo_mode === "1" && F.demoData !== false;
  el.innerHTML = `<div class="login-card">
    <div class="login-brand">${logoHTML(52)}<div><h2>${esc(s.clinic_name)}</h2><p>${esc(t("login_sub"))}</p></div></div>
    <form class="card login-form" id="loginForm" autocomplete="on">
      <b>${esc(t("welcome_back"))}</b>
      <div class="form-error" hidden></div>
      ${field(t("username"), input("username", "", 'autocomplete="username" autocapitalize="none" spellcheck="false" required'))}
      ${field(t("password"), input("password", "", 'type="password" autocomplete="current-password" required'))}
      ${btn(t("login"), { ic: "log-in", cls: "primary block", type: "submit", attrs: 'id="loginBtn"' })}
      ${app.loginFlash ? notice(app.loginFlash, "warning", "clock") : ""}
    </form>
    <div class="login-foot">
      <div class="lang-switch" id="loginLang">${Object.entries(LANGS).map(([k, l]) => `<button type="button" data-lang="${k}" class="${getLang() === k ? "active" : ""}" style="flex:1">${esc(l)}</button>`).join("")}</div>
      ${demo ? `<details class="disclosure card tight"><summary>${icon("key-round", 15)}${esc(t("demo_accounts"))}</summary><table class="demo-table"><thead><tr><th>${esc(t("role"))}</th><th>${esc(t("username"))}</th><th>${esc(t("password"))}</th></tr></thead><tbody>${DEMO_USERS.map(([u, p, , r]) => `<tr class="pick" data-u="${esc(u)}" data-p="${esc(p)}"><td>${esc(t(r))}</td><td class="num">${esc(u)}</td><td class="num">${esc(p)}</td></tr>`).join("")}</tbody></table><div class="faint" style="margin-top:6px">${esc(t("demo_hint"))}</div></details>` : ""}
      ${notice(t("data_notice"), "neutral", "shield")}
      <div class="faint" style="text-align:center">${esc(CFG.productName || "Clinic Management Lite")} v${esc(CFG.version || "")}</div>
    </div></div>`;
  if (F.urdu === false) el.querySelector("#loginLang").hidden = true;
  el.querySelectorAll("#loginLang button").forEach((b) => b.addEventListener("click", () => app.setLanguage(b.dataset.lang)));
  el.querySelectorAll("tr.pick").forEach((tr) => tr.addEventListener("click", () => { el.querySelector('[name="username"]').value = tr.dataset.u; el.querySelector('[name="password"]').value = tr.dataset.p; el.querySelector('[name="password"]').focus(); }));
  const form = el.querySelector("#loginForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); const b = form.querySelector("#loginBtn"); b.disabled = true; const box = form.querySelector(".form-error"); box.hidden = true;
    try {
      const { user, error } = await auth.login(form.username.value, form.password.value);
      if (error) { box.innerHTML = notice(t(error.key, error.vars || {}), "error", "circle-alert"); box.hidden = false; return; }
      enterApp(user);
    } catch (err) { box.innerHTML = notice(errorMessage(err), "error", "circle-alert"); box.hidden = false; }
    finally { b.disabled = false; }
  });
  setTimeout(() => form.username.focus(), 30);
}
function enterApp(user) {
  app.user = user; app.ui = {}; app.loginFlash = "";
  document.getElementById("login").hidden = true;
  renderShell(); document.getElementById("app").hidden = false;
  const r = parseRoute(); if (!auth.canView(user, r.page)) navigate("dashboard"); else route(r);
}

// ------------------------------------------------------------ shell
function renderShell() {
  const s = store.settings; const page = parseRoute().page; const u = app.user; if (!u) return;
  document.getElementById("brand").innerHTML = `${logoHTML(40)}<div><div class="name">${esc(s.clinic_name)}</div><div class="sub">${esc(s.clinic_tagline || CFG.productName || "")}</div></div>`;
  document.getElementById("nav").innerHTML = app.allowedNav().map(([key, label, ic]) => `<button type="button" class="nav-item ${page === key ? "active" : ""}" data-nav="${key}">${icon(ic, 18)}<span>${esc(t(label))}</span></button>`).join("");
  document.getElementById("sidebarFoot").innerHTML = `<div class="sidebar-user"><span class="avatar">${esc(initials(u.full_name))}</span><div class="who"><b>${esc(u.full_name)}</b><span>${esc(t(u.role))}${u.doctor_name && u.role !== "doctor" ? ` · ${esc(u.doctor_name)}` : ""}</span></div></div>
    ${btn(t("logout"), { ic: "log-out", cls: "sm block", attrs: 'id="logoutBtn"' })}<div class="sidebar-version">${esc(CFG.productName || "")} v${esc(CFG.version || "")}</div>`;
  document.getElementById("collapseBtn").innerHTML = icon("chevrons-left", 16);
  document.getElementById("menuBtn").innerHTML = icon("menu", 18);
  document.getElementById("searchIcon").innerHTML = icon("search", 17);
  document.getElementById("globalSearch").placeholder = t("global_search_hint");
  document.getElementById("topMeta").innerHTML = `${icon("hospital", 15)}<span class="clinic">${esc(s.clinic_name)}</span><span class="dot"></span>${icon("calendar", 15)}<span>${esc(fmtDate(todayISO(), true))}</span>`;
  document.getElementById("profile").innerHTML = `<div class="who"><b>${esc(u.full_name)}</b><span>${esc(t(u.role))}</span></div><div class="avatar">${esc(initials(u.full_name))}</div>`;
  document.querySelectorAll("#langSwitch button").forEach((b) => b.classList.toggle("active", b.dataset.lang === getLang()));
  document.getElementById("langSwitch").hidden = F.urdu === false;
  const allowed = app.allowedNav();
  document.getElementById("bottomNav").innerHTML = BOTTOM.filter((k) => allowed.some((n) => n[0] === k)).map((k) => { const n = allowed.find((x) => x[0] === k); return `<button type="button" data-nav="${k}" class="${page === k ? "active" : ""}">${icon(n[2], 20)}<span>${esc(k === "dashboard" ? t("home") : k === "queue" ? t("token") : t(n[1]))}</span></button>`; }).join("") + `<button type="button" data-menu>${icon("menu", 20)}<span>${esc(t("more"))}</span></button>`;
  document.getElementById("logoutBtn").addEventListener("click", () => app.signOut(false));
  applyTheme();
}
function setActiveNav(page) { document.querySelectorAll("[data-nav]").forEach((b) => { if (b.classList.contains("nav-item") || b.closest("#bottomNav")) b.classList.toggle("active", b.dataset.nav === page); }); }

// ------------------------------------------------------------ routing
function route(r) {
  if (!app.user) return;
  const live = auth.validateSession(app.user.session_token);
  if (!live) { app.user = null; showLogin(true); return; }
  app.user = live;
  const view = document.getElementById("view");
  const mod = VIEWS[r.page] && NAV.some((n) => n[0] === r.page) ? VIEWS[r.page] : null;
  app.params = r.params; view.innerHTML = "";
  if (!mod) { navigate("dashboard"); return; }
  if (!auth.canView(app.user, r.page)) { view.innerHTML = `<div class="card">${notice(t("permission_denied"), "error", "lock")}</div>`; setActiveNav(r.page); return; }
  try { mod.render(view, app); } catch (e) { console.error(e); view.innerHTML = `<div class="card">${notice(`${t("error")} ${esc(e.message || e)}`, "error", "circle-alert")}</div>`; }
  setActiveNav(r.page); closeMenu();
  window.scrollTo({ top: 0 });
}
function closeMenu() { document.getElementById("app").classList.remove("menu-open"); }

// ------------------------------------------------------------ events
function bindShell() {
  const appEl = document.getElementById("app");
  document.addEventListener("click", (e) => {
    const nav = e.target.closest("[data-nav]"); if (nav) { navigate(nav.dataset.nav); return; }
    if (e.target.closest("[data-menu]") || e.target.closest("#menuBtn")) { appEl.classList.toggle("menu-open"); return; }
    if (e.target.closest("#backdrop")) { closeMenu(); return; }
    if (!e.target.closest("#searchWrap")) document.getElementById("searchResults").hidden = true;
  });
  document.getElementById("collapseBtn").addEventListener("click", () => { appEl.classList.toggle("sidebar-collapsed"); try { localStorage.setItem(`${CFG.storageKey || "cml"}:collapsed`, appEl.classList.contains("sidebar-collapsed") ? "1" : "0"); } catch { /* ignore */ } });
  document.querySelectorAll("#langSwitch button").forEach((b) => b.addEventListener("click", () => app.setLanguage(b.dataset.lang)));
  const search = document.getElementById("globalSearch"); const results = document.getElementById("searchResults");
  search.addEventListener("input", () => {
    const q = search.value.trim(); if (!q) { results.hidden = true; return; }
    const r = repo.globalSearch(q); const u = app.user;
    const col = (title, items, fn) => `<div><h4>${esc(title)}</h4>${items.length ? items.map(fn).join("") : `<div class="faint">-</div>`}</div>`;
    const canRx = auth.canView(u, "prescriptions"), canBill = auth.canView(u, "billing");
    const any = r.patients.length || (canBill && r.invoices.length) || (canRx && r.prescriptions.length);
    results.innerHTML = any ?
      col(t("patients"), r.patients, (p) => `<button type="button" data-go="patients" data-id="${p.id}">${esc(p.full_name)} <span class="faint num">${esc(p.patient_code)} · ${esc(p.phone)}</span></button>`) +
      (canBill ? col(t("invoices"), r.invoices, (i) => `<button type="button" data-go="billing" data-id="${i.id}"><span class="num">${esc(i.invoice_no)}</span> <span class="faint">${esc(i.patient)} · ${money(i.total)}</span></button>`) : "") +
      (canRx ? col(t("prescriptions"), r.prescriptions, (x) => `<button type="button" data-go="prescriptions" data-id="${x.id}"><span class="num">${esc(x.rx_number)}</span> <span class="faint">${esc(x.patient)}</span></button>`) : "")
      : `<div class="empty-msg">${esc(t("no_results"))}</div>`;
    results.hidden = false;
  });
  search.addEventListener("focus", () => { if (search.value.trim()) results.hidden = false; });
  results.addEventListener("click", (e) => { const b = e.target.closest("[data-go]"); if (!b) return; results.hidden = true; search.value = ""; navigate(b.dataset.go, { id: b.dataset.id }); });
  // idle timeout: check the session every minute and on activity
  setInterval(() => { if (app.user && !auth.validateSession(app.user.session_token, false)) { app.user = null; showLogin(true); } }, 60000);
  let lastTouch = 0;
  document.addEventListener("pointerdown", () => { const n = Date.now(); if (app.user && n - lastTouch > 30000) { lastTouch = n; if (!auth.validateSession(app.user.session_token)) { app.user = null; showLogin(true); } } }, true);
  store.subscribe(() => { if (app.user && !document.getElementById("app").hidden) { const s = store.settings; const el = document.querySelector("#brand .name"); if (el && el.textContent !== s.clinic_name) renderShell(); } });
}

// ------------------------------------------------------------ boot
async function boot() {
  await store.load();
  if (needsSeed() && F.demoData !== false) { try { await seedDemo(); } catch (e) { console.error("Seeding failed", e); } }
  let lang = null; try { lang = localStorage.getItem(`${CFG.storageKey || "cml"}:lang`); } catch { /* ignore */ }
  setLang(lang || store.settings.default_language || (CFG.clinic || {}).language || "en");
  applyTheme();
  bindShell();
  auth.cleanupSessions();
  try { if (localStorage.getItem(`${CFG.storageKey || "cml"}:collapsed`) === "1") document.getElementById("app").classList.add("sidebar-collapsed"); } catch { /* ignore */ }
  onRoute(route);
  document.getElementById("loading").remove();
  const user = auth.validateSession(auth.storedToken());
  if (user) enterApp(user); else showLogin(false);
  // Offline cache only on a real host; on localhost (development) make sure no stale worker is active.
  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    const dev = ["localhost", "127.0.0.1"].includes(location.hostname);
    if (dev) navigator.serviceWorker.getRegistrations().then((rs) => rs.forEach((r) => r.unregister()));
    else navigator.serviceWorker.register("sw.js").catch(() => { /* offline support unavailable */ });
  }
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); app.installPrompt = e; });
}
window.cml = app;
boot().catch((e) => { console.error(e); const l = document.getElementById("loading"); if (l) l.innerHTML = `<div class="card">${notice(String(e.message || e), "error", "circle-alert")}</div>`; });
