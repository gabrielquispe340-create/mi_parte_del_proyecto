import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Paleta de EGRESA: la misma de la web (frontend/src/styles.scss) para que
/// la app y el sitio se sientan un solo producto.
abstract final class AppColors {
  static const primario = Color(0xFF1E3A8A);
  static const primarioOscuro = Color(0xFF172554);
  static const primarioSuave = Color(0xFFEFF6FF);
  static const primarioBorde = Color(0xFFBFDBFE);

  static const fondo = Color(0xFFF8FAFC);
  static const superficie = Colors.white;
  static const borde = Color(0xFFE2E8F0);
  static const texto = Color(0xFF0F172A);
  static const textoSuave = Color(0xFF64748B);
  static const textoTenue = Color(0xFF7A8699);

  static const exito = Color(0xFF15803D);
  static const exitoSuave = Color(0xFFF0FDF4);
  static const alerta = Color(0xFFB45309);
  static const alertaSuave = Color(0xFFFFFBEB);
  static const peligro = Color(0xFFDC2626);
  static const peligroSuave = Color(0xFFFEF2F2);
  static const violeta = Color(0xFF6D28D9);
  static const violetaSuave = Color(0xFFF5F3FF);
  static const info = Color(0xFF0369A1);
  static const infoSuave = Color(0xFFF0F9FF);
}

abstract final class AppTheme {
  static const radio = 14.0;

