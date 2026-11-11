import 'package:flutter_test/flutter_test.dart';
import 'package:veda_learning/data/api_client.dart';
import 'package:veda_learning/main.dart';

void main() {
  testWidgets('welcome screen shows account actions', (tester) async {
    await tester.pumpWidget(VedaApp(api: ApiClient()));
    expect(find.text('Vedas Learning'), findsOneWidget);
    expect(find.text('Create account'), findsOneWidget);
    expect(find.text('Login'), findsOneWidget);
  });
}
