/* Data store: a plain state object (one array per table, mirroring the SQLite schema of the Python edition)
   persisted to IndexedDB under the configured storage key, with a localStorage fallback. Also holds the
   date / time / money / validation helpers (Asia/Karachi, PKR) ported from core/utils.py. */
const CFG = window.CML_CONFIG || {};
const CL = CFG.clinic || {};
export const STORAGE_KEY = `${CFG.storageKey || "cml"}:state`;
export const STATE_VERSION = 1;

// ---------------------------------------------------------------- constants (core/config.py)
export const ROLES = ["admin", "receptionist", "doctor"];
export const APPOINTMENT_STATUSES = ["Scheduled", "Arrived", "In Consultation", "Completed", "Cancelled", "No Show"];
export const VISIT_TYPES = ["New Visit", "Follow-up", "Walk-in", "Procedure"];
export const TOKEN_STATUSES = ["Waiting", "In Consultation", "Completed", "Cancelled"];
export const PAYMENT_METHODS = ["Cash", "Bank Transfer", "JazzCash", "Easypaisa", "Other"];
export const INVOICE_STATUSES = ["Unpaid", "Partial", "Paid", "Cancelled"];
export const GENDERS = ["Male", "Female", "Other"];
export const BLOOD_GROUPS = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
export const MEDICINE_CATEGORIES = ["Tablet", "Capsule", "Syrup", "Injection", "Drops", "Cream", "Inhaler", "Other"];
export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const SESSION_HOURS = 8;
export const IDLE_TIMEOUT_MIN = 30;
export const MAX_FAILED_LOGINS = 5;
export const LOCKOUT_MINUTES = 15;
export const MAX_UPLOAD_BYTES = 2 * 1024 * 1024;

export const DEFAULT_SETTINGS = {
  clinic_name: CL.name || "City Care Clinic",
  clinic_tagline: CL.tagline ?? "Family Medicine and General Practice",
  clinic_address: CL.address ?? "",
  clinic_phone: CL.phone ?? "",
  clinic_email: CL.email ?? "",
  clinic_logo: CL.logo || "",
  default_language: CL.language || "en",
  appointment_duration: String(CL.appointmentDuration || 15),
  default_consultation_fee: String(CL.defaultConsultationFee ?? 1500),
  token_prefix: CL.tokenPrefix ?? "T",
  currency_symbol: CL.currencySymbol || "Rs.",
  rx_footer_en: CL.rxFooterEn ?? "",
  rx_footer_ur: CL.rxFooterUr ?? "",
  receipt_footer_en: CL.receiptFooterEn ?? "",
  receipt_footer_ur: CL.receiptFooterUr ?? "",
  paper_size: CL.paperSize || "A5",
  show_urdu_on_prints: "1",
  rx_show_diagnosis: "1",
  low_stock_threshold: String(CL.lowStockThreshold ?? 10),
  expiry_warning_days: String(CL.expiryWarningDays ?? 90),
  max_discount_without_auth: String(CL.maxDiscountWithoutAuth ?? 0),
  follow_up_window_days: String(CL.followUpWindowDays ?? 7),
  demo_mode: "0",
  seeded_at: "",
};

export const TABLES = ["doctors", "doctor_schedule", "doctor_holidays", "users", "sessions", "patients", "appointments", "tokens",
  "consultations", "prescriptions", "prescription_items", "services", "invoices", "invoice_items", "payments", "medicines",
  "stock_movements", "audit_log"];

// ---------------------------------------------------------------- errors
export class AppError extends Error {
  constructor(key, vars = null) { super(key); this.key = key; this.vars = vars; }
}
export class SlotTakenError extends AppError {
  constructor(key = "err.slot_unavailable") { super(key); this.slotTaken = true; }
}
export const err = (key, vars) => new AppError(key, vars);

