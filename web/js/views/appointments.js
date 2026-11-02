/* Appointments: booking with free-slot generation, daily / weekly calendar, reschedule, cancel, arrivals
   (modules/appointments.py). Also exports the shared patient / doctor pickers. */
import { freshView, esc, fmtDate, fmtTime, fmtDay, pageHead, section, listRow, emptyState, statusBadge, badge, btn, iconBtn, field, input, select, textarea, dateInput, notice, openModal, closeModal, toast, formValues, showFormError, run, t, statusLabel, icon, isRTL, STATUS_TONES } from "../ui.js";
import { todayISO, addDays, weekBounds, WEEKDAYS, VISIT_TYPES, SlotTakenError } from "../store.js";
import { openRegisterDialog } from "./patients.js";

// ------------------------------------------------------------ shared pickers
/** Search box + select bound together. Returns {get(), set(id), refresh()} and renders into `container`. */
export function patientPicker(container, app, { selected = null, label = null, required = true } = {}) {
  const { repo } = app; let current = selected ? Number(selected) : null;
  const sel = repo.patient(current); let q = sel ? sel.patient_code : "";
  const draw = () => {
    const opts = repo.patientOptions(q, 200);
    if (current && !opts.some(([id]) => id === current)) { const p = repo.patient(current); if (p) opts.unshift([p.id, `${p.full_name} (${p.patient_code}, ${p.phone})`]); }
    container.innerHTML = `<div class="form-grid pick-wrap"><div class="field"><label>${esc(t("search"))}</label><input name="pq" value="${esc(q)}" placeholder="${esc(t("search_patients_hint"))}" autocomplete="off"/></div>
      ${field(label || t("patient"), opts.length ? select("pid", [["", t("choose")], ...opts], current || "") : `<select name="pid" disabled><option>${esc(t("no_data"))}</option></select>`, { required })}</div>`;
    const inp = container.querySelector('[name="pq"]'); let timer;
    inp.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { q = inp.value; const pos = inp.selectionStart; draw(); const n = container.querySelector('[name="pq"]'); n.focus(); n.setSelectionRange(pos, pos); }, 200); });
    const s = container.querySelector('[name="pid"]'); if (s) s.addEventListener("change", () => { current = s.value ? Number(s.value) : null; container.dispatchEvent(new CustomEvent("patientchange", { detail: current })); });
    if (opts.length && !current && opts.length === 1 && q) { current = opts[0][0]; container.querySelector('[name="pid"]').value = current; }
  };
  draw();
  return { get: () => current, set: (id) => { current = id; const p = repo.patient(id); q = p ? p.patient_code : ""; draw(); }, refresh: draw };
}
export function doctorOptionsFor(app, allowAll = false) {
  const { repo } = app; let opts = repo.doctorOptions();
  if (app.isDoctor() && app.user.doctor_id) opts = opts.filter(([id]) => id === app.user.doctor_id);
  return allowAll ? [[0, t("all")], ...opts] : opts;
}
const slotGrid = (slots, active) => slots.length ? `<div class="slot-grid">${slots.map((s) => `<button type="button" class="slot ${s === active ? "active" : ""}" data-slot="${s}">${fmtTime(s)}</button>`).join("")}</div><div class="faint mt" style="margin-top:6px">${esc(t("n_free", { n: slots.length }))}</div>` : notice(t("no_slots"), "warning", "clock");

