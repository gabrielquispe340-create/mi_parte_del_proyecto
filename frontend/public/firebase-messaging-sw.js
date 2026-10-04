// Service Worker para Firebase Cloud Messaging (FCM) — HU-21
importScripts('https://www.gstatic.com/firebasejs/10.9.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.9.0/firebase-messaging-compat.js');

// Configuración de Firebase (se sincroniza con tu proyecto de Firebase)
const firebaseConfig = {
  apiKey: "AIzaSyDummyKeyForEgresaUAGRMNotifications",
  authDomain: "egresa-uagrm.firebaseapp.com",
  projectId: "egresa-uagrm",
  storageBucket: "egresa-uagrm.appspot.com",
  messagingSenderId: "109876543210",
  appId: "1:109876543210:web:abcdef123456"
};

try {
  firebase.initializeApp(firebaseConfig);
  const messaging = firebase.messaging();

  messaging.onBackgroundMessage((payload) => {
    console.log('[firebase-messaging-sw.js] Mensaje Push FCM recibido en segundo plano:', payload);

    const notificationTitle = payload.notification?.title || payload.data?.title || 'Bolsa de Trabajo UAGRM';
    const notificationOptions = {
      body: payload.notification?.body || payload.data?.body || 'Tienes una nueva actualización en tu cuenta.',
      icon: '/favicon.ico',
      badge: '/favicon.ico',
      data: {
        link: payload.data?.link || payload.fcmOptions?.link || '/notificaciones'
      }
    };

    self.registration.showNotification(notificationTitle, notificationOptions);
  });
} catch (e) {
  console.warn('[firebase-messaging-sw.js] Firebase no configurado externamente, usando listeners nativos push.');
}

// Listener nativo de Push para máxima compatibilidad
self.addEventListener('push', (event) => {
  if (event.data) {
    try {
      const data = event.data.json();
      const title = data.notification?.title || data.title || 'Bolsa de Trabajo UAGRM';
      const options = {
        body: data.notification?.body || data.body || 'Tienes un nuevo aviso importante.',
        icon: '/favicon.ico',
        badge: '/favicon.ico',
        data: { link: data.link || data.data?.link || '/notificaciones' }
      };
      event.waitUntil(self.registration.showNotification(title, options));
    } catch (_) {
      event.waitUntil(
        self.registration.showNotification('Bolsa de Trabajo UAGRM', {
          body: event.data.text(),
          icon: '/favicon.ico'
        })
      );
    }
  }
});

// Manejo de clic en la notificación
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.link || '/notificaciones';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
