/* Patients: registration with duplicate detection, search, profile with full history, edit, deactivate, CSV export
   (modules/patients.py). */
import { freshView, esc, money, fmtDate, fmtTime, fmtDateTime, pageHead, section, kpiRow, listRow, emptyState, statusBadge, badge, avatar, btn, iconBtn, field, input, select, textarea, dateInput, check, table, paginate, pager, bindPager, tabsBar, bindTabs, kv, notice, openModal, closeModal, confirmDialog, toast, formValues, showFormError, toCSV, downloadFile, run, errorMessage, t, statusLabel, icon } from "../ui.js";
import { GENDERS, BLOOD_GROUPS, ageFromDob, todayISO } from "../store.js";
import { prescriptionItems } from "../repo.js";

const FORM_FIELDS = ["full_name", "phone", "gender", "dob", "blood_group", "address", "emergency_contact", "allergies", "medical_history"];

/** Registration / edit form markup. */
export function patientFormHTML(init = {}, compact = false) {
  return `<div class="form-grid-3">
    ${field(t("full_name"), input("full_name", init.full_name || "", 'maxlength="80" required'), { required: true, cls: compact ? "" : "span-2" })}
    ${field(t("phone"), input("phone", init.phone || "", 'maxlength="15" placeholder="03001234567" inputmode="tel" class="num"'), { required: true })}
    ${field(t("gender"), select("gender", GENDERS.map((g) => [g, t(g.toLowerCase())]), init.gender || "Male"), { required: true })}
    ${field(t("dob"), dateInput("dob", init.dob || "", `max="${todayISO()}" min="1900-01-01"`), { optional: true })}
    ${field(t("blood_group"), select("blood_group", BLOOD_GROUPS.map((b) => [b, b || "-"]), init.blood_group || ""))}
    ${field(t("emergency_contact"), input("emergency_contact", init.emergency_contact || "", 'maxlength="120" class="num"'), { optional: true })}
    ${field(t("address"), input("address", init.address || "", 'maxlength="300"'), { cls: "span-2" })}
    ${field(t("allergies"), textarea("allergies", init.allergies || "", 'maxlength="1000" rows="2"'), { optional: true, cls: "span-2" })}
    ${field(t("medical_history"), textarea("medical_history", init.medical_history || "", 'maxlength="4000" rows="2"'), { optional: true })}
  </div><div class="faint mt">${esc(t("required_fields"))}</div>`;
}
const dupList = (dups) => `<div class="list">${dups.map((d) => listRow({ title: `${esc(d.full_name)} <span class="faint num">${esc(d.patient_code)}</span>`, sub: `<span class="num">${esc(d.phone)}</span> · ${t("dob")}: ${fmtDate(d.dob)}`, avatarName: d.full_name, attrs: `class="row clickable" data-open-patient="${d.id}"` })).join("")}</div>`;

/** Registration dialog with duplicate detection. onSaved(patient) is called after a successful save. */
export function openRegisterDialog(app, onSaved, prefill = {}) {
  const { repo } = app;
  openModal({ title: t("register_patient"), ic: "user-plus", size: "lg", body: `<form id="patForm">${patientFormHTML(prefill)}<div id="dupBox" hidden></div></form>`,
    footer: btn(t("cancel"), { attrs: "data-close" }) + btn(t("save"), { ic: "save", cls: "primary", attrs: 'data-save' }),
    onMount: (m) => {
      const form = m.querySelector("#patForm"); const dupBox = m.querySelector("#dupBox"); let pending = null;
      const save = (force) => {
        const data = formValues(form);
        try {
          repo.patientFields(data);
          const dups = repo.findDuplicates(data.full_name, data.phone, data.dob);
          if (dups.length && !force) {
            pending = data;
            dupBox.innerHTML = `${notice(`${t("possible_duplicates")}. ${t("review_duplicates")}`, "warning", "triangle-alert")}${dupList(dups)}<div class="btn-group mt">${btn(t("register_anyway"), { cls: "primary", attrs: "data-force" })}</div>`;
            dupBox.hidden = false; dupBox.querySelector("[data-force]").addEventListener("click", () => save(true)); return;
          }
          const p = repo.createPatient(data, app.user);
          closeModal(); toast(`${t("saved")} ${p.patient_code}`); onSaved(p);
        } catch (e) { showFormError(form, e); }
      };
      m.querySelector("[data-save]").addEventListener("click", () => save(false));
      form.addEventListener("submit", (e) => { e.preventDefault(); save(false); });
      dupBox.addEventListener("click", (e) => { const r = e.target.closest("[data-open-patient]"); if (r) { closeModal(); app.navigate("patients", { id: r.dataset.openPatient }); } });
    } });
}

