/* Token queue: walk-ins, arrivals, live status board and printable token slips (modules/queue.py). */
import { freshView, esc, fmtDate, fmtTime, fmtDateTime, pageHead, section, kpiRow, emptyState, statusBadge, badge, avatar, tokenChip, btn, iconBtn, field, input, select, dateInput, notice, openModal, closeModal, toast, formValues, showFormError, printPreview, run, t, statusLabel, icon, getLang, STATUS_TONES } from "../ui.js";
import { todayISO, GENDERS } from "../store.js";
import { tokenSlipHTML } from "../print.js";
import { patientPicker, doctorOptionsFor } from "./appointments.js";

export function showTokenSlip(app, tokenId) {
  const tk = app.repo.token(tokenId); if (!tk) return;
  printPreview(tokenSlipHTML(tk, app.settings, getLang()), { title: `${t("token_slip")} ${app.settings.token_prefix || ""}${tk.token_no}`, size: "A6" });
}

export function openWalkInDialog(app, { patientId = null, onSaved = null } = {}) {
  const { repo } = app; const state = { mode: patientId ? "existing" : "existing", force: false };
  openModal({ title: t("register_walk_in"), ic: "ticket", size: "lg", body: `<form id="wiForm">
      <div class="segmented mb" id="wiMode"><button type="button" data-mode="existing" class="active">${esc(t("existing_patient"))}</button><button type="button" data-mode="new">${esc(t("new_patient"))}</button></div>
      <div id="wiExisting"></div>
      <div id="wiNew" hidden><div class="form-grid-3">${field(t("full_name"), input("full_name", "", 'maxlength="80"'), { required: true })}${field(t("phone"), input("phone", "", 'maxlength="15" placeholder="03001234567" class="num"'), { required: true })}${field(t("gender"), select("gender", GENDERS.map((g) => [g, t(g.toLowerCase())]), "Male"), { required: true })}</div><div id="wiDups" hidden></div></div>
      <div class="form-grid mt">${field(t("doctor"), select("doctor_id", doctorOptionsFor(app), app.isDoctor() ? app.user.doctor_id : "", app.isDoctor() ? "disabled" : ""), { required: true })}${field(t("notes"), input("notes", "", 'maxlength="300"'), { optional: true })}</div>
      <div id="wiDocStatus" class="mt"></div></form>`,
    footer: btn(t("cancel"), { attrs: "data-close" }) + btn(t("register_walk_in"), { ic: "ticket", cls: "primary", attrs: "data-save" }),
    onMount: (m) => {
      const form = m.querySelector("#wiForm"); const picker = patientPicker(m.querySelector("#wiExisting"), app, { selected: patientId });
      const docStatus = () => { const did = Number(form.doctor_id.value); const box = m.querySelector("#wiDocStatus"); if (!did) { box.innerHTML = ""; return; } const [s] = repo.doctorStatus(did, todayISO()); box.innerHTML = ["on_leave", "off_today"].includes(s) ? notice(`${repo.doctor(did).name}: ${t(s)}`, "warning", "triangle-alert") : ""; };
      form.doctor_id.addEventListener("change", docStatus); docStatus();
      m.querySelector("#wiMode").addEventListener("click", (e) => { const b = e.target.closest("[data-mode]"); if (!b) return; state.mode = b.dataset.mode; m.querySelectorAll("#wiMode button").forEach((x) => x.classList.toggle("active", x === b)); m.querySelector("#wiExisting").hidden = state.mode !== "existing"; m.querySelector("#wiNew").hidden = state.mode !== "new"; });
      const save = () => {
        const v = formValues(form); const did = Number(v.doctor_id);
        try {
          let pid = picker.get();
          if (state.mode === "new") {
            const data = { full_name: v.full_name, phone: v.phone, gender: v.gender }; repo.patientFields(data);
            const dups = repo.findDuplicates(data.full_name, data.phone);
            if (dups.length && !state.force) { const box = m.querySelector("#wiDups"); box.hidden = false; box.innerHTML = `${notice(t("possible_duplicates"), "warning", "triangle-alert")}<div class="list">${dups.map((x) => `<div class="row">${avatar(x.full_name, 32)}<div class="body"><div class="title">${esc(x.full_name)} <span class="faint num">${esc(x.patient_code)}</span></div><div class="sub num">${esc(x.phone)}</div></div></div>`).join("")}</div><label class="check mt"><input type="checkbox" id="wiForce"/><span>${esc(t("register_anyway"))}</span></label>`; box.querySelector("#wiForce").addEventListener("change", (e) => { state.force = e.target.checked; }); return; }
            pid = repo.createPatient(data, app.user).id;
          }
          if (!pid) throw new Error(t("err.select_patient"));
          const [, tid] = repo.registerWalkIn(pid, did, v.notes, app.user);
          closeModal(); toast(`${t("token")} ${app.settings.token_prefix || ""}${repo.token(tid).token_no}`); if (onSaved) onSaved(tid);
        } catch (e) { showFormError(form, e); }
      };
      m.querySelector("[data-save]").addEventListener("click", save); form.addEventListener("submit", (e) => { e.preventDefault(); save(); });
    } });
}

