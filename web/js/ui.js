/* Shared UI helpers: formatting, building blocks, modals, toasts, tables, CSV and printing. */
import { icon } from "./icons.js";
import { t, isRTL, statusLabel, getLang } from "./i18n.js";
import { store, todayISO, addDays, MAX_UPLOAD_BYTES, err } from "./store.js";

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const money = (v) => store.money(v);
export const fmtNum = (v) => (Number(v) || 0).toLocaleString("en-US");
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const DAYS_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const DAYS_UR = ["پیر", "منگل", "بدھ", "جمعرات", "جمعہ", "ہفتہ", "اتوار"];
const MONTHS_UR = ["جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون", "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر"];
/** 'YYYY-MM-DD' -> '02 Nov 2026' (long: 'Monday, 02 November 2026'). */
export function fmtDate(iso, long = false) {
  if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(String(iso))) return "-";
  const [y, m, d] = String(iso).slice(0, 10).split("-").map(Number);
  if (!long) return `${String(d).padStart(2, "0")} ${MONTHS[m - 1]} ${y}`;
  const wd = (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
  return isRTL() ? `${DAYS_UR[wd]}، ${d} ${MONTHS_UR[m - 1]} ${y}` : `${DAYS_LONG[wd]}, ${String(d).padStart(2, "0")} ${MONTHS_LONG[m - 1]} ${y}`;
}
export const fmtDay = (iso) => { const [y, m, d] = String(iso).slice(0, 10).split("-").map(Number); return `${String(d).padStart(2, "0")} ${MONTHS[m - 1]}`; };
export const fmtMonth = (ym) => { const [y, m] = String(ym).split("-").map(Number); return `${MONTHS[m - 1]} ${y}`; };
/** 'HH:MM' -> '9:15 AM'. */
export function fmtTime(hm) {
  if (!hm) return "-";
  const [h, m] = String(hm).slice(0, 5).split(":").map(Number); if (Number.isNaN(h)) return String(hm);
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h >= 12 ? "PM" : "AM"}`;
}
export function fmtDateTime(ts) { if (!ts) return "-"; const [d, tm] = String(ts).split(" "); return tm ? `${fmtDate(d)}, ${fmtTime(tm)}` : fmtDate(d); }
export const initials = (name) => (String(name || "").replace(/^Dr\.?\s*/i, "").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase() || "CL");
export const DEFAULT_LOGO = "assets/logo.svg";
export const logoSrc = () => store.settings.clinic_logo || (window.CML_CONFIG?.clinic?.logo) || DEFAULT_LOGO;
export const hasLogo = () => !!(store.settings.clinic_logo || window.CML_CONFIG?.clinic?.logo);

/** Replace the view container with a clean clone so listeners from the previous render are dropped. */
export function freshView() {
  const old = document.getElementById("view"); const next = old.cloneNode(false); old.replaceWith(next); return next;
}

// ------------------------------------------------------------------ blocks
export const pageHead = (title, subtitle = "", actions = "", ic = "") => `<div class="page-head"><div class="page-title">${ic ? `<span class="page-ic">${icon(ic, 20)}</span>` : ""}<div><h1>${esc(title)}</h1>${subtitle ? `<p>${esc(subtitle)}</p>` : ""}</div></div>${actions ? `<div class="page-actions">${actions}</div>` : ""}</div>`;
export const section = (title, ic = "", count = null, right = "") => `<div class="section"><h3>${ic ? icon(ic, 17) : ""}<span>${esc(title)}</span>${count !== null && count !== "" ? `<span class="count num">${esc(count)}</span>` : ""}</h3>${right ? `<div class="section-right">${right}</div>` : ""}</div>`;
export function kpi({ label, value, ic = "activity", tone = "primary", hint = "" }) {
  return `<div class="kpi"><div class="kpi-top"><span class="label">${esc(label)}</span><span class="ic-wrap tone-${tone}">${icon(ic, 18)}</span></div><div class="value num">${esc(value)}</div><div class="hint">${esc(hint)}</div></div>`;
}
export const kpiRow = (items) => `<div class="kpi-row">${items.map(kpi).join("")}</div>`;
export const STATUS_TONES = {
  Scheduled: "info", Arrived: "primary", Waiting: "primary", "In Consultation": "warning", Completed: "success", Cancelled: "danger", "No Show": "neutral",
  Paid: "success", Partial: "warning", Unpaid: "danger", Signed: "success", Draft: "neutral", Active: "success", Inactive: "neutral",
  "Low stock": "warning", Expired: "danger", "Expiring soon": "warning", OK: "success",
  available: "success", on_leave: "danger", off_today: "neutral", in_consultation: "warning",
};
export const badge = (text, tone = "neutral", ic = "") => `<span class="badge tone-${tone}">${ic ? icon(ic, 12) : ""}${esc(text)}</span>`;
export const statusBadge = (s) => badge(statusLabel(s), STATUS_TONES[s] || "neutral");
export const emptyState = (title, hint = "", ic = "inbox") => `<div class="empty"><span class="empty-ic">${icon(ic, 26)}</span><b>${esc(title)}</b>${hint ? `<span>${esc(hint)}</span>` : ""}</div>`;
export const notice = (text, tone = "info", ic = "info") => `<div class="alert ${tone}">${icon(ic, 16)}<span>${esc(text)}</span></div>`;
export const avatar = (name, size = 36, src = "") => src ? `<img class="avatar" src="${src}" alt="" style="width:${size}px;height:${size}px"/>` : `<span class="avatar soft" style="width:${size}px;height:${size}px;font-size:${Math.round(size * 0.36)}px">${esc(initials(name))}</span>`;
export const tokenChip = (n, big = false) => `<span class="tok ${big ? "big" : ""} num">${esc((store.getSetting("token_prefix", "") || "") + n)}</span>`;
export function listRow({ title, sub = "", value = "", valueSub = "", ic = "", tone = "primary", lead = "", avatarName = "", attrs = "" }) {
  const l = lead || (avatarName ? avatar(avatarName, 36) : ic ? `<span class="ic-wrap tone-${tone}">${icon(ic, 16)}</span>` : "");
  return `<div class="row" ${attrs}>${l}<div class="body"><div class="title">${title}</div>${sub ? `<div class="sub">${sub}</div>` : ""}</div><div class="end"><div class="v">${value}</div>${valueSub ? `<div class="s">${valueSub}</div>` : ""}</div></div>`;
}
export const kv = (pairs) => `<div class="kv">${pairs.map(([k, v, raw]) => `<span>${esc(k)}</span><b>${raw ? v : esc(v ?? "-")}</b>`).join("")}</div>`;
export const field = (label, inner, opts = {}) => `<div class="field ${opts.cls || ""}" ${opts.attrs || ""}><label>${esc(label)}${opts.required ? " *" : ""}${opts.optional ? ` <span class="faint">(${t("optional")})</span>` : ""}</label>${inner}${opts.help ? `<span class="help">${esc(opts.help)}</span>` : ""}<span class="err"></span></div>`;
export const input = (name, value = "", attrs = "") => `<input name="${name}" value="${esc(value)}" ${attrs}/>`;
export const textarea = (name, value = "", attrs = "") => `<textarea name="${name}" ${attrs}>${esc(value)}</textarea>`;
export const select = (name, options, value, attrs = "") => `<select name="${name}" ${attrs}>${options.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return `<option value="${esc(v)}" ${String(v) === String(value ?? "") ? "selected" : ""}>${esc(l)}</option>`; }).join("")}</select>`;
export const btn = (label, { ic = "", cls = "", attrs = "", type = "button" } = {}) => `<button type="${type}" class="btn ${cls}" ${attrs}>${ic ? icon(ic, 16) : ""}<span>${esc(label)}</span></button>`;
export const iconBtn = (ic, title, attrs = "", cls = "") => `<button type="button" class="btn-icon ${cls}" title="${esc(title)}" aria-label="${esc(title)}" ${attrs}>${icon(ic, 16)}</button>`;
export const check = (name, label, checked = false, attrs = "") => `<label class="check"><input type="checkbox" name="${name}" ${checked ? "checked" : ""} ${attrs}/><span>${esc(label)}</span></label>`;
export const tabsBar = (key, items, active) => `<div class="tabs" data-tabs="${key}">${items.map(([v, l]) => `<button type="button" class="${v === active ? "active" : ""}" data-tab="${esc(v)}">${esc(l)}</button>`).join("")}</div>`;
export function bindTabs(root, st, key, onChange) {
  root.querySelectorAll(`[data-tabs="${key}"]`).forEach((el) => el.addEventListener("click", (e) => { const b = e.target.closest("[data-tab]"); if (!b) return; st[key] = b.dataset.tab; onChange(); }));
}
export const dateInput = (name, value, attrs = "") => `<input type="date" name="${name}" value="${esc(value || "")}" ${attrs}/>`;

// ------------------------------------------------------------------ modal / toast / confirm
const modalRoot = () => document.getElementById("modalRoot");
export function openModal({ title, ic = "", body, footer = "", size = "", onMount, stack = false }) {
  if (!stack) closeModal(true);
  const wrap = document.createElement("div"); wrap.className = "modal-backdrop";
  wrap.innerHTML = `<div class="modal ${size}" role="dialog" aria-modal="true"><div class="modal-head"><h3>${ic ? icon(ic, 18) : ""}${esc(title)}</h3><button type="button" class="btn-icon" data-close aria-label="${esc(t("close"))}">${icon("x", 16)}</button></div><div class="modal-body">${body}</div>${footer ? `<div class="modal-foot">${footer}</div>` : ""}</div>`;
  wrap.addEventListener("click", (e) => { if (e.target === wrap || e.target.closest("[data-close]")) closeModal(); });
  modalRoot().appendChild(wrap);
  document.body.style.overflow = "hidden";
  const first = wrap.querySelector("input:not([type=hidden]):not([type=checkbox]), select, textarea, button.primary"); if (first) setTimeout(() => first.focus(), 30);
  if (onMount) onMount(wrap.querySelector(".modal"));
  return wrap.querySelector(".modal");
}
export function closeModal(all = false) { const r = modalRoot(); if (all) r.innerHTML = ""; else if (r.lastChild) r.lastChild.remove(); if (!r.firstChild) document.body.style.overflow = ""; }
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
export function confirmDialog({ title, body, danger = true, confirmText = "", extra = "" }) {
  return new Promise((resolve) => {
    openModal({ title, ic: danger ? "triangle-alert" : "info", size: "sm", body: `<p class="muted" style="margin:0 0 8px">${esc(body)}</p>${extra}<p class="faint" style="margin:0">${esc(t("cannot_undo"))}</p>`,
      footer: btn(t("cancel"), { attrs: "data-cancel" }) + btn(confirmText || t("confirm"), { cls: danger ? "danger-solid" : "primary", attrs: "data-ok" }),
      onMount: (m) => {
        m.querySelector("[data-ok]").addEventListener("click", () => { closeModal(); resolve(true); });
        m.querySelector("[data-cancel]").addEventListener("click", () => { closeModal(); resolve(false); });
        m.querySelector(".modal-head [data-close]").addEventListener("click", () => resolve(false));
        m.parentElement.addEventListener("click", (e) => { if (e.target === m.parentElement) resolve(false); });
      } });
  });
}
export function toast(message, type = "ok") {
  const root = document.getElementById("toastRoot"); const el = document.createElement("div");
  el.className = `toast ${type === "error" ? "error" : ""}`; el.innerHTML = `${icon(type === "error" ? "circle-alert" : "circle-check", 16)}<span>${esc(message)}</span>`;
  root.appendChild(el); setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(() => el.remove(), 300); }, type === "error" ? 4200 : 2600);
}
export function errorMessage(e) {
  if (!e) return t("error");
  if (e.key) return t(e.key, e.vars || {});
  const m = e.message || String(e);
  return m;
}
/** Run an action, show a toast on success or the error, and optionally re-render. */
export async function run(fn, okMessage = null, after = null) {
  try { const r = await fn(); if (okMessage) toast(okMessage); if (after) after(r); return r; } catch (e) { console.error(e); toast(errorMessage(e), "error"); return undefined; }
}

// ------------------------------------------------------------------ forms
export function formValues(form) { const o = {}; new FormData(form).forEach((v, k) => { o[k] = typeof v === "string" ? v.trim() : v; }); form.querySelectorAll("input[type=checkbox]").forEach((c) => { o[c.name] = c.checked; }); return o; }
export function setError(form, name, msg) { const f = form.querySelector(`[name="${name}"]`)?.closest(".field"); if (f) { f.classList.toggle("invalid", !!msg); const e = f.querySelector(".err"); if (e) e.textContent = msg || ""; } }
export function showFormError(form, e) { let box = form.querySelector(".form-error"); if (!box) { box = document.createElement("div"); box.className = "form-error"; form.prepend(box); } box.innerHTML = notice(errorMessage(e), "error", "circle-alert"); box.hidden = false; }
export function clearFormError(form) { const box = form.querySelector(".form-error"); if (box) box.hidden = true; }
/** Read an image file, validate type and size, scale it to fit max px and return a PNG data URL. */
export function readImageFile(file, max = 512) {
  return new Promise((resolve, reject) => {
    if (!file) return reject(err("err.invalid_image"));
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) return reject(err("err.invalid_image"));
    if (file.size > MAX_UPLOAD_BYTES) return reject(err("err.image_too_large"));
    const img = new Image(); const url = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.width, img.height)); const w = Math.max(1, Math.round(img.width * scale)), h = Math.max(1, Math.round(img.height * scale));
      const c = document.createElement("canvas"); c.width = w; c.height = h; c.getContext("2d").drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url); resolve(c.toDataURL("image/png"));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(err("err.invalid_image")); };
    img.src = url;
  });
}

// ------------------------------------------------------------------ tables & pagination
export function table({ columns, rows, cls = "responsive", empty = "" }) {
  if (!rows.length && empty) return empty;
  const th = columns.map((c) => `<th class="${c.cls || ""}">${esc(c.label)}</th>`).join("");
  const body = rows.map((r) => `<tr ${r.attrs || ""}>${r.cells.map((cell, i) => { const c = columns[i] || {}; return `<td class="${c.cls || ""}" data-label="${esc(c.label)}">${cell}</td>`; }).join("")}</tr>`).join("");
  return `<div class="table-wrap"><table class="tbl ${cls}"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
}
export function paginate(items, key, size, state) {
  const total = items.length; const pages = Math.max(1, Math.ceil(total / size));
  const page = Math.min(Math.max(1, state[key] || 1), pages); state[key] = page;
  return { items: items.slice((page - 1) * size, page * size), page, pages, total };
}
export function pager({ page, pages, total }, key) {
  if (total <= 0 || pages <= 1) return "";
  return `<div class="pager"><button type="button" class="btn sm" data-pager="${key}" data-dir="-1" ${page <= 1 ? "disabled" : ""}>${icon(isRTL() ? "chevron-right" : "chevron-left", 14)}<span>${esc(t("previous"))}</span></button><span>${esc(t("page"))} <span class="num">${page}</span> ${esc(t("of"))} <span class="num">${pages}</span> <span class="faint">(<span class="num">${total}</span> ${esc(t("rows"))})</span></span><button type="button" class="btn sm" data-pager="${key}" data-dir="1" ${page >= pages ? "disabled" : ""}><span>${esc(t("next"))}</span>${icon(isRTL() ? "chevron-left" : "chevron-right", 14)}</button></div>`;
}
export function bindPager(root, st, onChange) {
  root.querySelectorAll("[data-pager]").forEach((b) => b.addEventListener("click", () => { const k = b.dataset.pager; st[k] = (st[k] || 1) + Number(b.dataset.dir); onChange(); }));
}

