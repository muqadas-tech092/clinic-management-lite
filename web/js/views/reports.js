/* Reports and analytics: operational, financial and stock reports with lightweight SVG charts, CSV export and a
   print-ready tabular report (modules/reports.py). Everything is computed from the stored records. */
import { freshView, esc, money, fmtDate, fmtDay, fmtMonth, pageHead, section, kpiRow, listRow, emptyState, statusBadge, btn, field, select, dateInput, table, tabsBar, bindTabs, rangeFor, printPreview, toCSV, downloadFile, notice, t, statusLabel } from "../ui.js";
import { columnChart, groupedColumnChart, hbarChart, lineAreaChart, donutChart, mountCharts } from "../charts.js";
import { todayISO, addDays, weekday, daysBetween } from "../store.js";
import { reportHTML } from "../print.js";
import { doctorOptionsFor } from "./appointments.js";

const PRESETS = ["this_month", "last_7", "last_30", "this_week", "last_month", "custom"];
/** Group rows by period: returns [{key, label, rows}] sorted by key. */
function groupBy(rows, dateOf, gran) {
  const m = new Map();
  for (const r of rows) {
    const d = dateOf(r).slice(0, 10); let key, label;
    if (gran === "weekly") { key = addDays(d, -weekday(d)); label = `Wk ${fmtDay(key)}`; } else if (gran === "monthly") { key = d.slice(0, 7); label = fmtMonth(key); } else { key = d; label = fmtDay(d); }
    if (!m.has(key)) m.set(key, { key, label, rows: [] }); m.get(key).rows.push(r);
  }
  return [...m.values()].sort((a, b) => (a.key < b.key ? -1 : 1));
}
const exportBar = (key) => `<div class="btn-group mt">${btn(t("download_csv"), { ic: "file-spreadsheet", cls: "sm", attrs: `data-csv="${key}"` })}${btn(t("print_report"), { ic: "printer", cls: "sm", attrs: `data-print="${key}"` })}</div>`;

