// Minimal service worker for PWA recognition.
// On iOS over non-localhost HTTP, this will not register (HTTPS required).
// Still useful for Android. If HTTPS is added later, iOS gains full PWA support.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
    event.waitUntil(self.clients.claim());
});
