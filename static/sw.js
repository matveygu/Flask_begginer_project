const CACHE = 'fizteh-v1';

const PRECACHE = [
    '/static/css/main.css',
    '/static/js/slots.js',
    '/static/images/slots/0_diamond.png',
    '/static/images/slots/0_floppy.png',
    '/static/images/slots/0_hourglass.png',
    '/static/images/slots/0_seven.png',
    '/static/images/slots/0_telephone.png',
];

self.addEventListener('install', function (e) {
    e.waitUntil(
        caches.open(CACHE).then(function (cache) {
            return cache.addAll(PRECACHE);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function (e) {
    e.waitUntil(
        caches.keys().then(function (keys) {
            return Promise.all(
                keys.filter(function (k) { return k !== CACHE; })
                    .map(function (k) { return caches.delete(k); })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', function (e) {
    // Only cache GET requests; skip API/AJAX calls
    if (e.request.method !== 'GET') return;
    const url = new URL(e.request.url);
    if (url.pathname.startsWith('/spin') ||
        url.pathname.startsWith('/roll_dice') ||
        url.pathname.startsWith('/update_balance') ||
        url.pathname.startsWith('/like')) {
        return;
    }

    e.respondWith(
        caches.match(e.request).then(function (cached) {
            return cached || fetch(e.request).then(function (response) {
                // Cache static assets only
                if (url.pathname.startsWith('/static/')) {
                    var clone = response.clone();
                    caches.open(CACHE).then(function (cache) {
                        cache.put(e.request, clone);
                    });
                }
                return response;
            });
        })
    );
});