export function render(_root, app) {
  const root = freshView(); const { repo } = app; const today = todayISO(); const s = app.settings;
  const st = app.ui.reports || (app.ui.reports = { preset: "this_month", from: addDays(today, -29), to: today, doctor: 0, gran: "daily", tab: "appointments" });
  const lock = app.isDoctor() ? app.user.doctor_id : null;
  const [start, end] = st.preset === "custom" ? rangeFor("custom", { from: st.from, to: st.to }) : rangeFor(st.preset);
  const did = lock || Number(st.doctor) || null; const docName = did ? (repo.doctor(did) || {}).name : "";
  const sub = `${fmtDate(start)} - ${fmtDate(end)}${docName ? ` · ${docName}` : ""}`;
  const tabs = [["appointments", t("report_appointments")], ["registrations", t("report_registrations")], ["doctors", t("report_doctors")]];
  if (app.canView("billing")) tabs.push(["collection", t("report_collection")], ["outstanding", t("report_outstanding")]);
  if (app.canView("inventory")) tabs.push(["stock", t("report_stock")]);
  if (!tabs.some((x) => x[0] === st.tab)) st.tab = "appointments";
  let pane = ""; const exp = {};
  if (st.tab === "appointments") {
    const ap = repo.appointmentsBetween(start, end, did);
    if (!ap.length) pane = emptyState(t("no_data"), "", "calendar");
    else {
      const total = ap.length, comp = ap.filter((a) => a.status === "Completed").length, canc = ap.filter((a) => ["Cancelled", "No Show"].includes(a.status)).length;
      const grp = groupBy(ap, (a) => a.appt_date, st.gran).map((g) => ({ period: g.label, appointments: g.rows.length, completed: g.rows.filter((a) => a.status === "Completed").length, cancelled: g.rows.filter((a) => ["Cancelled", "No Show"].includes(a.status)).length }));
      const count = (k) => { const m = new Map(); for (const a of ap) m.set(a[k], (m.get(a[k]) || 0) + 1); return [...m.entries()].map(([label, value]) => ({ label: statusLabel(label), value })).sort((a, b) => b.value - a.value); };
      pane = kpiRow([{ label: t("appointments"), value: total, ic: "calendar", tone: "primary", hint: sub }, { label: t("completed_visits"), value: comp, ic: "circle-check", tone: "success", hint: `${Math.round(comp / total * 100)}%` }, { label: t("cancelled_no_show"), value: canc, ic: "circle-x", tone: "danger", hint: `${Math.round(canc / total * 100)}%` }, { label: t("walk_ins"), value: ap.filter((a) => a.visit_type === "Walk-in").length, ic: "ticket", tone: "neutral" }])
        + groupedColumnChart({ items: grp.map((g) => ({ label: g.period, values: [g.completed, g.cancelled] })), series: [t("completed"), t("cancelled_no_show")], colors: ["#087F8C", "#C6862A"], height: 280 })
        + `<div class="grid grid-2 mt"><div>${section(t("visit_type"), "list")}${hbarChart({ items: count("visit_type") })}</div><div>${section(t("status"), "list")}${hbarChart({ items: count("status"), color: "#5B7483" })}</div></div><div class="mt">${table({ columns: [{ label: t("period") }, { label: t("appointments"), cls: "num" }, { label: t("completed"), cls: "num" }, { label: t("cancelled_no_show"), cls: "num" }], rows: grp.map((g) => ({ cells: [esc(g.period), String(g.appointments), String(g.completed), String(g.cancelled)] })) })}</div>` + exportBar("appointments");
      exp.appointments = { title: "Appointments report", rows: grp, columns: [{ key: "period", label: t("period") }, { key: "appointments", label: t("appointments"), num: true }, { key: "completed", label: t("completed"), num: true }, { key: "cancelled", label: t("cancelled_no_show"), num: true }], summary: [[t("appointments"), total], [t("completed"), comp], [t("cancelled_no_show"), canc]] };
    }
  } else if (st.tab === "registrations") {
    const regs = repo.registrationsBetween(start, end);
    if (!regs.length) pane = emptyState(t("no_data"), "", "user-plus");
    else {
      const grp = groupBy(regs, (p) => p.created_at, st.gran); const byG = new Map(); for (const p of regs) byG.set(p.gender, (byG.get(p.gender) || 0) + 1);
      pane = kpiRow([{ label: t("recent_registrations"), value: regs.length, ic: "user-plus", tone: "primary", hint: sub }, ...[...byG.entries()].map(([g, n]) => ({ label: statusLabel(g), value: n, ic: "user", tone: "neutral" }))])
        + columnChart({ items: grp.map((g) => ({ label: g.label, value: g.rows.length })), height: 260 })
        + `<div class="mt">${table({ columns: [{ label: t("patient_id"), cls: "num" }, { label: t("name") }, { label: t("gender") }, { label: t("phone"), cls: "num" }, { label: t("registered") }], rows: regs.map((p) => ({ cells: [esc(p.patient_code), esc(p.full_name), esc(statusLabel(p.gender)), esc(p.phone), fmtDate(p.created_at)] })) })}</div>` + exportBar("registrations");
      exp.registrations = { title: "Patient registrations", rows: regs.map((p) => ({ ...p, registered: p.created_at.slice(0, 10) })), columns: [{ key: "patient_code", label: t("patient_id") }, { key: "full_name", label: t("name") }, { key: "gender", label: t("gender") }, { key: "phone", label: t("phone") }, { key: "registered", label: t("registered") }], summary: [[t("recent_registrations"), regs.length]] };
    }
  } else if (st.tab === "doctors") {
    const dw = repo.doctorWise(start, end, did); const bill = app.canView("billing");
    if (!dw.length) pane = emptyState(t("no_data"), "", "stethoscope");
    else {
      pane = `<div class="grid grid-2"><div>${section(t("visits_by_doctor"), "stethoscope")}${hbarChart({ items: dw.map((d) => ({ label: d.doctor, value: d.completed })) })}</div>${bill ? `<div>${section(t("collection_by_doctor"), "wallet")}${hbarChart({ items: dw.map((d) => ({ label: d.doctor, value: d.collection })), color: "#4C5FD5", fmt: (v) => money(v) })}</div>` : ""}</div>
        <div class="mt">${table({ columns: [{ label: t("doctor") }, { label: t("appointments"), cls: "num" }, { label: t("completed"), cls: "num" }, { label: t("cancelled_no_show"), cls: "num" }, { label: t("consultations"), cls: "num" }, ...(bill ? [{ label: t("collection"), cls: "num" }] : [])], rows: dw.map((d) => ({ cells: [esc(d.doctor), String(d.appointments), String(d.completed), String(d.cancelled), String(d.consultations), ...(bill ? [money(d.collection)] : [])] })) })}</div>` + exportBar("doctors");
      exp.doctors = { title: "Doctor-wise report", rows: dw.map((d) => ({ ...d, collection: bill ? money(d.collection) : undefined })), columns: [{ key: "doctor", label: t("doctor") }, { key: "appointments", label: t("appointments"), num: true }, { key: "completed", label: t("completed"), num: true }, { key: "cancelled", label: t("cancelled_no_show"), num: true }, { key: "consultations", label: t("consultations"), num: true }, ...(bill ? [{ key: "collection", label: t("collection"), num: true }] : [])], summary: [] };
    }
  } else if (st.tab === "collection") {
    const daily = repo.dailyCollection(start, end, did); const byMethod = repo.collectionByMethod(start, end, did); const inv = repo.invoicesList(start, end, null, "", did);
    const collected = daily.reduce((x, d) => x + d.amount, 0); const billed = inv.reduce((x, i) => x + i.total, 0); const disc = inv.reduce((x, i) => x + i.discount_amount, 0);
    const grp = groupBy(daily, (d) => d.day, st.gran).map((g) => ({ period: g.label, collection: g.rows.reduce((x, d) => x + d.amount, 0) }));
    const monthly = repo.monthlyRevenue(addDays(today, -365), did);
    pane = kpiRow([{ label: t("report_collection"), value: money(collected), ic: "wallet", tone: "primary", hint: sub }, { label: t("billed"), value: money(billed), ic: "receipt", tone: "neutral", hint: t("n_invoices", { n: inv.length }) }, { label: t("discount"), value: money(disc), ic: "percent", tone: "warning" }, { label: t("avg_per_day"), value: money(collected / Math.max(daily.length, 1)), ic: "trending-up", tone: "neutral" }])
      + (collected ? columnChart({ items: grp.map((g) => ({ label: g.period, value: g.collection })), height: 280, fmt: (v) => money(v) }) : emptyState(t("no_data"), "", "wallet"))
      + `<div class="grid grid-2 mt"><div>${section(t("payment_method"), "credit-card")}${byMethod.length ? donutChart({ items: byMethod.map((m) => ({ label: statusLabel(m.method), value: m.amount })), fmt: (v) => money(v), otherLabel: t("other") }) : emptyState(t("no_data"), "", "credit-card")}</div><div>${section(t("monthly_revenue"), "trending-up")}${monthly.length ? lineAreaChart({ labels: monthly.map((m) => fmtMonth(m.month)), series: [{ label: t("collection"), values: monthly.map((m) => m.amount) }], height: 220, fmt: (v) => money(v) }) : emptyState(t("no_data"), "", "trending-up")}</div></div>
      <div class="mt">${table({ columns: [{ label: t("period") }, { label: t("collection"), cls: "num" }], rows: grp.map((g) => ({ cells: [esc(g.period), money(g.collection)] })) })}</div>` + exportBar("collection");
    exp.collection = { title: "Collection report", rows: grp.map((g) => ({ period: g.period, collection: money(g.collection) })), columns: [{ key: "period", label: t("period") }, { key: "collection", label: t("collection"), num: true }], summary: [[t("collection"), money(collected)], [t("billed"), money(billed)], [t("discount"), money(disc)]] };
  } else if (st.tab === "outstanding") {
    const out = repo.outstandingInvoices(did).map((i) => ({ ...i, days: daysBetween(i.invoice_date, today) }));
    if (!out.length) pane = emptyState(t("no_outstanding"), "", "circle-check");
    else {
      const bins = [["0-7", 0, 7], ["8-30", 8, 30], ["31-90", 31, 90], ["90+", 91, 100000]].map(([l, a, b]) => ({ label: `${l} ${t("days").toLowerCase()}`, value: out.filter((i) => i.days >= a && i.days <= b).reduce((x, i) => x + i.outstanding, 0) }));
      pane = kpiRow([{ label: t("outstanding"), value: money(out.reduce((x, i) => x + i.outstanding, 0)), ic: "credit-card", tone: "danger", hint: t("n_invoices", { n: out.length }) }, ...bins.map((b) => ({ label: b.label, value: money(b.value), ic: "clock", tone: "neutral" }))])
        + table({ columns: [{ label: t("invoice"), cls: "num" }, { label: t("date") }, { label: t("patient") }, { label: t("patient_id"), cls: "num" }, { label: t("phone"), cls: "num" }, { label: t("total"), cls: "num" }, { label: t("received"), cls: "num" }, { label: t("outstanding"), cls: "num" }, { label: t("days"), cls: "num" }], rows: out.map((i) => ({ attrs: `class="clickable" data-inv="${i.id}"`, cells: [esc(i.invoice_no), fmtDate(i.invoice_date), esc(i.patient), esc(i.patient_code), esc(i.phone), money(i.total), money(i.paid), money(i.outstanding), String(i.days)] })) }) + exportBar("outstanding");
      exp.outstanding = { title: "Outstanding payments", rows: out.map((i) => ({ ...i, total: money(i.total), paid: money(i.paid), outstanding: money(i.outstanding) })), columns: [{ key: "invoice_no", label: t("invoice") }, { key: "invoice_date", label: t("date") }, { key: "patient", label: t("patient") }, { key: "patient_code", label: t("patient_id") }, { key: "phone", label: t("phone") }, { key: "total", label: t("total"), num: true }, { key: "paid", label: t("received"), num: true }, { key: "outstanding", label: t("outstanding"), num: true }, { key: "days", label: t("days"), num: true }], summary: [[t("outstanding"), money(out.reduce((x, i) => x + i.outstanding, 0))], [t("invoices"), out.length]] };
    }
  } else {
    const meds = repo.medicines(); const alerts = repo.stockAlerts(); const flags = new Map(alerts.map((a) => [a.id, a.alert]));
    if (!meds.length) pane = emptyState(t("no_data"), "", "package");
    else {
      const byCat = new Map(); for (const m of meds) byCat.set(m.category, (byCat.get(m.category) || 0) + m.quantity);
      pane = `<div class="grid grid-2"><div>${section(t("units_by_category"), "package")}${hbarChart({ items: [...byCat.entries()].map(([label, value]) => ({ label: statusLabel(label), value })).sort((a, b) => b.value - a.value) })}</div><div>${section(t("warnings"), "triangle-alert")}${alerts.length ? `<div class="list">${alerts.slice(0, 8).map((a) => listRow({ title: esc(a.name), sub: `<span class="num">${esc(a.sku)}</span> · <span class="num">${a.quantity}</span> ${t("units")}`, value: a.flags.map((f) => statusBadge(f)).join(" ") })).join("")}</div>` : emptyState(t("no_warnings"), "", "circle-check")}</div></div>
        <div class="mt">${table({ columns: [{ label: t("sku"), cls: "num" }, { label: t("name") }, { label: t("category") }, { label: t("quantity"), cls: "num" }, { label: t("reorder"), cls: "num" }, { label: t("expiry") }, { label: t("value"), cls: "num" }, { label: t("alert") }], rows: meds.map((m) => ({ cells: [esc(m.sku), esc(m.name), esc(statusLabel(m.category)), String(m.quantity), String(m.reorder_level), m.expiry_date ? fmtDate(m.expiry_date) : "-", money(m.quantity * m.purchase_price), esc(flags.get(m.id) || "")] })) })}</div>` + exportBar("stock");
      exp.stock = { title: "Stock report", rows: meds.map((m) => ({ ...m, value: money(m.quantity * m.purchase_price), alert: flags.get(m.id) || "", expiry_date: m.expiry_date || "" })), columns: [{ key: "sku", label: t("sku") }, { key: "name", label: t("name") }, { key: "category", label: t("category") }, { key: "quantity", label: t("quantity"), num: true }, { key: "reorder_level", label: t("reorder"), num: true }, { key: "expiry_date", label: t("expiry") }, { key: "value", label: t("value"), num: true }, { key: "alert", label: t("alert") }], summary: [[t("items"), meds.length], [t("units"), meds.reduce((x, m) => x + m.quantity, 0)], [t("warnings"), alerts.length]] };
    }
  }
  root.innerHTML = `${pageHead(t("reports"), s.clinic_name, "", "bar-chart")}
  <div class="card tight mb"><div class="toolbar"><div class="field narrow">${select("preset", PRESETS.map((p) => [p, t(p)]), st.preset)}</div><div class="field narrow">${dateInput("from", start, st.preset === "custom" ? "" : "disabled")}</div><div class="field narrow">${dateInput("to", end, st.preset === "custom" ? "" : "disabled")}</div>${lock ? "" : `<div class="field narrow">${select("doctor", doctorOptionsFor(app, true), st.doctor)}</div>`}<div class="field narrow">${select("gran", [["daily", t("daily")], ["weekly", t("weekly")], ["monthly", t("monthly")]], st.gran)}</div></div></div>
  <div class="card">${tabsBar("tab", tabs, st.tab)}${start > end ? notice(t("start_before_end"), "error", "circle-alert") : pane}</div>`;
  mountCharts(root); bindTabs(root, st, "tab", () => app.refresh());
  for (const name of ["preset", "from", "to", "doctor", "gran"]) { const el = root.querySelector(`[name="${name}"]`); if (el) el.addEventListener("change", () => { st[name] = el.value || st[name]; if (name === "preset" && el.value === "custom") { st.from = start; st.to = end; } app.refresh(); }); }
  root.addEventListener("click", (e) => {
    const inv = e.target.closest("[data-inv]"); if (inv) { app.navigate("billing", { id: inv.dataset.inv }); return; }
    const c = e.target.closest("[data-csv]"); if (c && exp[c.dataset.csv]) { const x = exp[c.dataset.csv]; downloadFile(`${c.dataset.csv}_${today}.csv`, toCSV(x.rows, x.columns.map((k) => k.key), x.columns.map((k) => k.label)), "text/csv"); return; }
    const p = e.target.closest("[data-print]"); if (p && exp[p.dataset.print]) { const x = exp[p.dataset.print]; printPreview(reportHTML(x.title, sub, x.columns, x.rows, s, x.summary), { title: x.title, size: "A4", orientation: "landscape" }); }
  });
}
