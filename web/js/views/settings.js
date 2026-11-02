/* Settings: clinic profile and logo, doctors and schedules, users, services, prints, backup / restore, audit log and
   security (modules/settings.py). Administrators see everything; other roles can only change their own password. */
import { freshView, esc, money, fmtDate, fmtDateTime, pageHead, section, kpiRow, listRow, emptyState, statusBadge, badge, avatar, btn, iconBtn, field, input, select, textarea, dateInput, check, notice, table, kv, tabsBar, bindTabs, openModal, closeModal, confirmDialog, toast, formValues, showFormError, readImageFile, toCSV, downloadFile, run, errorMessage, logoSrc, hasLogo, t, statusLabel, icon, getLang } from "../ui.js";
import { store, todayISO, WEEKDAYS, ROLES, SESSION_HOURS, IDLE_TIMEOUT_MIN, MAX_FAILED_LOGINS, LOCKOUT_MINUTES, validTime } from "../store.js";
import { LANGS } from "../i18n.js";
import { seedDemo } from "../seed.js";

const CFG = window.CML_CONFIG || {};

function clinicTab(app, s) {
  return `<form class="card mb" id="clinicForm">${section(t("clinic_profile"), "hospital")}<div class="form-grid-3">
    ${field(t("clinic_name"), input("clinic_name", s.clinic_name, 'maxlength="80" required'), { required: true })}${field(t("tagline"), input("clinic_tagline", s.clinic_tagline, 'maxlength="100"'), { cls: "span-2" })}
    ${field(t("address"), input("clinic_address", s.clinic_address, 'maxlength="200"'), { cls: "span-3" })}
    ${field(t("phone"), input("clinic_phone", s.clinic_phone, 'maxlength="40" class="num"'))}${field(t("email"), input("clinic_email", s.clinic_email, 'maxlength="80" type="email"'))}${field(t("currency_symbol"), input("currency_symbol", s.currency_symbol, 'maxlength="6"'))}
    ${field(t("default_fee"), input("default_consultation_fee", s.default_consultation_fee, 'type="number" min="0" step="1" class="num"'))}${field(t("appointment_duration"), input("appointment_duration", s.appointment_duration, 'type="number" min="5" max="120" step="5" class="num"'))}${field(t("token_prefix"), input("token_prefix", s.token_prefix, 'maxlength="3"'))}
    ${field(t("default_language"), select("default_language", Object.entries(LANGS), s.default_language))}${field(t("follow_up_window"), input("follow_up_window_days", s.follow_up_window_days, 'type="number" min="1" max="60" class="num"'))}${field(t("max_discount_no_auth"), input("max_discount_without_auth", s.max_discount_without_auth, 'type="number" min="0" step="1" class="num"'))}
    </div><div class="form-foot">${btn(t("save"), { ic: "save", cls: "primary", type: "submit" })}</div></form>
    <div class="card">${section(t("clinic_logo"), "image")}<div class="hero">${hasLogo() ? `<img src="${logoSrc()}" alt="" style="width:96px;height:96px;object-fit:contain;border-radius:12px;border:1px solid var(--line);background:#fff"/>` : `<div class="empty-ic">${icon("image", 24)}</div>`}<div class="t"><p>${esc(t("logo_hint"))}</p><div class="btn-group mt"><label class="btn primary">${icon("upload", 16)}<span>${esc(t("upload_logo"))}</span><input type="file" id="logoFile" accept="image/png,image/jpeg,image/webp" hidden/></label>${hasLogo() ? btn(t("remove_logo"), { ic: "trash", cls: "danger", attrs: 'id="logoRemove"' }) : ""}</div></div></div></div>`;
}
function bindClinic(root, app) {
  const form = root.querySelector("#clinicForm"); form.addEventListener("submit", (e) => { e.preventDefault(); const v = formValues(form); if (v.clinic_name.length < 2) { showFormError(form, new Error(t("err.clinic_name_required"))); return; } v.currency_symbol = v.currency_symbol || "Rs."; store.setSettings(v); store.audit("update", "settings", "clinic", null, app.user); toast(t("saved")); app.rerenderShell(); app.refresh(); });
  root.querySelector("#logoFile").addEventListener("change", async (e) => { const f = e.target.files[0]; if (!f) return; try { const data = await readImageFile(f, 512); store.setSettings({ clinic_logo: data }); store.audit("update", "settings", "clinic_logo", null, app.user); toast(t("saved")); app.rerenderShell(); app.refresh(); } catch (err) { toast(errorMessage(err), "error"); } });
  const rm = root.querySelector("#logoRemove"); if (rm) rm.addEventListener("click", () => { store.setSettings({ clinic_logo: "" }); app.rerenderShell(); app.refresh(); });
}