// ------------------------------------------------------------ booking dialog
export function openBookingDialog(app, { patientId = null, date = null, onSaved = null } = {}) {
  const { repo } = app; const today = todayISO();
  const state = { doctor: app.isDoctor() ? app.user.doctor_id : (repo.doctors()[0] || {}).id, date: date && date >= today ? date : today, slot: null };
  openModal({ title: t("new_appointment"), ic: "calendar-plus", size: "lg", body: `<form id="bookForm"><div id="pick"></div>
      <div class="form-grid-3 mt">
        ${field(t("doctor"), select("doctor_id", doctorOptionsFor(app), state.doctor, app.isDoctor() ? "disabled" : ""), { required: true })}
        ${field(t("date"), dateInput("date", state.date, `min="${today}" max="${addDays(today, 120)}"`), { required: true })}
        ${field(t("visit_type"), select("visit_type", VISIT_TYPES.filter((v) => v !== "Walk-in").map((v) => [v, statusLabel(v)]), "New Visit"))}
      </div>
      <div class="field mt"><label>${esc(t("slot"))} *</label><div id="slots"></div></div>
      <div class="field mt">${field(t("notes"), input("notes", "", 'maxlength="300"'), { optional: true })}</div></form>`,
    footer: btn(t("cancel"), { attrs: "data-close" }) + btn(t("book"), { ic: "calendar-check", cls: "primary", attrs: "data-save" }),
    onMount: (m) => {
      const form = m.querySelector("#bookForm"); const picker = patientPicker(m.querySelector("#pick"), app, { selected: patientId });
      const drawSlots = () => { const slots = state.doctor ? repo.availableSlots(state.doctor, state.date) : []; if (!slots.includes(state.slot)) state.slot = null; const hol = state.doctor ? repo.isHoliday(state.doctor, state.date) : null; m.querySelector("#slots").innerHTML = hol ? notice(`${t("on_leave")}: ${hol.reason || ""}`, "warning", "triangle-alert") : slotGrid(slots, state.slot); };
      form.doctor_id.addEventListener("change", () => { state.doctor = Number(form.doctor_id.value); drawSlots(); });
      form.date.addEventListener("change", () => { state.date = form.date.value || today; drawSlots(); });
      m.querySelector("#slots").addEventListener("click", (e) => { const b = e.target.closest("[data-slot]"); if (!b) return; state.slot = b.dataset.slot; m.querySelectorAll(".slot").forEach((x) => x.classList.toggle("active", x.dataset.slot === state.slot)); });
      drawSlots();
      const save = () => {
        const v = formValues(form);
        try {
          if (!picker.get()) throw new Error(t("err.select_patient"));
          if (!state.slot) throw new Error(t("err.select_slot"));
          const id = repo.createAppointment(picker.get(), state.doctor, state.date, state.slot, v.visit_type, v.notes, app.user);
          closeModal(); toast(t("appointment_saved")); if (onSaved) onSaved(id, state.date);
        } catch (e) { if (e instanceof SlotTakenError) { showFormError(form, new Error(t("slot_taken"))); drawSlots(); } else showFormError(form, e); }
      };
      m.querySelector("[data-save]").addEventListener("click", save); form.addEventListener("submit", (e) => { e.preventDefault(); save(); });
    } });
}
function openReschedule(app, apptId, onSaved) {
  const { repo } = app; const a = repo.appointment(apptId); if (!a) return; const today = todayISO();
  const state = { date: a.appt_date >= today ? a.appt_date : today, slot: null };
  openModal({ title: `${t("reschedule")} · ${a.patient_name}`, ic: "rotate-ccw", body: `<form id="resForm"><div class="muted mb">${esc(a.doctor_name)} · ${t("from")}: ${fmtDate(a.appt_date)} ${fmtTime(a.appt_time)}</div>
      ${field(t("date"), dateInput("date", state.date, `min="${today}" max="${addDays(today, 120)}"`))}<div class="field mt"><label>${esc(t("slot"))} *</label><div id="slots"></div></div></form>`,
    footer: btn(t("cancel"), { attrs: "data-close" }) + btn(t("confirm"), { ic: "check", cls: "primary", attrs: "data-save" }),
    onMount: (m) => {
      const form = m.querySelector("#resForm");
      const drawSlots = () => { const slots = repo.availableSlots(a.doctor_id, state.date, apptId); if (!slots.includes(state.slot)) state.slot = null; m.querySelector("#slots").innerHTML = slotGrid(slots, state.slot); };
      form.date.addEventListener("change", () => { state.date = form.date.value || today; drawSlots(); });
      m.querySelector("#slots").addEventListener("click", (e) => { const b = e.target.closest("[data-slot]"); if (!b) return; state.slot = b.dataset.slot; m.querySelectorAll(".slot").forEach((x) => x.classList.toggle("active", x.dataset.slot === state.slot)); });
      drawSlots();
      m.querySelector("[data-save]").addEventListener("click", () => { try { if (!state.slot) throw new Error(t("err.select_slot")); repo.rescheduleAppointment(apptId, state.date, state.slot, app.user); closeModal(); toast(t("saved")); onSaved(state.date); } catch (e) { showFormError(form, e instanceof SlotTakenError ? new Error(t("slot_taken")) : e); drawSlots(); } });
    } });
}

