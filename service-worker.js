const CACHE_NAME = "nexus-v1";
const API_CACHE = "nexus-api-v1";

// Arquivos para cachear na instalação
const STATIC_ASSETS = [
  "/Nexus/",
  "/Nexus/index.html",
  "/Nexus/dashboard.html",
  "/Nexus/mesas.html",
  "/Nexus/comanda.html",
  "/Nexus/produtos.html",
  "/Nexus/insumos.html",
  "/Nexus/fichas_tecnicas.html",
  "/Nexus/vendas.html",
  "/Nexus/cadastro.html",
  "/Nexus/manifest.json",
  "/Nexus/imagens/favicon.png",
  "/Nexus/imagens/icon-192x192.png",
  "/Nexus/imagens/icon-512x512.png"
];

// Instalar service worker e cachear arquivos estáticos
self.addEventListener("install", event => {
  console.log("[Service Worker] Instalando...");
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log("[Service Worker] Cacheando arquivos estáticos");
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Ativar service worker e limpar caches antigos
self.addEventListener("activate", event => {
  console.log("[Service Worker] Ativando...");
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME && cacheName !== API_CACHE) {
            console.log("[Service Worker] Removendo cache antigo:", cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Interceptar requisições
self.addEventListener("fetch", event => {
  const { request } = event;
  const url = new URL(request.url);

  // Estratégia para chamadas de API (Network First)
  if (url.origin === "https://nexus-backend-pvj4.onrender.com") {
    event.respondWith(
      caches.open(API_CACHE).then(cache => {
        return fetch(request)
          .then(response => {
            // Cachear apenas respostas bem-sucedidas de GET
            if (request.method === "GET" && response.status === 200) {
              cache.put(request, response.clone());
            }
            return response;
          })
          .catch(() => {
            // Se offline, retornar do cache
            return cache.match(request);
          });
      })
    );
    return;
  }

  // Estratégia para arquivos estáticos (Cache First)
  event.respondWith(
    caches.match(request).then(cachedResponse => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(request).then(response => {
        // Não cachear se não for uma resposta válida
        if (!response || response.status !== 200 || response.type !== "basic") {
          return response;
        }

        // Cachear a resposta
        const responseToCache = response.clone();
        caches.open(CACHE_NAME).then(cache => {
          cache.put(request, responseToCache);
        });

        return response;
      });
    })
  );
});

// Sincronização em background (opcional)
self.addEventListener("sync", event => {
  if (event.tag === "sync-data") {
    event.waitUntil(syncData());
  }
});

async function syncData() {
  console.log("[Service Worker] Sincronizando dados...");
  // Implementar lógica de sincronização se necessário
}

// Notificações push (opcional)
self.addEventListener("push", event => {
  const options = {
    body: event.data ? event.data.text() : "Nova atualização disponível!",
    icon: "/Nexus/imagens/icon-192x192.png",
    badge: "/Nexus/imagens/favicon.png",
    vibrate: [200, 100, 200]
  };

  event.waitUntil(
    self.registration.showNotification("Nexus Restaurante", options)
  );
});

// Click em notificação
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow("/Nexus/dashboard.html")
  );
});