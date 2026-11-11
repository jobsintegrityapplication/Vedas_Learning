import 'package:flutter/foundation.dart';

class AppConfig {
  static const String fromEnvironment = String.fromEnvironment('API_BASE_URL');

  static String get apiBaseUrl {
    if (fromEnvironment.isNotEmpty) return fromEnvironment;
    if (kIsWeb) return 'http://127.0.0.1:8000';
    if (defaultTargetPlatform == TargetPlatform.android) return 'http://10.0.2.2:8000';
    return 'http://127.0.0.1:8000';
  }
}
