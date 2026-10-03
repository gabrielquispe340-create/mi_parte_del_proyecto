import 'package:egresa_app/core/models/entrevista.dart';
import 'package:egresa_app/core/models/vacante.dart';
import 'package:egresa_app/core/theme/app_theme.dart';
import 'package:egresa_app/core/utils/formatos.dart';
import 'package:egresa_app/features/postulaciones/tarjeta_entrevista.dart';
import 'package:egresa_app/features/vacantes/vacante_detalle_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _entrevistaJson({
  required String estado,
  required DateTime inicio,
  String modalidad = 'virtual',
}) =>
    {
      'id': 'e1',
      'application_id': 'p1',
      'scheduled_start': inicio.toUtc().toIso8601String(),
      'scheduled_end': inicio.add(const Duration(hours: 1)).toUtc().toIso8601String(),
      'modality': modalidad,
      'location': modalidad == 'onsite' ? 'Av. Busch 123' : null,
      'meeting_url': modalidad == 'virtual' ? 'https://meet.example.com/egresa' : null,
      'notes': 'Traé tu CV impreso.',
      'status': estado,
      'candidate_feedback': null,
      'rejection_count': 0,
      'requires_manual_review': false,
      'created_at': DateTime.now().toUtc().toIso8601String(),
      'updated_at': DateTime.now().toUtc().toIso8601String(),
      'empresa_nombre': 'TECNOVA',
      'vacante_titulo': 'Desarrollador Junior',
    };

Vacante _vacante() => Vacante.fromJson({
      'id': 'v1',
      'title': 'Desarrollador Junior',
      'company': {'trade_name': 'TECNOVA'},
      'description': 'Desarrollo de APIs.',
      'seniority_level': 'junior',
      'employment_type': 'temporary',
      'work_modality': 'remote',
      'city': 'Santa Cruz',
      'salary_min': '4200.00',
      'salary_max': '5200.00',
      'currency': 'BOB',
      'salary_visible': true,
      'positions_available': 2,
      'skills': [],
    });

Widget _app(Widget hijo) => MaterialApp(theme: AppTheme.claro(), home: Scaffold(body: SingleChildScrollView(child: hijo)));

