const CACHE = "khds-shell-v1";
const SHELL = ["/manifest.json", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith("khds-") && key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  // Never cache project data, uploads, TTS, or API responses: those require a live server.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/files/")) return;

  // Always fetch the HTML shell from the live server so a newly deployed UI
  // appears immediately; the app is online-first, not an offline editor.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request));
    return;
  }

  if (url.pathname.startsWith("/assets/") || SHELL.includes(url.pathname)) {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) caches.open(CACHE).then((cache) => cache.put(request, response.clone()));
      return response;
    })));
  }
});
