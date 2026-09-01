// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';

import 'package:punto_venta_express/main.dart';

void main() {
  testWidgets('muestra el catálogo y agrega un producto', (tester) async {
    await tester.pumpWidget(const PosApp());
    expect(find.text('PUNTO DE VENTA'), findsOneWidget);
    expect(find.text('Taco de pastor'), findsOneWidget);
    await tester.tap(find.text('Taco de pastor'));
    await tester.pump();
    expect(find.text('1'), findsOneWidget);
  });
}
