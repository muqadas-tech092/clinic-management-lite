/* Domain layer: every business rule and query of core/repo.py, ported to run on the in-browser state.
   Views never touch the tables directly; they call these functions. */
import { store, err, AppError, SlotTakenError, nowISO, todayISO, nowTime, addDays, weekday, parseTime, timeSlots, validDate, validTime,
  normalizePhone, cleanText, round2, toFloat, GENDERS, VISIT_TYPES, APPOINTMENT_STATUSES, PAYMENT_METHODS, ROLES, WEEKDAYS } from "./store.js";

export { AppError, SlotTakenError };
const S = () => store.state;
const byId = (table, id) => S()[table].find((r) => r.id === id) || null;
const d10 = (v) => (validDate(v) ? String(v).slice(0, 10) : "");
const actorId = (actor) => (actor ? actor.id ?? null : null);
const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
const userName = (id) => { const u = id ? S().users.find((x) => x.id === id) : null; return u ? u.full_name : ""; };
const docName = (id) => { const d = id ? byId("doctors", id) : null; return d ? d.name : ""; };

// ===================================================================== doctors
export const doctors = (activeOnly = true) => S().doctors.filter((d) => !activeOnly || d.is_active).sort((a, b) => a.name.localeCompare(b.name));
export const doctor = (id) => byId("doctors", id);
export const doctorOptions = (activeOnly = true) => doctors(activeOnly).map((d) => [d.id, d.name]);

export function saveDoctor(data, doctorId = null, actor = null) {
  const name = cleanText(data.name, 100);
  if (name.length < 2) throw err("err.doctor_name_required");
  const fee = toFloat(data.consultation_fee, 0);
  if (fee < 0) throw err("err.fee_negative");
  const fields = {
    name, specialization: cleanText(data.specialization, 100), qualification: cleanText(data.qualification, 150),
    registration_no: cleanText(data.registration_no, 60), phone: cleanText(data.phone, 30), email: cleanText(data.email, 100),
    consultation_fee: fee, photo_data: data.photo_data || "", is_active: data.is_active === undefined || data.is_active ? 1 : 0, updated_at: nowISO(),
  };
  if (doctorId) {
    const d = byId("doctors", doctorId); if (!d) throw err("err.select_doctor");
    Object.assign(d, fields);
    store.audit("update", "doctor", doctorId, { name }, actor); store.commit();
    return doctorId;
  }
  const id = store.nextId("doctors");
  S().doctors.push({ id, ...fields, created_at: nowISO() });
  for (let wd = 0; wd < 7; wd++) S().doctor_schedule.push({ id: store.nextId("doctor_schedule"), doctor_id: id, weekday: wd, is_working: wd === 6 ? 0 : 1, start_time: "09:00", end_time: "17:00", break_start: "13:00", break_end: "14:00" });
  store.audit("create", "doctor", id, { name }, actor); store.commit();
  return id;
}
export function doctorSchedule(doctorId) {
  const existing = new Set(S().doctor_schedule.filter((r) => r.doctor_id === doctorId).map((r) => r.weekday));
  let added = false;
  for (let wd = 0; wd < 7; wd++) if (!existing.has(wd)) { S().doctor_schedule.push({ id: store.nextId("doctor_schedule"), doctor_id: doctorId, weekday: wd, is_working: wd === 6 ? 0 : 1, start_time: "09:00", end_time: "17:00", break_start: "", break_end: "" }); added = true; }
  if (added) store.commit();
  return S().doctor_schedule.filter((r) => r.doctor_id === doctorId).sort((a, b) => a.weekday - b.weekday);
}
export function saveSchedule(doctorId, rows, actor = null) {
  for (const r of rows) {
    if (r.is_working) {
      const s = parseTime(r.start_time), e = parseTime(r.end_time);
      if (s === null || e === null || s >= e) throw err("err.invalid_hours", { day: WEEKDAYS[r.weekday] });
      const bs = r.break_start ? parseTime(r.break_start) : null, be = r.break_end ? parseTime(r.break_end) : null;
      if ((r.break_start && bs === null) || (r.break_end && be === null) || (bs !== null && be === null) || (be !== null && bs === null) || (bs !== null && be !== null && bs >= be)) throw err("err.invalid_break", { day: WEEKDAYS[r.weekday] });
    }
  }
  const sched = doctorSchedule(doctorId);
  for (const r of rows) {
    const row = sched.find((x) => x.weekday === r.weekday); if (!row) continue;
    Object.assign(row, { is_working: r.is_working ? 1 : 0, start_time: r.start_time, end_time: r.end_time, break_start: r.break_start || "", break_end: r.break_end || "" });
  }
  store.audit("update", "doctor_schedule", doctorId, null, actor); store.commit();
}
export const holidays = (doctorId, fromDate = null) => S().doctor_holidays.filter((h) => h.doctor_id === doctorId && (!fromDate || h.holiday_date >= d10(fromDate))).sort((a, b) => cmp(a.holiday_date, b.holiday_date));
export function addHoliday(doctorId, date, reason = "", actor = null) {
  const d = d10(date); if (!d) throw err("err.date_required");
  if (!S().doctor_holidays.some((h) => h.doctor_id === doctorId && h.holiday_date === d)) S().doctor_holidays.push({ id: store.nextId("doctor_holidays"), doctor_id: doctorId, holiday_date: d, reason: cleanText(reason, 120) });
  store.audit("create", "holiday", doctorId, { date: d }, actor); store.commit();
}
export function removeHoliday(holidayId, actor = null) {
  S().doctor_holidays = S().doctor_holidays.filter((h) => h.id !== holidayId);
  store.audit("delete", "holiday", holidayId, null, actor); store.commit();
}
export const isHoliday = (doctorId, d) => S().doctor_holidays.find((h) => h.doctor_id === doctorId && h.holiday_date === d10(d)) || null;
export const doctorDay = (doctorId, d) => { const wd = weekday(d10(d)); return doctorSchedule(doctorId).find((r) => r.weekday === wd) || null; };
/** Returns [statusKey, hoursText] for the availability card. */
export function doctorStatus(doctorId, d) {
  const hol = isHoliday(doctorId, d);
  if (hol) return ["on_leave", hol.reason || ""];
  const day = doctorDay(doctorId, d);
  if (!day || !day.is_working) return ["off_today", ""];
  const hours = `${day.start_time} - ${day.end_time}`;
  const busy = S().tokens.some((t) => t.doctor_id === doctorId && t.token_date === d10(d) && t.status === "In Consultation");
  return [busy ? "in_consultation" : "available", hours];
}

