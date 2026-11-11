import 'package:flutter_test/flutter_test.dart';
import 'package:veda_learning/core/language_service.dart';

void main() {
  test('all ten requested interface locales have lesson labels', () {
    final service = LanguageService();
    expect(LanguageService.supported.map((item) => item.code).toSet(),
        {'en', 'hi', 'kn', 'ta', 'te', 'ml', 'mr', 'bn', 'gu', 'pa'});
    for (final language in LanguageService.supported) {
      service.select(language.code);
      expect(service.text('practice'), isNotEmpty, reason: language.code);
      expect(service.text('meaning'), isNotEmpty, reason: language.code);
      expect(service.text('complete'), isNotEmpty, reason: language.code);
    }
  });
}
