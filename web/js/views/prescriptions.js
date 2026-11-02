/* Prescriptions: history, editing before signing, signing by the prescribing doctor, printable documents
   in English, Urdu or bilingual (modules/prescriptions.py). */
import { freshView, esc, fmtDate, fmtDateTime, pageHead, section, kpiRow, emptyState, statusBadge, btn, field, input, select, dateInput, notice, table, kv, toast, formValues, showFormError, printPreview, run, t, statusLabel } from "../ui.js";
import { todayISO, addDays } from "../store.js";
import { prescriptionHTML } from "../print.js";
import { patientSummary, rxEditorHTML, bindRxEditor, readRxItems } from "./consultations.js";
import { doctorOptionsFor } from "./appointments.js";

export function printButtons(app, rx, items) {
  const urdu = app.settings.show_urdu_on_prints !== "0";
  return `<div class="btn-group stack">${btn(t("print_en"), { ic: "printer", cls: "primary", attrs: 'data-print="en"' })}${urdu ? btn(t("print_ur"), { ic: "printer", attrs: 'data-print="ur"' }) + btn(t("print_both"), { ic: "printer", attrs: 'data-print="both"' }) : ""}</div>`;
}
export function showPrescriptionPrint(app, rxId, lang) {
  const rx = app.repo.prescription(rxId); const items = app.repo.prescriptionItems(rxId);
  printPreview(prescriptionHTML(rx, items, app.settings, lang), { title: rx.rx_number, size: app.settings.paper_size || "A5" });
}

function renderDetail(root, app, id) {
  const { repo } = app; const rx = repo.prescription(id); if (!rx) { app.navigate("prescriptions"); return; }
  const st = app.ui.prescriptions || (app.ui.prescriptions = {});
  const items = repo.prescriptionItems(id); const owner = app.isDoctor() && app.user.doctor_id === rx.doctor_id; const editable = owner && rx.status !== "Signed";
  const p = repo.patient(rx.patient_id);
  root.innerHTML = `${pageHead(rx.rx_number, `${rx.patient_name} · ${rx.doctor_name} · ${fmtDate(rx.visit_date || rx.created_at)}`, `${btn(t("back"), { ic: "arrow-left", attrs: 'data-nav="prescriptions"' })}<span style="align-self:center">${statusBadge(rx.status)}</span>`, "file-text")}
  <div class="grid grid-1-2">
    <div class="stack">${patientSummary(app, p, ["admin", "doctor"].includes(app.user.role))}
      ${rx.diagnosis ? `<div class="card">${section(t("diagnosis"), "clipboard-list")}<div style="font-size:.9rem">${esc(rx.diagnosis)}</div></div>` : ""}
      <div class="card">${section(t("print"), "printer")}${printButtons(app, rx, items)}${rx.status === "Signed" ? `<div class="faint mt">${esc(t("signed_at"))}: ${fmtDateTime(rx.signed_at)}</div>` : ""}</div>
    </div>
    <div class="stack">
      ${editable && st.edit === id ? `<form class="card" id="rxForm">${section(`${t("edit")} · ${rx.rx_number}`, "pencil")}${rxEditorHTML(items)}<div class="mt">${field(t("notes"), input("notes", rx.notes || "", 'maxlength="500"'))}</div><div class="form-foot">${btn(t("save"), { ic: "save", cls: "primary", attrs: 'data-save' })}${btn(t("cancel"), { attrs: 'data-cancel-edit' })}</div></form>`
      : `<div class="card">${section(t("medicine"), "pill", items.length)}${items.length ? table({ columns: [{ label: "#", cls: "num" }, { label: t("medicine") }, { label: t("dosage") }, { label: t("frequency") }, { label: t("duration") }, { label: t("instructions") }], rows: items.map((it, i) => ({ cells: [String(i + 1), `<b>${esc(it.medicine_name)}</b>`, esc(it.dosage), esc(it.frequency), esc(it.duration), esc(it.instructions)] })) }) : emptyState(t("no_medicines"), "", "pill")}
        ${rx.notes ? `<div class="mt" style="font-size:.88rem"><b>${esc(t("notes"))}:</b> ${esc(rx.notes)}</div>` : ""}${rx.follow_up_date ? `<div class="mt" style="font-size:.88rem"><b>${esc(t("follow_up_date"))}:</b> ${fmtDate(rx.follow_up_date)}</div>` : ""}
        ${editable ? `<div class="form-foot">${btn(t("edit"), { ic: "pencil", attrs: 'id="btnEdit"' })}${btn(t("sign_prescription"), { ic: "pen-line", cls: "primary", attrs: 'id="btnSign"' })}</div><div class="faint mt">${esc(t("editable_until_signed"))}</div>` : rx.status !== "Signed" ? `<div class="mt">${notice(t("only_prescriber"), "info", "lock")}</div>` : ""}</div>`}
      ${rx.consultation_id ? `<div>${btn(`${t("view")} · ${t("consultations")}`, { ic: "stethoscope", cls: "sm", attrs: `data-nav-cons="${rx.consultation_id}"` })}</div>` : ""}
    </div>
  </div>`;
  bindRxEditor(root);
  root.addEventListener("click", (e) => {
    const pb = e.target.closest("[data-print]"); if (pb) { showPrescriptionPrint(app, id, pb.dataset.print); return; }
    if (e.target.closest("#btnEdit")) { st.edit = id; app.refresh(); return; }
    if (e.target.closest("[data-cancel-edit]")) { st.edit = null; app.refresh(); return; }
    if (e.target.closest("#btnSign")) { run(() => repo.signPrescription(id, app.user), t("signed"), () => app.refresh()); return; }
    const cb = e.target.closest("[data-nav-cons]"); if (cb) { app.navigate("consultations", { id: cb.dataset.navCons }); return; }
    if (e.target.closest("[data-save]")) { const form = root.querySelector("#rxForm"); try { repo.updatePrescription(id, readRxItems(form), formValues(form).notes, app.user); st.edit = null; toast(t("saved")); app.refresh(); } catch (err) { showFormError(form, err); } }
  });
}

