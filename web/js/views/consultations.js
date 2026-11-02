/* Consultations: clinical documentation by the treating doctor. The software never suggests, pre-fills or
   auto-generates diagnoses, medicines or doses (modules/consultations.py). */
import { freshView, esc, fmtDate, fmtTime, fmtDateTime, pageHead, section, kpiRow, listRow, emptyState, statusBadge, badge, avatar, tokenChip, btn, iconBtn, field, input, select, textarea, dateInput, check, notice, table, kv, toast, formValues, showFormError, clearFormError, run, t, statusLabel, icon } from "../ui.js";
import { todayISO, addDays, ageFromDob } from "../store.js";
import { patientPicker, doctorOptionsFor } from "./appointments.js";

// ------------------------------------------------------------ shared pieces
export function patientSummary(app, p, clinical = true) {
  const allergy = p.allergies ? badge(p.allergies, "danger", "triangle-alert") : badge(t("none"), "neutral");
  return `<div class="card"><div class="hero mb">${avatar(p.full_name, 44)}<div class="t"><h2>${esc(p.full_name)}</h2><p><span class="num">${esc(p.patient_code)}</span> · ${esc(statusLabel(p.gender))} · ${esc(ageFromDob(p.dob))}</p></div></div>
    ${kv([[t("phone"), p.phone], [t("blood_group"), p.blood_group || "-"], [t("allergies"), allergy, true]])}
    ${clinical && p.medical_history ? `<div class="mt" style="font-size:.86rem"><span class="muted">${esc(t("medical_history"))}:</span> ${esc(p.medical_history)}</div>` : ""}</div>`;
}
export function previousVisits(app, patientId, excludeId = null) {
  const visits = app.repo.consultationsForPatient(patientId, 6).filter((v) => v.id !== excludeId);
  return `<div class="card">${section(t("previous_visits"), "history", visits.length)}${visits.length ? visits.map((v) => `<details class="panel mb"><summary>${icon("stethoscope", 14)}${fmtDate(v.visit_date)} · ${esc(v.doctor_name)} · ${esc(v.diagnosis || "-")}</summary>
    ${kv([[t("symptoms"), v.symptoms || "-"], [t("diagnosis"), v.diagnosis || "-"], ["BP", `${v.bp_systolic || "-"}/${v.bp_diastolic || "-"}`], [t("clinical_notes"), v.clinical_notes || "-"]])}
    ${v.prescription_id ? `<div class="faint mt">${app.repo.prescriptionItems(v.prescription_id).map((it) => `${esc(it.medicine_name)} · ${esc(it.dosage)} · ${esc(it.frequency)} · ${esc(it.duration)}`).join("<br/>")}</div>` : ""}</details>`).join("") : emptyState(t("no_data"), "", "history")}</div>`;
}
const RX_COLS = ["medicine_name", "dosage", "frequency", "duration", "instructions"];
const rxRow = (it = {}) => `<tr>${RX_COLS.map((c, i) => `<td><input data-rx="${c}" value="${esc(it[c] || "")}" maxlength="${c === "instructions" ? 300 : c === "medicine_name" ? 150 : 80}" ${i === 0 ? `placeholder="${esc(t("medicine"))}"` : ""}/></td>`).join("")}<td class="rm">${iconBtn("x", t("remove"), 'data-rx-rm', "danger")}</td></tr>`;
/** Free-text prescription editor: nothing is suggested or pre-filled beyond the saved rows. */
export function rxEditorHTML(items = []) {
  const rows = items.length ? items : [{}, {}, {}];
  return `<div class="faint mb">${esc(t("rx_hint"))}</div><table class="rx-editor" id="rxEditor"><thead><tr><th>${esc(t("medicine"))} *</th><th>${esc(t("dosage"))}</th><th>${esc(t("frequency"))}</th><th>${esc(t("duration"))}</th><th>${esc(t("instructions"))}</th><th></th></tr></thead><tbody>${rows.map(rxRow).join("")}</tbody></table>${btn(t("add_row"), { ic: "plus", cls: "sm", attrs: 'data-rx-add' })}`;
}
export function bindRxEditor(root) {
  root.addEventListener("click", (e) => {
    if (e.target.closest("[data-rx-add]")) { root.querySelector("#rxEditor tbody").insertAdjacentHTML("beforeend", rxRow()); root.querySelector("#rxEditor tbody tr:last-child input").focus(); }
    const rm = e.target.closest("[data-rx-rm]"); if (rm) { const tb = rm.closest("tbody"); rm.closest("tr").remove(); if (!tb.children.length) tb.insertAdjacentHTML("beforeend", rxRow()); }
  });
}
export function readRxItems(root) { return [...root.querySelectorAll("#rxEditor tbody tr")].map((tr) => Object.fromEntries(RX_COLS.map((c) => [c, tr.querySelector(`[data-rx="${c}"]`).value.trim()]))).filter((r) => r.medicine_name); }

