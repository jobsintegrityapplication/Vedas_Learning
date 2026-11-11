import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';
import 'package:video_player/video_player.dart';

import '../state/session.dart';
import '../core/language_service.dart';
import '../core/recording_duration.dart';
import '../core/recording_download_stub.dart'
    if (dart.library.html) '../core/recording_download_web.dart';
import '../widgets/forms.dart';

class LessonPage extends StatefulWidget {
  const LessonPage({super.key, required this.slug});
  final String slug;
  @override
  State<LessonPage> createState() => _LessonPageState();
}

class _LessonPageState extends State<LessonPage> with WidgetsBindingObserver {
  static const Map<String, String> _guruAudioByLesson = {
    'rigveda-01': 'assets/audio/guru_reference/rigveda-01.ogg',
    'rigveda-02': 'assets/audio/guru_reference/rigveda-02.ogg',
    'rigveda-03': 'assets/audio/guru_reference/rigveda-03.ogg',
    'rigveda-04': 'assets/audio/guru_reference/rigveda-04.ogg',
    'rigveda-05': 'assets/audio/guru_reference/rigveda-05.ogg',
    'rigveda-06': 'assets/audio/guru_reference/rigveda-06.ogg',
    'rigveda-07': 'assets/audio/guru_reference/rigveda-07.ogg',
    'rigveda-08': 'assets/audio/guru_reference/rigveda-08.ogg',
    'rigveda-09': 'assets/audio/guru_reference/rigveda-09.ogg',
  };
  static const Map<String, String> _lessonVideoAssets = {
    'rigveda-01': 'assets/videos/rigveda-01-truth-righteousness.mp4',
    'rigveda-02': 'assets/videos/rigveda-02-everyone-walk-together.mp4',
    'rigveda-03': 'assets/videos/rigveda-03-united-thoughts.mp4',
    'rigveda-04': 'assets/videos/rigveda-04-good-ideas-directions.mp4',
    'rigveda-05': 'assets/videos/rigveda-05-morning-opportunity.mp4',
    'rigveda-06': 'assets/videos/rigveda-06-mutual-love-friendship.mp4',
    'rigveda-07': 'assets/videos/rigveda-07-pursuit-knowledge.mp4',
    'rigveda-08': 'assets/videos/rigveda-08-value-sharing.mp4',
    'rigveda-09': 'assets/videos/rigveda-09-universal-peace.mp4',
  };

  Map<String, dynamic>? lesson;
  Map<String, dynamic>? multilingualLesson;
  Map<String, dynamic>? guruTimingLesson;
  String? error;
  final recorder = AudioRecorder();
  StreamSubscription<RecordState>? recorderStateSubscription;
  StreamSubscription<Duration>? guruPositionSubscription;
  StreamSubscription<PlayerState>? guruStateSubscription;
  final player = AudioPlayer();
  final guruPlayer = AudioPlayer();
  VideoPlayerController? lessonVideoController;
  bool lessonVideoLoadFailed = false;
  bool _lessonVideoIsPlaying = false;
  String? path;
  String? result;
  Map<String, dynamic>? alignmentResult;
  Map<String, dynamic>? speechReport;
  Map<String, dynamic>? profileAudio;
  Map<int, String> wordClipAssets = {};
  int? activeWordIndex;
  String? activeAkshara;
  bool guruPlaybackActive = false;
  bool _guruTimelinePlayback = false;
  bool _guruSourceIsFullVerse = true;
  String recitationProfile = 'Common';
  bool recording = false;
  bool recordingPreviewed = false;
  bool uploading = false;
  bool userRequestedRecorderStop = false;
  bool recorderStopInProgress = false;
  Duration? savedRecordingDuration;
  String browserRecordingExtension = 'webm';
  String? pendingEvaluationId;
  bool completed = false;
  int activeLine = 0;
  List<int> completedLines = [];
  double playbackSpeed = 1.0;
  Timer? lessonTimer;
  DateTime? lessonTimeStartedAt;
  final Stopwatch recordingStopwatch = Stopwatch();
  Timer? recordingTick;
  late final Session session;

  Duration get recordingElapsed => recordingStopwatch.elapsed;
  bool get minimumRecordingReached =>
      RecordingDurationPolicy.canStop(recordingElapsed);
  int get recordingSecondsRemaining =>
      RecordingDurationPolicy.secondsRemaining(recordingElapsed);
  String get recordingElapsedLabel =>
      RecordingDurationPolicy.formatElapsed(recordingElapsed);

  @override
  void initState() {
    super.initState();
    session = context.read<Session>();
    WidgetsBinding.instance.addObserver(this);
    recorderStateSubscription = recorder.onStateChanged().listen(
      _handleRecorderState,
      onError: (Object error) {
        if (mounted && recording && !userRequestedRecorderStop) {
          _handleUnexpectedRecorderStop();
        }
      },
    );
    guruPositionSubscription =
        guruPlayer.positionStream.listen(_syncGuruHighlight);
    guruStateSubscription = guruPlayer.playerStateStream.listen((state) {
      if (state.processingState == ProcessingState.completed &&
          _guruTimelinePlayback) {
        _clearGuruHighlight();
      }
    });
    _load();
    if (_lessonVideoAssets.containsKey(widget.slug)) {
      unawaited(_loadLessonVideo());
    }
  }

  Future<void> _loadLessonVideo() async {
    final asset = _lessonVideoAssets[widget.slug];
    if (asset == null) return;
    final controller = VideoPlayerController.asset(asset);
    lessonVideoController = controller;
    controller.addListener(() {
      final isPlaying = controller.value.isPlaying;
      if (mounted && isPlaying != _lessonVideoIsPlaying) {
        setState(() => _lessonVideoIsPlaying = isPlaying);
      }
    });
    try {
      await controller.initialize();
      if (!mounted) return;
      setState(() {});
    } catch (_) {
      if (mounted) setState(() => lessonVideoLoadFailed = true);
    }
  }

  Future<void> _pauseLessonVideo() async {
    final controller = lessonVideoController;
    if (controller != null &&
        controller.value.isInitialized &&
        controller.value.isPlaying) {
      await controller.pause();
    }
  }

  Future<void> _toggleLessonVideo() async {
    final controller = lessonVideoController;
    if (controller == null || !controller.value.isInitialized) return;
    if (recording) {
      showMessage(context, 'Stop recording before playing the lesson video.');
      return;
    }
    await player.pause();
    await guruPlayer.pause();
    if (controller.value.isPlaying) {
      await controller.pause();
    } else {
      await controller.play();
    }
    if (mounted) {
      setState(() => _lessonVideoIsPlaying = controller.value.isPlaying);
    }
  }