function doctorsTab(app, st) {
  const { repo } = app; const docs = repo.doctors(false);
  if (st.doc === undefined) st.doc = docs.length ? docs[0].id : 0; if (st.doc && !docs.some((d) => d.id === st.doc)) st.doc = 0;
  const doc = st.doc ? repo.doctor(st.doc) : null; st.docTab = st.docTab || "profile";
  const list = `<div class="list">${btn(t("add_doctor"), { ic: "plus", cls: `sm block ${st.doc ? "" : "primary"}`, attrs: 'data-doc="0"' })}${docs.map((d) => listRow({ title: esc(d.name) + (d.is_active ? "" : ` ${statusBadge("Inactive")}`), sub: esc(d.specialization), lead: avatar(d.name, 36, d.photo_data), attrs: `class="row clickable ${d.id === st.doc ? "strong" : ""}" data-doc="${d.id}"` })).join("")}</div>`;
  const profile = (d) => `<form id="docForm"><div class="form-grid-3">${field(t("name"), input("name", d.name || "", 'maxlength="100" placeholder="Dr. ..."'), { required: true, cls: "span-2" })}${field(t("specialization"), input("specialization", d.specialization || "", 'maxlength="100"'))}
    ${field(t("qualification"), input("qualification", d.qualification || "", 'maxlength="150" placeholder="MBBS, FCPS"'))}${field(t("registration_no"), input("registration_no", d.registration_no || "", 'maxlength="60"'), { cls: "span-2" })}
    ${field(t("phone"), input("phone", d.phone || "", 'maxlength="30" class="num"'))}${field(t("email"), input("email", d.email || "", 'maxlength="100"'))}${field(t("consultation_fee"), input("consultation_fee", d.consultation_fee ?? 0, 'type="number" min="0" step="1" class="num"'))}
    ${d.id ? `<div class="field"><label>&nbsp;</label>${check("is_active", t("active"), !!d.is_active)}</div>` : ""}</div><div class="form-foot">${btn(t("save"), { ic: "save", cls: "primary", type: "submit" })}</div></form>`;
  let pane = "";
  if (!doc) pane = profile({});
  else if (st.docTab === "profile") pane = profile(doc);
  else if (st.docTab === "photo") pane = `<div class="hero">${avatar(doc.name, 96, doc.photo_data)}<div class="t"><p>${esc(t("logo_hint"))}</p><div class="btn-group mt"><label class="btn primary">${icon("upload", 16)}<span>${esc(t("upload_photo"))}</span><input type="file" id="docPhoto" accept="image/png,image/jpeg,image/webp" hidden/></label>${doc.photo_data ? btn(t("remove_photo"), { ic: "trash", cls: "danger", attrs: 'id="docPhotoRm"' }) : ""}</div></div></div>`;
  else if (st.docTab === "hours") pane = `<form id="schedForm"><div class="table-wrap"><table class="tbl"><thead><tr><th>${esc(t("day"))}</th><th>${esc(t("working"))}</th><th>${esc(t("start_time"))}</th><th>${esc(t("end_time"))}</th><th>${esc(t("break_start"))}</th><th>${esc(t("break_end"))}</th></tr></thead><tbody>
    ${repo.doctorSchedule(doc.id).map((r) => `<tr><td><b>${esc(statusLabel(WEEKDAYS[r.weekday]))}</b></td><td><input type="checkbox" name="on_${r.weekday}" ${r.is_working ? "checked" : ""} style="width:18px;height:18px;accent-color:var(--primary)"/></td><td><input class="input num" name="s_${r.weekday}" value="${esc(r.start_time)}" placeholder="09:00" style="min-width:90px"/></td><td><input class="input num" name="e_${r.weekday}" value="${esc(r.end_time)}" placeholder="17:00" style="min-width:90px"/></td><td><input class="input num" name="bs_${r.weekday}" value="${esc(r.break_start || "")}" placeholder="13:00" style="min-width:90px"/></td><td><input class="input num" name="be_${r.weekday}" value="${esc(r.break_end || "")}" placeholder="14:00" style="min-width:90px"/></td></tr>`).join("")}</tbody></table></div>
    <div class="faint mt">${esc(t("hours_hint"))}</div><div class="form-foot">${btn(t("save"), { ic: "save", cls: "primary", type: "submit" })}</div></form>`;
  else { const hols = repo.holidays(doc.id, todayISO()); pane = `<form id="holForm" class="toolbar mb"><div class="field narrow">${dateInput("holiday_date", todayISO(), `min="${todayISO()}"`)}</div><div class="field grow">${input("reason", "", `maxlength="100" placeholder="${esc(t("reason"))}"`)}</div>${btn(t("add_holiday"), { ic: "plus", cls: "primary", type: "submit" })}</form>
    ${hols.length ? `<div class="list">${hols.map((h) => listRow({ title: fmtDate(h.holiday_date, true), sub: esc(h.reason || "-"), ic: "calendar-x", tone: "danger", value: iconBtn("trash", t("remove"), `data-hol="${h.id}"`, "danger") })).join("")}</div>` : emptyState(t("no_holidays"), "", "calendar")}`; }
  return `<div class="grid grid-1-2"><div class="card">${section(t("doctors"), "stethoscope", docs.length)}${list}</div><div class="card">${doc ? `<div class="hero mb">${avatar(doc.name, 56, doc.photo_data)}<div class="t"><h2>${esc(doc.name)}</h2><p>${esc(doc.specialization)} · ${esc(doc.qualification)} · <span class="num">${esc(doc.registration_no)}</span></p></div></div>${tabsBar("docTab", [["profile", t("profile")], ["photo", t("photo")], ["hours", t("working_hours")], ["holidays", t("holidays")]], st.docTab)}` : section(t("add_doctor"), "user-plus")}${pane}</div></div>`;
}
function bindDoctors(root, app, st) {
  const { repo } = app;
  root.querySelectorAll("[data-doc]").forEach((el) => el.addEventListener("click", () => { st.doc = Number(el.dataset.doc); st.docTab = "profile"; app.refresh(); }));
  bindTabs(root, st, "docTab", () => app.refresh());
  const df = root.querySelector("#docForm"); if (df) df.addEventListener("submit", (e) => { e.preventDefault(); const v = formValues(df); try { const id = repo.saveDoctor({ ...v, photo_data: st.doc ? (repo.doctor(st.doc) || {}).photo_data : "", is_active: st.doc ? v.is_active : true }, st.doc || null, app.user); st.doc = id; toast(t("saved")); app.refresh(); } catch (err) { showFormError(df, err); } });
  const ph = root.querySelector("#docPhoto"); if (ph) ph.addEventListener("change", async (e) => { const f = e.target.files[0]; if (!f) return; try { const data = await readImageFile(f, 256); const d = repo.doctor(st.doc); repo.saveDoctor({ ...d, photo_data: data }, st.doc, app.user); toast(t("saved")); app.refresh(); } catch (err) { toast(errorMessage(err), "error"); } });
  const prm = root.querySelector("#docPhotoRm"); if (prm) prm.addEventListener("click", () => { const d = repo.doctor(st.doc); repo.saveDoctor({ ...d, photo_data: "" }, st.doc, app.user); app.refresh(); });
  const sf = root.querySelector("#schedForm"); if (sf) sf.addEventListener("submit", (e) => { e.preventDefault(); const v = formValues(sf); const rows = WEEKDAYS.map((_, wd) => ({ weekday: wd, is_working: v[`on_${wd}`], start_time: v[`s_${wd}`], end_time: v[`e_${wd}`], break_start: v[`bs_${wd}`], break_end: v[`be_${wd}`] })); try { for (const r of rows) if (r.is_working && (!validTime(r.start_time) || !validTime(r.end_time) || (r.break_start && !validTime(r.break_start)) || (r.break_end && !validTime(r.break_end)))) throw new Error(`${t("err.invalid_time")} (${statusLabel(WEEKDAYS[r.weekday])})`); repo.saveSchedule(st.doc, rows, app.user); toast(t("saved")); app.refresh(); } catch (err) { showFormError(sf, err); } });
  const hf = root.querySelector("#holForm"); if (hf) hf.addEventListener("submit", (e) => { e.preventDefault(); const v = formValues(hf); run(() => repo.addHoliday(st.doc, v.holiday_date, v.reason, app.user), t("saved"), () => app.refresh()); });
  root.querySelectorAll("[data-hol]").forEach((b) => b.addEventListener("click", () => { repo.removeHoliday(Number(b.dataset.hol), app.user); app.refresh(); }));
}

