import 'dart:html' as html;

void clearSignupTokenFromUrl() {
  final location = html.window.location;
  html.window.history.replaceState(
    null,
    '',
    location.origin + (location.pathname ?? '/'),
  );
}
