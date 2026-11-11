import 'package:flutter_test/flutter_test.dart';
import 'package:veda_learning/core/recording_duration.dart';

void main() {
  test('short shloka recording can stop after the two-second minimum', () {
    expect(RecordingDurationPolicy.canStop(Duration.zero), isFalse);
    expect(
        RecordingDurationPolicy.canStop(
            const Duration(seconds: 1, milliseconds: 999)),
        isFalse);
    expect(RecordingDurationPolicy.canStop(const Duration(seconds: 2)), isTrue);
  });

  test('countdown is rounded up and does not jump below zero', () {
    expect(RecordingDurationPolicy.secondsRemaining(Duration.zero), 2);
    expect(
        RecordingDurationPolicy.secondsRemaining(
            const Duration(milliseconds: 1)),
        2);
    expect(
        RecordingDurationPolicy.secondsRemaining(
            const Duration(seconds: 1, milliseconds: 1)),
        1);
    expect(RecordingDurationPolicy.secondsRemaining(const Duration(seconds: 2)),
        0);
    expect(RecordingDurationPolicy.secondsRemaining(const Duration(seconds: 3)),
        0);
  });

  test('elapsed display stays monotonic in minutes and seconds', () {
    expect(RecordingDurationPolicy.formatElapsed(const Duration(seconds: 9)),
        '00:09');
    expect(RecordingDurationPolicy.formatElapsed(const Duration(seconds: 15)),
        '00:15');
    expect(RecordingDurationPolicy.formatElapsed(const Duration(seconds: 61)),
        '01:01');
  });
}