function usersTab(app, st) {
  const { repo } = app; const users = repo.usersList(); const docs = repo.doctorOptions();
  if (!st.user || !users.some((u) => u.id === st.user)) st.user = users.length ? users[0].id : null;
  const target = st.user ? app.auth.getUser(st.user) : null;
  return `<div class="card mb">${section(t("users"), "users", users.length)}${table({ columns: [{ label: t("username"), cls: "num" }, { label: t("name") }, { label: t("role") }, { label: t("doctor") }, { label: t("status") }, { label: t("last_login") }], rows: users.map((u) => ({ cells: [esc(u.username), esc(u.full_name), esc(t(u.role)), esc(u.doctor || "-"), statusBadge(u.is_active ? "Active" : "Inactive"), u.last_login ? fmtDateTime(u.last_login) : "-"] })) })}</div>
  <div class="grid grid-2"><form class="card" id="userNew">${section(t("add_user"), "user-plus")}<div class="stack">${field(t("username"), input("username", "", 'maxlength="40" autocomplete="off" autocapitalize="none"'), { required: true })}${field(t("full_name"), input("full_name", "", 'maxlength="100"'), { required: true })}${field(t("role"), select("role", ROLES.map((r) => [r, t(r)]), "receptionist"))}${field(t("linked_doctor"), select("doctor_id", [[0, "-"], ...docs], 0))}${field(t("temporary_password"), input("password", "", 'type="password" autocomplete="new-password"'), { required: true, help: t("password_policy") })}${btn(t("create_user"), { ic: "user-plus", cls: "primary", type: "submit" })}</div></form>
  <div class="card" id="userMng">${section(t("manage_user"), "key-round")}${target ? `<div class="stack">${field(t("user"), select("mng_user", users.map((u) => [u.id, `${u.username} (${u.full_name})`]), st.user))}${field(t("full_name"), input("mng_name", target.full_name, 'maxlength="100"'))}${field(t("role"), select("mng_role", ROLES.map((r) => [r, t(r)]), target.role))}${field(t("linked_doctor"), select("mng_doc", [[0, "-"], ...docs], target.doctor_id || 0))}
    <div class="btn-group">${btn(t("save"), { ic: "save", cls: "primary", attrs: 'id="mngSave"' })}${target.id !== app.user.id ? btn(target.is_active ? t("deactivate") : t("activate"), { ic: target.is_active ? "circle-x" : "circle-check", attrs: 'id="mngToggle"' }) : ""}${btn(t("sign_out_everywhere"), { ic: "log-out", attrs: 'id="mngRevoke"' })}</div>
    ${field(t("reset_password"), input("mng_pw", "", 'type="password" autocomplete="new-password"'), { help: t("password_policy") })}${btn(t("set_password"), { ic: "key-round", attrs: 'id="mngPw"' })}</div>` : emptyState(t("no_data"), "", "users")}</div></div>`;
}
function bindUsers(root, app, st) {
  const { repo, auth } = app;
  const nf = root.querySelector("#userNew"); nf.addEventListener("submit", async (e) => { e.preventDefault(); const v = formValues(nf); try { if (v.role === "doctor" && !Number(v.doctor_id)) throw new Error(t("err.select_doctor_for_user")); await auth.createUser(v.username, v.password, v.full_name, v.role, Number(v.doctor_id) || null, app.user); toast(t("saved")); app.refresh(); } catch (err) { showFormError(nf, err); } });
  const mng = root.querySelector("#userMng"); const sel = mng.querySelector('[name="mng_user"]'); if (!sel) return;
  sel.addEventListener("change", () => { st.user = Number(sel.value); app.refresh(); });
  mng.querySelector("#mngSave").addEventListener("click", () => run(() => repo.updateUser(st.user, mng.querySelector('[name="mng_name"]').value, mng.querySelector('[name="mng_role"]').value, Number(mng.querySelector('[name="mng_doc"]').value) || null, app.user), t("saved"), () => app.refresh()));
  const tg = mng.querySelector("#mngToggle"); if (tg) tg.addEventListener("click", () => { const u = auth.getUser(st.user); repo.setUserActive(st.user, !u.is_active, app.user); app.refresh(); });
  mng.querySelector("#mngRevoke").addEventListener("click", () => { auth.revokeAllSessions(st.user, app.user, st.user === app.user.id ? app.user.session_token : null); toast(t("sessions_revoked")); });
  mng.querySelector("#mngPw").addEventListener("click", async () => { const pw = mng.querySelector('[name="mng_pw"]').value; try { await auth.setPassword(st.user, pw, app.user); toast(t("password_updated")); mng.querySelector('[name="mng_pw"]').value = ""; } catch (err) { toast(errorMessage(err), "error"); } });
}

