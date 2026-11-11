import 'dart:async';

import 'package:flutter/foundation.dart';

import '../data/api_client.dart';

class Session extends ChangeNotifier {
  Session(this.api);

  final ApiClient api;
  String? userId;
  String? role;
  String? email;
  String? username;
  String? refreshToken;
  String? _usageSessionId;
  Timer? _usageHeartbeat;

  bool get isLoggedIn => api.accessToken != null;
  bool get isAdmin => role == 'admin';

  Future<Map<String, dynamic>> startSignup(String email) {
    return api.post('/api/auth/register', body: {'email': email});
  }

  Future<Map<String, dynamic>> registerDirect({
    required String email,
    required String phone,
    required String password,
    required String confirmPassword,
  }) {
    return api.post('/api/auth/register-direct', body: {
      'email': email,
      'phone': phone,
      'password': password,
      'confirm_password': confirmPassword,
    });
  }

  Future<void> verifySignupLink(String email, String token) async {
    await api.post('/api/auth/verify-email-link', body: {
      'email': email,
      'verification_token': token,
    });
  }

  Future<void> completeSignup({
    required String email,
    required String verificationToken,
    required String fullName,
    String phone = '',
    required String password,
  }) async {
    final data = await api.post('/api/auth/complete-signup', body: {
      'email': email,
      'verification_token': verificationToken,
      'full_name': fullName,
      if (phone.trim().isNotEmpty) 'phone': phone.trim(),
      'password': password,
    });
    await _acceptAuth(data, email);
  }

  Future<void> login(String identifier, String password) async {
    final data = await api.post('/api/auth/login',
        body: {'identifier': identifier, 'password': password});
    await _acceptAuth(data, identifier);
  }

  Future<Map<String, dynamic>> forgot(String emailAddress) {
    return api.post('/api/auth/forgot-password', body: {'email': emailAddress});
  }

  Future<void> reset(String emailAddress, String otp, String password) async {
    await api.post('/api/auth/reset-password',
        body: {'email': emailAddress, 'otp': otp, 'new_password': password});
  }

  Future<void> logout() async {
    await pauseUsageTracking();
    try {
      if (api.accessToken != null) {
        await api.post('/api/auth/logout');
      }
    } catch (_) {
      // Always clear local credentials even if the server is unreachable.
    }
    api.accessToken = null;
    refreshToken = null;
    userId = null;
    role = null;
    email = null;
    username = null;
    notifyListeners();
  }

  Future<void> refreshSession() async {
    if (refreshToken == null) {
      throw ApiException('Session expired');
    }
    final data = await api
        .post('/api/auth/refresh', body: {'refresh_token': refreshToken});
    await _acceptAuth(data, email ?? '');
  }

  Future<Map<String, dynamic>?> logLearningEvent(
      {required String eventType,
      String? scriptureSlug,
      String? lessonSlug,
      int durationSeconds = 0}) async {
    if (api.accessToken == null) return null;
    try {
      return await api.post('/api/activity', body: {
        'event_type': eventType,
        if (scriptureSlug != null) 'scripture_slug': scriptureSlug,
        if (lessonSlug != null) 'lesson_slug': lessonSlug,
        'duration_seconds': durationSeconds,
      });
    } catch (_) {
      // Activity collection must not block learning if the network is temporarily unavailable.
      return null;
    }
  }

  Future<void> _acceptAuth(Map<String, dynamic> data, String identifier) async {
    api.accessToken = data['access_token'] as String?;
    refreshToken = data['refresh_token'] as String?;
    userId = data['user_id']?.toString();
    role = data['role']?.toString();
    username = data['username']?.toString();
    email = identifier.contains('@')
        ? identifier
        : (data['email']?.toString() ?? email);
    notifyListeners();
    await resumeUsageTracking();
  }

  Future<void> resumeUsageTracking() async {
    if (!isLoggedIn || _usageSessionId != null) return;
    try {
      final data = await api.post('/api/activity/sessions');
      _usageSessionId = data['session_id']?.toString();
      if (_usageSessionId != null) {
        _usageHeartbeat?.cancel();
        _usageHeartbeat = Timer.periodic(const Duration(seconds: 30),
            (_) => unawaited(_sendUsageHeartbeat()));
      }
    } catch (_) {
      // A failed activity request must not block app use.
    }
  }

  Future<void> _sendUsageHeartbeat() async {
    final id = _usageSessionId;
    if (id == null || !isLoggedIn) return;
    try {
      await api.post('/api/activity/sessions/$id/heartbeat');
    } catch (_) {
      // A later heartbeat can recover after a temporary network interruption.
    }
  }

  Future<void> pauseUsageTracking() async {
    _usageHeartbeat?.cancel();
    _usageHeartbeat = null;
    final id = _usageSessionId;
    _usageSessionId = null;
    if (id == null || !isLoggedIn) return;
    try {
      await api.post('/api/activity/sessions/$id/end');
    } catch (_) {
      // Stale sessions are closed by the backend when a later session starts.
    }
  }
}
