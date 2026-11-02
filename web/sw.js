/* Service worker: caches the app shell so it opens instantly and works offline.
   Bump CACHE_VERSION whenever files change so clients pick up the update. */
const CACHE_VERSION = "cml-v1.0.0";
const SHELL = [
  "./", "./index.html", "./config.js", "./manifest.webmanifest",
  "./css/app.css",
  "./js/app.js", "./js/store.js", "./js/repo.js", "./js/auth.js", "./js/seed.js", "./js/ui.js", "./js/icons.js",
  "./js/i18n.js", "./js/charts.js", "./js/router.js", "./js/print.js",
  "./js/views/dashboard.js", "./js/views/patients.js", "./js/views/appointments.js", "./js/views/queue.js",
  "./js/views/consultations.js", "./js/views/prescriptions.js", "./js/views/billing.js", "./js/views/inventory.js",
  "./js/views/reports.js", "./js/views/settings.js",
  "./assets/logo.svg", "./assets/logo.png",
];

self.addEventListener("install", (event) => {
  // cache: "reload" bypasses the browser's HTTP cache, so a new version never installs stale files
  // (GitHub Pages marks files fresh for 10 minutes).
  event.waitUntil(caches.open(CACHE_VERSION).then((c) => c.addAll(SHELL.map((u) => new Request(u, { cache: "reload" })))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Fonts and other cross-origin assets: network first, fall back to cache.
  if (url.origin !== self.location.origin) {
    event.respondWith(
      fetch(req).then((res) => { const copy = res.clone(); caches.open(CACHE_VERSION).then((c) => c.put(req, copy)); return res; })
        .catch(() => caches.match(req))
    );
    return;
  }
  // Same-origin app files: cache first, refresh in the background.
  event.respondWith(
    caches.match(req).then((cached) => {
      const fetching = fetch(req, { cache: "no-cache" }).then((res) => {
        if (res && res.ok) caches.open(CACHE_VERSION).then((c) => c.put(req, res.clone()));
        return res;
      }).catch(() => cached);
      return cached || fetching;
    })
  );
});
