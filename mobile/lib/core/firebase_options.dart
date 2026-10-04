import 'package:firebase_core/firebase_core.dart';

/// Proyecto de Firebase de EGRESA para la app Android (avisos push, HU-21).
/// Son los identificadores públicos de google-services.json, no secretos: van dentro
/// del APK. La llave privada del servidor nunca está en la app.
const opcionesFirebaseAndroid = FirebaseOptions(
  apiKey: 'AIzaSyCSXGT_vrqrJk_VAb8hYhi4TO4rAlTRoSY',
  appId: '1:943257325084:android:9a80af0a9f82ad1ce299d9',
  messagingSenderId: '943257325084',
  projectId: 'egresa-uagrm',
  storageBucket: 'egresa-uagrm.firebasestorage.app',
);