// ------------------------------------------------------------ page
export function render(_root, app) {
  const root = freshView(); const { repo } = app; const today = todayISO();
  const st = app.ui.appointments || (app.ui.appointments = { date: today, view: "daily", doctor: 0 });
  if (app.params.date) { st.date = app.params.date; }
  const canEdit = app.canEdit("appointments"); const lock = app.isDoctor() ? app.user.doctor_id : null;
  const did = lock || Number(st.doctor) || null;
  if (app.params.new && canEdit) { const pid = app.params.patient; app.params = {}; history.replaceState(null, "", "#/appointments"); setTimeout(() => openBookingDialog(app, { patientId: pid, onSaved: (id, d) => { st.date = d; st.view = "daily"; app.refresh(); } }), 0); }
  const d = st.date;
  let body = "";
  if (st.view === "weekly") {
    const [ws, we] = weekBounds(d); const appts = repo.appointmentsBetween(ws, we, did);
    body = section(`${t("weekly_view")} · ${fmtDate(ws)} - ${fmtDate(we)}`, "calendar-days", appts.length) + `<div class="week-grid">${Array.from({ length: 7 }, (_, i) => {
      const day = addDays(ws, i); const sub = appts.filter((a) => a.appt_date === day);
      return `<div class="week-day ${day === today ? "today" : ""}"><div class="wd">${esc(statusLabel(WEEKDAYS[i]))}</div><div class="wdate">${fmtDay(day)} · ${esc(t("n_appointments", { n: sub.length }))}</div>
        ${sub.slice(0, 8).map((r) => `<div class="chip tone-${STATUS_TONES[r.status] || "neutral"}" data-patient="${r.patient_id}" title="${esc(r.status)}"><b>${fmtTime(r.appt_time)}</b>${esc(r.patient)}<span>${esc(r.doctor.replace(/^Dr\.\s*/, ""))}</span></div>`).join("")}
        ${sub.length > 8 ? `<div class="faint">${esc(t("more_n", { n: sub.length - 8 }))}</div>` : ""}${btn(t("view"), { cls: "sm", attrs: `data-day="${day}"` })}</div>`; }).join("")}</div>`;
  } else {
    const appts = repo.appointmentsForDate(d, did);
    body = section(`${d === today ? t("today") + " · " : ""}${fmtDate(d, true)}`, "calendar", appts.length) + (appts.length ? `<div class="list">${appts.map((r) => {
      const open = !["Completed", "Cancelled", "No Show"].includes(r.status);
      const acts = canEdit && open ? `<div class="actions">
        ${r.status === "Scheduled" && d === today ? btn(t("mark_arrived"), { ic: "user-round-check", cls: "sm primary", attrs: `data-act="arrive" data-id="${r.id}"` }) : ""}
        ${["Scheduled", "Arrived"].includes(r.status) && d >= today ? iconBtn("rotate-ccw", t("reschedule"), `data-act="reschedule" data-id="${r.id}"`) : ""}
        ${["Scheduled", "Arrived"].includes(r.status) ? iconBtn("circle-x", t("cancel"), `data-act="cancel" data-id="${r.id}"`, "danger") : ""}
        ${["Scheduled", "Arrived"].includes(r.status) && d <= today ? iconBtn("x", t("mark_no_show"), `data-act="noshow" data-id="${r.id}"`) : ""}</div>` : "";
      return listRow({ title: `<a href="#/patients?id=${r.patient_id}" class="plain">${esc(r.patient)}</a> <span class="faint num">${esc(r.patient_code)} · ${esc(r.phone)}</span>`, sub: `${esc(r.doctor)} · ${esc(statusLabel(r.visit_type))}${r.token_no ? ` · ${t("token")} <span class="num">${r.token_no}</span>` : ""}${r.notes ? ` · ${esc(r.notes)}` : ""}`,
        lead: `<span class="time num">${fmtTime(r.appt_time)}</span>`, value: statusBadge(r.status), valueSub: acts });
    }).join("")}</div>` : emptyState(t("no_appointments_today"), "", "calendar"));
  }
  let hours = "";
  if (did) { const doc = repo.doctor(did); const [status, h] = repo.doctorStatus(did, d); const day = repo.doctorDay(did, d); hours = `<div class="muted mt">${esc(doc.name)} · ${esc(t("working_hours"))}: <span class="num">${esc(h || "-")}</span>${day && day.break_start ? ` · ${esc(t("break"))} <span class="num">${esc(day.break_start)}-${esc(day.break_end)}</span>` : ""} ${badge(t(status), STATUS_TONES[status])}</div>`; }
  root.innerHTML = `${pageHead(t("appointments"), `${t("daily_view")} / ${t("weekly_view")}`, canEdit ? btn(t("new_appointment"), { ic: "calendar-plus", cls: "primary", attrs: 'id="btnNew"' }) : "", "calendar")}
  <div class="card tight mb"><div class="toolbar">
    ${iconBtn(isRTL() ? "chevron-right" : "chevron-left", t("previous"), 'id="prev"')}<div class="field narrow">${dateInput("date", d, 'id="dateInp"')}</div>${iconBtn(isRTL() ? "chevron-left" : "chevron-right", t("next"), 'id="next"')}
    ${d !== today ? btn(t("today"), { cls: "sm", attrs: 'id="btnToday"' }) : ""}
    <div class="field narrow">${select("doctor", doctorOptionsFor(app, !lock), did || 0, lock ? "disabled" : "")}</div>
    <div class="segmented" id="viewSeg"><button type="button" data-view="daily" class="${st.view !== "weekly" ? "active" : ""}">${esc(t("daily_view"))}</button><button type="button" data-view="weekly" class="${st.view === "weekly" ? "active" : ""}">${esc(t("weekly_view"))}</button></div>
  </div></div>
  <div class="card">${body}${hours}</div>`;
  const step = st.view === "weekly" ? 7 : 1;
  root.querySelector("#prev").addEventListener("click", () => { st.date = addDays(st.date, -step); app.refresh(); });
  root.querySelector("#next").addEventListener("click", () => { st.date = addDays(st.date, step); app.refresh(); });
  root.querySelector("#dateInp").addEventListener("change", (e) => { st.date = e.target.value || today; app.refresh(); });
  const tb = root.querySelector("#btnToday"); if (tb) tb.addEventListener("click", () => { st.date = today; app.refresh(); });
  root.querySelector('[name="doctor"]').addEventListener("change", (e) => { st.doctor = Number(e.target.value); app.refresh(); });
  root.querySelector("#viewSeg").addEventListener("click", (e) => { const b = e.target.closest("[data-view]"); if (b) { st.view = b.dataset.view; app.refresh(); } });
  const nb = root.querySelector("#btnNew"); if (nb) nb.addEventListener("click", () => openBookingDialog(app, { date: d, onSaved: (id, nd) => { st.date = nd; st.view = "daily"; app.refresh(); } }));
  root.addEventListener("click", (e) => {
    const dayBtn = e.target.closest("[data-day]"); if (dayBtn) { st.date = dayBtn.dataset.day; st.view = "daily"; app.refresh(); return; }
    const chip = e.target.closest("[data-patient]"); if (chip) { app.navigate("patients", { id: chip.dataset.patient }); return; }
    const a = e.target.closest("[data-act]"); if (!a) return; const id = Number(a.dataset.id);
    if (a.dataset.act === "arrive") run(() => repo.markArrived(id, app.user), t("mark_arrived"), () => app.refresh());
    else if (a.dataset.act === "reschedule") openReschedule(app, id, (nd) => { st.date = nd; app.refresh(); });
    else if (a.dataset.act === "cancel") run(() => repo.setAppointmentStatus(id, "Cancelled", app.user), t("cancel"), () => app.refresh());
    else if (a.dataset.act === "noshow") run(() => repo.setAppointmentStatus(id, "No Show", app.user), t("no_show"), () => app.refresh());
  });
}