export function render(_root, app) {
  const root = freshView();
  const id = app.params.id ? Number(app.params.id) : null;
  if (id) renderProfile(root, app, id); else renderList(root, app);
}

function renderList(root, app) {
  const { repo } = app; const st = app.ui.patients || (app.ui.patients = { q: "", inactive: false, page: 1 });
  const canEdit = app.canEdit("patients");
  const all = repo.searchPatients(st.q, 100000, !st.inactive);
  const pg = paginate(all, "page", 25, st);
  root.innerHTML = `${pageHead(t("patients"), t("n_patients", { n: repo.searchPatients("", 100000).length }), canEdit ? btn(t("register_patient"), { ic: "user-plus", cls: "primary", attrs: 'id="btnNew"' }) : "", "users")}
  <div class="card">
    <div class="toolbar mb"><div class="field grow">${input("q", st.q, `placeholder="${esc(t("search_patients_hint"))}" id="patQ" autocomplete="off"`)}</div>${app.isAdmin() ? `<div class="field" style="flex:0 0 auto">${check("inactive", t("include_inactive"), st.inactive, 'id="patInactive"')}</div>` : ""}${btn(t("download_csv"), { ic: "file-spreadsheet", attrs: 'id="patCsv"' })}</div>
    ${all.length ? table({
      columns: [{ label: t("patient"), cls: "cell-primary" }, { label: t("patient_id"), cls: "num" }, { label: t("age") }, { label: t("gender") }, { label: t("phone"), cls: "num" }, { label: t("visits"), cls: "num" }, { label: t("last_visit") }, { label: t("registered") }, ...(st.inactive ? [{ label: t("status") }] : [])],
      rows: pg.items.map((p) => ({ attrs: `class="clickable" data-id="${p.id}"`, cells: [`<div class="cell-main">${avatar(p.full_name, 32)}<div><b>${esc(p.full_name)}</b></div></div>`, esc(p.patient_code), esc(ageFromDob(p.dob)), esc(statusLabel(p.gender)), esc(p.phone), String(p.visits), p.last_visit ? fmtDate(p.last_visit) : "-", fmtDate(p.created_at), ...(st.inactive ? [statusBadge(p.is_active ? "Active" : "Inactive")] : [])] })),
    }) + pager(pg, "page") : emptyState(st.q ? t("no_data") : t("no_patients"), "", "users")}
  </div>`;
  const q = root.querySelector("#patQ"); let timer;
  q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { st.q = q.value; st.page = 1; const pos = q.selectionStart; app.refresh(); const nq = document.getElementById("patQ"); nq.focus(); nq.setSelectionRange(pos, pos); }, 250); });
  const inact = root.querySelector("#patInactive"); if (inact) inact.addEventListener("change", () => { st.inactive = inact.checked; st.page = 1; app.refresh(); });
  root.querySelector("#patCsv").addEventListener("click", () => downloadFile(`patients_${todayISO()}.csv`, toCSV(all.map((p) => ({ ...p, age: ageFromDob(p.dob), last_visit: p.last_visit || "", registered: p.created_at.slice(0, 10) })), ["patient_code", "full_name", "gender", "dob", "age", "phone", "address", "blood_group", "allergies", "visits", "last_visit", "registered"]), "text/csv"));
  const nb = root.querySelector("#btnNew"); if (nb) nb.addEventListener("click", () => openRegisterDialog(app, (p) => app.navigate("patients", { id: p.id })));
  bindPager(root, st, () => app.refresh());
  root.addEventListener("click", (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) app.navigate("patients", { id: tr.dataset.id }); });
}