  String _videoTime(Duration duration) {
    final totalSeconds = duration.inSeconds;
    final minutes = (totalSeconds ~/ 60).toString().padLeft(2, '0');
    final seconds = (totalSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  Widget _lessonVideoCard(BuildContext context) {
    final controller = lessonVideoController;
    final lessonTitle = lesson?['title']?.toString() ?? 'Sanskrit lesson';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Lesson video · $lessonTitle',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            const Text(
                'Watch the video, then return to the shloka and meaning.'),
            const SizedBox(height: 12),
            if (lessonVideoLoadFailed)
              const Text('This lesson video could not be loaded.')
            else if (controller == null || !controller.value.isInitialized)
              const SizedBox(
                height: 200,
                child: Center(child: CircularProgressIndicator()),
              )
            else ...[
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: AspectRatio(
                  aspectRatio: controller.value.aspectRatio > 0
                      ? controller.value.aspectRatio
                      : 16 / 9,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      VideoPlayer(controller),
                      if (!_lessonVideoIsPlaying)
                        IconButton.filledTonal(
                          tooltip: 'Play lesson video',
                          onPressed: _toggleLessonVideo,
                          iconSize: 42,
                          icon: const Icon(Icons.play_arrow),
                        ),
                    ],
                  ),
                ),
              ),
              VideoProgressIndicator(
                controller,
                allowScrubbing: true,
                padding: const EdgeInsets.symmetric(vertical: 10),
                colors: VideoProgressColors(
                  playedColor: Theme.of(context).colorScheme.primary,
                  bufferedColor:
                      Theme.of(context).colorScheme.primary.withOpacity(0.25),
                  backgroundColor:
                      Theme.of(context).colorScheme.onSurface.withOpacity(0.15),
                ),
              ),
              Row(
                children: [
                  IconButton(
                    tooltip:
                        _lessonVideoIsPlaying ? 'Pause video' : 'Play video',
                    onPressed: _toggleLessonVideo,
                    icon: Icon(_lessonVideoIsPlaying
                        ? Icons.pause_circle_filled
                        : Icons.play_circle_fill),
                  ),
                  ValueListenableBuilder<VideoPlayerValue>(
                    valueListenable: controller,
                    builder: (context, value, child) => Text(
                        '${_videoTime(value.position)} / ${_videoTime(value.duration)}'),
                  ),
                  const Spacer(),
                  const Text('Use the bar to seek'),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _handleRecorderState(RecordState state) {
    if (state == RecordState.stop && recording && !userRequestedRecorderStop) {
      _handleUnexpectedRecorderStop();
    }
  }

  void _handleUnexpectedRecorderStop() {
    if (!mounted || !recording) return;
    final elapsed = recordingElapsedLabel;
    setState(() {
      recording = false;
      path = null;
      recordingPreviewed = false;
    });
    recordingTick?.cancel();
    recordingTick = null;
    recordingStopwatch
      ..stop()
      ..reset();
    showMessage(
      context,
      'The browser stopped microphone capture unexpectedly after $elapsed. The partial recording was discarded; start again and keep this page open until the line is finished.',
    );
  }

  Future<void> _load() async {
    try {
      final data =
          await context.read<Session>().api.get('/api/lessons/${widget.slug}');
      if (!mounted) return;
      final payload = Map<String, dynamic>.from(data as Map);
      final draftContent = await _loadMultilingualLesson();
      final timingContent = await _loadGuruTimingLesson();
      final doneLines = ((payload['completed_line_indices'] as List?) ?? [])
          .map((v) => v as int)
          .toList();
      final lineCount =
          (payload['lines'] as List? ?? [payload['sanskrit']]).length;
      final nextLine =
          List<int>.generate(lineCount, (index) => index).firstWhere(
        (index) => !doneLines.contains(index),
        orElse: () => lineCount - 1,
      );
      final wordAssets = await _loadWordClipAssets(payload);
      setState(() {
        lesson = payload;
        multilingualLesson = draftContent;
        guruTimingLesson = timingContent;
        wordClipAssets = wordAssets;
        completed = lesson!['completed_at'] != null;
        completedLines = doneLines;
        activeLine = nextLine;
      });
      await _loadProfileAudio();
      await session.logLearningEvent(
          eventType: 'lesson_opened', lessonSlug: widget.slug);
      if (!mounted) return;
      _startLessonTimer();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<Map<String, dynamic>?> _loadMultilingualLesson() async {
    try {
      final payload = jsonDecode(await rootBundle
          .loadString('assets/rigveda_multilingual_content_draft.json')) as Map;
      final records = payload['records'] as List? ?? const [];
      for (final record in records.whereType<Map>()) {
        if (record['lesson_slug'] == widget.slug) {
          return Map<String, dynamic>.from(record);
        }
      }
    } catch (_) {
      // Keep the Sanskrit lesson usable when the optional reading aid is absent.
    }
    return null;
  }

  Future<Map<String, dynamic>?> _loadGuruTimingLesson() async {
    try {
      final payload = jsonDecode(
              await rootBundle.loadString('assets/guru_timing_candidates.json'))
          as Map;
      final lessons = payload['lessons'] as List? ?? const [];
      for (final item in lessons.whereType<Map>()) {
        if (item['lesson_id'] == widget.slug &&
            item['alignment_status'] == 'completed_candidate') {
          return Map<String, dynamic>.from(item);
        }
      }
    } catch (_) {
      // Keep playback available without automatic highlighting if timing is absent.
    }
    return null;
  }

  List<String> _localizedVerseLines(String text, int lineCount) {
    final parts = text.split('।');
    if (lineCount > 1 && parts.length == lineCount) {
      return [
        for (var index = 0; index < parts.length; index++)
          index == lineCount - 1
              ? parts[index].trim()
              : '${parts[index].trim()} ।',
      ];
    }
    return [text.trim()];
  }

  Widget _buildSyncedVerseLine(String line, int lineIndex, BuildContext context,
      {bool matchSanskritAkshara = true, double fontSize = 25}) {
    final lessonLines =
        (lesson!['lines'] as List? ?? [lesson!['sanskrit']]).cast<String>();
    final wordOffset = _wordsForLesson({
      'sanskrit': lessonLines.take(lineIndex).join('\n'),
    }).length;
    final tokens = line.trim().split(RegExp(r'\s+'));
    final scheme = Theme.of(context).colorScheme;
    final spans = <InlineSpan>[];
    var localWordIndex = 0;
    for (var localIndex = 0; localIndex < tokens.length; localIndex++) {
      final raw = tokens[localIndex];
      final word = raw.replaceAll(RegExp(r'[।॥,;:!?]+$'), '');
      final punctuation = raw.substring(word.length);
      final isWord = word.isNotEmpty;
      final globalIndex = wordOffset + localWordIndex;
      final isCurrentWord =
          guruPlaybackActive && activeWordIndex == globalIndex;
      final syllable =
          isCurrentWord && matchSanskritAkshara ? activeAkshara : null;
      final syllableStart = syllable == null ? -1 : word.indexOf(syllable);

      if (!isWord) {
        // A standalone danda is punctuation, not another word position.
      } else if (guruPlaybackActive && !isCurrentWord) {
        spans.add(TextSpan(
            text: word,
            style: TextStyle(color: scheme.onSurface.withOpacity(0.32))));
      } else if (syllable != null && syllableStart >= 0) {
        final syllableEnd = syllableStart + syllable.length;
        if (syllableStart > 0) {
          spans.add(TextSpan(
              text: word.substring(0, syllableStart),
              style: TextStyle(color: scheme.onSurface.withOpacity(0.48))));
        }
        spans.add(TextSpan(
            text: word.substring(syllableStart, syllableEnd),
            style: TextStyle(
                color: scheme.onPrimaryContainer,
                backgroundColor: scheme.primaryContainer,
                fontWeight: FontWeight.w800,
                decoration: TextDecoration.underline)));
        if (syllableEnd < word.length) {
          spans.add(TextSpan(
              text: word.substring(syllableEnd),
              style: TextStyle(color: scheme.onSurface.withOpacity(0.48))));
        }
      } else {
        final selectedForPractice =
            !guruPlaybackActive && lineIndex == activeLine;
        spans.add(TextSpan(
            text: word,
            style: TextStyle(
                color: guruPlaybackActive
                    ? isCurrentWord
                        ? scheme.onPrimaryContainer
                        : scheme.onSurface.withOpacity(0.32)
                    : selectedForPractice
                        ? scheme.primary
                        : scheme.onSurface,
                backgroundColor: isCurrentWord && guruPlaybackActive
                    ? scheme.primaryContainer
                    : null,
                fontWeight: selectedForPractice || isCurrentWord
                    ? FontWeight.w700
                    : FontWeight.w600)));
      }
      if (punctuation.isNotEmpty) {
        spans.add(TextSpan(
            text: punctuation,
            style: TextStyle(
                color: guruPlaybackActive
                    ? scheme.onSurface.withOpacity(isCurrentWord ? 0.48 : 0.32)
                    : scheme.onSurface)));
      }
      if (isWord) localWordIndex++;
      if (localIndex + 1 < tokens.length) spans.add(const TextSpan(text: ' '));
    }
    return Text.rich(
      TextSpan(children: spans),
      textAlign: TextAlign.center,
      style: TextStyle(fontSize: fontSize, height: 1.9),
    );
  }

  Future<void> _savePreferredContentLanguage(String code) async {
    try {
      await session.api.post('/api/profile/preferred-language',
          body: {'preferred_language': code});
    } catch (error) {
      if (mounted) {
        showMessage(context,
            'Language changed for this session but could not be saved: $error');
      }
    }
  }

  List<String> _wordsForLesson(Map<String, dynamic> data) {
    final raw = data['sanskrit']?.toString() ?? '';
    return raw
        .split(RegExp(r'\s+'))
        .map((word) => word.replaceAll(RegExp(r'[।॥,;:!?]+$'), ''))
        .where((word) => word.isNotEmpty)
        .toList();
  }

  List<String> _wordsFromText(String text) => text
      .split(RegExp(r'\s+'))
      .map((word) => word.replaceAll(RegExp(r'[।॥,;:!?]+$'), ''))
      .where((word) => word.isNotEmpty)
      .toList();

  int _wordOffsetForLine(int lineIndex) {
    final lines =
        (lesson!['lines'] as List? ?? [lesson!['sanskrit']]).cast<String>();
    return _wordsForLesson({
      'sanskrit': lines.take(lineIndex).join('\n'),
    }).length;
  }

  String _localizedEvaluationWord(Object? rawWord, {int? wordIndex}) {
    final word = rawWord?.toString().replaceAll(
              RegExp(r'[।॥,;:!?]+$'),
              '',
            ) ??
        '';
    final languages = multilingualLesson?['languages'] as Map?;
    final selected =
        languages?[context.read<LanguageService>().contentLanguageCode];
    final localizedText =
        selected is Map ? selected['mantra_text']?.toString() : null;
    if (localizedText == null || localizedText.isEmpty) return word;
    final localizedWords = _wordsFromText(localizedText);
    final referenceWords = _wordsForLesson(lesson!);
    var index = wordIndex;
    if (index == null || index < 0 || index >= localizedWords.length) {
      index = referenceWords.indexOf(word);
    }
    if (index == null || index < 0 || index >= localizedWords.length) {
      return word;
    }
    return localizedWords[index];
  }

  int? _timingMilliseconds(dynamic value) {
    if (value is num) return value.round();
    return double.tryParse('$value')?.round();
  }

  Map<String, dynamic>? _reviewedWordTimingFor(int index) {
    final words = _wordsForLesson(lesson ?? const <String, dynamic>{});
    final rawTimings = lesson?['word_audio_timings'];
    if (rawTimings is! List ||
        index < 0 ||
        index >= rawTimings.length ||
        index >= words.length) return null;
    final raw = rawTimings[index];
    if (raw is! Map) return null;
    final timing = Map<String, dynamic>.from(raw);
    final startMs = _timingMilliseconds(timing['start_ms']);
    final endMs = _timingMilliseconds(timing['end_ms']);
    if (timing['word_order'] != index ||
        timing['word'] != words[index] ||
        startMs == null ||
        endMs == null ||
        endMs <= startMs) {
      return null;
    }
    return timing;
  }

  Map<String, dynamic>? _wordTimingFor(int index) {
    final reviewed = _reviewedWordTimingFor(index);
    if (reviewed != null) return reviewed;
    final words = _wordsForLesson(lesson ?? const <String, dynamic>{});
    if (index < 0 ||
        index >= words.length ||
        !_guruAudioByLesson.containsKey(widget.slug)) return null;
    final candidates = guruTimingLesson?['words'] as List? ?? const [];
    for (final raw in candidates.whereType<Map>()) {
      if (int.tryParse('${raw['word_order']}') == index + 1 &&
          raw['word'] == words[index]) {
        final timing = Map<String, dynamic>.from(raw);
        final startMs = _timingMilliseconds(timing['start_ms']);
        final endMs = _timingMilliseconds(timing['end_ms']);
        if (startMs != null && endMs != null && endMs > startMs) {
          return timing;
        }
      }
    }
    return null;
  }

  List<Map<String, dynamic>> get _guruWordTimings =>
      (guruTimingLesson?['words'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList();

  List<Map<String, dynamic>> get _guruAksharaTimings =>
      (guruTimingLesson?['aksharas'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList();

  void _syncGuruHighlight(Duration position) {
    if (!_guruTimelinePlayback || !mounted) return;
    final milliseconds = position.inMilliseconds;
    Map<String, dynamic>? currentWord;
    for (final word in _guruWordTimings) {
      final start = _timingMilliseconds(word['start_ms']);
      final end = _timingMilliseconds(word['end_ms']);
      if (start != null &&
          end != null &&
          milliseconds >= start &&
          milliseconds < end) {
        currentWord = word;
        break;
      }
    }
    final currentOrder = currentWord == null
        ? null
        : int.tryParse('${currentWord['word_order']}');
    final nextWordIndex = currentOrder == null ? null : currentOrder - 1;
    String? nextAkshara;
    if (nextWordIndex != null) {
      for (final item in _guruAksharaTimings) {
        if (int.tryParse('${item['word_order']}') != nextWordIndex + 1)
          continue;
        final start = _timingMilliseconds(item['start_ms']);
        final end = _timingMilliseconds(item['end_ms']);
        if (start != null &&
            end != null &&
            milliseconds >= start &&
            milliseconds < end) {
          nextAkshara = item['akshara']?.toString();
          break;
        }
      }
    }
    if (activeWordIndex == nextWordIndex && activeAkshara == nextAkshara)
      return;
    setState(() {
      activeWordIndex = nextWordIndex;
      activeAkshara = nextAkshara;
    });
  }

  void _clearGuruHighlight() {
    _guruTimelinePlayback = false;
    if (!mounted) return;
    setState(() {
      guruPlaybackActive = false;
      activeWordIndex = null;
      activeAkshara = null;
    });
  }

  void _beginGuruTimeline() {
    if (_guruWordTimings.isEmpty) {
      _guruTimelinePlayback = false;
      if (mounted) setState(() => guruPlaybackActive = false);
      return;
    }
    _guruTimelinePlayback = true;
    if (!mounted) return;
    setState(() {
      guruPlaybackActive = true;
      activeWordIndex = null;
      activeAkshara = null;
    });
  }

  bool _hasWordAudio(int index) =>
      wordClipAssets.containsKey(index) || _wordTimingFor(index) != null;

  Future<void> _playTimedWord(int index, {required bool sourceLoaded}) async {
    final timing = _wordTimingFor(index);
    final fullAudioAsset = _guruAudioByLesson[widget.slug];
    if (timing == null || fullAudioAsset == null) return;
    if (!sourceLoaded) await guruPlayer.setAsset(fullAudioAsset);
    await guruPlayer.setSpeed(playbackSpeed);
    final startMs = _timingMilliseconds(timing['start_ms']);
    final endMs = _timingMilliseconds(timing['end_ms']);
    if (startMs == null || endMs == null || endMs <= startMs) return;
    _guruSourceIsFullVerse = true;
    _beginGuruTimeline();
    await guruPlayer.seek(Duration(milliseconds: startMs));
    final reachedEnd = guruPlayer.positionStream
        .firstWhere((position) => position.inMilliseconds >= endMs);
    final playback = guruPlayer.play();
    await reachedEnd.timeout(const Duration(seconds: 15));
    await guruPlayer.pause();
    await playback;
  }

  Future<void> _playWordSegment(int index,
      {bool verseSourceLoaded = false}) async {
    final wordAsset = wordClipAssets[index];
    if (wordAsset != null) {
      _guruSourceIsFullVerse = false;
      _guruTimelinePlayback = false;
      await guruPlayer.setAsset(wordAsset);
      await guruPlayer.setSpeed(playbackSpeed);
      await guruPlayer.play();
      return;
    }
    await _playTimedWord(index, sourceLoaded: verseSourceLoaded);
  }

  Future<Map<int, String>> _loadWordClipAssets(
      Map<String, dynamic> data) async {
    final words = _wordsForLesson(data);
    final available = <int, String>{};
    for (var index = 0; index < words.length; index++) {
      final asset =
          'assets/audio/guru_words/${data['slug']}/word-${(index + 1).toString().padLeft(2, '0')}.ogg';
      try {
        final bytes = await rootBundle.load(asset);
        // Flutter web can receive index.html for an unknown asset when the web
        // server uses SPA fallback routing. Only advertise real OGG files.
        if (bytes.lengthInBytes < 4 ||
            bytes.getUint8(0) != 0x4f ||
            bytes.getUint8(1) != 0x67 ||
            bytes.getUint8(2) != 0x67 ||
            bytes.getUint8(3) != 0x53) {
          continue;
        }
        available[index] = asset;
      } on FlutterError {
        // Keep missing clips unavailable instead of estimating word boundaries.
      }
    }
    return available;
  }

  String? get _mantraReference {
    final raw = lesson?['reference']?.toString() ?? '';
    final match = RegExp(
            r'(?:Rigveda|RV)\s+(\d{1,2})[.]([0-9]{1,3})[.]([0-9]{1,3})',
            caseSensitive: false)
        .firstMatch(raw);
    if (match == null) return null;
    return 'RV.${match.group(1)!.padLeft(2, '0')}.${match.group(2)!.padLeft(3, '0')}.${match.group(3)!.padLeft(2, '0')}';
  }

  Future<void> _loadProfileAudio() async {
    final ref = _mantraReference;
    if (ref == null) {
      if (mounted) setState(() => profileAudio = null);
      return;
    }
    try {
      final data = await session.api.get(
          '/api/recitation/${Uri.encodeComponent(ref)}/audio?profile=$recitationProfile');
      if (mounted)
        setState(() => profileAudio = Map<String, dynamic>.from(data as Map));
    } catch (_) {
      if (mounted) setState(() => profileAudio = null);
    }
  }

  void _startLessonTimer() {
    if (lesson == null || lessonTimer != null) return;
    lessonTimeStartedAt = DateTime.now();
    lessonTimer =
        Timer.periodic(const Duration(seconds: 30), (_) => _flushLessonTime());
  }

  Future<void> _flushLessonTime() async {
    final startedAt = lessonTimeStartedAt;
    if (startedAt == null) return;
    final seconds =
        DateTime.now().difference(startedAt).inSeconds.clamp(0, 60).toInt();
    lessonTimeStartedAt = DateTime.now();
    if (seconds > 0) {
      await session.logLearningEvent(
          eventType: 'lesson_time',
          lessonSlug: widget.slug,
          durationSeconds: seconds);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _startLessonTimer();
    } else {
      lessonTimer?.cancel();
      lessonTimer = null;
      unawaited(_flushLessonTime());
    }
  }

  Future<void> _completeLesson() async {
    final data = await session.logLearningEvent(
        eventType: 'lesson_completed', lessonSlug: widget.slug);
    if (!mounted) return;
    if (data == null) {
      showMessage(context,
          'Could not save completion. Please try again when connected.');
      return;
    }
    setState(() => completed = true);
    showMessage(
        context,
        data['course_completed'] == true
            ? 'Lesson complete. You completed this course.'
            : 'Lesson complete.');
  }

  Future<void> start() async {
    try {
      if (recording || recorderStopInProgress) return;
      await _pauseLessonVideo();
      if (!await recorder.hasPermission())
        throw Exception('Microphone permission denied');
      final AudioEncoder encoder;
      if (kIsWeb) {
        if (await recorder.isEncoderSupported(AudioEncoder.opus)) {
          encoder = AudioEncoder.opus;
          browserRecordingExtension = 'webm';
        } else if (await recorder.isEncoderSupported(AudioEncoder.aacLc)) {
          encoder = AudioEncoder.aacLc;
          browserRecordingExtension = 'm4a';
        } else {
          throw Exception(
              'This browser does not support a compatible audio recording format. Please use a current version of Chrome or Edge.');
        }
      } else {
        encoder = AudioEncoder.aacLc;
      }
      final config = RecordConfig(
        encoder: encoder,
        autoGain: false,
        echoCancel: false,
        noiseSuppress: false,
      );
      if (kIsWeb) {
        path = null;
      } else {
        final dir = await getApplicationDocumentsDirectory();
        path =
            '${dir.path}/recitation_${DateTime.now().millisecondsSinceEpoch}.m4a';
      }
      final outputName = kIsWeb
          ? 'recitation_${DateTime.now().millisecondsSinceEpoch}.$browserRecordingExtension'
          : path!;
      await recorder.start(config, path: outputName);
      recordingPreviewed = false;
      savedRecordingDuration = null;
      recordingStopwatch
        ..reset()
        ..start();
      recordingTick?.cancel();
      recordingTick = Timer.periodic(const Duration(milliseconds: 250), (_) {
        if (!mounted || !recording) return;
        if (recordingElapsed >= RecordingDurationPolicy.maximumRecitation) {
          unawaited(stop());
        } else {
          setState(() {});
        }
      });
      setState(() => recording = true);
      // Reflect the active microphone immediately; analytics must not leave the
      // UI showing Start while the recorder is already capturing audio.
      unawaited(session.logLearningEvent(
          eventType: 'recording_started', lessonSlug: widget.slug));
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    }
  }

  Future<void> stop() async {
    if (!recording || recorderStopInProgress) return;
    if (!minimumRecordingReached) {
      showMessage(context,
          'Keep recording for at least 2 seconds. ${recordingSecondsRemaining}s remaining.');
      return;
    }
    recorderStopInProgress = true;
    userRequestedRecorderStop = true;
    try {
      final recorded = await recorder.stop();
      if (kIsWeb && (recorded == null || !recorded.startsWith('blob:'))) {
        throw Exception(
            'The browser did not return the finished recording. Please record again.');
      }
      final timerDuration = recordingElapsed;
      var actualDuration = timerDuration;
      if (kIsWeb && recorded != null) {
        try {
          await player.setUrl(recorded);
          actualDuration = player.duration ?? timerDuration;
        } catch (_) {
          // Keep the completed clip available; playback will show any media error.
        }
      }
      setState(() {
        recording = false;
        path = recorded ?? path;
        recordingPreviewed = false;
        savedRecordingDuration = actualDuration;
      });
      if (mounted &&
          (timerDuration - actualDuration).abs() > const Duration(seconds: 1)) {
        showMessage(context,
            'The clip is ${RecordingDurationPolicy.formatElapsed(actualDuration)} but the recording timer reached ${RecordingDurationPolicy.formatElapsed(timerDuration)}. Review the capture before continuing.');
      }
      if (kIsWeb && recorded != null) {
        try {
          await saveBrowserRecording(recorded,
              'veda_${widget.slug}_line_${activeLine + 1}.$browserRecordingExtension');
        } catch (e) {
          if (mounted) {
            showMessage(context,
                'Recording is ready to play, but could not download it: $e');
          }
        }
      }
      recordingTick?.cancel();
      recordingTick = null;
      recordingStopwatch
        ..stop()
        ..reset();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        recording = false;
        path = null;
        recordingPreviewed = false;
      });
      recordingTick?.cancel();
      recordingTick = null;
      recordingStopwatch
        ..stop()
        ..reset();
      showMessage(context, 'Could not finish the recording: $e');
    } finally {
      userRequestedRecorderStop = false;
      recorderStopInProgress = false;
    }
  }

  Future<void> playMine() async {
    final recordingPath = path;
    if (recordingPath == null) return;
    try {
      await _pauseLessonVideo();
      if (kIsWeb) {
        await player.setUrl(recordingPath);
      } else {
        await player.setFilePath(recordingPath);
      }
      final duration = player.duration;
      if (duration != null && duration > Duration.zero) {
        savedRecordingDuration = duration;
        if (mounted) setState(() {});
      }
      await player.play();
      if (mounted) setState(() => recordingPreviewed = true);
      await session.logLearningEvent(
          eventType: 'learner_audio_played', lessonSlug: widget.slug);
    } catch (e) {
      if (mounted) showMessage(context, 'Could not play your recording: $e');
    }
  }

  Future<void> playMyAlignedSegment(int startMs, int endMs) async {
    final recordingPath = path;
    if (recordingPath == null || startMs < 0 || endMs <= startMs) return;
    try {
      await _pauseLessonVideo();
      if (kIsWeb) {
        await player.setUrl(recordingPath);
      } else {
        await player.setFilePath(recordingPath);
      }
      final durationMs = player.duration?.inMilliseconds;
      final safeEndMs = durationMs == null || durationMs <= 0
          ? endMs
          : endMs.clamp(0, durationMs).toInt();
      if (startMs >= safeEndMs) {
        showMessage(
            context, 'This aligned segment is outside the saved recording.');
        return;
      }
      await player.seek(Duration(milliseconds: startMs));
      final reachedEnd = player.positionStream
          .firstWhere((position) => position.inMilliseconds >= safeEndMs);
      final playback = player.play();
      final timeoutSeconds = ((safeEndMs - startMs) / 1000).ceil() + 4;
      await reachedEnd.timeout(Duration(seconds: timeoutSeconds));
      await player.pause();
      await playback;
    } on TimeoutException {
      await player.pause();
      if (mounted)
        showMessage(context, 'Could not finish playing that audio segment.');
    } catch (e) {
      if (mounted)
        showMessage(context, 'Could not play that audio segment: $e');
    }
  }

  Future<void> saveRecordingToDevice() async {
    final recordingPath = path;
    if (!kIsWeb || recordingPath == null) return;
    try {
      await saveBrowserRecording(recordingPath,
          'veda_${widget.slug}_line_${activeLine + 1}.$browserRecordingExtension');
      if (mounted) showMessage(context, 'Recording saved to your Downloads.');
    } catch (e) {
      if (mounted) showMessage(context, 'Could not save recording: $e');
    }
  }

  Future<void> playGuru() async {
    await _pauseLessonVideo();
    final localAsset = _guruAudioByLesson[widget.slug];
    if (localAsset != null) {
      await guruPlayer.setAsset(localAsset);
      await guruPlayer.setSpeed(playbackSpeed);
      _guruSourceIsFullVerse = true;
      _beginGuruTimeline();
      await guruPlayer.play();
      await session.logLearningEvent(
          eventType: 'reference_audio_played', lessonSlug: widget.slug);
      return;
    }
    final full = profileAudio?['full_mantra'];
    final url = full is Map && full['available'] == true
        ? full['audio_url']?.toString()
        : null;
    if (url == null || url.isEmpty) {
      showMessage(context,
          '$recitationProfile reference audio is not available for this mantra.');
      return;
    }
    await guruPlayer.setUrl(url);
    await guruPlayer.setSpeed(playbackSpeed);
    _guruSourceIsFullVerse = true;
    _beginGuruTimeline();
    await guruPlayer.play();
    await session.logLearningEvent(
        eventType: 'reference_audio_played', lessonSlug: widget.slug);
  }

  Future<void> repeatGuru() async {
    await _pauseLessonVideo();
    await guruPlayer.seek(Duration.zero);
    await guruPlayer.setSpeed(playbackSpeed);
    if (_guruSourceIsFullVerse) {
      _beginGuruTimeline();
    } else if (mounted) {
      setState(() => guruPlaybackActive = activeWordIndex != null);
    }
    await guruPlayer.play();
  }

  Future<void> playGuruWord(int index) async {
    if (!_hasWordAudio(index)) return;
    await _pauseLessonVideo();
    _guruTimelinePlayback = false;
    setState(() {
      guruPlaybackActive = true;
      activeWordIndex = index;
      activeAkshara = null;
    });
    try {
      await _playWordSegment(index);
      await session.logLearningEvent(
          eventType: 'reference_audio_played', lessonSlug: widget.slug);
    } catch (e) {
      if (mounted)
        showMessage(context, 'Could not play this Guru word segment: $e');
    } finally {
      _clearGuruHighlight();
    }
  }

  Future<void> _playProfileWordClip(int wordOrder, String url) async {
    final index = wordOrder - 1;
    if (index < 0 || index >= _wordsForLesson(lesson!).length) return;
    await _pauseLessonVideo();
    setState(() {
      guruPlaybackActive = true;
      activeWordIndex = index;
      activeAkshara = null;
    });
    _guruTimelinePlayback = false;
    _guruSourceIsFullVerse = false;
    try {
      await guruPlayer.setUrl(url);
      await guruPlayer.setSpeed(playbackSpeed);
      await guruPlayer.play();
    } catch (e) {
      if (mounted)
        showMessage(context, 'Could not play this Guru word clip: $e');
    } finally {
      _clearGuruHighlight();
    }
  }

  Future<void> playWordSequence(List<String> words) async {
    if (words.isEmpty ||
        !List<bool>.generate(words.length, _hasWordAudio)
            .every((available) => available)) return;
    await _pauseLessonVideo();
    try {
      final verseAsset = _guruAudioByLesson[widget.slug];
      var verseSourceLoaded = false;
      if (verseAsset != null && wordClipAssets.isEmpty) {
        await guruPlayer.setAsset(verseAsset);
        verseSourceLoaded = true;
      }
      await session.logLearningEvent(
          eventType: 'reference_audio_played', lessonSlug: widget.slug);
      for (var index = 0; index < words.length; index++) {
        if (!mounted) break;
        _guruTimelinePlayback = false;
        setState(() {
          guruPlaybackActive = true;
          activeWordIndex = index;
          activeAkshara = null;
        });
        final usesSeparateClip = wordClipAssets.containsKey(index);
        await _playWordSegment(index,
            verseSourceLoaded: verseSourceLoaded && !usesSeparateClip);
        if (usesSeparateClip) verseSourceLoaded = false;
      }
    } catch (e) {
      if (mounted)
        showMessage(context, 'Could not play the Guru word sequence: $e');
    } finally {
      _clearGuruHighlight();
    }
  }

  Future<void> submit() async {
    if (path == null || !recordingPreviewed || uploading) return;
    setState(() => uploading = true);
    try {
      final response = await context.read<Session>().api.upload(
          widget.slug, path!,
          lineIndex: activeLine,
          profile: recitationProfile,
          mantraReference: _mantraReference);
      final recordingId = response['recording_id']?.toString();
      if (recordingId != null && response['queued'] == true) {
        setState(() {
          pendingEvaluationId = recordingId;
          result =
              'Recording uploaded. Evaluation is processing; check its status in a moment.';
        });
        unawaited(_pollQueuedEvaluation(recordingId));
      } else {
        _showEvaluation(response);
      }
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    } finally {
      if (mounted) setState(() => uploading = false);
    }
  }

  Future<void> _pollQueuedEvaluation(String recordingId) async {
    var consecutiveErrors = 0;
    for (var attempt = 0; attempt < 45; attempt++) {
      await Future<void>.delayed(const Duration(seconds: 2));
      if (!mounted || pendingEvaluationId != recordingId) return;
      try {
        final response = Map<String, dynamic>.from(
            await session.api.get('/api/recordings/$recordingId') as Map);
        consecutiveErrors = 0;
        if (!const {'queued', 'pending', 'running'}
            .contains(response['status'])) {
          _showEvaluation({
            ...response,
            'alignment': response['alignment'],
            'evaluation_status': response['status'],
          });
          return;
        }
      } catch (_) {
        consecutiveErrors++;
        if (consecutiveErrors >= 3) break;
      }
    }
    if (!mounted || pendingEvaluationId != recordingId) return;
    setState(() {
      result = consecutiveErrors >= 3
          ? 'Could not reach the evaluation service. Your recording is saved; tap Check evaluation to retry.'
          : 'Evaluation has not completed after 90 seconds. Your recording is saved; the evaluation worker may be unavailable. Tap Check evaluation to retry.';
    });
  }

  void _showEvaluation(Map<String, dynamic> response) {
    final report = response['report'] is Map
        ? Map<String, dynamic>.from(response['report'] as Map)
        : null;
    final wordAccuracy = report?['word_accuracy'] is Map
        ? Map<String, dynamic>.from(report!['word_accuracy'] as Map)
        : <String, dynamic>{};
    final matchPercent = wordAccuracy['match_percent'];
    final passThresholdPercent = wordAccuracy['pass_threshold_percent'] ?? 90;
    final accepted = report?['accepted'] == true;
    final diagnosticOnly = report?['diagnostic_only'] == true;
    setState(() {
      pendingEvaluationId = null;
      result = diagnosticOnly
          ? 'Development diagnostic only. This candidate-text comparison cannot pass or unlock progress. ${report?['acceptance_reason'] ?? ''}'
          : accepted
              ? 'Accepted. Word match met the required $passThresholdPercent% threshold.'
              : matchPercent is num
                  ? 'Word match: ${matchPercent.toStringAsFixed(1)}% ($passThresholdPercent% required). ${report?['acceptance_reason'] ?? response['message'] ?? 'Please retry.'}'
                  : (report?['acceptance_reason'] ??
                          response['message'] ??
                          'Automatic Sanskrit evaluation is unavailable; no score was invented.')
                      .toString();
      alignmentResult = response['alignment'] is Map
          ? Map<String, dynamic>.from(response['alignment'] as Map)
          : null;
      speechReport = report;
    });
  }

  Future<void> checkEvaluation() async {
    final recordingId = pendingEvaluationId;
    if (recordingId == null || uploading) return;
    setState(() => uploading = true);
    try {
      final response = Map<String, dynamic>.from(
          await session.api.get('/api/recordings/$recordingId') as Map);
      if (const {'queued', 'pending', 'running'}.contains(response['status'])) {
        if (mounted)
          setState(() => result = 'Still processing. Check again shortly.');
      } else {
        _showEvaluation({
          ...response,
          'report': response['report'],
          'alignment': response['alignment'],
          'evaluation_status': response['status'],
        });
      }
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    } finally {
      if (mounted) setState(() => uploading = false);
    }
  }

  Future<void> completeActiveLine() async {
    if (speechReport?['accepted'] != true) {
      showMessage(
        context,
        speechReport?['acceptance_reason']?.toString() ??
            'A validated Sanskrit word assessment is required before this line can be marked complete.',
      );
      return;
    }
    try {
      await session.api.post('/api/lessons/${widget.slug}/lines/complete',
          body: {'line_index': activeLine});
      if (!mounted) return;
      final count = (lesson!['lines'] as List).length;
      setState(() {
        if (!completedLines.contains(activeLine))
          completedLines.add(activeLine);
        if (activeLine + 1 < count) {
          activeLine++;
          path = null;
          result = null;
          alignmentResult = null;
          speechReport = null;
        }
      });
      if (completedLines.length == count) await _completeLesson();
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(recorderStateSubscription?.cancel());
    unawaited(guruPositionSubscription?.cancel());
    unawaited(guruStateSubscription?.cancel());
    unawaited(lessonVideoController?.dispose());
    lessonTimer?.cancel();
    recordingTick?.cancel();
    unawaited(_flushLessonTime());
    recorder.dispose();
    player.dispose();
    guruPlayer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (error != null)
      return Scaffold(appBar: AppBar(), body: Center(child: Text(error!)));
    if (lesson == null)
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    final meanings = lesson!['word_meanings'];
    final language = context.watch<LanguageService>();
    final translationMap = lesson!['translations'] is Map
        ? lesson!['translations'] as Map
        : const {};
    final localized = translationMap[language.code] is Map &&
            translationMap[language.code]['status'] == 'approved'
        ? translationMap[language.code] as Map
        : const {};
    final lines =
        (lesson!['lines'] as List? ?? [lesson!['sanskrit']]).cast<String>();
    activeLine = activeLine.clamp(0, lines.length - 1).toInt();
    final draftLanguages = multilingualLesson?['languages'] is Map
        ? multilingualLesson!['languages'] as Map
        : const {};
    final selectedContentCode = language.contentLanguageCode;
    final selectedContent = draftLanguages[selectedContentCode] is Map
        ? draftLanguages[selectedContentCode] as Map
        : null;
    final draftMeaning = selectedContent?['meaning']?.toString();
    final displayedMeaning =
        draftMeaning != null && draftMeaning.trim().isNotEmpty
            ? draftMeaning
            : localized['meaning'] ?? lesson!['meaning'];
    final draftApplication = selectedContent?['application']?.toString();
    final displayedApplication =
        draftApplication != null && draftApplication.trim().isNotEmpty
            ? draftApplication
            : localized['daily_application'] ?? lesson!['daily_application'];
    final multilingualText = selectedContent?['mantra_text']?.toString();
    final localizedMantraLines = multilingualText == null
        ? null
        : _localizedVerseLines(multilingualText, lines.length);
    final selectedContentLabel = LanguageService.contentLanguages
        .firstWhere((item) => item.code == selectedContentCode,
            orElse: () => const LearningLanguage('en', 'English'))
        .name;
    final sanskritWords = _wordsForLesson(lesson!);
    final fullAudio = profileAudio?['full_mantra'];
    final hasProfileAudio = _guruAudioByLesson.containsKey(widget.slug) ||
        (fullAudio is Map && fullAudio['available'] == true);
    final wordAudio = (profileAudio?['word_audio'] as List? ?? const [])
        .whereType<Map>()
        .where((x) => x['available'] == true)
        .toList();
    return Scaffold(
      appBar: AppBar(title: Text(language.text('practice')), actions: [
        DropdownButton<String>(
            value: language.code,
            underline: const SizedBox.shrink(),
            items: LanguageService.supported
                .map((item) =>
                    DropdownMenuItem(value: item.code, child: Text(item.name)))
                .toList(),
            onChanged: (value) {
              if (value != null) {
                language.select(value);
                unawaited(_savePreferredContentLanguage(value));
              }
            })
      ]),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('${lesson!['title']}',
              style:
                  const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
          Text('${lesson!['reference']}',
              style: TextStyle(color: Theme.of(context).colorScheme.primary)),
          Row(children: [
            const Text('Recitation profile'),
            const SizedBox(width: 12),
            DropdownButton<String>(
              value: recitationProfile,
              items: const [
                DropdownMenuItem(value: 'Kanchi', child: Text('Kanchi')),
                DropdownMenuItem(value: 'Sringeri', child: Text('Sringeri')),
                DropdownMenuItem(
                    value: 'Common', child: Text('Common (shared reference)'))
              ],
              onChanged: (value) {
                if (value == null) return;
                setState(() {
                  recitationProfile = value;
                  profileAudio = null;
                });
                _loadProfileAudio();
              },
            )
          ]),
          const SizedBox(height: 8),
          Text(completed
              ? 'Shloka complete'
              : 'Complete each line to finish this shloka'),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text('Full shloka · current practice line highlighted',
                      style: Theme.of(context).textTheme.titleSmall),
                ),
                const SizedBox(height: 6),
                for (var index = 0; index < lines.length; index++) ...[
                  _buildSyncedVerseLine(lines[index], index, context),
                  if (index + 1 < lines.length) const SizedBox(height: 2),
                ],
                if (selectedContent != null &&
                    localizedMantraLines != null) ...[
                  const SizedBox(height: 14),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text('Choose your shloka language',
                        style: Theme.of(context).textTheme.titleSmall),
                  ),
                  DropdownButton<String>(
                    value: selectedContentCode,
                    isExpanded: true,
                    items: LanguageService.contentLanguages
                        .map((item) => DropdownMenuItem(
                            value: item.code, child: Text(item.name)))
                        .toList(),
                    onChanged: (value) {
                      if (value == null) return;
                      language.selectContentLanguage(value);
                      unawaited(_savePreferredContentLanguage(value));
                    },
                  ),
                  Text('Shloka reading · $selectedContentLabel',
                      style: Theme.of(context).textTheme.titleSmall),
                  const SizedBox(height: 4),
                  for (var index = 0;
                      index < localizedMantraLines.length;
                      index++) ...[
                    _buildSyncedVerseLine(
                        localizedMantraLines[index], index, context,
                        matchSanskritAkshara: false, fontSize: 22),
                    if (index + 1 < localizedMantraLines.length)
                      const SizedBox(height: 2),
                  ],
                  const Text(
                      'Draft script reading aid; Sanskrit and native-language review is pending.',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 12, color: Colors.black54)),
                ],
                const SizedBox(height: 8),
                Text(
                    '${language.text('line')} ${activeLine + 1} of ${lines.length} • ${completedLines.length}/${lines.length} complete'),
                Text(
                    '${language.text('review')} IAST/phonetic guidance and svara are pending Guru review; validated svara evaluation is unavailable.'),
                const Text(
                    'Pronunciation checklist (general): preserve ह्रस्व/दीर्घ vowel length, aspirated/unaspirated and dental/retroflex consonants, anusvāra, visarga and conjuncts. No Vedic accents are supplied here.'),
                if (multilingualLesson == null &&
                    (lesson!['iast_lines'] as List? ?? const []).length >
                        activeLine) ...[
                  const SizedBox(height: 12),
                  Text('${(lesson!['iast_lines'] as List)[activeLine]}',
                      textAlign: TextAlign.center),
                ],
                const SizedBox(height: 12),
                FilledButton.tonalIcon(
                  onPressed: playGuru,
                  icon: const Icon(Icons.volume_up),
                  label: Text(hasProfileAudio
                      ? (_guruAudioByLesson.containsKey(widget.slug)
                          ? 'Guru · ${language.text('play')}'
                          : '$recitationProfile · ${language.text('play')}')
                      : '$recitationProfile · ${language.text('noAudio')}'),
                ),
                OutlinedButton.icon(
                    onPressed: hasProfileAudio ? repeatGuru : null,
                    icon: const Icon(Icons.replay),
                    label: const Text('Repeat audio')),
                if (guruTimingLesson != null)
                  const Column(children: [
                    Text(
                        'During Guru playback, the current Sanskrit akṣara and corresponding selected-language word are highlighted; the remaining words are dimmed.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 12)),
                    Text(
                        'Highlights follow candidate Guru timings; review is pending.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 11, color: Colors.black54)),
                  ]),
                const SizedBox(height: 12),
                Align(
                    alignment: Alignment.centerLeft,
                    child: Text('Learn each word',
                        style: Theme.of(context).textTheme.titleSmall)),
                const SizedBox(height: 6),
                Wrap(
                  alignment: WrapAlignment.center,
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (var index = 0; index < sanskritWords.length; index++)
                      ActionChip(
                        avatar: Icon(
                          _hasWordAudio(index)
                              ? Icons.volume_up
                              : Icons.volume_off,
                          size: 18,
                        ),
                        label: Text(sanskritWords[index]),
                        backgroundColor: activeWordIndex == index
                            ? Theme.of(context).colorScheme.primaryContainer
                            : null,
                        onPressed: _hasWordAudio(index)
                            ? () => playGuruWord(index)
                            : null,
                      ),
                  ],
                ),
                if (sanskritWords.isNotEmpty &&
                    List<bool>.generate(sanskritWords.length, _hasWordAudio)
                        .every((available) => available))
                  OutlinedButton.icon(
                    onPressed: () => playWordSequence(sanskritWords),
                    icon: const Icon(Icons.play_arrow),
                    label: const Text('Play words in sequence'),
                  )
                else
                  Text(
                    '${List<bool>.generate(sanskritWords.length, _hasWordAudio).where((available) => available).length} of ${sanskritWords.length} word audio ranges available. A Guru timing pass is needed for words without ranges.',
                    style: const TextStyle(fontSize: 12, color: Colors.black54),
                    textAlign: TextAlign.center,
                  ),
                if (wordAudio.isNotEmpty)
                  Wrap(spacing: 8, children: [
                    for (final clip in wordAudio)
                      OutlinedButton(
                        onPressed: () async {
                          final url = clip['audio_url']?.toString();
                          final order = int.tryParse('${clip['word_order']}');
                          if (url == null || order == null) return;
                          await _playProfileWordClip(order, url);
                        },
                        child: Text('Word ${clip['word_order']}'),
                      )
                  ]),
                DropdownButton<double>(
                    value: playbackSpeed,
                    items: const [0.5, 0.75, 1.0]
                        .map((v) => DropdownMenuItem(
                            value: v, child: Text('${v}× speed')))
                        .toList(),
                    onChanged: (v) => setState(() => playbackSpeed = v ?? 1.0)),
                OutlinedButton.icon(
                  onPressed: completedLines.contains(activeLine) ||
                          speechReport?['accepted'] != true
                      ? null
                      : completeActiveLine,
                  icon: const Icon(Icons.check),
                  label: Text(completedLines.contains(activeLine)
                      ? language.text('done')
                      : language.text('complete')),
                ),
              ]),
            ),
          ),
          if (_lessonVideoAssets.containsKey(widget.slug))
            _lessonVideoCard(context),
          Text(language.text('meaning'),
              style:
                  const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          Text('$displayedMeaning'),
          if (selectedContentCode == 'sa' &&
              (draftMeaning == null || draftMeaning.trim().isEmpty))
            const Text(
                'A Sanskrit artha was not supplied; showing the available reference meaning.',
                style: TextStyle(fontSize: 12, color: Colors.black54)),
          if ((displayedApplication ?? '').toString().isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(language.text('application'),
                style:
                    const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            Text('$displayedApplication'),
            if (selectedContentCode == 'sa' &&
                (draftApplication == null || draftApplication.trim().isEmpty))
              const Text(
                  'A Sanskrit daily application was not supplied; showing the available reference application.',
                  style: TextStyle(fontSize: 12, color: Colors.black54)),
            if (selectedContent != null &&
                selectedContentCode != 'en' &&
                selectedContentCode != 'sa')
              const Text(
                  'Draft translation; native-language and Sanskrit review is pending.',
                  style: TextStyle(fontSize: 12, color: Colors.black54)),
          ],
          if (meanings is List && meanings.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Text('Word meanings',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ...meanings
                .map((item) => Text('${item['word']}: ${item['meaning']}')),
          ],
          const SizedBox(height: 20),
          const Text('Your recitation',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const Text(
              'Record the highlighted practice line from the full shloka above. Capture stops automatically at 30 seconds, or tap Stop when you finish. On web, the clip is also downloaded to your device; on mobile, it is saved in app storage. Play the saved clip to check the full take before submitting.'),
          const SizedBox(height: 10),
          FilledButton.icon(
            onPressed:
                recording ? (minimumRecordingReached ? stop : null) : start,
            icon: Icon(
                recording && minimumRecordingReached ? Icons.stop : Icons.mic),
            label: Text(recording
                ? minimumRecordingReached
                    ? 'Stop recording · $recordingElapsedLabel'
                    : 'Keep recording · ${recordingSecondsRemaining}s left'
                : language.text('record')),
          ),
          if (recording)
            Text('● REC $recordingElapsedLabel · auto-stops at 00:30',
                textAlign: TextAlign.center,
                style: const TextStyle(
                    fontSize: 13,
                    color: Colors.red,
                    fontWeight: FontWeight.w600)),
          if (recording)
            Text('${recordingElapsed.inSeconds} / 30 seconds maximum',
                textAlign: TextAlign.center),
          if (!recording && savedRecordingDuration != null)
            Text(
                'Saved recording: ${RecordingDurationPolicy.formatElapsed(savedRecordingDuration!)}',
                textAlign: TextAlign.center),
          OutlinedButton.icon(
              onPressed:
                  path == null || recording || uploading ? null : playMine,
              icon: const Icon(Icons.play_arrow),
              label: Text(
                  '${recordingPreviewed ? 'Play my recording again' : 'Play my recording'}${savedRecordingDuration == null ? '' : ' (${RecordingDurationPolicy.formatElapsed(savedRecordingDuration!)})'}')),
          if (kIsWeb && path != null && !recording)
            OutlinedButton.icon(
                onPressed: uploading ? null : saveRecordingToDevice,
                icon: const Icon(Icons.download),
                label: const Text('Save recording to this device')),
          FilledButton(
              onPressed:
                  path == null || !recordingPreviewed || recording || uploading
                      ? null
                      : submit,
              child: Text(uploading ? 'Evaluating…' : 'Evaluate recording')),
          if (pendingEvaluationId != null)
            OutlinedButton(
                onPressed: uploading ? null : checkEvaluation,
                child: Text(uploading ? 'Checking…' : 'Check evaluation')),
          if (path != null && !recordingPreviewed && !recording)
            const Text('Play the complete recording before evaluation.',
                style: TextStyle(fontSize: 12, color: Colors.black54)),
          if (result != null)
            Card(
                child: Padding(
                    padding: const EdgeInsets.all(12), child: Text(result!))),
          if (alignmentResult != null)
            Card(
                child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Word-level transcript comparison',
                              style: TextStyle(fontWeight: FontWeight.bold)),
                          if ((alignmentResult!['skipped'] as List? ?? [])
                              .isNotEmpty)
                            Text(
                                'Omitted from transcript: ${((alignmentResult!['skipped'] as List).map(_localizedEvaluationWord)).join(', ')}',
                                style: const TextStyle(color: Colors.red)),
                          ...((alignmentResult!['substituted'] as List? ??
                                  const [])
                              .map<Widget>((item) {
                            final substitution =
                                Map<String, dynamic>.from(item as Map);
                            return Text(
                                'Transcript substitution: expected ${_localizedEvaluationWord(substitution['expected'])}, recognized ${_localizedEvaluationWord(substitution['actual'])}. Retry this word against the reference.',
                                style:
                                    const TextStyle(color: Colors.deepOrange));
                          })),
                          if ((alignmentResult!['extra'] as List? ?? [])
                              .isNotEmpty)
                            Text(
                                'Additional transcript tokens: ${((alignmentResult!['extra'] as List).map(_localizedEvaluationWord)).join(', ')}'),
                        ]))),
          if (speechReport != null)
            Card(
                child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (speechReport!['diagnostic_only'] == true)
                            const Text(
                                'TEST MODE · using unreviewed lesson text; results are diagnostic only'),
                          if ((speechReport!['word_accuracy']
                              as Map?)?['match_percent'] is num)
                            Text(
                                '${speechReport!['diagnostic_only'] == true ? 'Candidate word match (diagnostic)' : 'Word match'}: ${((speechReport!['word_accuracy'] as Map)['match_percent'] as num).toStringAsFixed(1)}% · ${(speechReport!['word_accuracy'] as Map)['pass_threshold_percent']}% required'),
                          if ((speechReport!['pronunciation']
                              as Map?)?['overall_percent'] is num)
                            Text(
                                'Pronunciation score: ${((speechReport!['pronunciation'] as Map)['overall_percent'] as num).toStringAsFixed(1)}%'),
                          Text(
                              'Forced alignment: ${((speechReport!['forced_alignment'] as Map?)?['status'] ?? 'unavailable')}'),
                          ...(((speechReport!['forced_alignment']
                                      as Map?)?['words'] as List? ??
                                  const [])
                              .map<Widget>((item) {
                            final word = Map<String, dynamic>.from(item as Map);
                            final wordOrder =
                                int.tryParse('${word['word_order']}');
                            final startMs = int.tryParse('${word['start_ms']}');
                            final endMs = int.tryParse('${word['end_ms']}');
                            final wordOffset = _wordOffsetForLine(activeLine);
                            final guruWordIndex = wordOrder == null
                                ? -1
                                : wordOffset + wordOrder - 1;
                            final localizedWord = _localizedEvaluationWord(
                              word['word'],
                              wordIndex:
                                  guruWordIndex < 0 ? null : guruWordIndex,
                            );
                            final canPlayGuru = guruWordIndex >= 0 &&
                                _hasWordAudio(guruWordIndex);
                            return Padding(
                              padding: const EdgeInsets.symmetric(vertical: 4),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                      '${word['word_order']}. $localizedWord · ${word['start_ms']}–${word['end_ms']} ms · candidate timing'),
                                  Wrap(spacing: 8, children: [
                                    OutlinedButton.icon(
                                      onPressed:
                                          startMs == null || endMs == null
                                              ? null
                                              : () => playMyAlignedSegment(
                                                  startMs, endMs),
                                      icon: const Icon(Icons.person, size: 16),
                                      label: const Text('Play my word'),
                                    ),
                                    if (canPlayGuru)
                                      OutlinedButton.icon(
                                        onPressed: () =>
                                            playGuruWord(guruWordIndex),
                                        icon: const Icon(Icons.volume_up,
                                            size: 16),
                                        label: const Text('Play Guru word'),
                                      ),
                                  ]),
                                ],
                              ),
                            );
                          })),
                          if (((speechReport!['guru_student_timing_comparison']
                                  as Map?)?['status'] ==
                              'candidate_only')) ...[
                            const SizedBox(height: 8),
                            const Text(
                                'Relative Guru timing comparison · preview only, not pronunciation errors'),
                            ...(((speechReport![
                                            'guru_student_timing_comparison']
                                        as Map?)?['words'] as List? ??
                                    const [])
                                .map<Widget>((item) {
                              final timing =
                                  Map<String, dynamic>.from(item as Map);
                              final timingOrder =
                                  int.tryParse('${timing['word_order']}');
                              final timingWordIndex = timingOrder == null
                                  ? null
                                  : _wordOffsetForLine(activeLine) +
                                      timingOrder -
                                      1;
                              final localizedTimingWord =
                                  _localizedEvaluationWord(
                                timing['word'],
                                wordIndex: timingWordIndex,
                              );
                              final durationDelta =
                                  timing['normalized_duration_delta'];
                              final pauseDelta = timing['pause_before_delta'];
                              return Text(
                                  '${timing['word_order']}. $localizedTimingWord · duration Δ ${durationDelta is num ? (durationDelta * 100).toStringAsFixed(1) : 'n/a'}pp · pause Δ ${pauseDelta is num ? (pauseDelta * 100).toStringAsFixed(1) : 'n/a'}pp');
                            })),
                          ],
                          if (((speechReport!['forced_alignment']
                                      as Map?)?['aksharas'] as List? ??
                                  const [])
                              .isNotEmpty) ...[
                            const SizedBox(height: 8),
                            const Text(
                                'Akṣara timing candidates · not pronunciation scores'),
                            Wrap(
                              spacing: 4,
                              children: (((speechReport!['forced_alignment']
                                          as Map?)?['aksharas'] as List? ??
                                      const [])
                                  .map<Widget>((item) {
                                final akshara =
                                    Map<String, dynamic>.from(item as Map);
                                final startMs =
                                    int.tryParse('${akshara['start_ms']}');
                                final endMs =
                                    int.tryParse('${akshara['end_ms']}');
                                return ActionChip(
                                  avatar:
                                      const Icon(Icons.play_arrow, size: 16),
                                  label: Text('${akshara['akshara']}'),
                                  onPressed: startMs == null || endMs == null
                                      ? null
                                      : () =>
                                          playMyAlignedSegment(startMs, endMs),
                                );
                              }).toList()),
                            ),
                          ],
                          Text(
                              'Phonetic assessment: ${((speechReport!['pronunciation'] as Map?)?['status'] ?? 'unavailable')}'),
                          ...(((speechReport!['pronunciation']
                                      as Map?)?['phonetic_evidence'] as List? ??
                                  const [])
                              .map<Widget>((item) {
                            final finding =
                                Map<String, dynamic>.from(item as Map);
                            return Text(
                                '${finding['feature']}: ${finding['reference_value']} → ${finding['observed_value']} (${finding['confidence']}); ${finding['correction_guidance']}');
                          })),
                          ...(((speechReport!['word_accuracy']
                                          as Map?)?['correction_guidance']
                                      as List? ??
                                  const [])
                              .map<Widget>((item) {
                            final correction =
                                Map<String, dynamic>.from(item as Map);
                            final targetWord = _localizedEvaluationWord(
                                correction['target_word']);
                            final recognizedWord =
                                correction['recognized_word'];
                            final wordDetail = recognizedWord == null
                                ? targetWord
                                : '$targetWord (${_localizedEvaluationWord(recognizedWord)})';
                            return Text(
                                '${correction['issue']}: $wordDetail · ${correction['guidance']}');
                          })),
                          Text(
                              'Vedic accent assessment: ${((speechReport!['svara'] as Map?)?['status'] ?? 'unavailable')}'),
                          ...(((speechReport!['svara']
                                          as Map?)?['correction_guidance']
                                      as List? ??
                                  const [])
                              .map<Widget>((item) {
                            if (item is Map)
                              return Text(
                                  '${item['correction_guidance'] ?? item['guidance'] ?? item}');
                            return Text(item.toString());
                          })),
                        ]))),
          const Text(
            'Word accuracy, pronunciation and Vedic svara are reported only when a validated engine is configured. This screen will not invent scores.',
            style: TextStyle(fontSize: 12, color: Colors.black54),
          ),
        ],
      ),
    );
  }
}
