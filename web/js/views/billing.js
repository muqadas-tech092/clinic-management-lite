/* Billing and payments: invoices, administrator-authorized discounts, partial payments, receipts, daily
   collection and outstanding balances (modules/billing.py). */
import { freshView, esc, money, fmtDate, fmtTime, fmtDateTime, pageHead, section, kpiRow, emptyState, statusBadge, btn, field, input, select, textarea, dateInput, notice, table, kv, tabsBar, bindTabs, openModal, closeModal, confirmDialog, toast, formValues, showFormError, clearFormError, printPreview, run, toCSV, downloadFile, t, statusLabel, icon } from "../ui.js";
import { todayISO, addDays, PAYMENT_METHODS, INVOICE_STATUSES, toFloat, round2 } from "../store.js";
import { receiptHTML } from "../print.js";
import { patientPicker, doctorOptionsFor } from "./appointments.js";

export function showReceipt(app, invId, lang) {
  const inv = app.repo.invoice(invId);
  printPreview(receiptHTML(inv, app.settings, lang), { title: inv.invoice_no, size: app.settings.paper_size || "A5" });
}
const methodOptions = () => PAYMENT_METHODS.map((m) => [m, statusLabel(m)]);

// ------------------------------------------------------------ new invoice
export function openInvoiceDialog(app, { patientId = null, onSaved = null } = {}) {
  const { repo, auth } = app; const s = app.settings; const services = repo.services(); const unbilled = repo.unbilledVisits(todayISO());
  const state = { pre: null, authorizedBy: "", authName: "" };
  const maxFree = toFloat(s.max_discount_without_auth, 0);
  openModal({ title: t("new_invoice"), ic: "receipt", size: "lg", body: `<form id="invForm">
      ${unbilled.length ? `<div class="field mb">${field(t("unbilled_visits"), select("unbilled", [["", t("choose_visit")], ...unbilled.map((u) => [u.appointment_id, `${fmtTime(u.appt_time)} · ${u.patient} (${u.patient_code}) · ${u.doctor} · ${statusLabel(u.status)}`])], ""))}</div>` : ""}
      <div id="pick"></div>
      <div class="form-grid mt">${field(t("doctor"), select("doctor_id", [["", "-"], ...doctorOptionsFor(app)], app.isDoctor() ? app.user.doctor_id : ""))}${field(`${t("consultation_fee")} (${esc(s.currency_symbol)})`, input("fee", s.default_consultation_fee || 0, 'type="number" min="0" step="1" class="num"'))}</div>
      <div class="field mt"><label>${esc(t("services"))}</label><div class="list">${services.map((sv) => `<label class="row" style="cursor:pointer"><input type="checkbox" name="svc_${sv.id}" data-svc="${sv.id}" data-price="${sv.price}" data-name="${esc(sv.name)}" style="width:18px;height:18px;accent-color:var(--primary)"/><div class="body"><div class="title">${esc(sv.name)}</div></div><div class="end num">${money(sv.price)}</div><input type="number" name="qty_${sv.id}" value="1" min="1" step="1" class="num" style="width:64px;min-height:34px;border:1px solid var(--line-strong);border-radius:8px;padding:4px 8px" hidden/></label>`).join("")}</div></div>
      <div class="form-grid mt">${field(t("other_charge"), input("extra_desc", "", 'maxlength="100"'), { optional: true })}${field(`${t("amount")} (${esc(s.currency_symbol)})`, input("extra_amt", "", 'type="number" min="0" step="1" class="num"'))}</div>
      <div class="form-grid mt">${field(`${t("discount")} (${esc(s.currency_symbol)})`, input("discount", "0", 'type="number" min="0" step="1" class="num"'))}${field(t("reason"), input("discount_reason", "", 'maxlength="120"'))}</div>
      <div id="authBox" class="mt" hidden></div>
      <div class="form-grid-3 mt">${field(`${t("received")} (${esc(s.currency_symbol)})`, input("received", "", 'type="number" min="0" step="1" class="num"'))}${field(t("payment_method"), select("method", methodOptions(), "Cash"))}${field(t("reference"), input("reference", "", 'maxlength="100"'), { optional: true })}</div>
      <div class="mt">${field(t("notes"), input("notes", "", 'maxlength="300"'), { optional: true })}</div>
      <div class="card soft mt" id="summary"></div></form>`,
    footer: btn(t("cancel"), { attrs: "data-close" }) + btn(t("save"), { ic: "save", cls: "primary", attrs: "data-save" }),
    onMount: (m) => {
      const form = m.querySelector("#invForm"); const picker = patientPicker(m.querySelector("#pick"), app, { selected: patientId });
      const calc = () => {
        const fee = toFloat(form.fee.value, 0); let svc = 0; const items = [];
        form.querySelectorAll("[data-svc]").forEach((c) => { const qty = form[`qty_${c.dataset.svc}`]; qty.hidden = !c.checked; if (c.checked) { const q = Math.max(1, parseInt(qty.value) || 1); items.push({ description: c.dataset.name, qty: q, unit_price: toFloat(c.dataset.price) }); svc += q * toFloat(c.dataset.price); } });
        const extraAmt = toFloat(form.extra_amt.value, 0); if (form.extra_desc.value.trim() && extraAmt > 0) { items.push({ description: form.extra_desc.value.trim(), qty: 1, unit_price: extraAmt }); svc += extraAmt; }
        const subtotal = round2(fee + svc); const discount = Math.min(Math.max(0, toFloat(form.discount.value, 0)), subtotal); const total = round2(subtotal - discount);
        if (form.received.dataset.touched !== "1") form.received.value = total;
        const received = Math.min(Math.max(0, toFloat(form.received.value, 0)), total);
        form.discount_reason.disabled = discount <= 0;
        const box = m.querySelector("#authBox");
        if (discount > 0) {
          if (app.isAdmin() || discount <= maxFree) { state.authorizedBy = app.user.username; box.hidden = false; box.innerHTML = notice(`${t("authorized_by")}: ${app.user.full_name}`, "success", "shield-check"); }
          else if (state.authorizedBy) { box.hidden = false; box.innerHTML = notice(`${t("authorized_by")}: ${state.authName}`, "success", "shield-check"); }
          else { box.hidden = false; if (!box.querySelector("#authUser")) box.innerHTML = `${notice(t("discount_auth"), "warning", "lock")}<div class="form-grid-3 mt">${field(t("admin_username"), input("auth_user", "", 'id="authUser" autocomplete="off"'))}${field(t("admin_password"), input("auth_pw", "", 'type="password" id="authPw" autocomplete="new-password"'))}<div class="field"><label>&nbsp;</label>${btn(t("authorize"), { ic: "key-round", attrs: 'id="authBtn"' })}</div></div><div id="authMsg"></div>`; }
        } else { state.authorizedBy = ""; box.hidden = true; box.innerHTML = ""; }
        m.querySelector("#summary").innerHTML = kv([[t("consultation_fee"), money(fee)], [t("services"), money(svc)], [t("discount"), `- ${money(discount)}`], [t("total"), `<b style="font-size:1.05rem;color:var(--primary)">${money(total)}</b>`, true], [t("received"), money(received)], [t("outstanding"), `<span class="danger-text">${money(total - received)}</span>`, true]]);
        return { fee, items, discount, total, received };
      };
      form.addEventListener("input", (e) => { if (e.target.name === "received") e.target.dataset.touched = "1"; calc(); });
      form.addEventListener("change", calc);
      form.addEventListener("click", async (e) => {
        if (e.target.closest("#authBtn")) { const ok = await auth.authorizeAdmin(form.auth_user.value, form.auth_pw.value); const msg = m.querySelector("#authMsg"); if (ok) { state.authorizedBy = ok.username; state.authName = ok.full_name; calc(); } else msg.innerHTML = notice(t("authorization_failed"), "error", "circle-alert"); }
      });
      const ub = form.querySelector('[name="unbilled"]'); if (ub) ub.addEventListener("change", () => { const u = unbilled.find((x) => String(x.appointment_id) === ub.value); state.pre = u || null; if (u) { picker.set(u.patient_id); form.doctor_id.value = u.doctor_id; form.fee.value = u.consultation_fee; form.received.dataset.touched = ""; } calc(); });
      form.doctor_id.addEventListener("change", () => { const d = repo.doctor(Number(form.doctor_id.value)); if (d && !state.pre) { form.fee.value = d.consultation_fee; form.received.dataset.touched = ""; calc(); } });
      if (app.isDoctor()) { const d = repo.doctor(app.user.doctor_id); if (d) form.fee.value = d.consultation_fee; }
      calc();
      const save = () => {
        const { fee, items, discount, received } = calc(); const v = formValues(form);
        try {
          if (!picker.get()) throw new Error(t("err.select_patient"));
          const id = repo.createInvoice({ patientId: picker.get(), doctorId: Number(v.doctor_id) || null, consultationFee: fee, items, discount, discountReason: v.discount_reason, authorizedBy: state.authorizedBy,
            consultationId: state.pre ? state.pre.consultation_id : null, appointmentId: state.pre ? state.pre.appointment_id : null, notes: v.notes,
            payment: received > 0 ? { amount: received, method: v.method, reference: v.reference } : null, actor: app.user });
          closeModal(); toast(t("invoice_saved")); if (onSaved) onSaved(id);
        } catch (e) { showFormError(form, e); }
      };
      m.querySelector("[data-save]").addEventListener("click", save); form.addEventListener("submit", (e) => { e.preventDefault(); save(); });
    } });
}

