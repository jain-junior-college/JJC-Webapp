const CACHE_NAME = 'jj-college-v1';
const ASSETS = [
  '/',
  '/static/css/landing.css',
  '/static/images/logo.jpg',
  '/static/images/icons/icon-192.png'
];

// Install Service Worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

// Fetch Assets
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
