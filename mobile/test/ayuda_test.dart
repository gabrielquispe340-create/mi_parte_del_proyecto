import 'package:egresa_app/core/widgets/boton_ayuda.dart';
import 'package:egresa_app/features/ayuda/ayuda_contenido.dart';
import 'package:egresa_app/features/ayuda/ayuda_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('El botón de ayuda abre el tema de la pantalla y lleva a toda la ayuda', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(appBar: AppBar(title: const Text('Vacantes'), actions: const [BotonAyuda('vacantes')])),
      ),
    );

    await tester.tap(find.byTooltip('Ayuda'));
    await tester.pumpAndSettle();
    expect(find.text('Buscar vacantes'), findsOneWidget);
    expect(find.text('Ver toda la ayuda'), findsOneWidget);

    await tester.tap(find.text('Ver toda la ayuda'));
    await tester.pumpAndSettle();
    expect(find.byType(AyudaScreen), findsOneWidget);
    // Un egresado no ve los temas de empresa.
    expect(find.text('Agenda de entrevistas'), findsNothing);

    await tester.enterText(find.byType(TextField), 'denuncio');
    await tester.pumpAndSettle();
    expect(find.text('Postularte a una vacante'), findsOneWidget);
    expect(find.text('Buscar vacantes'), findsNothing);
  });

  test('La búsqueda ignora acentos y separa egresados de empresas', () {
    expect(buscarTemasAyuda('ENTREVISTA', esEmpresa: true).map((t) => t.id), contains('agenda'));
    expect(buscarTemasAyuda('entrevista', esEmpresa: false).map((t) => t.id), isNot(contains('agenda')));
    expect(buscarTemasAyuda('afinidad', esEmpresa: false).map((t) => t.id), contains('vacantes'));
    expect(buscarTemasAyuda('', esEmpresa: true).every((t) => t.sirvePara(esEmpresa: true)), isTrue);
    expect(temaAyuda('no-existe').id, 'web');
  });
}