// ------------------------------------------------------------ detail
function renderDetail(root, app, id) {
  const { repo } = app; const inv = repo.invoice(id); if (!inv) { app.navigate("billing"); return; }
  const canEdit = app.canEdit("billing"); const urdu = app.settings.show_urdu_on_prints !== "0";
  const rows = []; if (inv.consultation_fee) rows.push([t("consultation_fee"), 1, inv.consultation_fee, inv.consultation_fee]); for (const it of inv.items) rows.push([it.description, it.qty, it.unit_price, it.amount]);
  root.innerHTML = `${pageHead(inv.invoice_no, `${inv.patient_name} · ${inv.patient_code} · ${fmtDate(inv.invoice_date)}`, `${btn(t("back"), { ic: "arrow-left", attrs: 'data-nav="billing"' })}<span style="align-self:center">${statusBadge(inv.status)}</span>`, "receipt")}
  <div class="grid grid-3-2">
    <div class="stack">
      <div class="card">${section(t("invoice"), "receipt")}${table({ columns: [{ label: t("description") }, { label: t("qty"), cls: "num" }, { label: t("rate"), cls: "num" }, { label: t("amount"), cls: "num" }], rows: rows.map((r) => ({ cells: [esc(r[0]), String(r[1]), money(r[2]), money(r[3])] })) })}
        <div class="mt">${kv([[t("subtotal"), money(inv.consultation_fee + inv.services_total)], ...(inv.discount_amount ? [[`${t("discount")} (${inv.discount_reason || "-"}, ${t("authorized_by").toLowerCase()}: ${inv.discount_authorized_by})`, `- ${money(inv.discount_amount)}`]] : []), [t("total"), `<b>${money(inv.total)}</b>`, true], [t("received"), money(inv.paid)], [t("outstanding"), `<b class="danger-text">${money(inv.outstanding)}</b>`, true], [t("doctor"), inv.doctor_name || "-"], [t("created_by"), `${inv.created_by_name || "-"} · ${fmtDateTime(inv.created_at)}`]])}</div>${inv.notes ? `<div class="muted mt">${esc(inv.notes)}</div>` : ""}</div>
      <div class="card">${section(t("payment_history"), "wallet", inv.payments.length)}${inv.payments.length ? table({ columns: [{ label: t("date") }, { label: t("payment_method") }, { label: t("reference") }, { label: t("amount"), cls: "num" }, { label: t("received_by") }], rows: inv.payments.map((p) => ({ cells: [fmtDateTime(p.paid_at), esc(statusLabel(p.method)), esc(p.reference || "-"), money(p.amount), esc(p.received_by_name || "-")] })) }) : emptyState(t("no_data"), "", "wallet")}</div>
    </div>
    <div class="stack">
      <div class="card">${section(t("receipt"), "printer")}<div class="btn-group stack">${btn(t("print_en"), { ic: "printer", cls: "primary", attrs: 'data-print="en"' })}${urdu ? btn(t("print_both"), { ic: "printer", attrs: 'data-print="both"' }) + btn(t("print_ur"), { ic: "printer", attrs: 'data-print="ur"' }) : ""}</div></div>
      ${canEdit && ["Unpaid", "Partial"].includes(inv.status) ? `<form class="card" id="payForm">${section(t("record_payment"), "banknote")}<div class="stack">${field(`${t("amount")} (${esc(app.settings.currency_symbol)})`, input("amount", inv.outstanding, `type="number" min="1" max="${inv.outstanding}" step="1" class="num"`))}${field(t("payment_method"), select("method", methodOptions(), "Cash"))}${field(t("reference"), input("reference", "", 'maxlength="100"'), { optional: true })}${btn(t("record_payment"), { ic: "banknote", cls: "primary", type: "submit" })}</div></form>` : ""}
      ${canEdit && inv.status !== "Cancelled" && inv.paid === 0 ? `<details class="panel"><summary>${icon("circle-x", 15)}${esc(t("cancel_invoice"))}</summary><form id="cancelForm" class="stack">${field(t("reason"), input("reason", "", 'maxlength="120" required'))}${btn(t("confirm"), { cls: "danger", type: "submit" })}</form></details>` : ""}
      <div>${btn(t("patient_profile"), { ic: "user", cls: "sm", attrs: `data-nav-patient="${inv.patient_id}"` })}</div>
    </div>
  </div>`;
  root.addEventListener("click", (e) => { const pb = e.target.closest("[data-print]"); if (pb) showReceipt(app, id, pb.dataset.print); const pp = e.target.closest("[data-nav-patient]"); if (pp) app.navigate("patients", { id: pp.dataset.navPatient }); });
  const pf = root.querySelector("#payForm"); if (pf) pf.addEventListener("submit", (e) => { e.preventDefault(); const v = formValues(pf); try { repo.recordPayment(id, v.amount, v.method, v.reference, "", app.user); toast(t("saved")); app.refresh(); } catch (err) { showFormError(pf, err); } });
  const cf = root.querySelector("#cancelForm"); if (cf) cf.addEventListener("submit", async (e) => { e.preventDefault(); const v = formValues(cf); if (await confirmDialog({ title: t("cancel_invoice"), body: `${inv.invoice_no} · ${v.reason}` })) run(() => repo.cancelInvoice(id, v.reason, app.user), t("saved"), () => app.refresh()); });
}

