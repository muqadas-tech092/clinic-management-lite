/* Authentication, sessions and role-based permissions (core/auth.py). Passwords are hashed with PBKDF2-SHA256
   through Web Crypto and stored in IndexedDB together with the rest of the state. */
import { store, err, nowISO, shiftDateTime, minutesSince, ROLES, SESSION_HOURS, IDLE_TIMEOUT_MIN, MAX_FAILED_LOGINS, LOCKOUT_MINUTES, cleanText } from "./store.js";

export const ROLE_LABELS = { admin: "Administrator", receptionist: "Receptionist", doctor: "Doctor" };
// Module permission matrix (core/config.py). Levels: "edit" > "view" > null.
export const PERMISSIONS = {
  dashboard:     { admin: "edit", receptionist: "view", doctor: "view" },
  appointments:  { admin: "edit", receptionist: "edit", doctor: "view" },
  patients:      { admin: "edit", receptionist: "edit", doctor: "edit" },
  queue:         { admin: "edit", receptionist: "edit", doctor: "edit" },
  consultations: { admin: "view", receptionist: null,   doctor: "edit" },
  prescriptions: { admin: "view", receptionist: null,   doctor: "edit" },
  billing:       { admin: "edit", receptionist: "edit", doctor: "view" },
  inventory:     { admin: "edit", receptionist: "edit", doctor: "view" },
  reports:       { admin: "edit", receptionist: "view", doctor: "view" },
  settings:      { admin: "edit", receptionist: "view", doctor: "view" },
};

const S = () => store.state;
const SESSION_KEY = `${(window.CML_CONFIG || {}).storageKey || "cml"}:session`;

// ---------------------------------------------------------------- passwords (PBKDF2 via Web Crypto)
const ITERATIONS = 120000;
const enc = new TextEncoder();
const b64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
const unb64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
function subtle() {
  if (!(window.crypto && window.crypto.subtle)) throw err("secure_context");
  return window.crypto.subtle;
}
async function derive(password, salt, iterations) {
  const key = await subtle().importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  return subtle().deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations }, key, 256);
}
export async function hashPassword(password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const bits = await derive(password, salt, ITERATIONS);
  return `pbkdf2$${ITERATIONS}$${b64(salt)}$${b64(bits)}`;
}
export async function verifyPassword(password, stored) {
  try {
    const [algo, iter, salt, hash] = String(stored || "").split("$");
    if (algo !== "pbkdf2") return false;
    const bits = new Uint8Array(await derive(password, unb64(salt), Number(iter)));
    const want = unb64(hash);
    if (bits.length !== want.length) return false;
    let diff = 0; for (let i = 0; i < bits.length; i++) diff |= bits[i] ^ want[i];
    return diff === 0;
  } catch { return false; }
}
export function passwordPolicyError(password) {
  const p = String(password || "");
  if (p.length < 8) return "err.password_short";
  if (/^\d+$/.test(p) || /^[A-Za-z]+$/.test(p)) return "err.password_mix";
  return null;
}
export const randomToken = () => b64(crypto.getRandomValues(new Uint8Array(32))).replace(/[+/=]/g, (c) => ({ "+": "-", "/": "_", "=": "" }[c]));

// ---------------------------------------------------------------- users
function decorate(u) {
  if (!u) return null;
  const d = u.doctor_id ? S().doctors.find((x) => x.id === u.doctor_id) : null;
  const { password_hash, ...rest } = u;
  return { ...rest, doctor_name: d ? d.name : null };
}
export const getUserRaw = (id) => S().users.find((u) => u.id === id) || null;
export const getUser = (id) => decorate(getUserRaw(id));
export const getUserByUsernameRaw = (username) => { const n = String(username || "").trim().toLowerCase(); return S().users.find((u) => u.username.toLowerCase() === n) || null; };
export const getUserByUsername = (username) => decorate(getUserByUsernameRaw(username));

export async function createUser(username, password, fullName, role, doctorId = null, actor = null) {
  username = cleanText(username, 40);
  if (!username) throw err("err.username_required");
  if (!ROLES.includes(role)) throw err("err.invalid_role");
  const pe = passwordPolicyError(password); if (pe) throw err(pe);
  if (getUserByUsernameRaw(username)) throw err("err.username_exists");
  const hash = await hashPassword(password);
  const id = store.nextId("users");
  S().users.push({ id, username, password_hash: hash, full_name: cleanText(fullName, 100), role, doctor_id: role === "doctor" ? (doctorId || null) : null,
    is_active: 1, failed_attempts: 0, locked_until: null, last_login: null, created_at: nowISO() });
  store.audit("create", "user", id, { username, role }, actor);
  store.commit();
  return id;
}
export async function setPassword(userId, newPassword, actor = null) {
  const pe = passwordPolicyError(newPassword); if (pe) throw err(pe);
  const u = getUserRaw(userId); if (!u) throw err("err.invalid_login");
  u.password_hash = await hashPassword(newPassword); u.failed_attempts = 0; u.locked_until = null;
  for (const s of S().sessions) if (s.user_id === userId) s.revoked = 1;
  store.audit("password_reset", "user", userId, null, actor);
  store.commit();
}
export async function changeOwnPassword(user, current, newPassword) {
  const u = getUserRaw(user.id);
  if (!u || !(await verifyPassword(current, u.password_hash))) throw err("err.current_password");
  const pe = passwordPolicyError(newPassword); if (pe) throw err(pe);
  u.password_hash = await hashPassword(newPassword);
  store.audit("password_change", "user", user.id, null, user);
  store.commit();
}