function consultationFormHTML(ex = {}, rx = null, canSign = true) {
  const v = (k) => (ex[k] === null || ex[k] === undefined ? "" : ex[k]);
  return `<form id="consForm" class="card">${section(ex.id ? `${t("consultations")} · ${t("edit")}` : t("consultations"), "stethoscope")}
    ${field(t("symptoms"), textarea("symptoms", v("symptoms"), 'rows="3" maxlength="4000"'))}
    <div class="field mt"><label>${esc(t("vitals"))}</label><div class="vitals-grid">
      ${[["bp_systolic", "BP sys", "120", "1"], ["bp_diastolic", "BP dia", "80", "1"], ["pulse", t("pulse"), "72", "1"], ["temperature", t("temperature"), "98.6", "0.1"], ["weight", t("weight"), "70", "0.1"], ["height", t("height"), "170", "0.5"], ["spo2", t("spo2"), "98", "1"]].map(([n, l, ph, step]) => field(l, input(n, v(n), `type="number" step="${step}" placeholder="${ph}" class="num"`))).join("")}
    </div></div>
    <div class="form-grid mt">${field(t("clinical_notes"), textarea("clinical_notes", v("clinical_notes"), 'rows="4" maxlength="8000"'))}${field(t("diagnosis"), textarea("diagnosis", v("diagnosis"), 'rows="4" maxlength="2000"'))}</div>
    <div class="form-grid mt">${field(t("follow_up_date"), dateInput("follow_up_date", v("follow_up_date"), `min="${todayISO()}"`), { optional: true })}</div>
    <div class="field mt"><label>${esc(t("prescriptions"))}</label>${rxEditorHTML(rx ? rx.items : [])}</div>
    <div class="mt">${field(`${t("rx_notes")}`, input("rx_notes", rx ? rx.notes || "" : "", 'maxlength="500"'), { optional: true })}</div>
    <div class="form-foot">${btn(t("save_consultation"), { ic: "save", cls: "primary", attrs: 'data-save="save"' })}${canSign ? btn(t("save_and_sign"), { ic: "pen-line", attrs: 'data-save="sign"' }) : ""}${ex.id ? btn(t("cancel"), { attrs: 'data-cancel-edit' }) : ""}</div>
  </form>`;
}
function readConsForm(form) { const v = formValues(form); return { data: { symptoms: v.symptoms, bp_systolic: v.bp_systolic, bp_diastolic: v.bp_diastolic, pulse: v.pulse, temperature: v.temperature, weight: v.weight, height: v.height, spo2: v.spo2, clinical_notes: v.clinical_notes, diagnosis: v.diagnosis, follow_up_date: v.follow_up_date || null }, items: readRxItems(form), rxNotes: v.rx_notes }; }

