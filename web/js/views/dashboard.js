/* Dashboard: live KPIs, schedule, queue, collection chart, availability and reminders (modules/dashboard.py). */
import { freshView, esc, money, fmtDate, fmtTime, fmtDay, pageHead, section, kpiRow, listRow, emptyState, statusBadge, badge, avatar, tokenChip, btn, dateInput, t, icon } from "../ui.js";
import { columnChart, mountCharts } from "../charts.js";
import { todayISO, addDays } from "../store.js";

export function render(_root, app) {
  const root = freshView(); const { repo, store } = app;
  const st = app.ui.dashboard || (app.ui.dashboard = {});
  const today = todayISO(); const d = st.date || today; const isToday = d === today;
  const doctorId = app.isDoctor() ? app.user.doctor_id : null;
  const s = repo.dashboardStats(d, doctorId); const label = isToday ? t("today") : fmtDate(d);
  const appts = repo.appointmentsForDate(d, doctorId);
  const q = repo.queueForDate(d, doctorId, ["Waiting", "In Consultation"]);
  const coll = repo.dailyCollection(addDays(d, -13), d, doctorId);
  let docs = repo.doctors(); if (doctorId) docs = docs.filter((x) => x.id === doctorId);
  const recent = repo.recentPatients(6);
  const window_ = parseInt(store.getSetting("follow_up_window_days", "7")) || 7;
  const fus = repo.upcomingFollowUps(addDays(d, -3), addDays(d, window_), doctorId);

  root.innerHTML = `${pageHead(t("dashboard"), `${store.settings.clinic_name} · ${fmtDate(d, true)}`, `<div class="field" style="min-width:170px">${dateInput("date", d, 'id="dashDate"')}</div>${isToday ? "" : btn(t("today"), { attrs: 'id="dashToday"', cls: "sm" })}`, "layout-dashboard")}
  ${kpiRow([
    { label: isToday ? t("todays_appointments") : t("appointments"), value: s.appointments, ic: "calendar", tone: "primary", hint: `${s.completed} ${t("completed").toLowerCase()} · ${s.cancelled} ${t("cancelled").toLowerCase()}` },
    { label: t("patients_waiting"), value: s.waiting, ic: "hourglass", tone: "warning", hint: `${s.in_consultation} ${t("in_consultation").toLowerCase()}` },
    { label: t("completed_visits"), value: s.completed, ic: "circle-check", tone: "success", hint: label },
    { label: isToday ? t("todays_collection") : t("daily_collection"), value: money(s.collection), ic: "wallet", tone: "primary", hint: label },
    { label: t("pending_payments"), value: money(s.pending), ic: "credit-card", tone: "danger", hint: t("all") },
  ])}
  <div class="grid grid-8-5">
    <div class="card">${section(`${t("todays_schedule")} · ${label}`, "calendar", appts.length)}
      ${appts.length ? `<div class="list">${appts.map((r) => listRow({ title: `${esc(r.patient)} <span class="faint num">${esc(r.patient_code)}</span>`, sub: `${esc(r.doctor)} · ${esc(statusLabel(r.visit_type))}`,
        lead: `<span class="time num">${fmtTime(r.appt_time)}</span>${r.token_no ? tokenChip(r.token_no) : `<span class="tok ghost">${icon("user", 16)}</span>`}`, value: statusBadge(r.status), attrs: `class="row clickable" data-patient="${r.patient_id}"` })).join("")}</div>` : emptyState(t("no_appointments_today"), "", "calendar")}
    </div>
    <div class="card">${section(t("live_queue"), "ticket", q.length)}
      ${q.length ? `<div class="list">${q.map((r) => listRow({ title: esc(r.patient), sub: esc(r.doctor), lead: tokenChip(r.token_no), value: statusBadge(r.status) })).join("")}</div>` : emptyState(t("queue_empty"), "", "ticket")}
      ${app.canView("queue") && q.length ? `<div class="mt">${btn(t("go_to_queue"), { ic: "arrow-right", cls: "sm block", attrs: 'data-nav="queue"' })}</div>` : ""}
    </div>
  </div>
  <div class="grid grid-8-5 mt">
    <div class="card">${section(`${t("daily_collection")} · ${t("last_days", { n: 14 })}`, "trending-up")}
      ${coll.some((c) => c.amount) ? columnChart({ items: coll.map((c) => ({ label: fmtDay(c.day), value: c.amount })), height: 250, fmt: (v) => money(v) }) : emptyState(t("no_data"), "", "trending-up")}
    </div>
    <div class="card">${section(t("doctor_availability"), "stethoscope")}
      ${docs.length ? `<div class="list">${docs.map((doc) => { const [status, hours] = repo.doctorStatus(doc.id, d); return listRow({ title: esc(doc.name), sub: `${esc(doc.specialization)}${hours ? ` · <span class="num">${esc(hours)}</span>` : ""}`, lead: avatar(doc.name, 36, doc.photo_data), value: badge(t(status), { available: "success", on_leave: "danger", off_today: "neutral", in_consultation: "warning" }[status]) }); }).join("")}</div>` : emptyState(t("no_data"), "", "stethoscope")}
    </div>
  </div>
  <div class="grid grid-2 mt">
    <div class="card">${section(t("recent_registrations"), "user-plus")}
      ${recent.length ? `<div class="list">${recent.map((p) => listRow({ title: `${esc(p.full_name)} <span class="faint num">${esc(p.patient_code)}</span>`, sub: `<span class="num">${esc(p.phone)}</span> · ${fmtDate(p.created_at)}`, avatarName: p.full_name, attrs: `class="row clickable" data-patient="${p.id}"` })).join("")}</div>` : emptyState(t("no_patients"), "", "users")}
    </div>
    <div class="card">${section(`${t("follow_up_reminders")} · ${t("next_days", { n: window_ })}`, "bell")}
      ${fus.length ? `<div class="list">${fus.slice(0, 8).map((r) => { const overdue = r.follow_up_date < d; const b = badge(r.booked ? t("booked") : overdue ? t("overdue") : t("due"), r.booked ? "success" : overdue ? "danger" : "warning"); return listRow({ title: `${esc(r.patient)} <span class="faint num">${esc(r.patient_code)}</span>`, sub: `${esc(r.doctor)} · <span class="num">${esc(r.phone)}</span>`, lead: `<span class="time num">${fmtDate(r.follow_up_date)}</span>`, value: b, attrs: `class="row clickable" data-patient="${r.patient_id}"` }); }).join("")}</div>${fus.length > 8 ? `<div class="faint mt">${esc(t("more_n", { n: fus.length - 8 }))}</div>` : ""}` : emptyState(t("no_follow_ups"), "", "bell")}
    </div>
  </div>`;
  mountCharts(root);
  root.querySelector("#dashDate").addEventListener("change", (e) => { st.date = e.target.value || today; app.refresh(); });
  const tb = root.querySelector("#dashToday"); if (tb) tb.addEventListener("click", () => { st.date = today; app.refresh(); });
  root.addEventListener("click", (e) => { const r = e.target.closest("[data-patient]"); if (r && !e.target.closest("[data-nav]")) app.navigate("patients", { id: r.dataset.patient }); });
}
import { statusLabel } from "../i18n.js";
