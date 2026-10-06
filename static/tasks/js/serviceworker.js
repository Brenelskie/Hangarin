// Cache only Hangarin's public offline page and static presentation assets.
// Never store authenticated HTML, forms, account responses, or task data.
const CACHE_NAME = 'hangarin-static-v1';
const PRECACHE_URLS = [
  '/offline/',
  '/static/tasks/css/hangarin.css',
  '/static/tasks/js/hangarin.js',
  '/static/tasks/img/favicon.svg',
  '/static/tasks/img/icon-192.png',
  '/static/tasks/img/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names => Promise.all(
      names.filter(name => name.startsWith('hangarin-static-') && name !== CACHE_NAME)
        .map(name => caches.delete(name))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  // Always fetch live HTML. If disconnected, display only a public offline page.
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match('/offline/')));
    return;
  }

  const url = new URL(request.url);
  if (url.origin === self.location.origin && PRECACHE_URLS.includes(url.pathname)) {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request)));
  }
});
