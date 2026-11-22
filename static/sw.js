// Minimaalinen service worker: sovellus on asennettavissa; kaikki pyynnöt menevät verkkoon.
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {});