// ==================================================================== patients
export const patient = (id) => byId("patients", id);
export const patientByCode = (code) => S().patients.find((p) => p.patient_code === String(code || "").trim().toUpperCase()) || null;
function lastVisit(pid) { let best = null; for (const c of S().consultations) if (c.patient_id === pid && (!best || c.visit_date > best)) best = c.visit_date; return best; }
function visitCount(pid) { let n = 0; for (const a of S().appointments) if (a.patient_id === pid && a.status !== "Cancelled") n++; return n; }
export function searchPatients(q = "", limit = 50, activeOnly = true) {
  q = String(q || "").trim(); const ql = q.toLowerCase(); const qp = normalizePhone(q) || q; const qu = q.toUpperCase();
  let list = S().patients.filter((p) => (!activeOnly || p.is_active) && (!q || p.full_name.toLowerCase().includes(ql) || p.phone.includes(qp) || p.patient_code.includes(qu)));
  list = list.slice().sort((a, b) => cmp(b.created_at, a.created_at) || b.id - a.id).slice(0, limit);
  return list.map((p) => ({ ...p, last_visit: lastVisit(p.id), visits: visitCount(p.id) }));
}
export const patientOptions = (q = "", limit = 300) => searchPatients(q, limit).map((p) => [p.id, `${p.full_name} (${p.patient_code}, ${p.phone})`]);
export function findDuplicates(fullName, phone, dob = null, excludeId = null) {
  const phoneN = normalizePhone(phone); const name = String(fullName || "").trim().toLowerCase(); const d = d10(dob);
  return S().patients.filter((p) => p.is_active && p.id !== excludeId && (p.phone === phoneN || (p.full_name.toLowerCase() === name && (!d || p.dob === d))))
    .map((p) => ({ id: p.id, patient_code: p.patient_code, full_name: p.full_name, phone: p.phone, dob: p.dob }));
}
export function patientFields(data) {
  const name = cleanText(data.full_name, 100); const phone = normalizePhone(data.phone || "");
  if (name.length < 2) throw err("err.patient_name_required");
  if (!phone || phone.length < 10) throw err("err.phone_required");
  if (!GENDERS.includes(data.gender)) throw err("err.gender_required");
  const dob = d10(data.dob) || null;
  if (dob && dob > todayISO()) throw err("err.dob_future");
  return { full_name: name, dob, gender: data.gender, phone, address: cleanText(data.address, 300), blood_group: data.blood_group || "",
    emergency_contact: cleanText(data.emergency_contact, 120), allergies: cleanText(data.allergies, 1000), medical_history: cleanText(data.medical_history, 4000) };
}
export function createPatient(data, actor = null) {
  const fields = patientFields(data);
  const n = store.nextSeq("patient"); const code = `P-${String(n).padStart(5, "0")}`;
  const id = store.nextId("patients"); const now = nowISO();
  const row = { id, patient_code: code, ...fields, is_active: 1, created_at: now, updated_at: now };
  S().patients.push(row);
  store.audit("create", "patient", code, { name: fields.full_name }, actor); store.commit();
  return row;
}
export function updatePatient(id, data, actor = null) {
  const p = byId("patients", id); if (!p) throw err("err.select_patient");
  Object.assign(p, patientFields(data), { updated_at: nowISO() });
  store.audit("update", "patient", id, { name: p.full_name }, actor); store.commit();
}
export function deactivatePatient(id, actor = null) {
  const p = byId("patients", id); if (!p) return;
  p.is_active = 0; p.updated_at = nowISO();
  store.audit("deactivate", "patient", id, null, actor); store.commit();
}
export const recentPatients = (limit = 6) => S().patients.filter((p) => p.is_active).sort((a, b) => cmp(b.created_at, a.created_at) || b.id - a.id).slice(0, limit);
export function patientHistory(pid) {
  return {
    appointments: S().appointments.filter((a) => a.patient_id === pid).map((a) => ({ ...a, doctor: docName(a.doctor_id) })).sort((a, b) => cmp(b.appt_date, a.appt_date) || cmp(b.appt_time, a.appt_time)),
    consultations: S().consultations.filter((c) => c.patient_id === pid).map((c) => ({ ...c, doctor: docName(c.doctor_id) })).sort((a, b) => cmp(b.visit_date, a.visit_date) || b.id - a.id),
    prescriptions: S().prescriptions.filter((r) => r.patient_id === pid).map((r) => ({ ...r, doctor: docName(r.doctor_id), items: S().prescription_items.filter((i) => i.prescription_id === r.id).length })).sort((a, b) => b.id - a.id),
    invoices: S().invoices.filter((i) => i.patient_id === pid).map((i) => ({ ...i, paid: paidFor(i.id) })).sort((a, b) => b.id - a.id),
  };
}