function renderProfile(root, app, pid) {
  const { repo } = app; const p = repo.patient(pid);
  if (!p) { app.navigate("patients"); return; }
  const st = app.ui.patientProfile || (app.ui.patientProfile = { tab: "appointments" });
  const canEdit = app.canEdit("patients"); const clinical = ["admin", "doctor"].includes(app.user.role);
  const hist = repo.patientHistory(pid);
  const tabs = [["appointments", t("appointments")]]; if (clinical) tabs.push(["consultations", t("consultations")], ["prescriptions", t("prescriptions")]); if (app.canView("billing")) tabs.push(["invoices", t("billing")]);
  if (!tabs.some((x) => x[0] === st.tab)) st.tab = "appointments";
  let pane = "";
  if (st.tab === "appointments") {
    const d = hist.appointments;
    pane = d.length ? table({ columns: [{ label: t("date") }, { label: t("time") }, { label: t("doctor") }, { label: t("visit_type") }, { label: t("status") }, { label: t("notes") }],
      rows: d.map((a) => ({ cells: [fmtDate(a.appt_date), `<span class="num">${fmtTime(a.appt_time)}</span>`, esc(a.doctor), esc(statusLabel(a.visit_type)), statusBadge(a.status), esc(a.notes || "")] })) }) + `<div class="mt">${btn(t("download_csv"), { ic: "file-spreadsheet", cls: "sm", attrs: 'data-csv="appointments"' })}</div>` : emptyState(t("no_data"), "", "calendar");
  } else if (st.tab === "consultations") {
    const d = hist.consultations;
    pane = d.length ? d.map((r) => { const c = repo.consultation(r.id); return `<details class="panel mb"><summary>${icon("stethoscope", 15)}${fmtDate(c.visit_date)} · ${esc(c.doctor_name)} · ${esc(c.diagnosis || "-")}</summary>
      ${kv([[t("symptoms"), c.symptoms || "-"], [t("diagnosis"), c.diagnosis || "-"], ["BP", `${c.bp_systolic || "-"}/${c.bp_diastolic || "-"}`], [t("pulse"), c.pulse || "-"], [t("temperature"), c.temperature || "-"], [t("weight"), c.weight || "-"], [t("clinical_notes"), c.clinical_notes || "-"], [t("follow_up_date"), fmtDate(c.follow_up_date)]])}
      <div class="btn-group mt">${btn(t("view"), { ic: "eye", cls: "sm", attrs: `data-nav-cons="${c.id}"` })}${c.prescription_id ? btn(t("open_prescription"), { ic: "file-text", cls: "sm", attrs: `data-nav-rx="${c.prescription_id}"` }) : ""}</div></details>`; }).join("") + `<div class="mt">${btn(t("download_csv"), { ic: "file-spreadsheet", cls: "sm", attrs: 'data-csv="consultations"' })}</div>` : emptyState(t("no_data"), "", "stethoscope");
  } else if (st.tab === "prescriptions") {
    const d = hist.prescriptions;
    pane = d.length ? `<div class="list">${d.map((r) => listRow({ title: `<span class="num">${esc(r.rx_number)}</span> · ${esc(r.doctor)}`, sub: `${fmtDateTime(r.created_at)} · ${r.items} ${t("medicine").toLowerCase()}`, ic: "file-text", value: statusBadge(r.status), valueSub: btn(t("view"), { cls: "sm", attrs: `data-nav-rx="${r.id}"` }) })).join("")}</div>` : emptyState(t("no_data"), "", "file-text");
  } else {
    const d = hist.invoices; const out = d.reduce((s, i) => s + (i.status === "Cancelled" ? 0 : i.total - i.paid), 0);
    pane = d.length ? (out > 0 ? notice(`${t("outstanding")}: ${money(out)}`, "warning", "credit-card") + '<div class="mb"></div>' : "") + table({ columns: [{ label: t("invoice"), cls: "num" }, { label: t("date") }, { label: t("total"), cls: "num" }, { label: t("received"), cls: "num" }, { label: t("outstanding"), cls: "num" }, { label: t("status") }],
      rows: d.map((i) => ({ attrs: `class="clickable" data-nav-inv="${i.id}"`, cells: [esc(i.invoice_no), fmtDate(i.invoice_date), money(i.total), money(i.paid), money(i.total - i.paid), statusBadge(i.status)] })) }) + `<div class="mt">${btn(t("download_csv"), { ic: "file-spreadsheet", cls: "sm", attrs: 'data-csv="invoices"' })}</div>` : emptyState(t("no_data"), "", "receipt");
  }
  const allergy = p.allergies ? badge(p.allergies, "danger", "triangle-alert") : badge(t("none"), "neutral");
  root.innerHTML = `${pageHead(p.full_name, `${p.patient_code} · ${t("patient_profile")}`, `${btn(t("back"), { ic: "arrow-left", attrs: 'data-nav="patients"' })}${canEdit ? btn(t("edit"), { ic: "pencil", cls: "primary", attrs: 'id="btnEdit"' }) : ""}`, "user")}
  <div class="grid grid-1-2">
    <div class="stack">
      <div class="card">
        <div class="hero mb">${avatar(p.full_name, 56)}<div class="t"><h2>${esc(p.full_name)}</h2><p><span class="num">${esc(p.patient_code)}</span> · ${esc(statusLabel(p.gender))} · ${esc(ageFromDob(p.dob))}</p></div>${p.is_active ? "" : statusBadge("Inactive")}</div>
        ${kv([[t("phone"), p.phone], [t("dob"), fmtDate(p.dob)], [t("blood_group"), p.blood_group || "-"], [t("emergency_contact"), p.emergency_contact || "-"], [t("address"), p.address || "-"], [t("registered"), fmtDate(p.created_at)], [t("allergies"), allergy, true]])}
        ${clinical && p.medical_history ? `<div class="mt"><div class="faint">${esc(t("medical_history"))}</div><div style="font-size:.88rem">${esc(p.medical_history)}</div></div>` : ""}
      </div>
      ${(app.canEdit("appointments") || app.canEdit("queue") || app.canEdit("billing") || (app.isAdmin() && p.is_active)) ? `<div class="card">${section(t("quick_actions"), "sparkles")}<div class="btn-group stack">
        ${app.canEdit("appointments") ? btn(t("new_appointment"), { ic: "calendar-plus", attrs: `data-go="appointments" data-extra="new=1"` }) : ""}
        ${app.canEdit("queue") && !app.isDoctor() ? btn(t("register_walk_in"), { ic: "ticket", attrs: `data-go="queue" data-extra="walkin=1"` }) : ""}
        ${app.canEdit("billing") ? btn(t("new_invoice"), { ic: "receipt", attrs: `data-go="billing" data-extra="new=1"` }) : ""}
        ${app.isAdmin() && p.is_active ? btn(t("deactivate_record"), { ic: "user-round", cls: "danger", attrs: 'id="btnDeact"' }) : ""}
      </div></div>` : ""}
    </div>
    <div class="card">${tabsBar("tab", tabs, st.tab)}${pane}</div>
  </div>`;
  bindTabs(root, st, "tab", () => app.refresh());
  const eb = root.querySelector("#btnEdit"); if (eb) eb.addEventListener("click", () => openModal({ title: t("edit_patient"), ic: "pencil", size: "lg", body: `<form id="patEdit">${patientFormHTML(p)}</form>`,
    footer: btn(t("cancel"), { attrs: "data-close" }) + btn(t("save"), { ic: "save", cls: "primary", attrs: "data-save" }),
    onMount: (m) => { const form = m.querySelector("#patEdit"); const save = () => { try { repo.updatePatient(pid, formValues(form), app.user); closeModal(); toast(t("saved")); app.refresh(); } catch (e) { showFormError(form, e); } }; m.querySelector("[data-save]").addEventListener("click", save); form.addEventListener("submit", (e) => { e.preventDefault(); save(); }); } }));
  const db = root.querySelector("#btnDeact"); if (db) db.addEventListener("click", async () => { if (await confirmDialog({ title: t("deactivate_record"), body: t("deactivate_hint"), confirmText: t("deactivate") })) { repo.deactivatePatient(pid, app.user); toast(t("saved")); app.navigate("patients"); } });
  root.addEventListener("click", (e) => {
    const go = e.target.closest("[data-go]"); if (go) { app.navigate(go.dataset.go, Object.fromEntries(new URLSearchParams(`${go.dataset.extra}&patient=${pid}`))); return; }
    const rx = e.target.closest("[data-nav-rx]"); if (rx) { app.navigate("prescriptions", { id: rx.dataset.navRx }); return; }
    const cons = e.target.closest("[data-nav-cons]"); if (cons) { app.navigate("consultations", { id: cons.dataset.navCons }); return; }
    const inv = e.target.closest("[data-nav-inv]"); if (inv) { app.navigate("billing", { id: inv.dataset.navInv }); return; }
    const csv = e.target.closest("[data-csv]"); if (csv) {
      const k = csv.dataset.csv; const d = hist[k];
      const spec = { appointments: ["appt_date", "appt_time", "doctor", "visit_type", "status", "notes"], consultations: ["visit_date", "doctor", "symptoms", "diagnosis", "bp_systolic", "bp_diastolic", "pulse", "temperature", "weight", "height", "spo2", "clinical_notes", "follow_up_date"], invoices: ["invoice_no", "invoice_date", "total", "paid", "status"] }[k];
      downloadFile(`${p.patient_code}_${k}.csv`, toCSV(d, spec), "text/csv");
    }
  });
}
