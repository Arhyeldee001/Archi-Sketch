// Empty service worker - just enough to trigger PWA
self.addEventListener('install', event => {
  self.skipWaiting();
});