// ------------------------------------------------------------ detail
function renderDetail(root, app, id) {
  const { repo } = app; const c = repo.consultation(id); if (!c) { app.navigate("consultations"); return; }
  const st = app.ui.consultations || (app.ui.consultations = {});
  const rx = c.prescription_id ? repo.prescription(c.prescription_id) : null; const items = rx ? repo.prescriptionItems(rx.id) : [];
  const canEdit = app.isDoctor() && app.user.doctor_id === c.doctor_id && (!rx || rx.status !== "Signed");
  const p = repo.patient(c.patient_id);
  root.innerHTML = `${notice(t("clinical_notice"), "info", "shield")}<div class="mb"></div>
  ${pageHead(`${c.patient_name} · ${fmtDate(c.visit_date)}`, `${c.doctor_name} · ${t("consultations")}`, `${btn(t("back"), { ic: "arrow-left", attrs: 'data-nav="consultations"' })}${canEdit && !st.edit ? btn(t("edit"), { ic: "pencil", cls: "primary", attrs: 'id="btnEdit"' }) : ""}`, "stethoscope")}
  ${st.edit === id && canEdit ? consultationFormHTML(c, rx ? { ...rx, items } : null, true) : `<div class="grid grid-1-2">
    <div class="stack">${patientSummary(app, p)}${previousVisits(app, c.patient_id, id)}</div>
    <div class="stack"><div class="card">${section(t("consultations"), "clipboard-list")}${kv([[t("symptoms"), c.symptoms || "-"], [t("diagnosis"), c.diagnosis || "-"], ["BP", `${c.bp_systolic || "-"}/${c.bp_diastolic || "-"} mmHg`], [t("pulse"), c.pulse || "-"], [t("temperature"), c.temperature || "-"], [t("weight"), c.weight || "-"], [t("height"), c.height || "-"], [t("spo2"), c.spo2 || "-"], [t("clinical_notes"), c.clinical_notes || "-"], [t("follow_up_date"), fmtDate(c.follow_up_date)], [t("recorded"), fmtDateTime(c.created_at)]])}</div>
    <div class="card">${section(t("prescriptions"), "file-text")}${rx ? `<div class="mb"><b class="num">${esc(rx.rx_number)}</b> ${statusBadge(rx.status)}</div>${items.length ? table({ columns: [{ label: t("medicine") }, { label: t("dosage") }, { label: t("frequency") }, { label: t("duration") }, { label: t("instructions") }], rows: items.map((it) => ({ cells: [esc(it.medicine_name), esc(it.dosage), esc(it.frequency), esc(it.duration), esc(it.instructions)] })) }) : `<div class="muted">${esc(t("no_medicines"))}</div>`}${rx.notes ? `<div class="muted mt">${esc(rx.notes)}</div>` : ""}<div class="mt">${btn(t("open_prescription"), { ic: "file-text", cls: "sm", attrs: `data-rx="${rx.id}"` })}</div>` : emptyState(t("no_data"), "", "file-text")}</div></div></div>`}`;
  const eb = root.querySelector("#btnEdit"); if (eb) eb.addEventListener("click", () => { st.edit = id; app.refresh(); });
  root.addEventListener("click", (e) => {
    const rxb = e.target.closest("[data-rx]"); if (rxb && rxb.dataset.rx && !rxb.closest("#rxEditor")) { app.navigate("prescriptions", { id: rxb.dataset.rx }); return; }
    if (e.target.closest("[data-cancel-edit]")) { st.edit = null; app.refresh(); return; }
    const sb = e.target.closest("[data-save]"); if (!sb) return;
    const form = root.querySelector("#consForm"); const { data, items: its, rxNotes } = readConsForm(form);
    try { const rxId = repo.updateConsultation(id, data, its, rxNotes, app.user); if (sb.dataset.save === "sign" && rxId) repo.signPrescription(rxId, app.user); st.edit = null; toast(t("consultation_saved")); app.refresh(); } catch (err) { showFormError(form, err); }
  });
  bindRxEditor(root);
}