// ================================================================ appointments
export const stepMinutes = () => parseInt(store.getSetting("appointment_duration", "15")) || 15;
export function bookedTimes(doctorId, d, excludeApptId = null) {
  const ds = d10(d); const out = new Set();
  for (const a of S().appointments) if (a.doctor_id === doctorId && a.appt_date === ds && !["Cancelled", "No Show"].includes(a.status) && a.id !== excludeApptId) out.add(a.appt_time);
  return out;
}
export function availableSlots(doctorId, d, excludeApptId = null, includePast = false) {
  const ds = d10(d); if (!ds || !doctorId) return [];
  if (isHoliday(doctorId, ds)) return [];
  const day = doctorDay(doctorId, ds);
  if (!day || !day.is_working) return [];
  const slots = timeSlots(day.start_time, day.end_time, stepMinutes(), day.break_start, day.break_end);
  const taken = bookedTimes(doctorId, ds, excludeApptId);
  const cutoff = ds === todayISO() && !includePast ? nowTime() : null;
  return slots.filter((s) => !taken.has(s) && !(cutoff && s < cutoff));
}
export function appointment(id) {
  const a = byId("appointments", id); if (!a) return null;
  const p = byId("patients", a.patient_id) || {};
  return { ...a, patient_name: p.full_name, patient_code: p.patient_code, patient_phone: p.phone, dob: p.dob, gender: p.gender, doctor_name: docName(a.doctor_id) };
}
export function createAppointment(patientId, doctorId, apptDate, apptTime, visitType = "New Visit", notes = "", actor = null, status = "Scheduled", enforceSlots = true) {
  const d = d10(apptDate);
  if (!d) throw err("err.date_required");
  if (!VISIT_TYPES.includes(visitType)) throw err("err.invalid_visit_type");
  if (!byId("patients", patientId)) throw err("err.select_patient");
  if (!byId("doctors", doctorId)) throw err("err.select_doctor");
  if (enforceSlots) {
    if (d < todayISO()) throw err("err.past_booking");
    if (!availableSlots(doctorId, d).includes(apptTime)) throw new SlotTakenError();
  }
  if (!validTime(apptTime)) throw err("err.select_slot");
  // partial unique index ux_appt_slot
  if (!["Cancelled", "No Show"].includes(status) && bookedTimes(doctorId, d).has(apptTime)) throw new SlotTakenError();
  const id = store.nextId("appointments"); const now = nowISO();
  S().appointments.push({ id, patient_id: patientId, doctor_id: doctorId, appt_date: d, appt_time: apptTime, duration_min: stepMinutes(), visit_type: visitType, status, notes: cleanText(notes, 500), created_by: actorId(actor), created_at: now, updated_at: now });
  store.audit("create", "appointment", id, { patient_id: patientId, doctor_id: doctorId, date: d, time: apptTime }, actor); store.commit();
  return id;
}
export function rescheduleAppointment(id, newDate, newTime, actor = null) {
  const a = byId("appointments", id); if (!a) throw err("err.appointment_not_found");
  if (["Completed", "Cancelled", "In Consultation"].includes(a.status)) throw err("err.cannot_reschedule", { status: a.status.toLowerCase() });
  if (!availableSlots(a.doctor_id, newDate, id).includes(newTime)) throw new SlotTakenError();
  const from = `${a.appt_date} ${a.appt_time}`;
  Object.assign(a, { appt_date: d10(newDate), appt_time: newTime, status: "Scheduled", updated_at: nowISO() });
  for (const t of S().tokens) if (t.appointment_id === id && t.status === "Waiting") t.status = "Cancelled";
  store.audit("reschedule", "appointment", id, { from, to: `${a.appt_date} ${newTime}` }, actor); store.commit();
}
export function setAppointmentStatus(id, status, actor = null) {
  if (!APPOINTMENT_STATUSES.includes(status)) throw err("err.invalid_status");
  const a = byId("appointments", id); if (!a) throw err("err.appointment_not_found");
  a.status = status; a.updated_at = nowISO();
  if (["Cancelled", "No Show"].includes(status)) for (const t of S().tokens) if (t.appointment_id === id && t.status === "Waiting") t.status = "Cancelled";
  store.audit("status", "appointment", id, { status }, actor); store.commit();
}
function decorateAppt(a) {
  const p = byId("patients", a.patient_id) || {};
  const tok = S().tokens.find((t) => t.appointment_id === a.id && t.status !== "Cancelled");
  return { ...a, patient: p.full_name, patient_code: p.patient_code, phone: p.phone, doctor: docName(a.doctor_id), token_no: tok ? tok.token_no : null, token_id: tok ? tok.id : null };
}
export function appointmentsForDate(d, doctorId = null, statuses = null) {
  const ds = d10(d);
  return S().appointments.filter((a) => a.appt_date === ds && (!doctorId || a.doctor_id === doctorId) && (!statuses || statuses.includes(a.status))).map(decorateAppt).sort((a, b) => cmp(a.appt_time, b.appt_time) || a.id - b.id);
}
export function appointmentsBetween(start, end, doctorId = null) {
  const s = d10(start), e = d10(end);
  return S().appointments.filter((a) => a.appt_date >= s && a.appt_date <= e && (!doctorId || a.doctor_id === doctorId)).map(decorateAppt).sort((a, b) => cmp(a.appt_date, b.appt_date) || cmp(a.appt_time, b.appt_time));
}
export function upcomingFollowUps(start, end, doctorId = null) {
  const s = d10(start), e = d10(end);
  return S().consultations.filter((c) => c.follow_up_date && c.follow_up_date >= s && c.follow_up_date <= e && (!doctorId || c.doctor_id === doctorId)).map((c) => {
    const p = byId("patients", c.patient_id) || {};
    const booked = S().appointments.filter((a) => a.patient_id === c.patient_id && a.appt_date === c.follow_up_date && a.status !== "Cancelled").length;
    return { id: c.id, follow_up_date: c.follow_up_date, patient: p.full_name, patient_code: p.patient_code, phone: p.phone, patient_id: c.patient_id, doctor: docName(c.doctor_id), doctor_id: c.doctor_id, diagnosis: c.diagnosis, booked };
  }).sort((a, b) => cmp(a.follow_up_date, b.follow_up_date));
}

