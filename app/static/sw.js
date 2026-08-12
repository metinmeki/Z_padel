const CACHE_NAME = 'zpadel-admin-v1';
const OFFLINE_URLS = ['/static/css/admin.css', '/static/images/logo/Zpadel.jpeg'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(OFFLINE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;

  // Only handle simple GET requests for http(s) — skip POST, range requests, chrome-extension, etc.
  if (req.method !== 'GET' || !req.url.startsWith('http')) {
    return;
  }

  event.respondWith(
    fetch(req)
      .then((response) => {
        // Only cache successful, non-partial (non-206) responses
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
        }
        return response;
      })
      .catch(() =>
        caches.match(req).then((cached) => cached || new Response('Offline', { status: 503 }))
      )
  );
});

self.addEventListener('push', (e) => {
  let title = 'Z Padel', body = 'إشعار جديد', url = '/admin';
  try {
    const d = e.data.json();
    title = d.title || title;
    body  = d.body  || body;
    url   = d.url   || url;
  } catch(_) {}

  e.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon:             '/static/images/logo/Zpadel.jpeg',
      badge:            '/static/images/logo/Zpadel.jpeg',
      vibrate:          [200, 100, 200],
      requireInteraction: true,
      data:             { url },
    })
  );
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      for (const c of list) {
        if (c.url.includes('/admin') && 'focus' in c) return c.focus();
      }
      return clients.openWindow(e.notification.data.url || '/admin');
    })
  );
});