function tokenCard(app, r, canEdit) {
  const own = !app.isDoctor() || app.user.doctor_id === r.doctor_id; const active = ["Waiting", "In Consultation"].includes(r.status);
  const when = r.appt_time ? fmtTime(r.appt_time) : fmtDateTime(r.created_at);
  const acts = [];
  if (canEdit && own && r.status === "Waiting") acts.push(btn(t("start"), { ic: "play", cls: "sm primary", attrs: `data-act="start" data-id="${r.id}"` }));
  if (canEdit && own && r.status === "In Consultation") {
    if (app.isDoctor() && app.canEdit("consultations")) acts.push(btn(t("consultations"), { ic: "stethoscope", cls: "sm primary", attrs: `data-act="consult" data-id="${r.id}"` }));
    acts.push(btn(t("complete"), { ic: "circle-check", cls: "sm", attrs: `data-act="complete" data-id="${r.id}"` }));
    acts.push(iconBtn("rotate-ccw", t("back_to_waiting"), `data-act="requeue" data-id="${r.id}"`));
  }
  if (canEdit && own && active) acts.push(iconBtn("circle-x", t("cancel"), `data-act="cancel" data-id="${r.id}"`, "danger"));
  if (r.status !== "Cancelled") acts.push(iconBtn("printer", t("token_slip"), `data-act="slip" data-id="${r.id}"`));
  return `<div class="token-card">${tokenChip(r.token_no)}<div class="body"><b><a href="#/patients?id=${r.patient_id}" class="plain">${esc(r.patient)}</a> <span class="faint num">${esc(r.patient_code)}</span></b><span>${esc(r.doctor)} · ${esc(statusLabel(r.visit_type || "Walk-in"))} · <span class="num">${when}</span></span></div>${statusBadge(r.status)}<div class="actions">${acts.join("")}</div></div>`;
}