// ------------------------------------------------------------ page
export function render(_root, app) {
  const root = freshView(); const { repo } = app; const today = todayISO();
  if (app.params.id) { renderDetail(root, app, Number(app.params.id)); return; }
  const st = app.ui.billing || (app.ui.billing = {});
  Object.assign(st, { tab: st.tab || "invoices", from: st.from || addDays(today, -7), to: st.to || today, status: st.status || "", q: st.q || "", day: st.day || today });
  const canEdit = app.canEdit("billing"); const lock = app.isDoctor() ? app.user.doctor_id : null;
  if (app.params.new && canEdit) { const pid = app.params.patient; app.params = {}; history.replaceState(null, "", "#/billing"); setTimeout(() => openInvoiceDialog(app, { patientId: pid, onSaved: (id) => app.navigate("billing", { id }) }), 0); }
  let pane = "";
  if (st.tab === "invoices") {
    const list = repo.invoicesList(st.from, st.to, st.status || null, st.q, lock);
    const sum = (k) => list.reduce((s, i) => s + i[k], 0);
    pane = `<div class="toolbar mb"><div class="field narrow">${dateInput("from", st.from)}</div><div class="field narrow">${dateInput("to", st.to)}</div><div class="field narrow">${select("status", [["", t("all")], ...INVOICE_STATUSES.map((x) => [x, statusLabel(x)])], st.status)}</div><div class="field grow">${input("q", st.q, 'placeholder="INV-2026-00001 / name / ID" autocomplete="off"')}</div>${btn(t("download_csv"), { ic: "file-spreadsheet", attrs: 'data-csv="invoices"' })}</div>
      ${list.length ? kpiRow([{ label: t("invoices"), value: list.length, ic: "receipt", tone: "primary", hint: `${fmtDate(st.from)} - ${fmtDate(st.to)}` }, { label: t("total"), value: money(sum("total")), ic: "banknote", tone: "primary" }, { label: t("received"), value: money(sum("paid")), ic: "wallet", tone: "success" }, { label: t("outstanding"), value: money(sum("outstanding")), ic: "credit-card", tone: "danger" }]) +
        table({ columns: [{ label: t("invoice"), cls: "num cell-primary" }, { label: t("date") }, { label: t("patient") }, { label: t("patient_id"), cls: "num" }, { label: t("doctor") }, { label: t("total"), cls: "num" }, { label: t("received"), cls: "num" }, { label: t("outstanding"), cls: "num" }, { label: t("status") }],
          rows: list.slice(0, 300).map((i) => ({ attrs: `class="clickable" data-id="${i.id}"`, cells: [`<b>${esc(i.invoice_no)}</b>`, fmtDate(i.invoice_date), esc(i.patient), esc(i.patient_code), esc(i.doctor || "-"), money(i.total), money(i.paid), money(i.outstanding), statusBadge(i.status)] })) }) : emptyState(t("no_data"), "", "receipt")}`;
    st._list = list;
  } else if (st.tab === "collection") {
    const byMethod = repo.collectionByMethod(st.day, st.day, lock); const pays = repo.paymentsOn(st.day, lock); const total = byMethod.reduce((s, m) => s + m.amount, 0);
    pane = `<div class="toolbar mb"><div class="field narrow">${dateInput("day", st.day, `max="${today}"`)}</div>${btn(t("download_csv"), { ic: "file-spreadsheet", attrs: 'data-csv="collection"' })}</div>
      ${kpiRow([{ label: t("daily_collection"), value: money(total), ic: "wallet", tone: "primary", hint: fmtDate(st.day) }, ...byMethod.map((m) => ({ label: statusLabel(m.method), value: money(m.amount), ic: "banknote", tone: "neutral", hint: t("n_payments", { n: m.payments }) }))])}
      ${pays.length ? table({ columns: [{ label: t("time") }, { label: t("invoice"), cls: "num" }, { label: t("patient") }, { label: t("doctor") }, { label: t("payment_method") }, { label: t("reference") }, { label: t("amount"), cls: "num" }, { label: t("received_by") }], rows: pays.map((p) => ({ attrs: `class="clickable" data-id="${p.invoice_id}"`, cells: [fmtTime(p.paid_at.slice(11, 16)), esc(p.invoice_no), esc(p.patient), esc(p.doctor || "-"), esc(statusLabel(p.method)), esc(p.reference || "-"), money(p.amount), esc(p.received_by_name || "-")] })) }) : emptyState(t("no_data"), "", "wallet")}`;
    st._pays = pays;
  } else {
    const out = repo.outstandingInvoices(lock); const total = out.reduce((s, i) => s + i.outstanding, 0);
    pane = out.length ? kpiRow([{ label: t("outstanding"), value: money(total), ic: "credit-card", tone: "danger", hint: t("n_invoices", { n: out.length }) }]) + table({ columns: [{ label: t("invoice"), cls: "num cell-primary" }, { label: t("date") }, { label: t("patient") }, { label: t("patient_id"), cls: "num" }, { label: t("phone"), cls: "num" }, { label: t("total"), cls: "num" }, { label: t("received"), cls: "num" }, { label: t("outstanding"), cls: "num" }],
      rows: out.map((i) => ({ attrs: `class="clickable" data-id="${i.id}"`, cells: [`<b>${esc(i.invoice_no)}</b>`, fmtDate(i.invoice_date), esc(i.patient), esc(i.patient_code), esc(i.phone), money(i.total), money(i.paid), money(i.outstanding)] })) }) : emptyState(t("no_outstanding"), "", "circle-check");
  }
  root.innerHTML = `${pageHead(t("billing"), t("daily_collection"), canEdit ? btn(t("new_invoice"), { ic: "plus", cls: "primary", attrs: 'id="btnNew"' }) : "", "credit-card")}
  <div class="card">${tabsBar("tab", [["invoices", t("invoices")], ["collection", t("daily_collection")], ["outstanding", t("outstanding")]], st.tab)}${pane}</div>`;
  bindTabs(root, st, "tab", () => app.refresh());
  for (const name of ["from", "to", "status", "day"]) { const el = root.querySelector(`[name="${name}"]`); if (el) el.addEventListener("change", () => { st[name] = el.type === "date" ? (el.value || st[name]) : el.value; app.refresh(); }); }
  const qi = root.querySelector('[name="q"]'); if (qi) { let timer; qi.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { st.q = qi.value; const pos = qi.selectionStart; app.refresh(); const n = document.querySelector('#view [name="q"]'); n.focus(); n.setSelectionRange(pos, pos); }, 250); }); }
  const nb = root.querySelector("#btnNew"); if (nb) nb.addEventListener("click", () => openInvoiceDialog(app, { onSaved: (id) => app.navigate("billing", { id }) }));
  root.addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-id]"); if (tr) { app.navigate("billing", { id: tr.dataset.id }); return; }
    const c = e.target.closest("[data-csv]"); if (!c) return;
    if (c.dataset.csv === "invoices") downloadFile(`invoices_${st.from}_${st.to}.csv`, toCSV(st._list, ["invoice_no", "invoice_date", "patient", "patient_code", "doctor", "total", "paid", "outstanding", "status"]), "text/csv");
    else downloadFile(`collection_${st.day}.csv`, toCSV(st._pays, ["paid_at", "invoice_no", "patient", "patient_code", "doctor", "method", "reference", "amount", "received_by_name"]), "text/csv");
  });
}