// ---------------------------------------------------------------- persistence
function openDB() {
  return new Promise((resolve) => {
    if (!("indexedDB" in window)) return resolve(null);
    let req;
    try { req = indexedDB.open(`${CFG.storageKey || "cml"}-db`, 1); } catch { return resolve(null); }
    req.onupgradeneeded = () => req.result.createObjectStore("kv");
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve(null);
    req.onblocked = () => resolve(null);
  });
}
function idbGet(db, key) {
  if (!db) return Promise.resolve(null);
  return new Promise((resolve) => {
    try {
      const tx = db.transaction("kv", "readonly"); const req = tx.objectStore("kv").get(key);
      req.onsuccess = () => resolve(req.result ?? null); req.onerror = () => resolve(null);
    } catch { resolve(null); }
  });
}
function idbSet(db, key, value) {
  if (!db) return Promise.resolve(false);
  return new Promise((resolve) => {
    try {
      const tx = db.transaction("kv", "readwrite"); tx.objectStore("kv").put(value, key);
      tx.oncomplete = () => resolve(true); tx.onerror = () => resolve(false); tx.onabort = () => resolve(false);
    } catch { resolve(false); }
  });
}

// ---------------------------------------------------------------- time (Asia/Karachi)
export const TIMEZONE = "Asia/Karachi";
const p2 = (n) => String(n).padStart(2, "0");
const PARTS = new Intl.DateTimeFormat("en-GB", { timeZone: TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
/** Current wall-clock in the clinic time zone as {y,m,d,hh,mm,ss}. */
export function nowParts(date = new Date()) {
  const o = {};
  for (const p of PARTS.formatToParts(date)) if (p.type !== "literal") o[p.type] = p.value;
  return { y: Number(o.year), m: Number(o.month), d: Number(o.day), hh: Number(o.hour) % 24, mm: Number(o.minute), ss: Number(o.second) };
}
export const nowISO = () => { const n = nowParts(); return `${n.y}-${p2(n.m)}-${p2(n.d)} ${p2(n.hh)}:${p2(n.mm)}:${p2(n.ss)}`; };
export const todayISO = () => { const n = nowParts(); return `${n.y}-${p2(n.m)}-${p2(n.d)}`; };
export const nowTime = () => { const n = nowParts(); return `${p2(n.hh)}:${p2(n.mm)}`; };
export const isoDate = (y, m, d) => `${y}-${p2(m)}-${p2(d)}`;
const toUTC = (iso) => { const [y, m, d] = String(iso).slice(0, 10).split("-").map(Number); return Date.UTC(y, m - 1, d); };
export const addDays = (iso, n) => { const dt = new Date(toUTC(iso) + n * 86400000); return isoDate(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate()); };
export const daysBetween = (a, b) => Math.round((toUTC(b) - toUTC(a)) / 86400000);
/** Monday = 0 ... Sunday = 6 (Python weekday()). */
export const weekday = (iso) => (new Date(toUTC(iso)).getUTCDay() + 6) % 7;
export const weekBounds = (iso) => { const s = addDays(iso, -weekday(iso)); return [s, addDays(s, 6)]; };
export const monthBounds = (iso) => { const s = iso.slice(0, 8) + "01"; const nxt = addDays(addDays(s, 31).slice(0, 8) + "01", 0); return [s, addDays(nxt, -1)]; };
export const validDate = (s) => /^\d{4}-\d{2}-\d{2}$/.test(String(s || "")) && !Number.isNaN(toUTC(s));
export const validTime = (s) => /^([01]\d|2[0-3]):[0-5]\d$/.test(String(s || ""));
export const parseTime = (s) => (validTime(s) ? Number(s.slice(0, 2)) * 60 + Number(s.slice(3, 5)) : null);
export const minutesToTime = (m) => `${p2(Math.floor(m / 60))}:${p2(m % 60)}`;
/** Shift a 'YYYY-MM-DD HH:MM:SS' stamp by minutes (wall-clock arithmetic). */
export function shiftDateTime(stamp, minutes) {
  const [d, tm = "00:00:00"] = stamp.split(" "); const [hh, mm, ss = 0] = tm.split(":").map(Number);
  const ms = toUTC(d) + ((hh * 60 + mm + minutes) * 60 + Number(ss)) * 1000; const dt = new Date(ms);
  return `${isoDate(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate())} ${p2(dt.getUTCHours())}:${p2(dt.getUTCMinutes())}:${p2(dt.getUTCSeconds())}`;
}
export const minutesSince = (stamp, now = nowISO()) => { const f = (s) => { const [d, tm = "00:00:00"] = s.split(" "); const [hh, mm, ss = 0] = tm.split(":").map(Number); return toUTC(d) + ((hh * 60 + mm) * 60 + Number(ss)) * 1000; }; return (f(now) - f(stamp)) / 60000; };

/** All 'HH:MM' slot starts between start and end, skipping the break window (core/utils.time_slots). */
export function timeSlots(start, end, stepMin, breakStart = "", breakEnd = "") {
  const s = parseTime(start), e = parseTime(end);
  if (s === null || e === null || !(stepMin > 0)) return [];
  const bs = parseTime(breakStart), be = parseTime(breakEnd);
  const out = [];
  for (let cur = s; cur + stepMin <= e; cur += stepMin) {
    const inBreak = bs !== null && be !== null && bs <= cur && cur < be;
    if (!inBreak) out.push(minutesToTime(cur));
  }
  return out;
}
export function ageFromDob(dob, today = todayISO()) {
  if (!validDate(dob)) return "-";
  const [ty, tm, td] = today.split("-").map(Number); const [y, m, d] = dob.split("-").map(Number);
  let years = ty - y - ((tm < m || (tm === m && td < d)) ? 1 : 0);
  if (years >= 2) return `${years} y`;
  const months = (ty - y) * 12 + tm - m - (td < d ? 1 : 0);
  return `${Math.max(months, 0)} m`;
}
export function ageYears(dob, today = todayISO()) {
  if (!validDate(dob)) return null;
  const [ty, tm, td] = today.split("-").map(Number); const [y, m, d] = dob.split("-").map(Number);
  return ty - y - ((tm < m || (tm === m && td < d)) ? 1 : 0);
}

// ---------------------------------------------------------------- money / validation
export const round2 = (n) => Math.round((Number(n) || 0) * 100) / 100;
export const toFloat = (v, d = 0) => { const n = parseFloat(v); return Number.isFinite(n) ? n : d; };
export function formatMoney(value, symbol = "Rs.") {
  const v = Number(value) || 0; const neg = v < 0; const a = Math.abs(v);
  const s = Math.abs(a - Math.round(a)) < 0.005 ? Math.round(a).toLocaleString("en-US") : a.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${neg ? "-" : ""}${symbol} ${s}`;
}
export function normalizePhone(phone) {
  let p = String(phone || "").replace(/[^\d+]/g, "");
  if (p.startsWith("+92")) p = "0" + p.slice(3);
  else if (p.startsWith("92") && p.length === 12) p = "0" + p.slice(2);
  return p;
}
export const validPhone = (phone) => /^0\d{9,10}$/.test(normalizePhone(phone));
export const cleanText = (v, max = 2000) => String(v ?? "").trim().slice(0, max);

// ---------------------------------------------------------------- state
export function emptyState() {
  const s = { version: STATE_VERSION, settings: { ...DEFAULT_SETTINGS }, ids: {}, seq: {} };
  for (const t of TABLES) s[t] = [];
  return s;
}

class Store {
  constructor() { this.state = emptyState(); this.db = null; this.listeners = new Set(); this._timer = null; this._suspended = 0; this._dirty = false; this.lastError = ""; }

  async load() {
    this.db = await openDB();
    let raw = await idbGet(this.db, STORAGE_KEY);
    if (!raw) { try { raw = localStorage.getItem(STORAGE_KEY); } catch { raw = null; } }
    if (raw) {
      try { this.adopt(typeof raw === "string" ? JSON.parse(raw) : raw); } catch (e) { console.error("State could not be read, starting fresh", e); }
    }
    return this.state;
  }
  /** Replace the in-memory state with a parsed object (used by load and restore). */
  adopt(parsed) {
    if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.patients) || !Array.isArray(parsed.users)) throw err("err.not_backup_file");
    const fresh = emptyState();
    const next = { ...fresh, ...parsed };
    next.settings = { ...fresh.settings, ...(parsed.settings || {}) };
    next.ids = { ...(parsed.ids || {}) }; next.seq = { ...(parsed.seq || {}) };
    for (const t of TABLES) if (!Array.isArray(next[t])) next[t] = [];
    this.state = next;
  }
  subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  /** Mark the state changed: persist (coalesced) and notify listeners. */
  commit() {
    if (this._suspended) { this._dirty = true; return; }
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this.persist(), 0);
    for (const fn of this.listeners) { try { fn(this.state); } catch (e) { console.error(e); } }
  }
  /** Run many mutations with a single persist at the end (used by the seeder and restore). */
  async batch(fn) {
    this._suspended++;
    try { await fn(); } finally { this._suspended--; }
    if (!this._suspended && this._dirty) { this._dirty = false; this.commit(); }
  }
  async persist() {
    const json = JSON.stringify(this.state);
    const ok = await idbSet(this.db, STORAGE_KEY, json);
    if (!ok) { try { localStorage.setItem(STORAGE_KEY, json); } catch (e) { this.lastError = String(e); } }
    return ok;
  }
  async flush() { clearTimeout(this._timer); return this.persist(); }
  exportJSON() { return JSON.stringify({ ...this.state, sessions: [], exported_at: nowISO(), app: CFG.productName || "Clinic Management Lite" }, null, 1); }
  async importJSON(text) {
    const parsed = JSON.parse(text);
    this.adopt(parsed);
    this.state.sessions = [];
    this.commit(); await this.flush();
  }
  async reset() {
    this.state = emptyState();
    await idbSet(this.db, STORAGE_KEY, JSON.stringify(this.state));
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
    for (const fn of this.listeners) fn(this.state);
  }
  /** Auto-increment primary key per table. */
  nextId(table) { this.state.ids[table] = (this.state.ids[table] || 0) + 1; return this.state.ids[table]; }
  /** Named counters for business numbers (patient codes, Rx and invoice numbers). */
  nextSeq(name) { this.state.seq[name] = (this.state.seq[name] || 0) + 1; return this.state.seq[name]; }

  get settings() { return this.state.settings; }
  getSetting(key, fallback = "") { const v = this.state.settings[key]; return v === undefined || v === null ? (DEFAULT_SETTINGS[key] ?? fallback) : v; }
  setSettings(values) { for (const [k, v] of Object.entries(values)) this.state.settings[k] = v === null || v === undefined ? "" : String(v); this.commit(); }
  money(v) { return formatMoney(v, this.getSetting("currency_symbol", "Rs.")); }

  /** Audit trail entry (core/audit.py). */
  audit(action, entity, entityId = null, details = null, user = null) {
    const row = {
      id: this.nextId("audit_log"), user_id: user ? user.id ?? null : null, username: user ? user.username || "system" : "system",
      action, entity, entity_id: entityId === null || entityId === undefined ? null : String(entityId),
      details: details && typeof details === "object" ? JSON.stringify(details) : (details || ""), created_at: nowISO(),
    };
    this.state.audit_log.push(row);
  }
  tableCounts() { const o = {}; for (const t of TABLES) o[t] = this.state[t].length; return o; }
}

export const store = new Store();
window.addEventListener("pagehide", () => { store.flush(); });