// ------------------------------------------------------------------ date ranges
export function rangeFor(preset, custom = {}) {
  const today = todayISO();
  switch (preset) {
    case "today": return [today, today];
    case "last_7": return [addDays(today, -6), today];
    case "last_30": return [addDays(today, -29), today];
    case "this_month": return [today.slice(0, 8) + "01", today];
    case "this_week": { const wd = (new Date(today + "T00:00:00Z").getUTCDay() + 6) % 7; const s = addDays(today, -wd); return [s, addDays(s, 6)]; }
    case "last_month": { const first = today.slice(0, 8) + "01"; const e = addDays(first, -1); return [e.slice(0, 8) + "01", e]; }
    case "custom": { let s = custom.from || addDays(today, -29), e = custom.to || today; if (s > e) [s, e] = [e, s]; return [s, e]; }
    default: return [addDays(today, -29), today];
  }
}

// ------------------------------------------------------------------ CSV
export function toCSV(rows, columns, headers = null) {
  const q = (v) => { const s = String(v ?? ""); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return "﻿" + [(headers || columns).map(q).join(","), ...rows.map((r) => columns.map((c) => q(typeof c === "function" ? c(r) : r[c])).join(","))].join("\n");
}
export function downloadFile(name, content, mime = "text/plain") {
  const blob = new Blob([content], { type: mime }); const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const csvButton = (label, attrs) => btn(label || t("download_csv"), { ic: "file-spreadsheet", cls: "sm", attrs });

// ------------------------------------------------------------------ printing
let pageStyle = null;
function setPageSize(size, orientation) {
  if (!pageStyle) { pageStyle = document.createElement("style"); pageStyle.id = "printPage"; document.head.appendChild(pageStyle); }
  pageStyle.textContent = `@page { size: ${size} ${orientation}; margin: 10mm; }`;
}
/** Put the document HTML into the print root and open the browser print dialog. */
export function printHTML(html, { size = "A5", orientation = "portrait" } = {}) {
  const root = document.getElementById("printRoot"); root.innerHTML = html; root.hidden = false;
  setPageSize(size, orientation);
  const done = () => { root.hidden = true; root.innerHTML = ""; window.removeEventListener("afterprint", done); };
  window.addEventListener("afterprint", done); setTimeout(() => window.print(), 80);
}
/** Preview a print document in a modal with a Print button. */
export function printPreview(html, { title = "", size = "A5", orientation = "portrait" } = {}) {
  openModal({ title: title || t("preview"), ic: "printer", size: "lg", body: `<div class="print-preview">${html}</div>`,
    footer: btn(t("close"), { attrs: "data-close" }) + btn(t("print_now"), { ic: "printer", cls: "primary", attrs: "data-print" }),
    onMount: (m) => { m.querySelector("[data-print]").addEventListener("click", () => printHTML(html, { size, orientation })); } });
}

export const isMobile = () => window.matchMedia("(max-width: 640px)").matches;
export { icon, t, isRTL, statusLabel, getLang };