function servicesTab(app) {
  const svcs = app.repo.services(false);
  return `<div class="grid grid-2-1"><div class="card">${section(t("services"), "briefcase-medical", svcs.length)}${svcs.length ? `<div class="list">${svcs.map((s) => `<div class="row"><div class="body"><div class="title">${esc(s.name)}${s.is_active ? "" : ` ${statusBadge("Inactive")}`}</div></div><input class="input num" type="number" min="0" step="1" value="${s.price}" data-price="${s.id}" style="width:120px"/><div class="actions">${iconBtn("save", t("save"), `data-svc-save="${s.id}"`)}${iconBtn(s.is_active ? "circle-x" : "circle-check", s.is_active ? t("disable") : t("enable"), `data-svc-toggle="${s.id}"`)}</div></div>`).join("")}</div>` : emptyState(t("no_data"), "", "briefcase-medical")}</div>
  <form class="card" id="svcNew">${section(t("add_service"), "plus")}<div class="stack">${field(t("service_name"), input("name", "", 'maxlength="100"'), { required: true })}${field(`${t("price")} (${esc(app.settings.currency_symbol)})`, input("price", 0, 'type="number" min="0" step="1" class="num"'))}${btn(t("add"), { ic: "plus", cls: "primary", type: "submit" })}</div></form></div>`;
}
function bindServices(root, app) {
  const { repo } = app;
  root.querySelector("#svcNew").addEventListener("submit", (e) => { e.preventDefault(); const f = e.target; const v = formValues(f); try { repo.saveService(v.name, v.price, null, true, app.user); toast(t("saved")); app.refresh(); } catch (err) { showFormError(f, err); } });
  root.addEventListener("click", (e) => {
    const sv = e.target.closest("[data-svc-save]"); if (sv) { const id = Number(sv.dataset.svcSave); const s = repo.services(false).find((x) => x.id === id); run(() => repo.saveService(s.name, root.querySelector(`[data-price="${id}"]`).value, id, !!s.is_active, app.user), t("saved"), () => app.refresh()); }
    const tg = e.target.closest("[data-svc-toggle]"); if (tg) { const id = Number(tg.dataset.svcToggle); const s = repo.services(false).find((x) => x.id === id); run(() => repo.saveService(s.name, s.price, id, !s.is_active, app.user), t("saved"), () => app.refresh()); }
  });
}

