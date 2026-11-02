/* Medicine inventory: stock list, add / edit, audited adjustments, low-stock and expiry warnings
   (modules/inventory.py). Convenience stock list only; not a licensed pharmacy system. */
import { freshView, esc, money, fmtDate, fmtDateTime, pageHead, section, kpiRow, listRow, emptyState, statusBadge, badge, btn, field, input, select, dateInput, check, notice, table, tabsBar, bindTabs, openModal, closeModal, toast, formValues, showFormError, toCSV, downloadFile, run, t, statusLabel } from "../ui.js";
import { todayISO, addDays, MEDICINE_CATEGORIES } from "../store.js";

const REASONS = [["Purchase", "reason_purchase"], ["Dispensed", "reason_dispensed"], ["Return to supplier", "reason_return"], ["Expired / disposed", "reason_expired"], ["Damaged", "reason_damaged"], ["Count correction", "reason_correction"], ["Other", "reason_other"]];

function medicineFormHTML(init = {}) {
  const editing = !!init.id;
  return `<div class="form-grid-3">
    ${field(t("name"), input("name", init.name || "", 'maxlength="120" required'), { required: true, cls: "span-2" })}
    ${field(t("category"), select("category", MEDICINE_CATEGORIES.map((c) => [c, statusLabel(c)]), init.category || "Tablet"))}
    ${field(t("sku"), input("sku", init.sku || "", `maxlength="40" class="num" ${editing ? "disabled" : ""}`), { required: true })}
    ${field(t("opening_stock"), input("quantity", init.quantity ?? 0, `type="number" min="0" step="1" class="num" ${editing ? "disabled" : ""}`), { help: editing ? t("opening_stock_hint") : "" })}
    ${field(t("reorder_level"), input("reorder_level", init.reorder_level ?? 10, 'type="number" min="0" step="1" class="num"'))}
    ${field(t("purchase_price"), input("purchase_price", init.purchase_price ?? 0, 'type="number" min="0" step="0.01" class="num"'))}
    ${field(t("selling_price"), input("selling_price", init.selling_price ?? 0, 'type="number" min="0" step="0.01" class="num"'))}
    ${field(t("expiry"), dateInput("expiry_date", init.expiry_date || ""), { optional: true })}
    ${field(t("supplier"), input("supplier", init.supplier || "", 'maxlength="120"'), { cls: "span-2" })}
    ${editing ? `<div class="field"><label>&nbsp;</label>${check("is_active", t("active"), !!init.is_active)}</div>` : ""}
  </div>`;
}
function openMedicineDialog(app, med, onSaved) {
  const { repo } = app;
  openModal({ title: med ? `${t("edit_medicine")} · ${med.sku}` : t("add_medicine"), ic: "pill", size: "lg", body: `<form id="medForm">${medicineFormHTML(med || {})}</form>`,
    footer: btn(t("cancel"), { attrs: "data-close" }) + btn(t("save"), { ic: "save", cls: "primary", attrs: "data-save" }),
    onMount: (m) => { const form = m.querySelector("#medForm"); const save = () => { const v = formValues(form); if (med) { v.sku = med.sku; v.quantity = med.quantity; } try { repo.saveMedicine(v, med ? med.id : null, app.user); closeModal(); toast(t("saved")); onSaved(); } catch (e) { showFormError(form, e); } }; m.querySelector("[data-save]").addEventListener("click", save); form.addEventListener("submit", (e) => { e.preventDefault(); save(); }); } });
}