void main() {
  group('Entrevista.fromJson', () {
    test('convierte la fecha UTC a hora local y reconoce una propuesta por responder', () {
      final inicio = DateTime.now().add(const Duration(days: 2));
      final e = Entrevista.fromJson(_entrevistaJson(estado: 'pending_confirmation', inicio: inicio));

      expect(e.inicio.isUtc, isFalse);
      expect(e.inicio.difference(inicio).inSeconds.abs(), lessThan(1));
      expect(e.esVirtual, isTrue);
      expect(e.requiereRespuesta, isTrue);
      expect(e.empresaNombre, 'TECNOVA');
    });

    test('una propuesta cuya fecha ya pasó no pide respuesta', () {
      final e = Entrevista.fromJson(
        _entrevistaJson(estado: 'pending_confirmation', inicio: DateTime.now().subtract(const Duration(days: 3))),
      );
      expect(e.pendiente, isTrue);
      expect(e.requiereRespuesta, isFalse);
    });
  });

  group('formatos', () {
    final ahora = DateTime(2026, 10, 3, 12);

    test('fechas en español', () {
      expect(fechaCorta(DateTime(2026, 10, 3)), '3 oct. 2026');
      expect(fechaLarga(DateTime(2026, 10, 8)), 'jueves 8 de octubre');
      expect(rangoHorario(DateTime(2026, 10, 8, 9, 5), DateTime(2026, 10, 8, 10)), '09:05 – 10:00');
    });

    test('tiempo relativo', () {
      expect(haceCuanto(DateTime(2026, 10, 3, 8), ahora: ahora), 'hoy');
      expect(haceCuanto(DateTime(2026, 10, 2), ahora: ahora), 'ayer');
      expect(haceCuanto(DateTime(2026, 9, 29), ahora: ahora), 'hace 4 días');
      expect(cuandoSera(DateTime(2026, 10, 4, 15), ahora: ahora), 'Mañana');
    });

    test('iniciales', () {
      expect(iniciales('Antonio Bravo'), 'AB');
      expect(iniciales('Antonio'), 'A');
    });
  });

  test('el salario se muestra en bolivianos con separador de miles', () {
    expect(_vacante().salarioLegible, 'Bs. 4.200 – 5.200');
    expect(_vacante().jornadaLegible, 'Temporal');
  });

  group('TarjetaEntrevista', () {
    testWidgets('una propuesta pendiente permite confirmar con un paso de confirmación', (tester) async {
      var confirmadas = 0;
      final e = Entrevista.fromJson(
        _entrevistaJson(estado: 'pending_confirmation', inicio: DateTime.now().add(const Duration(days: 3))),
      );
      await tester.pumpWidget(_app(TarjetaEntrevista(
        entrevista: e,
        onConfirmar: (_) async => confirmadas++,
        onRechazar: (_, _) async {},
      )));

      expect(find.text('Te propusieron una entrevista'), findsOneWidget);
      expect(find.text('Unirse a la videollamada'), findsOneWidget);
      expect(find.text('No puedo asistir'), findsOneWidget);

      await tester.tap(find.text('Confirmar asistencia'));
      await tester.pumpAndSettle();
      expect(confirmadas, 0, reason: 'primero pide confirmar en un diálogo');
      await tester.tap(find.widgetWithText(FilledButton, 'Confirmar'));
      await tester.pumpAndSettle();
      expect(confirmadas, 1);
    });

    testWidgets('rechazar exige un motivo y se lo pasa al callback', (tester) async {
      String? motivoEnviado;
      final e = Entrevista.fromJson(
        _entrevistaJson(estado: 'pending_confirmation', inicio: DateTime.now().add(const Duration(days: 3))),
      );
      await tester.pumpWidget(_app(TarjetaEntrevista(
        entrevista: e,
        onConfirmar: (_) async {},
        onRechazar: (_, motivo) async => motivoEnviado = motivo,
      )));

      await tester.tap(find.text('No puedo asistir'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Enviar respuesta'));
      await tester.pumpAndSettle();
      expect(find.text('Escribí un motivo (al menos 3 caracteres).'), findsOneWidget);
      expect(motivoEnviado, isNull);

      await tester.enterText(find.byType(TextFormField), 'Tengo un examen ese día');
      await tester.tap(find.text('Enviar respuesta'));
      await tester.pumpAndSettle();
      expect(motivoEnviado, 'Tengo un examen ese día');
    });

    testWidgets('una entrevista confirmada ya no muestra los botones de respuesta', (tester) async {
      final e = Entrevista.fromJson(
        _entrevistaJson(estado: 'confirmed', inicio: DateTime.now().add(const Duration(days: 1)), modalidad: 'onsite'),
      );
      await tester.pumpWidget(_app(TarjetaEntrevista(
        entrevista: e,
        onConfirmar: (_) async {},
        onRechazar: (_, _) async {},
      )));

      expect(find.text('Entrevista confirmada'), findsOneWidget);
      expect(find.text('Av. Busch 123'), findsOneWidget);
      expect(find.text('Confirmar asistencia'), findsNothing);
      expect(find.text('Unirse a la videollamada'), findsNothing);
    });
  });

  group('VacanteDetalleScreen (HU-34)', () {
    testWidgets('sin sesión invita a iniciar sesión en lugar de postularse', (tester) async {
      await tester.pumpWidget(MaterialApp(theme: AppTheme.claro(), home: VacanteDetalleScreen(vacante: _vacante())));
      expect(find.text('Iniciar sesión para postularme'), findsOneWidget);
      expect(find.text('Crear cuenta de egresado'), findsOneWidget);
      expect(find.text('Postularme'), findsNothing);
    });

    testWidgets('con sesión muestra el botón para postularse', (tester) async {
      await tester.pumpWidget(
        MaterialApp(theme: AppTheme.claro(), home: VacanteDetalleScreen(accessToken: 'token', vacante: _vacante())),
      );
      expect(find.text('Postularme'), findsOneWidget);
      expect(find.text('Bs. 4.200 – 5.200'), findsOneWidget);
    });
  });
}