function printsTab(app, s) {
  return `<form class="card" id="printsForm">${section(t("prints"), "printer")}<div class="form-grid-3">${field(t("paper_size"), select("paper_size", ["A5", "A4", "A6"], s.paper_size))}<div class="field"><label>&nbsp;</label>${check("rx_show_diagnosis", t("print_diagnosis"), s.rx_show_diagnosis !== "0")}</div><div class="field"><label>&nbsp;</label>${check("show_urdu_on_prints", t("offer_urdu"), s.show_urdu_on_prints !== "0")}</div></div>
  <div class="form-grid mt">${field(t("rx_footer_en"), textarea("rx_footer_en", s.rx_footer_en, 'rows="2"'))}${field(t("rx_footer_ur"), textarea("rx_footer_ur", s.rx_footer_ur, 'rows="2" dir="rtl" style="font-family:var(--font-ur)"'))}${field(t("receipt_footer_en"), textarea("receipt_footer_en", s.receipt_footer_en, 'rows="2"'))}${field(t("receipt_footer_ur"), textarea("receipt_footer_ur", s.receipt_footer_ur, 'rows="2" dir="rtl" style="font-family:var(--font-ur)"'))}</div>
  <div class="form-grid mt">${field(t("low_stock_threshold"), input("low_stock_threshold", s.low_stock_threshold, 'type="number" min="0" class="num"'))}${field(t("expiry_warning_days"), input("expiry_warning_days", s.expiry_warning_days, 'type="number" min="7" max="365" class="num"'))}</div>
  <div class="form-foot">${btn(t("save"), { ic: "save", cls: "primary", type: "submit" })}</div></form>`;
}
function bindPrints(root, app) {
  const f = root.querySelector("#printsForm"); f.addEventListener("submit", (e) => { e.preventDefault(); const v = formValues(f); store.setSettings({ ...v, rx_show_diagnosis: v.rx_show_diagnosis ? "1" : "0", show_urdu_on_prints: v.show_urdu_on_prints ? "1" : "0" }); store.audit("update", "settings", "prints", null, app.user); toast(t("saved")); app.refresh(); });
}

