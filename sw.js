// 班主任工作台 - Service Worker (离线缓存 + 后台同步)
const CACHE_NAME = 'teacher-workbench-v4';
const ASSETS_TO_CACHE = [
  '/',
  '/teacher-workbench.html',
  '/libs/echarts.min.js',
  '/libs/xlsx.full.min.js',
  '/libs/socket.io.min.js',
  '/manifest.json'
];

// Install: 预缓存所有静态资源
self.addEventListener('install', function(event) {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      console.log('[SW] Caching assets...');
      return cache.addAll(ASSETS_TO_CACHE).catch(function(err) {
        console.warn('[SW] Cache addAll failed (some may be unavailable):', err);
      });
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

// Activate: 清理旧缓存
self.addEventListener('activate', function(event) {
  console.log('[SW] Activating...');
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(key) { return key !== CACHE_NAME; })
            .map(function(key) { return caches.delete(key); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// Fetch: 缓存优先策略（离线可用）
self.addEventListener('fetch', function(event) {
  // 跳过非 GET 请求（API 写入操作）
  if (event.request.method !== 'GET') return;

  // 跳过 chrome-extension 等非 http/https 请求
  var url = new URL(event.request.url);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return;

  // API 请求：网络优先（不缓存API数据，因为需要实时性）
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(function() {
        // API 请求失败时返回离线提示
        return new Response(JSON.stringify({ offline: true, error: '当前处于离线模式' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }

  // Socket.IO 请求：网络优先
  if (url.pathname.startsWith('/socket.io/')) {
    event.respondWith(fetch(event.request).catch(function() {
      return new Response(null, { status: 503 });
    }));
    return;
  }

  // 静态资源：缓存优先
  event.respondWith(
    caches.match(event.request).then(function(cached) {
      if (cached) {
        // 后台更新缓存
        fetch(event.request).then(function(response) {
          if (response && response.status === 200) {
            caches.open(CACHE_NAME).then(function(cache) {
              cache.put(event.request, response.clone());
            });
          }
        }).catch(function() {});
        return cached;
      }
      // 不在缓存中，尝试网络
      return fetch(event.request).then(function(response) {
        if (response && response.status === 200) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      });
    })
  );
});

// 消息处理：接收主线程的同步请求
self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('[SW] Service Worker registered');
