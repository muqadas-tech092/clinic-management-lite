/* Tiny hash router (works on GitHub Pages without server rewrites). */
const listeners = new Set();
export function parseRoute() {
  const hash = location.hash.replace(/^#\/?/, "");
  const [page, query = ""] = hash.split("?");
  const params = Object.fromEntries(new URLSearchParams(query));
  return { page: page || "dashboard", params };
}
export function navigate(page, params = {}) {
  const q = new URLSearchParams(params).toString();
  const next = `#/${page}${q ? `?${q}` : ""}`;
  if (location.hash === next) { for (const fn of listeners) fn(parseRoute()); } else location.hash = next;
}
export function onRoute(fn) { listeners.add(fn); }
window.addEventListener("hashchange", () => { for (const fn of listeners) fn(parseRoute()); });