function backupTab(app) {
  const c = store.tableCounts(); const s = app.settings;
  return `<div class="grid grid-2"><div class="stack"><div class="card">${section(t("backup"), "database")}<p class="muted">${esc(t("backup_hint"))}</p>${kv([[t("patients"), c.patients], [t("appointments"), c.appointments], [t("invoices"), c.invoices], [t("audit_log"), c.audit_log]])}<div class="mt">${btn(t("download_backup"), { ic: "download", cls: "primary", attrs: 'id="bkDownload"' })}</div></div>
    <div class="card">${section(t("restore_backup"), "upload")}<p class="muted">${esc(t("restore_hint"))}</p><div class="stack"><label class="file-drop">${icon("file-json", 20)}<span id="bkName" class="muted">JSON</span><input type="file" id="bkFile" accept="application/json,.json"/></label>${check("ok", t("restore_confirm"), false, 'id="bkOk"')}${btn(t("restore_backup"), { ic: "upload", cls: "danger", attrs: 'id="bkRestore" disabled' })}</div></div></div>
  <div class="stack"><div class="card">${section(t("demo_mode"), "sparkles")}${kv([[t("demo_mode"), s.demo_mode === "1" ? t("yes") : t("no")], [t("seeded_at"), s.seeded_at ? fmtDateTime(s.seeded_at) : "-"]])}<p class="muted mt">${esc(t("reset_demo_hint"))}</p>${btn(t("reset_demo"), { ic: "rotate-ccw", cls: "danger", attrs: 'id="bkReset"' })}</div>${notice(t("data_notice"), "warning", "triangle-alert")}</div></div>`;
}
function bindBackup(root, app) {
  root.querySelector("#bkDownload").addEventListener("click", () => { store.audit("backup", "database", "json", null, app.user); store.commit(); downloadFile(`clinic_backup_${todayISO()}.json`, store.exportJSON(), "application/json"); });
  const file = root.querySelector("#bkFile"); const ok = root.querySelector("#bkOk"); const rb = root.querySelector("#bkRestore"); let text = null;
  const upd = () => { rb.disabled = !(text && ok.checked); };
  file.addEventListener("change", async () => { const f = file.files[0]; text = f ? await f.text() : null; root.querySelector("#bkName").textContent = f ? `${f.name} (${Math.round(f.size / 1024)} KB)` : "JSON"; upd(); });
  ok.addEventListener("change", upd);
  rb.addEventListener("click", async () => { if (!(await confirmDialog({ title: t("restore_backup"), body: t("restore_hint") }))) return; try { await store.importJSON(text); store.audit("restore", "database", "json", null, app.user); await store.flush(); toast(t("restore_done")); app.signOut(false); } catch (err) { toast(t("err.restore_failed", { msg: errorMessage(err) }), "error"); } });
  root.querySelector("#bkReset").addEventListener("click", async () => { if (!(await confirmDialog({ title: t("reset_demo"), body: t("reset_demo_hint") }))) return; await store.reset(); await seedDemo(); toast(t("saved")); app.signOut(false); });
}