export function render(_root, app) {
  const root = freshView(); const { repo } = app; const today = todayISO();
  const st = app.ui.queue || (app.ui.queue = { date: today, doctor: 0, lastToken: null });
  const canEdit = app.canEdit("queue"); const lock = app.isDoctor() ? app.user.doctor_id : null; const did = lock || Number(st.doctor) || null;
  if (app.params.walkin && canEdit && !app.isDoctor()) { const pid = app.params.patient; app.params = {}; history.replaceState(null, "", "#/queue"); setTimeout(() => openWalkInDialog(app, { patientId: pid, onSaved: (tid) => { st.lastToken = tid; st.date = today; app.refresh(); } }), 0); }
  const d = st.date; const q = repo.queueForDate(d, did);
  const count = (s) => q.filter((x) => x.status === s).length;
  const active = q.filter((x) => ["Waiting", "In Consultation"].includes(x.status)); const done = q.filter((x) => !["Waiting", "In Consultation"].includes(x.status));
  const sched = canEdit && d === today && !app.isDoctor() ? repo.appointmentsForDate(d, did, ["Scheduled"]) : [];
  const last = st.lastToken ? repo.token(st.lastToken) : null;
  root.innerHTML = `${pageHead(t("queue"), `${d === today ? t("today") + " · " : ""}${fmtDate(d, true)}`, canEdit && !app.isDoctor() ? btn(t("register_walk_in"), { ic: "user-plus", cls: "primary", attrs: 'id="btnWalkin"' }) : "", "ticket")}
  ${last ? `<div class="card soft mb"><div class="hero">${tokenChip(last.token_no, true)}<div class="t"><h2>${esc(last.patient_name)}</h2><p>${esc(last.doctor_name)} · ${esc(t("token_issued"))} · ${fmtDateTime(last.created_at)}</p></div><div class="btn-group">${btn(t("token_slip"), { ic: "printer", cls: "primary", attrs: `data-act="slip" data-id="${last.id}"` })}${btn(t("close"), { attrs: 'id="lastClose"' })}</div></div></div>` : ""}
  <div class="card tight mb"><div class="toolbar"><div class="field narrow">${select("doctor", doctorOptionsFor(app, !lock), did || 0, lock ? "disabled" : "")}</div><div class="field narrow">${dateInput("date", d, `max="${today}" id="qDate"`)}</div>${btn(t("refresh"), { ic: "refresh-cw", attrs: 'id="qRefresh"' })}</div></div>
  ${kpiRow([{ label: t("waiting"), value: count("Waiting"), ic: "hourglass", tone: "warning" }, { label: t("in_consultation"), value: count("In Consultation"), ic: "stethoscope", tone: "primary" }, { label: t("completed_visits"), value: count("Completed"), ic: "circle-check", tone: "success" }, { label: t("cancelled"), value: count("Cancelled"), ic: "circle-x", tone: "neutral" }])}
  ${sched.length ? `<details class="panel mb"><summary>${icon("user-round-check", 16)}${esc(t("mark_arrived"))} · ${sched.length} ${esc(t("not_arrived_yet").toLowerCase())}</summary><div class="list">${sched.map((r) => `<div class="row"><span class="time num">${fmtTime(r.appt_time)}</span><div class="body"><div class="title">${esc(r.patient)} <span class="faint num">${esc(r.patient_code)}</span></div><div class="sub">${esc(r.doctor)}</div></div><div class="end">${btn(t("mark_arrived"), { ic: "user-round-check", cls: "sm", attrs: `data-act="arrive" data-id="${r.id}"` })}</div></div>`).join("")}</div></details>` : ""}
  <div class="card">${section(t("live_queue"), "ticket", active.length)}${active.length ? active.map((r) => tokenCard(app, r, canEdit)).join("") : emptyState(t("queue_empty"), "", "ticket")}
  ${done.length ? `<details class="panel mt"><summary>${icon("history", 16)}${esc(t("completed_visits"))} / ${esc(t("cancelled"))} · ${done.length}</summary>${done.map((r) => tokenCard(app, r, canEdit)).join("")}</details>` : ""}</div>`;
  root.querySelector('[name="doctor"]').addEventListener("change", (e) => { st.doctor = Number(e.target.value); app.refresh(); });
  root.querySelector("#qDate").addEventListener("change", (e) => { st.date = e.target.value || today; app.refresh(); });
  root.querySelector("#qRefresh").addEventListener("click", () => app.refresh());
  const wb = root.querySelector("#btnWalkin"); if (wb) wb.addEventListener("click", () => openWalkInDialog(app, { onSaved: (tid) => { st.lastToken = tid; st.date = today; app.refresh(); } }));
  const lc = root.querySelector("#lastClose"); if (lc) lc.addEventListener("click", () => { st.lastToken = null; app.refresh(); });
  root.addEventListener("click", (e) => {
    const a = e.target.closest("[data-act]"); if (!a) return; const id = Number(a.dataset.id); const act = a.dataset.act;
    if (act === "slip") showTokenSlip(app, id);
    else if (act === "arrive") run(() => repo.markArrived(id, app.user), t("mark_arrived"), (tid) => { st.lastToken = tid; app.refresh(); });
    else if (act === "consult") app.navigate("consultations", { token: id });
    else run(() => repo.tokenAction(id, act, app.user), t("saved"), () => app.refresh());
  });
}
