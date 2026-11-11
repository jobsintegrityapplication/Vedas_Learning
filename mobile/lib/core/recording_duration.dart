class RecordingDurationPolicy {
  const RecordingDurationPolicy._();

  // Allow a complete shloka while still bounding accidental long recordings.
  static const minimumRecitation = Duration(seconds: 2);
  static const maximumRecitation = Duration(seconds: 30);

  static bool canStop(Duration elapsed) => elapsed >= minimumRecitation;

  static int secondsRemaining(Duration elapsed) {
    final remainingMs = (minimumRecitation - elapsed).inMilliseconds;
    return remainingMs <= 0 ? 0 : (remainingMs + 999) ~/ 1000;
  }

  static String formatElapsed(Duration elapsed) {
    final seconds = elapsed.inSeconds;
    return '${(seconds ~/ 60).toString().padLeft(2, '0')}:${(seconds % 60).toString().padLeft(2, '0')}';
  }
}