function auditTab(app, st) {
  const { repo } = app; st.aq = st.aq || ""; st.aent = st.aent || ""; st.alimit = st.alimit || 100;
  const rows = repo.auditRecent(Number(st.alimit), st.aent || null, st.aq);
  return `<div class="card"><div class="toolbar mb"><div class="field grow">${input("aq", st.aq, 'placeholder="username / action / details" autocomplete="off"')}</div><div class="field narrow">${select("aent", [["", t("all")], ...repo.auditEntities().map((e) => [e, e])], st.aent)}</div><div class="field narrow">${select("alimit", [100, 250, 500, 1000], st.alimit)}</div>${btn(t("download_csv"), { ic: "file-spreadsheet", attrs: 'id="auditCsv"' })}</div>
    ${rows.length ? table({ columns: [{ label: t("time") }, { label: t("user") }, { label: t("action") }, { label: t("entity") }, { label: "ID", cls: "num" }, { label: t("details") }], rows: rows.map((r) => ({ cells: [fmtDateTime(r.created_at), esc(r.username), esc(r.action), esc(r.entity), esc(r.entity_id || ""), `<span class="faint">${esc(r.details)}</span>`] })) }) : emptyState(t("no_data"), "", "shield")}</div>`;
}
function bindAudit(root, app, st) {
  const qi = root.querySelector('[name="aq"]'); let timer; qi.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { st.aq = qi.value; const pos = qi.selectionStart; app.refresh(); const n = document.querySelector('#view [name="aq"]'); n.focus(); n.setSelectionRange(pos, pos); }, 250); });
  for (const n of ["aent", "alimit"]) root.querySelector(`[name="${n}"]`).addEventListener("change", (e) => { st[n] = e.target.value; app.refresh(); });
  root.querySelector("#auditCsv").addEventListener("click", () => downloadFile(`audit_${todayISO()}.csv`, toCSV(app.repo.auditRecent(Number(st.alimit), st.aent || null, st.aq), ["created_at", "username", "action", "entity", "entity_id", "details"]), "text/csv"));
}