export function render(_root, app) {
  const root = freshView(); const { repo } = app; const today = todayISO();
  if (app.params.id) { renderDetail(root, app, Number(app.params.id)); return; }
  const st = app.ui.prescriptions || (app.ui.prescriptions = {});
  Object.assign(st, { from: st.from || addDays(today, -30), to: st.to || today, doctor: st.doctor || 0, status: st.status || "", q: st.q || "" });
  const isDoc = app.isDoctor();
  const list = repo.prescriptionsList(st.from, st.to, isDoc ? app.user.doctor_id : (Number(st.doctor) || null), st.q, st.status || null);
  root.innerHTML = `${pageHead(t("prescriptions"), t("visit_history"), "", "file-text")}
  <div class="card tight mb"><div class="toolbar"><div class="field narrow">${dateInput("from", st.from)}</div><div class="field narrow">${dateInput("to", st.to)}</div>${isDoc ? "" : `<div class="field narrow">${select("doctor", doctorOptionsFor(app, true), st.doctor)}</div>`}<div class="field narrow">${select("status", [["", t("all")], ["Draft", t("draft")], ["Signed", t("signed")]], st.status)}</div><div class="field grow">${input("q", st.q, 'placeholder="RX-2026-00001 / name / ID" autocomplete="off"')}</div></div></div>
  ${kpiRow([{ label: t("prescriptions"), value: list.length, ic: "file-text", tone: "primary", hint: `${fmtDate(st.from)} - ${fmtDate(st.to)}` }, { label: t("signed"), value: list.filter((r) => r.status === "Signed").length, ic: "badge-check", tone: "success" }, { label: t("draft"), value: list.filter((r) => r.status === "Draft").length, ic: "square-pen", tone: "warning" }])}
  <div class="card">${list.length ? table({ columns: [{ label: "Rx", cls: "num" }, { label: t("date") }, { label: t("patient"), cls: "cell-primary" }, { label: t("patient_id"), cls: "num" }, { label: t("doctor") }, { label: t("medicine"), cls: "num" }, { label: t("diagnosis") }, { label: t("status") }],
    rows: list.slice(0, 300).map((r) => ({ attrs: `class="clickable" data-id="${r.id}"`, cells: [esc(r.rx_number), fmtDateTime(r.created_at), `<b>${esc(r.patient)}</b>`, esc(r.patient_code), esc(r.doctor), String(r.items), esc(r.diagnosis || "-"), statusBadge(r.status)] })) }) : emptyState(t("no_data"), "", "file-text")}</div>`;
  for (const [name, key] of [["from", "from"], ["to", "to"], ["doctor", "doctor"], ["status", "status"]]) { const el = root.querySelector(`[name="${name}"]`); if (el) el.addEventListener("change", () => { st[key] = el.type === "date" ? (el.value || st[key]) : el.value; app.refresh(); }); }
  const qi = root.querySelector('[name="q"]'); let timer; qi.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { st.q = qi.value; const pos = qi.selectionStart; app.refresh(); const n = document.querySelector('#view [name="q"]'); n.focus(); n.setSelectionRange(pos, pos); }, 250); });
  root.addEventListener("click", (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) app.navigate("prescriptions", { id: tr.dataset.id }); });
}