// ====================================================================== tokens
export function token(id) {
  const tk = byId("tokens", id); if (!tk) return null;
  const p = byId("patients", tk.patient_id) || {}; const d = byId("doctors", tk.doctor_id) || {}; const a = tk.appointment_id ? byId("appointments", tk.appointment_id) : null;
  return { ...tk, patient_name: p.full_name, patient_code: p.patient_code, phone: p.phone, doctor_name: d.name, specialization: d.specialization, appt_time: a ? a.appt_time : null, visit_type: a ? a.visit_type : null };
}
function issueToken(patientId, doctorId, appointmentId, d) {
  if (appointmentId) { const existing = S().tokens.find((t) => t.appointment_id === appointmentId && t.status !== "Cancelled"); if (existing) return existing.id; }
  let n = 0; for (const t of S().tokens) if (t.token_date === d && t.doctor_id === doctorId && t.token_no > n) n = t.token_no;
  const id = store.nextId("tokens");
  S().tokens.push({ id, token_no: n + 1, token_date: d, doctor_id: doctorId, patient_id: patientId, appointment_id: appointmentId || null, status: "Waiting", created_at: nowISO(), started_at: null, completed_at: null });
  return id;
}
export function markArrived(apptId, actor = null) {
  const a = byId("appointments", apptId); if (!a) throw err("err.appointment_not_found");
  if (["Cancelled", "Completed"].includes(a.status)) throw err("err.appointment_is", { status: a.status.toLowerCase() });
  const tid = issueToken(a.patient_id, a.doctor_id, apptId, a.appt_date);
  if (a.status === "Scheduled") { a.status = "Arrived"; a.updated_at = nowISO(); }
  store.audit("arrived", "appointment", apptId, { token_id: tid }, actor); store.commit();
  return tid;
}
/** Walk-in appointment for now (or next free slot) plus a token. Returns [apptId, tokenId]. */
export function registerWalkIn(patientId, doctorId, notes = "", actor = null) {
  if (!byId("patients", patientId)) throw err("err.select_patient");
  if (!byId("doctors", doctorId)) throw err("err.select_doctor");
  const d = todayISO(); const free = availableSlots(doctorId, d);
  let t = free.length ? free[0] : nowTime();
  for (let attempt = 0; attempt < 60; attempt++) {
    if (!bookedTimes(doctorId, d).has(t)) {
      const id = store.nextId("appointments"); const now = nowISO();
      S().appointments.push({ id, patient_id: patientId, doctor_id: doctorId, appt_date: d, appt_time: t, duration_min: stepMinutes(), visit_type: "Walk-in", status: "Arrived", notes: cleanText(notes, 500), created_by: actorId(actor), created_at: now, updated_at: now });
      const tid = issueToken(patientId, doctorId, id, d);
      store.audit("walk_in", "appointment", id, { token_id: tid }, actor); store.commit();
      return [id, tid];
    }
    const m = parseTime(t) + 1; t = `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  }
  throw err("err.walkin_no_time");
}
const QUEUE_ORDER = { "In Consultation": 0, "Waiting": 1, "Completed": 2, "Cancelled": 3 };
export function queueForDate(d, doctorId = null, statuses = null) {
  const ds = d10(d);
  return S().tokens.filter((t) => t.token_date === ds && (!doctorId || t.doctor_id === doctorId) && (!statuses || statuses.includes(t.status))).map((t) => {
    const p = byId("patients", t.patient_id) || {}; const a = t.appointment_id ? byId("appointments", t.appointment_id) : null;
    return { ...t, patient: p.full_name, patient_code: p.patient_code, phone: p.phone, doctor: docName(t.doctor_id), appt_time: a ? a.appt_time : null, visit_type: a ? a.visit_type : null };
  }).sort((a, b) => (QUEUE_ORDER[a.status] ?? 9) - (QUEUE_ORDER[b.status] ?? 9) || a.token_no - b.token_no);
}
const TRANSITIONS = {
  start: ["Waiting", "In Consultation", "started_at", "In Consultation"],
  complete: ["In Consultation", "Completed", "completed_at", "Completed"],
  cancel: [null, "Cancelled", null, "Cancelled"],
  requeue: ["In Consultation", "Waiting", null, "Arrived"],
};
export function tokenAction(id, action, actor = null) {
  const tk = byId("tokens", id); if (!tk) throw err("err.token_not_found");
  const tr = TRANSITIONS[action]; if (!tr) throw err("err.unknown_action");
  const [required, newStatus, stamp, apptStatus] = tr;
  if (required && tk.status !== required) throw err("err.token_state", { status: tk.status, action });
  if (action === "cancel" && ["Completed", "Cancelled"].includes(tk.status)) throw err("err.token_already", { status: tk.status.toLowerCase() });
  tk.status = newStatus; if (stamp) tk[stamp] = nowISO();
  if (tk.appointment_id) { const a = byId("appointments", tk.appointment_id); if (a) { a.status = apptStatus; a.updated_at = nowISO(); } }
  store.audit(action, "token", id, { status: newStatus }, actor); store.commit();
}

// =============================================================== consultations
export function consultation(id) {
  const c = byId("consultations", id); if (!c) return null;
  const p = byId("patients", c.patient_id) || {}; const d = byId("doctors", c.doctor_id) || {};
  const rx = S().prescriptions.find((x) => x.consultation_id === c.id);
  return { ...c, patient_name: p.full_name, patient_code: p.patient_code, dob: p.dob, gender: p.gender, phone: p.phone, allergies: p.allergies,
    doctor_name: d.name, specialization: d.specialization, qualification: d.qualification, registration_no: d.registration_no, prescription_id: rx ? rx.id : null };
}
export const consultationsForPatient = (pid, limit = 20) => S().consultations.filter((c) => c.patient_id === pid).sort((a, b) => cmp(b.visit_date, a.visit_date) || b.id - a.id).slice(0, limit)
  .map((c) => { const rx = S().prescriptions.find((x) => x.consultation_id === c.id); return { ...c, doctor_name: docName(c.doctor_id), prescription_id: rx ? rx.id : null }; });
export function consultationsList(start, end, doctorId = null, search = "") {
  const s = d10(start), e = d10(end); const q = String(search || "").trim().toLowerCase();
  return S().consultations.filter((c) => c.visit_date >= s && c.visit_date <= e && (!doctorId || c.doctor_id === doctorId)).map((c) => {
    const p = byId("patients", c.patient_id) || {}; const rx = S().prescriptions.find((x) => x.consultation_id === c.id);
    return { id: c.id, visit_date: c.visit_date, patient: p.full_name, patient_code: p.patient_code, doctor: docName(c.doctor_id), diagnosis: c.diagnosis, follow_up_date: c.follow_up_date, status: c.status, rx_number: rx ? rx.rx_number : null, patient_id: c.patient_id };
  }).filter((r) => !q || (r.patient || "").toLowerCase().includes(q) || (r.patient_code || "").toLowerCase().includes(q) || (r.diagnosis || "").toLowerCase().includes(q))
    .sort((a, b) => cmp(b.visit_date, a.visit_date) || b.id - a.id);
}
function cleanItems(items) {
  const out = []; let i = 0;
  for (const it of items || []) {
    const name = cleanText(it.medicine_name, 150); if (!name) continue;
    out.push({ medicine_name: name, dosage: cleanText(it.dosage, 80), frequency: cleanText(it.frequency, 80), duration: cleanText(it.duration, 80), instructions: cleanText(it.instructions, 300), sort_order: i++ });
  }
  return out;
}
function vital(v, lo, hi, label, asInt = true) {
  if (v === null || v === undefined || v === "" || v === 0 || v === "0") return null;
  const n = asInt ? parseInt(v, 10) : parseFloat(v);
  if (!Number.isFinite(n) || (asInt && String(v).trim() !== String(n))) throw err("err.vital_number", { label });
  if (n < lo || n > hi) throw err("err.vital_range", { label, lo, hi });
  return n;
}
export function consultationFields(data) {
  return {
    symptoms: cleanText(data.symptoms, 4000),
    bp_systolic: vital(data.bp_systolic, 50, 300, "Systolic BP"), bp_diastolic: vital(data.bp_diastolic, 30, 200, "Diastolic BP"),
    pulse: vital(data.pulse, 20, 250, "Pulse"), temperature: vital(data.temperature, 90, 110, "Temperature (F)", false),
    weight: vital(data.weight, 0.5, 400, "Weight (kg)", false), height: vital(data.height, 20, 260, "Height (cm)", false), spo2: vital(data.spo2, 50, 100, "SpO2"),
    clinical_notes: cleanText(data.clinical_notes, 8000), diagnosis: cleanText(data.diagnosis, 2000), follow_up_date: d10(data.follow_up_date) || null,
  };
}
function createPrescriptionRow(consId, patientId, doctorId, items, notes, year) {
  const y = year || todayISO().slice(0, 4);
  const n = store.nextSeq(`rx_${y}`); const id = store.nextId("prescriptions"); const now = nowISO();
  S().prescriptions.push({ id, rx_number: `RX-${y}-${String(n).padStart(5, "0")}`, consultation_id: consId, patient_id: patientId, doctor_id: doctorId, notes: cleanText(notes, 2000), status: "Draft", signed_at: null, created_at: now, updated_at: now });
  insertItems(id, items);
  return id;
}
function insertItems(rxId, items) { for (const it of items) S().prescription_items.push({ id: store.nextId("prescription_items"), prescription_id: rxId, ...it }); }
/** Returns [consultationId, prescriptionId|null]. Saving completes the token and the appointment. */
export function createConsultation(patientId, doctorId, data, items, rxNotes = "", { appointmentId = null, tokenId = null, actor = null, visitDate = null } = {}) {
  if (!byId("patients", patientId)) throw err("err.select_patient");
  if (!byId("doctors", doctorId)) throw err("err.select_doctor");
  const fields = consultationFields(data); const clean = cleanItems(items); const vd = d10(visitDate) || todayISO(); const now = nowISO();
  const id = store.nextId("consultations");
  S().consultations.push({ id, patient_id: patientId, doctor_id: doctorId, appointment_id: appointmentId || null, token_id: tokenId || null, visit_date: vd, ...fields, status: "Completed", created_at: now, updated_at: now });
  let rxId = null;
  if (clean.length || cleanText(rxNotes)) rxId = createPrescriptionRow(id, patientId, doctorId, clean, rxNotes, vd.slice(0, 4));
  if (tokenId) { const tk = byId("tokens", tokenId); if (tk && tk.status !== "Cancelled") { tk.status = "Completed"; tk.completed_at = now; } }
  if (appointmentId) { const a = byId("appointments", appointmentId); if (a) { a.status = "Completed"; a.updated_at = now; } }
  store.audit("create", "consultation", id, { patient_id: patientId, rx_id: rxId }, actor); store.commit();
  return [id, rxId];
}
export function updateConsultation(id, data, items, rxNotes = "", actor = null) {
  const c = consultation(id); if (!c) throw err("err.consultation_not_found");
  const rx = c.prescription_id ? byId("prescriptions", c.prescription_id) : null;
  if (rx && rx.status === "Signed") throw err("err.rx_signed_locked");
  const fields = consultationFields(data); const clean = cleanItems(items);
  Object.assign(byId("consultations", id), fields, { updated_at: nowISO() });
  let rxId = c.prescription_id;
  if (rxId) {
    S().prescription_items = S().prescription_items.filter((i) => i.prescription_id !== rxId);
    insertItems(rxId, clean); rx.notes = cleanText(rxNotes, 2000); rx.updated_at = nowISO();
  } else if (clean.length || cleanText(rxNotes)) rxId = createPrescriptionRow(id, c.patient_id, c.doctor_id, clean, rxNotes, c.visit_date.slice(0, 4));
  store.audit("update", "consultation", id, null, actor); store.commit();
  return rxId;
}

// =============================================================== prescriptions
export function prescription(id) {
  const r = byId("prescriptions", id); if (!r) return null;
  const p = byId("patients", r.patient_id) || {}; const d = byId("doctors", r.doctor_id) || {}; const c = r.consultation_id ? byId("consultations", r.consultation_id) : null;
  return { ...r, patient_name: p.full_name, patient_code: p.patient_code, dob: p.dob, gender: p.gender, phone: p.phone, allergies: p.allergies,
    doctor_name: d.name, specialization: d.specialization, qualification: d.qualification, registration_no: d.registration_no,
    visit_date: c ? c.visit_date : null, diagnosis: c ? c.diagnosis : "", symptoms: c ? c.symptoms : "", follow_up_date: c ? c.follow_up_date : null,
    bp_systolic: c ? c.bp_systolic : null, bp_diastolic: c ? c.bp_diastolic : null, pulse: c ? c.pulse : null, temperature: c ? c.temperature : null, weight: c ? c.weight : null };
}
export const prescriptionItems = (rxId) => S().prescription_items.filter((i) => i.prescription_id === rxId).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
export function prescriptionsList(start, end, doctorId = null, search = "", status = null) {
  const s = d10(start), e = d10(end); const q = String(search || "").trim().toLowerCase();
  return S().prescriptions.filter((r) => r.created_at.slice(0, 10) >= s && r.created_at.slice(0, 10) <= e && (!doctorId || r.doctor_id === doctorId) && (!status || r.status === status)).map((r) => {
    const p = byId("patients", r.patient_id) || {}; const c = r.consultation_id ? byId("consultations", r.consultation_id) : null;
    return { id: r.id, rx_number: r.rx_number, created_at: r.created_at, patient: p.full_name, patient_code: p.patient_code, doctor: docName(r.doctor_id), status: r.status, items: prescriptionItems(r.id).length, diagnosis: c ? c.diagnosis : "", patient_id: r.patient_id };
  }).filter((r) => !q || (r.patient || "").toLowerCase().includes(q) || (r.patient_code || "").toLowerCase().includes(q) || r.rx_number.toLowerCase().includes(q)).sort((a, b) => b.id - a.id);
}
export function signPrescription(id, actor = null) {
  const rx = byId("prescriptions", id); if (!rx) throw err("err.rx_not_found");
  if (rx.status === "Signed") return;
  if (actor && actor.role === "doctor" && actor.doctor_id !== rx.doctor_id) throw err("err.only_prescriber");
  if (!prescriptionItems(id).length && !rx.notes) throw err("err.rx_empty");
  rx.status = "Signed"; rx.signed_at = nowISO(); rx.updated_at = nowISO();
  store.audit("sign", "prescription", rx.rx_number, null, actor); store.commit();
}
export function updatePrescription(id, items, notes, actor = null) {
  const rx = byId("prescriptions", id); if (!rx) throw err("err.rx_not_found");
  if (rx.status === "Signed") throw err("err.rx_signed_no_edit");
  const clean = cleanItems(items);
  S().prescription_items = S().prescription_items.filter((i) => i.prescription_id !== id);
  insertItems(id, clean); rx.notes = cleanText(notes, 2000); rx.updated_at = nowISO();
  store.audit("update", "prescription", rx.rx_number, null, actor); store.commit();
}

// ===================================================================== billing
export const services = (activeOnly = true) => S().services.filter((s) => !activeOnly || s.is_active).sort((a, b) => a.name.localeCompare(b.name));
export function saveService(name, price, serviceId = null, isActive = true, actor = null) {
  name = cleanText(name, 100); price = toFloat(price, 0);
  if (!name) throw err("err.service_name_required");
  if (price < 0) throw err("err.price_negative");
  if (S().services.some((s) => s.name.toLowerCase() === name.toLowerCase() && s.id !== serviceId)) throw err("err.service_exists");
  if (serviceId) {
    const s = byId("services", serviceId); Object.assign(s, { name, price, is_active: isActive ? 1 : 0 });
    store.audit("update", "service", serviceId, { name, price }, actor); store.commit(); return serviceId;
  }
  const id = store.nextId("services"); S().services.push({ id, name, price, is_active: isActive ? 1 : 0 });
  store.audit("create", "service", id, { name, price }, actor); store.commit(); return id;
}
export const invoiceStatusFor = (total, paid) => (total <= 0 || paid >= total - 0.005 ? "Paid" : paid > 0 ? "Partial" : "Unpaid");
const paidFor = (invId) => round2(S().payments.filter((p) => p.invoice_id === invId).reduce((s, p) => s + p.amount, 0));
export function createInvoice({ patientId, doctorId = null, consultationFee = 0, items = [], discount = 0, discountReason = "", authorizedBy = "", consultationId = null,
  appointmentId = null, notes = "", payment = null, actor = null, invoiceDate = null }) {
  if (!byId("patients", patientId)) throw err("err.select_patient");
  items = (items || []).filter((it) => cleanText(it.description));
  const fee = round2(toFloat(consultationFee, 0));
  if (fee < 0) throw err("err.fee_negative");
  let servicesTotal = 0; const clean = [];
  for (const it of items) {
    const qty = toFloat(it.qty, 1), price = toFloat(it.unit_price, 0);
    if (qty <= 0 || price < 0) throw err("err.service_qty");
    const amount = round2(qty * price); servicesTotal += amount;
    clean.push({ description: cleanText(it.description, 150), qty, unit_price: price, amount });
  }
  discount = round2(toFloat(discount, 0)); const subtotal = round2(fee + servicesTotal);
  if (discount < 0 || discount > subtotal) throw err("err.discount_range");
  if (discount > 0 && !authorizedBy) throw err("err.discount_auth");
  const total = round2(subtotal - discount);
  let paid = 0;
  if (payment) {
    paid = round2(toFloat(payment.amount, 0));
    if (paid < 0 || paid > total + 0.005) throw err("err.received_exceeds");
    if (paid > 0 && !PAYMENT_METHODS.includes(payment.method)) throw err("err.select_method");
  }
  const invDate = d10(invoiceDate) || todayISO(); const year = invDate.slice(0, 4);
  const n = store.nextSeq(`inv_${year}`); const invNo = `INV-${year}-${String(n).padStart(5, "0")}`;
  const id = store.nextId("invoices"); const now = nowISO();
  S().invoices.push({ id, invoice_no: invNo, patient_id: patientId, doctor_id: doctorId || null, appointment_id: appointmentId || null, consultation_id: consultationId || null, invoice_date: invDate,
    consultation_fee: fee, services_total: round2(servicesTotal), discount_amount: discount, discount_reason: cleanText(discountReason, 200), discount_authorized_by: authorizedBy || "",
    total, status: invoiceStatusFor(total, paid), notes: cleanText(notes, 500), created_by: actorId(actor), created_at: now, updated_at: now });
  for (const c of clean) S().invoice_items.push({ id: store.nextId("invoice_items"), invoice_id: id, ...c });
  if (paid > 0) S().payments.push({ id: store.nextId("payments"), invoice_id: id, amount: paid, method: payment.method, reference: cleanText(payment.reference, 100), paid_at: payment.paid_at || now, received_by: actorId(actor), notes: cleanText(payment.notes, 200) });
  store.audit("create", "invoice", invNo, { total, paid, discount, authorized_by: authorizedBy }, actor); store.commit();
  return id;
}
export function invoice(id) {
  const i = byId("invoices", id); if (!i) return null;
  const p = byId("patients", i.patient_id) || {}; const paid = paidFor(id);
  return { ...i, patient_name: p.full_name, patient_code: p.patient_code, phone: p.phone, doctor_name: docName(i.doctor_id), created_by_name: userName(i.created_by), paid, outstanding: round2(i.total - paid),
    items: S().invoice_items.filter((x) => x.invoice_id === id), payments: S().payments.filter((x) => x.invoice_id === id).map((x) => ({ ...x, received_by_name: userName(x.received_by) })).sort((a, b) => cmp(a.paid_at, b.paid_at)) };
}
export function recordPayment(invId, amount, method, reference = "", notes = "", actor = null) {
  const inv = invoice(invId); if (!inv) throw err("err.invoice_not_found");
  if (inv.status === "Cancelled") throw err("err.invoice_cancelled");
  amount = round2(toFloat(amount, 0));
  if (amount <= 0) throw err("err.amount_positive");
  if (amount > inv.outstanding + 0.005) throw err("err.amount_exceeds", { n: Math.round(inv.outstanding) });
  if (!PAYMENT_METHODS.includes(method)) throw err("err.select_method");
  const id = store.nextId("payments");
  S().payments.push({ id, invoice_id: invId, amount, method, reference: cleanText(reference, 100), paid_at: nowISO(), received_by: actorId(actor), notes: cleanText(notes, 200) });
  const row = byId("invoices", invId); row.status = invoiceStatusFor(inv.total, inv.paid + amount); row.updated_at = nowISO();
  store.audit("payment", "invoice", inv.invoice_no, { amount, method }, actor); store.commit();
  return id;
}
export function cancelInvoice(invId, reason = "", actor = null) {
  const inv = invoice(invId); if (!inv) throw err("err.invoice_not_found");
  if (inv.paid > 0) throw err("err.invoice_has_payments");
  const row = byId("invoices", invId); row.status = "Cancelled"; row.notes = cleanText(`${inv.notes} Cancelled: ${reason}`.trim(), 500); row.updated_at = nowISO();
  store.audit("cancel", "invoice", inv.invoice_no, { reason }, actor); store.commit();
}
function decorateInv(i) { const p = byId("patients", i.patient_id) || {}; const paid = paidFor(i.id); return { ...i, patient: p.full_name, patient_code: p.patient_code, phone: p.phone, doctor: docName(i.doctor_id), paid, outstanding: round2(i.total - paid) }; }
export function invoicesList(start, end, status = null, search = "", doctorId = null) {
  const s = d10(start), e = d10(end); const q = String(search || "").trim().toLowerCase();
  return S().invoices.filter((i) => i.invoice_date >= s && i.invoice_date <= e && (!status || i.status === status) && (!doctorId || i.doctor_id === doctorId)).map(decorateInv)
    .filter((r) => !q || (r.patient || "").toLowerCase().includes(q) || (r.patient_code || "").toLowerCase().includes(q) || r.invoice_no.toLowerCase().includes(q)).sort((a, b) => b.id - a.id);
}
export const outstandingInvoices = (doctorId = null) => S().invoices.filter((i) => ["Unpaid", "Partial"].includes(i.status) && (!doctorId || i.doctor_id === doctorId)).map(decorateInv).sort((a, b) => cmp(a.invoice_date, b.invoice_date));
export function collectionOn(d, doctorId = null) {
  const ds = d10(d); let sum = 0;
  for (const p of S().payments) if (p.paid_at.slice(0, 10) === ds) { if (doctorId) { const i = byId("invoices", p.invoice_id); if (!i || i.doctor_id !== doctorId) continue; } sum += p.amount; }
  return round2(sum);
}
export const pendingTotal = (doctorId = null) => round2(outstandingInvoices(doctorId).reduce((s, i) => s + i.outstanding, 0));
/** [{day, amount}] for every day in the range. */
export function dailyCollection(start, end, doctorId = null) {
  const s = d10(start), e = d10(end); const m = new Map();
  for (const p of S().payments) { const day = p.paid_at.slice(0, 10); if (day < s || day > e) continue; if (doctorId) { const i = byId("invoices", p.invoice_id); if (!i || i.doctor_id !== doctorId) continue; } m.set(day, (m.get(day) || 0) + p.amount); }
  const out = []; for (let d = s; d <= e; d = addDays(d, 1)) out.push({ day: d, amount: round2(m.get(d) || 0) });
  return out;
}
export function collectionByMethod(start, end, doctorId = null) {
  const s = d10(start), e = d10(end); const m = new Map();
  for (const p of S().payments) { const day = p.paid_at.slice(0, 10); if (day < s || day > e) continue; if (doctorId) { const i = byId("invoices", p.invoice_id); if (!i || i.doctor_id !== doctorId) continue; } const c = m.get(p.method) || { method: p.method, amount: 0, payments: 0 }; c.amount += p.amount; c.payments++; m.set(p.method, c); }
  return [...m.values()].map((c) => ({ ...c, amount: round2(c.amount) })).sort((a, b) => b.amount - a.amount);
}
export function paymentsOn(d, doctorId = null) {
  const ds = d10(d);
  return S().payments.filter((p) => p.paid_at.slice(0, 10) === ds).map((p) => { const i = byId("invoices", p.invoice_id) || {}; const pt = byId("patients", i.patient_id) || {}; return { ...p, invoice_no: i.invoice_no, invoice_id: i.id, doctor_id: i.doctor_id, patient: pt.full_name, patient_code: pt.patient_code, doctor: docName(i.doctor_id), received_by_name: userName(p.received_by) }; })
    .filter((p) => !doctorId || p.doctor_id === doctorId).sort((a, b) => cmp(a.paid_at, b.paid_at));
}
export function monthlyRevenue(fromDate, doctorId = null) {
  const s = d10(fromDate); const m = new Map();
  for (const p of S().payments) { const day = p.paid_at.slice(0, 10); if (day < s) continue; if (doctorId) { const i = byId("invoices", p.invoice_id); if (!i || i.doctor_id !== doctorId) continue; } const k = day.slice(0, 7); m.set(k, (m.get(k) || 0) + p.amount); }
  return [...m.entries()].map(([month, amount]) => ({ month, amount: round2(amount) })).sort((a, b) => cmp(a.month, b.month));
}
/** Completed or in-progress visits on a date that have no invoice yet. */
export function unbilledVisits(d, doctorId = null) {
  const ds = d10(d);
  return S().appointments.filter((a) => a.appt_date === ds && ["Arrived", "In Consultation", "Completed"].includes(a.status) && (!doctorId || a.doctor_id === doctorId)
    && !S().invoices.some((i) => i.appointment_id === a.id && i.status !== "Cancelled")).map((a) => {
    const p = byId("patients", a.patient_id) || {}; const doc = byId("doctors", a.doctor_id) || {}; const c = S().consultations.find((x) => x.appointment_id === a.id);
    return { appointment_id: a.id, appt_time: a.appt_time, patient_id: a.patient_id, patient: p.full_name, patient_code: p.patient_code, doctor: doc.name, doctor_id: a.doctor_id, consultation_fee: doc.consultation_fee || 0, status: a.status, consultation_id: c ? c.id : null };
  }).sort((a, b) => cmp(a.appt_time, b.appt_time));
}

// =================================================================== inventory
export function medicines(search = "", activeOnly = true, category = null) {
  const q = String(search || "").trim().toLowerCase();
  return S().medicines.filter((m) => (!activeOnly || m.is_active) && (!category || m.category === category) && (!q || m.name.toLowerCase().includes(q) || m.sku.toLowerCase().includes(q) || (m.supplier || "").toLowerCase().includes(q))).sort((a, b) => a.name.localeCompare(b.name));
}
export const medicine = (id) => byId("medicines", id);
export function saveMedicine(data, medId = null, actor = null) {
  const name = cleanText(data.name, 120); const sku = cleanText(data.sku, 40).toUpperCase();
  if (!name) throw err("err.medicine_name_required");
  if (!sku) throw err("err.sku_required");
  const qty = parseInt(data.quantity) || 0, reorder = parseInt(data.reorder_level) || 0, pp = toFloat(data.purchase_price, 0), sp = toFloat(data.selling_price, 0);
  if (qty < 0 || reorder < 0 || pp < 0 || sp < 0) throw err("err.negative_values");
  if (S().medicines.some((m) => m.sku === sku && m.id !== medId)) throw err("err.sku_exists");
  const fields = { name, category: data.category || "Other", sku, reorder_level: reorder, purchase_price: pp, selling_price: sp, expiry_date: d10(data.expiry_date) || null, supplier: cleanText(data.supplier, 120), is_active: data.is_active === undefined || data.is_active ? 1 : 0, updated_at: nowISO() };
  if (medId) {
    const m = byId("medicines", medId); if (!m) throw err("err.medicine_not_found");
    Object.assign(m, fields); store.audit("update", "medicine", sku, { name }, actor); store.commit(); return medId;
  }
  const id = store.nextId("medicines");
  S().medicines.push({ id, ...fields, quantity: qty, created_at: nowISO() });
  if (qty) S().stock_movements.push({ id: store.nextId("stock_movements"), medicine_id: id, change_qty: qty, reason: "Opening stock", reference: "", created_by: actorId(actor), created_at: nowISO() });
  store.audit("create", "medicine", sku, { name, qty }, actor); store.commit();
  return id;
}
export function adjustStock(medId, change, reason, reference = "", actor = null) {
  change = parseInt(change) || 0;
  if (change === 0) throw err("err.nonzero_qty");
  reason = cleanText(reason, 80); if (!reason) throw err("err.reason_required");
  const m = byId("medicines", medId); if (!m) throw err("err.medicine_not_found");
  const newQty = m.quantity + change;
  if (newQty < 0) throw err("err.stock_below_zero", { n: m.quantity });
  m.quantity = newQty; m.updated_at = nowISO();
  S().stock_movements.push({ id: store.nextId("stock_movements"), medicine_id: medId, change_qty: change, reason, reference: cleanText(reference, 100), created_by: actorId(actor), created_at: nowISO() });
  store.audit("stock", "medicine", m.sku, { change, reason, new_qty: newQty }, actor); store.commit();
  return newQty;
}
export const stockMovements = (medId, limit = 50) => S().stock_movements.filter((m) => m.medicine_id === medId).sort((a, b) => b.id - a.id).slice(0, limit).map((m) => ({ ...m, by_user: userName(m.created_by) }));
/** Medicines with a warning flag: Expired, Expiring soon, Low stock. */
export function stockAlerts() {
  const warn = parseInt(store.getSetting("expiry_warning_days", "90")) || 90; const t = todayISO(); const horizon = addDays(t, warn);
  return medicines().map((m) => {
    const flags = [];
    if (m.expiry_date && m.expiry_date < t) flags.push("Expired"); else if (m.expiry_date && m.expiry_date <= horizon) flags.push("Expiring soon");
    if (m.quantity <= m.reorder_level) flags.push("Low stock");
    return { ...m, flags, alert: flags.join(", ") };
  }).filter((m) => m.flags.length);
}

// =================================================================== dashboard
export function dashboardStats(d, doctorId = null) {
  const ds = d10(d); const ap = S().appointments.filter((a) => a.appt_date === ds && (!doctorId || a.doctor_id === doctorId)); const tk = S().tokens.filter((t) => t.token_date === ds && (!doctorId || t.doctor_id === doctorId));
  return {
    appointments: ap.filter((a) => a.status !== "Cancelled").length, waiting: tk.filter((t) => t.status === "Waiting").length, in_consultation: tk.filter((t) => t.status === "In Consultation").length,
    completed: ap.filter((a) => a.status === "Completed").length, cancelled: ap.filter((a) => ["Cancelled", "No Show"].includes(a.status)).length,
    collection: collectionOn(ds, doctorId), pending: pendingTotal(doctorId), new_patients: S().patients.filter((p) => p.created_at.slice(0, 10) === ds).length,
  };
}
export const usersList = () => S().users.map((u) => ({ id: u.id, username: u.username, full_name: u.full_name, role: u.role, doctor: docName(u.doctor_id), doctor_id: u.doctor_id, is_active: u.is_active, last_login: u.last_login, created_at: u.created_at })).sort((a, b) => a.role.localeCompare(b.role) || a.username.localeCompare(b.username));
export function setUserActive(userId, active, actor = null) {
  const u = S().users.find((x) => x.id === userId); if (!u) return;
  u.is_active = active ? 1 : 0;
  if (!active) for (const s of S().sessions) if (s.user_id === userId) s.revoked = 1;
  store.audit(active ? "activate" : "deactivate", "user", userId, null, actor); store.commit();
}
export function updateUser(userId, fullName, role, doctorId = null, actor = null) {
  if (!ROLES.includes(role)) throw err("err.invalid_role");
  const u = S().users.find((x) => x.id === userId); if (!u) return;
  Object.assign(u, { full_name: cleanText(fullName, 100), role, doctor_id: role === "doctor" ? (doctorId || null) : null });
  store.audit("update", "user", userId, { role }, actor); store.commit();
}

// ===================================================================== reports
export const registrationsBetween = (start, end) => { const s = d10(start), e = d10(end); return S().patients.filter((p) => p.created_at.slice(0, 10) >= s && p.created_at.slice(0, 10) <= e).sort((a, b) => cmp(a.created_at, b.created_at)); };
export function doctorWise(start, end, doctorId = null) {
  const s = d10(start), e = d10(end);
  return doctors(false).filter((d) => !doctorId || d.id === doctorId).map((d) => {
    const ap = S().appointments.filter((a) => a.doctor_id === d.id && a.appt_date >= s && a.appt_date <= e);
    let coll = 0; for (const p of S().payments) { const day = p.paid_at.slice(0, 10); if (day < s || day > e) continue; const i = byId("invoices", p.invoice_id); if (i && i.doctor_id === d.id) coll += p.amount; }
    return { doctor_id: d.id, doctor: d.name, appointments: ap.length, completed: ap.filter((a) => a.status === "Completed").length, cancelled: ap.filter((a) => ["Cancelled", "No Show"].includes(a.status)).length,
      consultations: S().consultations.filter((c) => c.doctor_id === d.id && c.visit_date >= s && c.visit_date <= e).length, collection: round2(coll) };
  }).sort((a, b) => b.appointments - a.appointments);
}
export function auditRecent(limit = 200, entity = null, search = "") {
  const q = String(search || "").trim().toLowerCase();
  return S().audit_log.filter((r) => (!entity || r.entity === entity) && (!q || (r.username || "").toLowerCase().includes(q) || r.action.toLowerCase().includes(q) || (r.details || "").toLowerCase().includes(q) || (r.entity_id || "").toLowerCase().includes(q))).sort((a, b) => b.id - a.id).slice(0, limit);
}
export const auditEntities = () => [...new Set(S().audit_log.map((r) => r.entity))].sort();
export function globalSearch(q, limit = 5) {
  q = String(q || "").trim().toLowerCase(); if (!q) return { patients: [], invoices: [], prescriptions: [] };
  return { patients: searchPatients(q, limit), invoices: invoicesList("0000-01-01", "9999-12-31", null, q).slice(0, limit), prescriptions: prescriptionsList("0000-01-01", "9999-12-31", null, q).slice(0, limit) };
}