// ---------------------------------------------------------------- sessions
/** Returns {user, error}; error is {key, vars}. Applies lockout after repeated failures. */
export async function login(username, password) {
  username = String(username || "").trim();
  if (!username || !password) return { user: null, error: { key: "enter_credentials" } };
  const u = getUserByUsernameRaw(username);
  if (!u || !u.is_active) return { user: null, error: { key: "invalid_login" } };
  const now = nowISO();
  if (u.locked_until && u.locked_until > now) {
    const mins = Math.floor(-minutesSince(u.locked_until, now)) + 1;
    return { user: null, error: { key: "account_locked", vars: { n: mins } } };
  }
  if (!(await verifyPassword(password, u.password_hash))) {
    let attempts = (u.failed_attempts || 0) + 1; let lock = null;
    if (attempts >= MAX_FAILED_LOGINS) { lock = shiftDateTime(now, LOCKOUT_MINUTES); attempts = 0; }
    u.failed_attempts = attempts; u.locked_until = lock;
    store.audit("login_failed", "user", u.id, { username }, { id: null, username });
    store.commit();
    if (lock) return { user: null, error: { key: "too_many_attempts", vars: { n: LOCKOUT_MINUTES } } };
    return { user: null, error: { key: "invalid_login" } };
  }
  const token = randomToken();
  u.failed_attempts = 0; u.locked_until = null; u.last_login = now;
  S().sessions.push({ token, user_id: u.id, created_at: now, last_seen: now, expires_at: shiftDateTime(now, SESSION_HOURS * 60), revoked: 0 });
  store.audit("login", "user", u.id, { username }, u);
  store.commit();
  try { sessionStorage.setItem(SESSION_KEY, token); } catch { /* ignore */ }
  const user = decorate(u); user.session_token = token;
  return { user, error: null };
}
export const storedToken = () => { try { return sessionStorage.getItem(SESSION_KEY) || ""; } catch { return ""; } };
/** Return the user for a live session, refreshing last_seen; null if expired / revoked. */
export function validateSession(token, touch = true) {
  if (!token) return null;
  const row = S().sessions.find((s) => s.token === token && !s.revoked);
  if (!row) return null;
  const now = nowISO();
  if (row.expires_at < now) return null;
  if (minutesSince(row.last_seen, now) > IDLE_TIMEOUT_MIN) { row.revoked = 1; store.commit(); return null; }
  if (touch && minutesSince(row.last_seen, now) >= 1) { row.last_seen = now; store.commit(); }
  const u = getUserRaw(row.user_id);
  if (!u || !u.is_active) return null;
  const user = decorate(u); user.session_token = token;
  return user;
}
export function logout(token, user = null) {
  const row = S().sessions.find((s) => s.token === token);
  if (row) row.revoked = 1;
  store.audit("logout", "user", user ? user.id : null, null, user);
  try { sessionStorage.removeItem(SESSION_KEY); } catch { /* ignore */ }
  store.commit();
}
export function revokeAllSessions(userId, actor = null, keepToken = null) {
  for (const s of S().sessions) if (s.user_id === userId && s.token !== keepToken) s.revoked = 1;
  store.audit("revoke_sessions", "user", userId, null, actor);
  store.commit();
}
export function cleanupSessions() {
  const now = nowISO(); const before = S().sessions.length;
  S().sessions = S().sessions.filter((s) => !s.revoked && s.expires_at >= now);
  if (S().sessions.length !== before) store.commit();
}

// ---------------------------------------------------------------- permissions
export const permission = (user, module) => (user ? (PERMISSIONS[module] || {})[user.role] || null : null);
export const canView = (user, module) => ["view", "edit"].includes(permission(user, module));
export const canEdit = (user, module) => permission(user, module) === "edit";
export const isAdmin = (user) => !!user && user.role === "admin";
export const isDoctor = (user) => !!user && user.role === "doctor";

/** Verify an administrator's credentials for an in-place authorization (discounts). */
export async function authorizeAdmin(username, password) {
  const u = getUserByUsernameRaw(username || "");
  if (u && u.is_active && u.role === "admin" && (await verifyPassword(password || "", u.password_hash))) return { id: u.id, username: u.username, full_name: u.full_name };
  return null;
}
