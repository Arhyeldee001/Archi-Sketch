const CACHE_NAME = 'archi-trace-v1';
const urlsToCache = [
  '/',
  '/static/js/main.js',
  '/static/css/styles.css',
  '/static/onboarding/',
  '/ar'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});