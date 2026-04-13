// sw-salan.js — Service Worker cho QUẢN LÝ SÀ LAN PWA
const CACHE = 'salan-trung-hieu-v1';

self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE).then(function(cache) {
      return cache.addAll(['./QUAN_LY_SA_LAN.html', './manifest-salan.json'])
        .then(function() {
          return Promise.allSettled(
            ['https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap']
            .map(function(url) { return cache.add(url).catch(function(){}); })
          );
        });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE; })
            .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function(e) {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    caches.match(e.request).then(function(cached) {
      if (cached) return cached;
      return fetch(e.request).then(function(res) {
        if (res && res.status === 200) {
          var resClone = res.clone();
          caches.open(CACHE).then(function(cache) {
            cache.put(e.request, resClone);
          });
        }
        return res;
      }).catch(function() {
        return caches.match('./QUAN_LY_SA_LAN.html');
      });
    })
  );
});
