const CACHE_NAME = "architrace-cache-v1";
const urlsToCache = [
  "/",
  "/index.html",
  "/templates/dashboard.html",
  "/templates/login.html",
  "/templates/accounts.html",
  "/templates/onboarding.html",
  "/templates/payment.html",
  "/templates/tutorials.html",
  "/static/style.css",
  "/static/login.js",
  "/static/script.js",
  "/static/icons/icon-192x192.png",
  "/static/icons/icon-512x512.png"
];


// Install service worker & cache files
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(urlsToCache);
    })
  );
});

// Fetch from cache or network
self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});

// Update old caches
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    })
  );
});
