export const environment = {
  production: false,
  apiUrl: 'http://127.0.0.1:8000/api',
  sessionTimeoutMinutes: 15,
  // Firebase Cloud Messaging (avisos push, HU-21). Son identificadores públicos del
  // proyecto, no secretos: el navegador los necesita para pedir su token.
  firebase: {
    apiKey: 'AIzaSyDgUw0cDtksG9w_7V1Md4bLPQpcuM_3TRs',
    authDomain: 'egresa-uagrm.firebaseapp.com',
    projectId: 'egresa-uagrm',
    storageBucket: 'egresa-uagrm.firebasestorage.app',
    messagingSenderId: '943257325084',
    appId: '1:943257325084:web:fd93fe2f21837d6fe299d9',
  },
  firebaseVapidKey: 'BARovUQda1nYkvsaAl5fU8S1WC162Ki1juxbgrH_R9YraLD7EFaC-f0tH52BMKqt7Jsgl-uNCU5VHf4Y0yWsCZs',
};
