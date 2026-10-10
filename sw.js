// sw.js — Service Worker cho app Quản Lý & Điều Phối Sà Lan – Trung Hiếu
// Mỗi lần sửa index.html / icon / manifest: tăng VERSION để máy đã cài tải bản mới.
const VERSION = 'th-salan-v4';
const PREFIX  = 'th-salan-';
const CORE    = VERSION + '-core';     // trang + icon + manifest
const RUNTIME = VERSION + '-rt';       // font, thư viện từ CDN
const LEGACY  = ['salan-trung-hieu-v1']; // cache của sw-salan.js cũ

const CORE_FILES = [
  './',
  './index.html',
  './manifest.json',
  './map-data.json',          // mạng sông, kênh thật (OpenStreetMap) + tuyến
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-192.png',
  './icons/icon-maskable-512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon-32.png',
];
// chỉ lưu các nguồn tĩnh này; API vị trí, Google Apps Script… luôn đi thẳng ra mạng
const CDN_IMMUTABLE = ['fonts.gstatic.com', 'cdnjs.cloudflare.com'];
const CDN_REFRESH   = ['fonts.googleapis.com'];
const NET_TIMEOUT   = 4000; // ms – sóng yếu trên sông thì mở bản đã lưu, cập nhật ngầm

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CORE);
    // tải từng tệp, bỏ qua HTTP cache; một tệp lỗi không làm hỏng cả lần cài
    await Promise.all(CORE_FILES.map(url =>
      cache.add(new Request(url, { cache: 'reload' })).catch(() => {})
    ));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys
      .filter(k => (k.startsWith(PREFIX) && k !== CORE && k !== RUNTIME) || LEGACY.includes(k))
      .map(k => caches.delete(k)));
    if (self.registration.navigationPreload) {
      try { await self.registration.navigationPreload.enable(); } catch (e) {}
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (url.origin === self.location.origin && url.pathname.includes('/api/')) return; // hàm máy chủ: luôn đi mạng

  if (req.mode === 'navigate') {
    event.respondWith(pageNetworkFirst(event));
  } else if (url.origin === self.location.origin) {
    event.respondWith(staleWhileRevalidate(event, CORE));
  } else if (CDN_IMMUTABLE.includes(url.hostname)) {
    event.respondWith(cacheFirst(event, RUNTIME));
  } else if (CDN_REFRESH.includes(url.hostname)) {
    event.respondWith(staleWhileRevalidate(event, RUNTIME));
  }
  // còn lại: không can thiệp
});

// Trang: ưu tiên bản mới trên mạng; mạng chậm/mất thì dùng bản đã lưu.
async function pageNetworkFirst(event) {
  const req = event.request;
  const cache = await caches.open(CORE);
  const network = (async () => {
    const res = (await event.preloadResponse) || (await fetch(req));
    if (res && res.ok && res.type === 'basic') event.waitUntil(cache.put(req, res.clone()));
    return res;
  })();
  event.waitUntil(network.catch(() => {}));

  const cached = (await cache.match(req, { ignoreSearch: true }))
    || (await cache.match('./index.html'))
    || (await cache.match('./'));
  if (!cached) return network.catch(offlinePage);

  const timeout = new Promise(resolve => setTimeout(() => resolve(cached), NET_TIMEOUT));
  return Promise.race([network.catch(() => cached), timeout]);
}

async function staleWhileRevalidate(event, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(event.request);
  const network = fetch(event.request).then(res => {
    if (res && (res.ok || res.type === 'opaque')) cache.put(event.request, res.clone());
    return res;
  });
  event.waitUntil(network.catch(() => {}));
  return cached || network;
}

async function cacheFirst(event, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(event.request);
  if (cached) return cached;
  const res = await fetch(event.request);
  if (res && (res.ok || res.type === 'opaque')) event.waitUntil(cache.put(event.request, res.clone()));
  return res;
}

function offlinePage() {
  return new Response(
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>Mất kết nối</title><body style="margin:0;display:grid;place-items:center;height:100vh;background:#0e1117;color:#f0f5fa;font-family:Roboto,sans-serif;text-align:center">' +
    '<div><h2 style="margin:0 0 8px">Chưa có kết nối mạng</h2><p style="color:#94a3b8">Mở lại app khi có sóng để tải dữ liệu lần đầu.</p>' +
    '<button onclick="location.reload()" style="margin-top:10px;padding:10px 20px;background:#e8a020;border:0;font-weight:700;cursor:pointer">Thử lại</button></div>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}