export function render(_root, app) {
  const root = freshView(); const { repo } = app; const s = app.settings;
  const st = app.ui.inventory || (app.ui.inventory = { tab: "stock", q: "", cat: "", inactive: false, med: null });
  const canEdit = app.canEdit("inventory");
  const alerts = repo.stockAlerts(); const flags = new Map(alerts.map((a) => [a.id, a.flags])); const all = repo.medicines();
  const n = (f) => alerts.filter((a) => a.flags.includes(f)).length; const units = all.reduce((x, m) => x + m.quantity, 0); const value = all.reduce((x, m) => x + m.quantity * m.purchase_price, 0);
  const tabs = [["stock", t("stock")], ["warnings", t("warnings")], ["adjust", canEdit ? t("adjust_stock") : t("movements")]];
  let pane = "";
  if (st.tab === "stock") {
    const meds = repo.medicines(st.q, !st.inactive, st.cat || null);
    pane = `<div class="toolbar mb"><div class="field grow">${input("q", st.q, 'placeholder="name / SKU / supplier" autocomplete="off"')}</div><div class="field narrow">${select("cat", [["", t("all")], ...MEDICINE_CATEGORIES.map((c) => [c, statusLabel(c)])], st.cat)}</div>${app.isAdmin() ? `<div class="field" style="flex:0 0 auto">${check("inactive", t("include_inactive"), st.inactive, 'id="medInactive"')}</div>` : ""}${btn(t("download_csv"), { ic: "file-spreadsheet", attrs: 'id="medCsv"' })}</div>
      ${meds.length ? table({ columns: [{ label: t("sku"), cls: "num" }, { label: t("name"), cls: "cell-primary" }, { label: t("category") }, { label: t("quantity"), cls: "num" }, { label: t("reorder"), cls: "num" }, { label: t("purchase_price"), cls: "num" }, { label: t("selling_price"), cls: "num" }, { label: t("expiry") }, { label: t("supplier") }, { label: t("alert") }],
        rows: meds.map((m) => ({ attrs: canEdit ? `class="clickable" data-id="${m.id}"` : "", cells: [esc(m.sku), `<b>${esc(m.name)}</b>${m.is_active ? "" : ` ${statusBadge("Inactive")}`}`, esc(statusLabel(m.category)), String(m.quantity), String(m.reorder_level), money(m.purchase_price), money(m.selling_price), m.expiry_date ? fmtDate(m.expiry_date) : "-", esc(m.supplier || ""), (flags.get(m.id) || []).map((f) => statusBadge(f)).join(" ")] })) }) : emptyState(t("no_data"), "", "package")}`;
    st._meds = meds;
  } else if (st.tab === "warnings") {
    pane = `${notice(t("inventory_notice"), "info", "shield")}<div class="mb"></div>${alerts.length ? `<div class="list">${alerts.map((a) => listRow({ title: esc(a.name), sub: `<span class="num">${esc(a.sku)}</span> · ${t("quantity")}: <span class="num">${a.quantity}</span> (${t("reorder").toLowerCase()} <span class="num">${a.reorder_level}</span>)${a.expiry_date ? ` · ${t("expiry")}: ${fmtDate(a.expiry_date)}` : ""}`, ic: "triangle-alert", tone: a.flags.includes("Expired") ? "danger" : "warning", value: a.flags.map((f) => statusBadge(f)).join(" ") })).join("")}</div>` : emptyState(t("no_warnings"), t("all_within_limits"), "circle-check")}`;
  } else {
    if (!st.med || !all.some((m) => m.id === st.med)) st.med = all.length ? all[0].id : null;
    const mv = st.med ? repo.stockMovements(st.med) : [];
    pane = all.length ? `<div class="field mb">${select("med", all.map((m) => [m.id, `${m.name} (${m.sku}) · ${m.quantity} ${t("in_stock")}`]), st.med)}</div>
      ${canEdit ? `<form id="adjForm" class="card soft mb"><div class="form-grid-4">${field(t("type"), select("direction", [["add", t("add_stock")], ["remove", t("remove_stock")]], "add"))}${field(t("quantity"), input("qty", 1, 'type="number" min="1" step="1" class="num"'))}${field(t("reason"), select("reason", REASONS.map(([v, k]) => [v, t(k)]), "Purchase"))}${field(t("reference"), input("reference", "", `maxlength="100" placeholder="${esc(t("reference_hint"))}"`), { optional: true })}</div><div class="form-foot">${btn(t("save"), { ic: "save", cls: "primary", type: "submit" })}</div></form>` : ""}
      ${section(t("movements"), "history", mv.length)}${mv.length ? table({ columns: [{ label: t("date") }, { label: t("change"), cls: "num" }, { label: t("reason") }, { label: t("reference") }, { label: t("by") }], rows: mv.map((m) => ({ cells: [fmtDateTime(m.created_at), `<b class="${m.change_qty < 0 ? "danger-text" : "primary-text"}">${m.change_qty > 0 ? "+" : ""}${m.change_qty}</b>`, esc(m.reason), esc(m.reference || "-"), esc(m.by_user || "-")] })) }) : emptyState(t("no_data"), "", "history")}` : emptyState(t("no_data"), "", "package");
  }
  root.innerHTML = `${pageHead(t("inventory"), t("inventory_notice"), canEdit ? btn(t("add_medicine"), { ic: "plus", cls: "primary", attrs: 'id="btnAdd"' }) : "", "package")}
  ${kpiRow([{ label: t("items"), value: all.length, ic: "package", tone: "primary", hint: t("n_units", { n: units }) }, { label: t("low_stock"), value: n("Low stock"), ic: "triangle-alert", tone: n("Low stock") ? "warning" : "success" }, { label: t("expiring_soon"), value: n("Expiring soon"), ic: "clock", tone: n("Expiring soon") ? "warning" : "success", hint: `${s.expiry_warning_days} ${t("days").toLowerCase()}` }, { label: t("expired"), value: n("Expired"), ic: "circle-x", tone: n("Expired") ? "danger" : "success" }, { label: t("stock_value"), value: money(value), ic: "banknote", tone: "neutral" }])}
  <div class="card">${tabsBar("tab", tabs, st.tab)}${pane}</div>`;
  bindTabs(root, st, "tab", () => app.refresh());
  const qi = root.querySelector('[name="q"]'); if (qi) { let timer; qi.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { st.q = qi.value; const pos = qi.selectionStart; app.refresh(); const nq = document.querySelector('#view [name="q"]'); nq.focus(); nq.setSelectionRange(pos, pos); }, 250); }); }
  const cat = root.querySelector('[name="cat"]'); if (cat) cat.addEventListener("change", () => { st.cat = cat.value; app.refresh(); });
  const ia = root.querySelector("#medInactive"); if (ia) ia.addEventListener("change", () => { st.inactive = ia.checked; app.refresh(); });
  const csv = root.querySelector("#medCsv"); if (csv) csv.addEventListener("click", () => downloadFile(`stock_${todayISO()}.csv`, toCSV(st._meds.map((m) => ({ ...m, alert: (flags.get(m.id) || []).join(", "), value: m.quantity * m.purchase_price })), ["sku", "name", "category", "quantity", "reorder_level", "purchase_price", "selling_price", "expiry_date", "supplier", "value", "alert"]), "text/csv"));
  const ab = root.querySelector("#btnAdd"); if (ab) ab.addEventListener("click", () => openMedicineDialog(app, null, () => app.refresh()));
  const ms = root.querySelector('[name="med"]'); if (ms) ms.addEventListener("change", () => { st.med = Number(ms.value); app.refresh(); });
  const af = root.querySelector("#adjForm"); if (af) af.addEventListener("submit", (e) => { e.preventDefault(); const v = formValues(af); try { const q = repo.adjustStock(st.med, v.direction === "add" ? Number(v.qty) : -Number(v.qty), v.reason, v.reference, app.user); toast(`${t("saved")} · ${q} ${t("in_stock")}`); app.refresh(); } catch (err) { showFormError(af, err); } });
  root.addEventListener("click", (e) => { const tr = e.target.closest("tr[data-id]"); if (tr && canEdit) openMedicineDialog(app, repo.medicine(Number(tr.dataset.id)), () => app.refresh()); });
}
