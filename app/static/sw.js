self.addEventListener('push', e => {
    const data = e.data.json();
    e.waitUntil(
        self.registration.showNotification(data.title, {
            body:  data.body,
            icon:  '/static/images/logo.png',
            data:  { url: data.url }
        })
    );
});

self.addEventListener('notificationclick', e => {
    e.notification.close();
    e.waitUntil(
        clients.openWindow(e.notification.data.url)
    );
});
