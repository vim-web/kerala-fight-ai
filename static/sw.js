const CACHE_NAME = 'kerala-fight-v5';
const ASSETS = [
  'static/characters/boss/angry.svg',
  'static/characters/boss/laughing.svg',
  'static/characters/boss/shocked.svg',
  'static/characters/boss/sulking.svg',
  'static/characters/boss/speaking.svg',
  'static/characters/girlfriend/angry.svg',
  'static/characters/girlfriend/laughing.svg',
  'static/characters/girlfriend/shocked.svg',
  'static/characters/girlfriend/sulking.svg',
  'static/characters/girlfriend/speaking.svg'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  // Network-first for HTML, JS, CSS so updates always load immediately
  if (url.pathname.endsWith('.js') || url.pathname.endsWith('.css') || url.pathname.endsWith('/')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }
  if (url.pathname.includes('/characters/')) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
  }
});