function securityTab(app) {
  const u = app.user; const v = CFG.vendor || {}; const lic = CFG.licence || {};
  return `<div class="grid grid-2"><form class="card" id="pwForm">${section(t("change_password"), "lock")}<div class="stack">${field(t("current_password"), input("current", "", 'type="password" autocomplete="current-password"'))}${field(t("new_password"), input("new", "", 'type="password" autocomplete="new-password"'), { help: t("password_policy") })}${field(t("repeat_password"), input("repeat", "", 'type="password" autocomplete="new-password"'))}${btn(t("update_password"), { ic: "key-round", cls: "primary", type: "submit" })}</div></form>
  <div class="stack"><div class="card">${section(t("session_policy"), "shield-check")}${kv([[t("signed_in_as"), `${u.full_name} (${u.username})`], [t("role"), t(u.role)], [t("idle_timeout"), `${IDLE_TIMEOUT_MIN} ${t("minutes")}`], [t("session_lifetime"), `${SESSION_HOURS} ${t("hours")}`], [t("lockout"), t("failed_attempts", { n: MAX_FAILED_LOGINS, m: LOCKOUT_MINUTES })], [t("password_hashing"), "PBKDF2-SHA256 (Web Crypto)"]])}<div class="mt">${btn(t("sign_out_others"), { ic: "log-out", cls: "sm", attrs: 'id="secRevoke"' })}</div></div>
  <div class="card">${section(t("about"), "info")}${kv([[t("version"), `${CFG.productName || "Clinic Management Lite"} ${CFG.version || ""}`], ...(v.name ? [["Vendor", `${v.name}${v.phone ? ` · ${v.phone}` : ""}${v.website ? ` · ${v.website}` : ""}`]] : []), ...(lic.plan ? [["Licence", `${lic.plan}${lic.licensedTo ? ` · ${lic.licensedTo}` : ""}${lic.expires ? ` · ${lic.expires}` : ""}`]] : []), [t("storage"), `IndexedDB · ${Math.round(store.exportJSON().length / 1024)} KB`], [t("language"), LANGS[getLang()]]])}${app.installPrompt ? `<div class="mt">${btn(t("install_app"), { ic: "monitor-smartphone", cls: "sm", attrs: 'id="installBtn"' })}</div>` : ""}</div>
  ${notice(t("prototype_notice"), "warning", "triangle-alert")}</div></div>`;
}
function bindSecurity(root, app) {
  const f = root.querySelector("#pwForm"); f.addEventListener("submit", async (e) => { e.preventDefault(); const v = formValues(f); try { if (v.new !== v.repeat) throw new Error(t("err.passwords_mismatch")); await app.auth.changeOwnPassword(app.user, v.current, v.new); toast(t("password_changed")); f.reset(); } catch (err) { showFormError(f, err); } });
  root.querySelector("#secRevoke").addEventListener("click", () => { app.auth.revokeAllSessions(app.user.id, app.user, app.user.session_token); toast(t("sessions_revoked")); });
  const ib = root.querySelector("#installBtn"); if (ib) ib.addEventListener("click", () => { app.installPrompt.prompt(); });
}

export function render(_root, app) {
  const root = freshView(); const s = app.settings;
  const st = app.ui.settings || (app.ui.settings = { tab: "clinic" });
  if (!app.isAdmin()) { root.innerHTML = `${pageHead(t("settings"), `${CFG.productName || ""} v${CFG.version || ""}`, "", "settings")}${notice(t("read_only"), "info", "info")}<div class="mb"></div>${securityTab(app)}`; bindSecurity(root, app); return; }
  const tabs = [["clinic", t("clinic_profile")], ["doctors", t("doctors")], ["users", t("users")], ["services", t("services")], ["prints", t("prints")], ["backup", t("backup")], ["audit", t("audit_log")], ["security", t("security")]];
  const panes = { clinic: () => clinicTab(app, s), doctors: () => doctorsTab(app, st), users: () => usersTab(app, st), services: () => servicesTab(app), prints: () => printsTab(app, s), backup: () => backupTab(app), audit: () => auditTab(app, st), security: () => securityTab(app) };
  root.innerHTML = `${pageHead(t("settings"), `${CFG.productName || ""} v${CFG.version || ""}`, "", "settings")}${tabsBar("tab", tabs, st.tab)}${panes[st.tab]()}`;
  bindTabs(root, st, "tab", () => app.refresh());
  ({ clinic: bindClinic, doctors: bindDoctors, users: bindUsers, services: bindServices, prints: bindPrints, backup: bindBackup, audit: bindAudit, security: bindSecurity })[st.tab](root, app, st);
}
