import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/theme.dart';
import 'core/language_service.dart';
import 'data/api_client.dart';
import 'features/auth.dart';
import 'state/session.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(VedaApp(api: ApiClient()));
}

class VedaApp extends StatelessWidget {
  const VedaApp({super.key, required this.api});
  final ApiClient api;

  @override
  Widget build(BuildContext context) {
    final linkParams = Uri.base.queryParameters;
    final signupToken = linkParams['signup_token'];
    final signupEmail = linkParams['email'];
    final initialPage = signupToken != null && signupEmail != null
        ? CompleteSignupPage(email: signupEmail, verificationToken: signupToken)
        : const WelcomePage();
    return ChangeNotifierProvider(
      create: (_) => Session(api),
      child: ChangeNotifierProvider(
        create: (_) => LanguageService(),
        child: Consumer<LanguageService>(
          builder: (context, language, _) => _UsageLifecycleBridge(
            child: MaterialApp(
              title: 'Vedas Learning',
              locale: language.locale,
              supportedLocales: LanguageService.supported.map((item) => Locale(item.code)),
              localizationsDelegates: GlobalMaterialLocalizations.delegates,
              debugShowCheckedModeBanner: false,
              theme: buildTheme(),
              home: initialPage,
            ),
          ),
        ),
      ),
    );
  }
}

class _UsageLifecycleBridge extends StatefulWidget {
  const _UsageLifecycleBridge({required this.child});
  final Widget child;

  @override
  State<_UsageLifecycleBridge> createState() => _UsageLifecycleBridgeState();
}

class _UsageLifecycleBridgeState extends State<_UsageLifecycleBridge> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final session = context.read<Session>();
    if (state == AppLifecycleState.resumed) {
      unawaited(session.resumeUsageTracking());
    } else {
      unawaited(session.pauseUsageTracking());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