  /// Barras del sistema sobre fondos claros: íconos oscuros arriba y una barra
  /// de navegación clara (el estilo por defecto del AppBar la pinta de negro).
  static const barrasSistema = SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.dark,
    statusBarBrightness: Brightness.light,
    systemNavigationBarColor: AppColors.superficie,
    systemNavigationBarIconBrightness: Brightness.dark,
    systemNavigationBarDividerColor: Colors.transparent,
    // Sin esto Android pone un velo oscuro sobre los botones del sistema; la
    // app ya deja una franja blanca debajo (ver builder en main.dart).
    systemNavigationBarContrastEnforced: false,
  );

  /// Para pantallas con cabecera azul, como el login.
  static final barrasSistemaSobreOscuro = barrasSistema.copyWith(
    statusBarIconBrightness: Brightness.light,
    statusBarBrightness: Brightness.dark,
  );

  static ThemeData claro() {
    final esquema = ColorScheme.fromSeed(seedColor: AppColors.primario).copyWith(
      primary: AppColors.primario,
      onPrimary: Colors.white,
      primaryContainer: AppColors.primarioSuave,
      onPrimaryContainer: AppColors.primarioOscuro,
      surface: AppColors.superficie,
      onSurface: AppColors.texto,
      onSurfaceVariant: AppColors.textoSuave,
      outline: AppColors.borde,
      outlineVariant: AppColors.borde,
      error: AppColors.peligro,
    );

    final base = ThemeData(
      useMaterial3: true,
      colorScheme: esquema,
      fontFamily: 'Inter',
      scaffoldBackgroundColor: AppColors.fondo,
    );

    final texto = base.textTheme
        .apply(bodyColor: AppColors.texto, displayColor: AppColors.texto)
        .copyWith(
          headlineSmall: base.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.5),
          titleLarge: base.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.3),
          titleMedium: base.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600, letterSpacing: -0.1),
          titleSmall: base.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
          labelLarge: base.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w600),
          bodyMedium: base.textTheme.bodyMedium?.copyWith(height: 1.45),
        );

    OutlineInputBorder borde(Color color, [double ancho = 1]) => OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: BorderSide(color: color, width: ancho),
    );

    final formaBoton = RoundedRectangleBorder(borderRadius: BorderRadius.circular(12));
    const textoBoton = TextStyle(fontFamily: 'Inter', fontWeight: FontWeight.w600, fontSize: 15);

    return base.copyWith(
      textTheme: texto,
      appBarTheme: AppBarTheme(
        backgroundColor: AppColors.fondo,
        foregroundColor: AppColors.texto,
        elevation: 0,
        scrolledUnderElevation: 0.6,
        shadowColor: AppColors.borde,
        surfaceTintColor: Colors.transparent,
        systemOverlayStyle: barrasSistema,
        centerTitle: false,
        titleTextStyle: texto.titleLarge?.copyWith(fontSize: 19),
      ),
      cardTheme: CardThemeData(
        color: AppColors.superficie,
        elevation: 0,
        margin: EdgeInsets.zero,
        surfaceTintColor: Colors.transparent,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radio),
          side: const BorderSide(color: AppColors.borde),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.superficie,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
        border: borde(AppColors.borde),
        enabledBorder: borde(AppColors.borde),
        focusedBorder: borde(AppColors.primario, 1.6),
        errorBorder: borde(AppColors.peligro),
        focusedErrorBorder: borde(AppColors.peligro, 1.6),
        hintStyle: const TextStyle(color: AppColors.textoTenue),
        labelStyle: const TextStyle(color: AppColors.textoSuave),
        prefixIconColor: AppColors.textoSuave,
        suffixIconColor: AppColors.textoSuave,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: const Size(64, 50), shape: formaBoton, textStyle: textoBoton),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.primario,
          foregroundColor: Colors.white,
          elevation: 0,
          minimumSize: const Size(64, 50),
          shape: formaBoton,
          textStyle: textoBoton,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.primario,
          minimumSize: const Size(64, 50),
          side: const BorderSide(color: AppColors.borde),
          shape: formaBoton,
          textStyle: textoBoton,
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: AppColors.primario, textStyle: textoBoton),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: AppColors.primario,
        foregroundColor: Colors.white,
        elevation: 2,
        highlightElevation: 4,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        extendedTextStyle: textoBoton,
      ),
      chipTheme: const ChipThemeData(
        backgroundColor: AppColors.fondo,
        side: BorderSide(color: AppColors.borde),
        shape: StadiumBorder(),
        labelStyle: TextStyle(fontFamily: 'Inter', fontSize: 13, fontWeight: FontWeight.w500, color: AppColors.texto),
        padding: EdgeInsets.symmetric(horizontal: 4),
      ),
      listTileTheme: const ListTileThemeData(
        iconColor: AppColors.textoSuave,
        titleTextStyle: TextStyle(
          fontFamily: 'Inter',
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: AppColors.texto,
        ),
        subtitleTextStyle: TextStyle(fontFamily: 'Inter', fontSize: 13, color: AppColors.textoSuave, height: 1.35),
      ),
      dividerTheme: const DividerThemeData(color: AppColors.borde, thickness: 1, space: 1),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppColors.texto,
        contentTextStyle: const TextStyle(fontFamily: 'Inter', color: Colors.white, fontSize: 14),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.superficie,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        titleTextStyle: texto.titleLarge?.copyWith(fontSize: 19),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.superficie,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.superficie,
        surfaceTintColor: Colors.transparent,
        indicatorColor: AppColors.primarioSuave,
        height: 68,
        elevation: 0,
        labelTextStyle: WidgetStateProperty.resolveWith(
          (estados) => TextStyle(
            fontFamily: 'Inter',
            fontSize: 12,
            fontWeight: estados.contains(WidgetState.selected) ? FontWeight.w600 : FontWeight.w500,
            color: estados.contains(WidgetState.selected) ? AppColors.primario : AppColors.textoSuave,
          ),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (estados) =>
              IconThemeData(color: estados.contains(WidgetState.selected) ? AppColors.primario : AppColors.textoSuave),
        ),
      ),
      tabBarTheme: const TabBarThemeData(
        labelColor: AppColors.primario,
        unselectedLabelColor: AppColors.textoSuave,
        indicatorColor: AppColors.primario,
        dividerColor: AppColors.borde,
        labelStyle: TextStyle(fontFamily: 'Inter', fontWeight: FontWeight.w600, fontSize: 14),
        unselectedLabelStyle: TextStyle(fontFamily: 'Inter', fontWeight: FontWeight.w500, fontSize: 14),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.primario,
        linearTrackColor: AppColors.borde,
      ),
    );
  }
}