// ------------------------------------------------------------ page
export function render(_root, app) {
  const root = freshView(); const { repo } = app; const today = todayISO();
  if (app.params.id) { renderDetail(root, app, Number(app.params.id)); return; }
  const st = app.ui.consultations || (app.ui.consultations = {});
  Object.assign(st, { from: st.from || addDays(today, -30), to: st.to || today, doctor: st.doctor || 0, q: st.q || "", mode: st.mode || "queue" });
  if (app.params.token) { st.token = Number(app.params.token); st.mode = "queue"; app.params = {}; history.replaceState(null, "", "#/consultations"); }
  const isDoc = app.isDoctor() && app.canEdit("consultations");
  let work = "";
  if (isDoc) {
    const did = app.user.doctor_id; const q = repo.queueForDate(today, did, ["In Consultation", "Waiting"]);
    if (st.token && !q.some((x) => x.id === st.token)) st.token = null;
    if (!st.token && q.length) st.token = q[0].id;
    let token = null, patient = null;
    if (st.mode === "queue") { token = st.token ? repo.token(st.token) : null; patient = token ? repo.patient(token.patient_id) : null; }
    else patient = st.patient ? repo.patient(st.patient) : null;
    work = `<div class="card mb">${section(`${t("live_queue")} · ${t("today")}`, "ticket", q.length, `<div class="segmented" id="consMode"><button type="button" data-mode="queue" class="${st.mode === "queue" ? "active" : ""}">${esc(t("from_queue"))}</button><button type="button" data-mode="patient" class="${st.mode === "patient" ? "active" : ""}">${esc(t("any_patient"))}</button></div>`)}
      ${st.mode === "queue" ? (q.length ? `<div class="field">${select("token", q.map((x) => [x.id, `${t("token")} ${x.token_no} · ${x.patient} (${x.patient_code}) · ${statusLabel(x.status)}`]), st.token)}</div>` : emptyState(t("queue_empty"), "", "ticket")) : `<div id="consPick"></div>`}</div>`;
    if (patient) work += `<div class="grid grid-1-2 mb"><div class="stack">${patientSummary(app, patient)}${previousVisits(app, patient.id)}</div><div>${consultationFormHTML({}, null, true)}</div></div>`;
    st._token = token; st._patient = patient;
  }
  const list = repo.consultationsList(st.from, st.to, isDoc ? app.user.doctor_id : (Number(st.doctor) || null), st.q);
  root.innerHTML = `${notice(t("clinical_notice"), "info", "shield")}<div class="mb"></div>${pageHead(t("consultations"), app.user.doctor_name || t("all"), "", "stethoscope")}${work}
  <div class="card">${section(t("visit_history"), "history", list.length)}
    <div class="toolbar mb"><div class="field narrow">${dateInput("from", st.from)}</div><div class="field narrow">${dateInput("to", st.to)}</div>${isDoc ? "" : `<div class="field narrow">${select("doctor", doctorOptionsFor(app, true), st.doctor)}</div>`}<div class="field grow">${input("q", st.q, `placeholder="${esc(t("search_patients_hint"))}" autocomplete="off"`)}</div></div>
    ${list.length ? table({ columns: [{ label: t("date") }, { label: t("patient"), cls: "cell-primary" }, { label: t("patient_id"), cls: "num" }, { label: t("doctor") }, { label: t("diagnosis") }, { label: "Rx", cls: "num" }, { label: t("follow_up_date") }],
      rows: list.slice(0, 200).map((r) => ({ attrs: `class="clickable" data-id="${r.id}"`, cells: [fmtDate(r.visit_date), `<b>${esc(r.patient)}</b>`, esc(r.patient_code), esc(r.doctor), esc(r.diagnosis || "-"), esc(r.rx_number || "-"), r.follow_up_date ? fmtDate(r.follow_up_date) : "-"] })) }) : emptyState(t("no_data"), "", "stethoscope")}</div>`;
  const bind = (name, key) => { const el = root.querySelector(`[name="${name}"]`); if (el) el.addEventListener("change", () => { st[key] = el.type === "date" ? (el.value || st[key]) : el.value; app.refresh(); }); };
  bind("from", "from"); bind("to", "to"); bind("doctor", "doctor");
  const qi = root.querySelector('[name="q"]'); let timer; qi.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { st.q = qi.value; const pos = qi.selectionStart; app.refresh(); const n = document.querySelector('#view [name="q"]'); n.focus(); n.setSelectionRange(pos, pos); }, 250); });
  const modeSeg = root.querySelector("#consMode"); if (modeSeg) modeSeg.addEventListener("click", (e) => { const b = e.target.closest("[data-mode]"); if (b) { st.mode = b.dataset.mode; app.refresh(); } });
  const tokSel = root.querySelector('[name="token"]'); if (tokSel) tokSel.addEventListener("change", () => { st.token = Number(tokSel.value); app.refresh(); });
  const pick = root.querySelector("#consPick"); if (pick) { patientPicker(pick, app, { selected: st.patient }); pick.addEventListener("patientchange", (e) => { st.patient = e.detail; app.refresh(); }); }
  bindRxEditor(root);
  root.addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]"); if (tr) { app.navigate("consultations", { id: tr.dataset.id }); return; }
    const sb = e.target.closest("[data-save]"); if (!sb) return;
    const form = root.querySelector("#consForm"); const { data, items, rxNotes } = readConsForm(form); const token = st._token, patient = st._patient;
    try {
      const [consId, rxId] = repo.createConsultation(patient.id, app.user.doctor_id, data, items, rxNotes, { appointmentId: token ? token.appointment_id : null, tokenId: token ? token.id : null, actor: app.user });
      if (sb.dataset.save === "sign" && rxId) repo.signPrescription(rxId, app.user);
      st.token = null; st.patient = null; toast(t("consultation_saved")); app.navigate("consultations", { id: consId });
    } catch (err) { showFormError(form, err); }
  });
}
