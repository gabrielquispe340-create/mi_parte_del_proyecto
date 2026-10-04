// Service worker de Firebase Cloud Messaging (avisos push de la web, HU-21).
// La versión de los scripts debe acompañar a la del paquete "firebase" de package.json.
importScripts('https://www.gstatic.com/firebasejs/12.19.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/12.19.0/firebase-messaging-compat.js');

// Identificadores públicos del proyecto (los mismos de environment.ts).
firebase.initializeApp({
  apiKey: 'AIzaSyDgUw0cDtksG9w_7V1Md4bLPQpcuM_3TRs',
  authDomain: 'egresa-uagrm.firebaseapp.com',
  projectId: 'egresa-uagrm',
  storageBucket: 'egresa-uagrm.firebasestorage.app',
  messagingSenderId: '943257325084',
  appId: '1:943257325084:web:fd93fe2f21837d6fe299d9',
});

const messaging = firebase.messaging();

// Con la pestaña cerrada o en segundo plano, Firebase ya muestra solo los avisos que
// traen "notification" (y al tocarlos abre fcm_options.link). Acá solo se muestran los
// que llegan únicamente con datos, para no duplicar el aviso.
messaging.onBackgroundMessage((payload) => {
  if (payload.notification) return;
  const datos = payload.data || {};
  self.registration.showNotification(datos.title || 'EGRESA', {
    body: datos.body || '',
    icon: '/favicon.ico',
    data: { link: datos.link || '/notificaciones' },
  });
});

// Clic en un aviso mostrado por este service worker: enfoca la pestaña de EGRESA o abre una.
self.addEventListener('notificationclick', (event) => {
  const link = event.notification.data && event.notification.data.link;
  if (!link) return;
  event.notification.close();
  const destino = new URL(link, self.location.origin).href;
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((ventanas) => {
      for (const ventana of ventanas) {
        if (ventana.url.startsWith(self.location.origin) && 'focus' in ventana) {
          ventana.navigate(destino);
          return ventana.focus();
        }
      }
      return clients.openWindow(destino);
    }),
  );
});
