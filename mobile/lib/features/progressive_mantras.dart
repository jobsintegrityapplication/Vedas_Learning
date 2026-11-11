import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import 'package:record/record.dart';

import '../core/language_service.dart';
import '../state/session.dart';
import '../core/recording_duration.dart';

class ProgressiveMantrasPage extends StatefulWidget {
  const ProgressiveMantrasPage({super.key});
  @override
  State<ProgressiveMantrasPage> createState() => _ProgressiveMantrasPageState();
}

class _ProgressiveMantrasPageState extends State<ProgressiveMantrasPage> {
  String profile = 'Kanchi';
  int? mandala;
  bool onlyBookmarks = false;
  bool loading = true;
  String? error;
  List mantras = [];
  Map<String, dynamic>? libraryIndex;
  int? sukta;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final query = <String, String>{'profile': profile};
      if (mandala != null) query['mandala'] = '$mandala';
      if (sukta != null) query['sukta'] = '$sukta';
      if (onlyBookmarks) query['bookmarked'] = 'true';
      final indexData = await context
          .read<Session>()
          .api
          .get('/api/recitation/library-index?profile=$profile');
      final data = await context.read<Session>().api.get(
          '/api/recitation/learning-mantras?${Uri(queryParameters: query).query}');
      if (mounted)
        setState(() {
          libraryIndex = Map<String, dynamic>.from(indexData as Map);
          mantras = (data as Map)['mantras'] as List? ?? [];
          loading = false;
        });
    } catch (e) {
      if (mounted)
        setState(() {
          error = e.toString();
          loading = false;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final language = context.watch<LanguageService>();
    String t(String key) => language.progressive(key);
    return Scaffold(
      appBar: AppBar(title: Text(t('title')), actions: [
        DropdownButton<String>(
            value: language.code,
            underline: const SizedBox.shrink(),
            items: LanguageService.supported
                .map((item) =>
                    DropdownMenuItem(value: item.code, child: Text(item.name)))
                .toList(),
            onChanged: (value) {
              if (value != null) language.select(value);
            }),
      ]),
      body: Column(children: [
        Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Wrap(spacing: 12, children: [
              DropdownButton<String>(
                  value: profile,
                  items: const [
                    DropdownMenuItem(value: 'Kanchi', child: Text('Kanchi')),
                    DropdownMenuItem(
                        value: 'Sringeri', child: Text('Sringeri')),
                    DropdownMenuItem(
                        value: 'Common',
                        child: Text('Common (shared reference)'))
                  ],
                  onChanged: (v) {
                    if (v == null) return;
                    setState(() {
                      profile = v;
                      mandala = null;
                      sukta = null;
                    });
                    _load();
                  }),
              DropdownButton<int?>(
                  value: mandala,
                  hint: Text(t('all_mandalas')),
                  items: [
                    DropdownMenuItem<int?>(
                        value: null, child: Text(t('all_mandalas'))),
                    for (final raw
                        in (libraryIndex?['mandalas'] as List? ?? const []))
                      DropdownMenuItem<int?>(
                          value: (raw as Map)['mandala'] as int,
                          child: Text(
                              'Maṇḍala ${raw['mandala']} · ${raw['available_mantra_count']}/${raw['expected_mantra_count']}')),
                  ],
                  onChanged: (v) {
                    setState(() {
                      mandala = v;
                      sukta = null;
                    });
                    _load();
                  }),
              if (mandala != null && libraryIndex != null)
                DropdownButton<int?>(
                  value: sukta,
                  hint: Text(t('all_suktas')),
                  items: [
                    DropdownMenuItem<int?>(
                        value: null, child: Text(t('all_suktas'))),
                    ...(((libraryIndex!['mandalas'] as List).firstWhere(
                                (x) => (x as Map)['mandala'] == mandala)
                            as Map)['suktas'] as List)
                        .map((x) {
                      final row = x as Map;
                      final n = row['sukta'] as int;
                      return DropdownMenuItem<int?>(
                          value: n,
                          child: Text(
                              'Sukta $n · ${row['available_mantra_count']} ready'));
                    }),
                  ],
                  onChanged: (v) {
                    setState(() => sukta = v);
                    _load();
                  },
                ),
              FilterChip(
                  label: Text(t('bookmarks')),
                  selected: onlyBookmarks,
                  onSelected: (v) {
                    setState(() => onlyBookmarks = v);
                    _load();
                  }),
            ])),
        Expanded(
            child: loading
                ? const Center(child: CircularProgressIndicator())
                : error != null
                    ? Center(child: Text(error!))
                    : mantras.isEmpty
                        ? Center(
                            child: Padding(
                                padding: const EdgeInsets.all(28),
                                child: Text(sukta == null
                                    ? t('no_records')
                                    : 'Maṇḍala $mandala · Sūkta $sukta — ${t('no_sukta')}')))
                        : ListView.builder(
                            itemCount: mantras.length,
                            itemBuilder: (context, index) {
                              final item = Map<String, dynamic>.from(
                                  mantras[index] as Map);
                              final done = item['completed_word_count'] ?? 0;
                              return Card(
                                  child: ListTile(
                                leading: Icon(item['completed'] == true
                                    ? Icons.check_circle
                                    : Icons.menu_book),
                                title: Text(
                                    '${item['mantra_reference']} · $profile'),
                                subtitle: Text(
                                    '$done / ${item['word_count']} words complete · resume at word ${item['current_word_order']} · ${item['full_audio_available'] == true ? 'full audio available' : 'full audio unavailable'}'),
                                trailing: Icon(item['bookmarked'] == true
                                    ? Icons.bookmark
                                    : Icons.chevron_right),
                                onTap: () async {
                                  await Navigator.push(
                                      context,
                                      MaterialPageRoute(
                                          builder: (_) => _MantraPracticePage(
                                              reference:
                                                  item['mantra_reference']
                                                      .toString(),
                                              profile: profile)));
                                  if (mounted) _load();
                                },
                              ));
                            })),
      ]),
    );
  }
}

class _MantraPracticePage extends StatefulWidget {
  const _MantraPracticePage({required this.reference, required this.profile});
  final String reference;
  final String profile;
  @override
  State<_MantraPracticePage> createState() => _MantraPracticePageState();
}

class _MantraPracticePageState extends State<_MantraPracticePage> {
  final recorder = AudioRecorder();
  final player = AudioPlayer();
  Map<String, dynamic>? data;
  Map<String, dynamic>? lastAttempt;
  String? path;
  String? error;
  bool recording = false;
  bool recordingPreviewed = false;
  bool busy = false;
  final Stopwatch recordingStopwatch = Stopwatch();
  Timer? recordingTick;
  int activeWord = 1;
  String attemptMode = 'word';

  Duration get recordingElapsed => recordingStopwatch.elapsed;
  bool get minimumRecordingReached =>
      RecordingDurationPolicy.canStop(recordingElapsed);
  int get recordingSecondsRemaining =>
      RecordingDurationPolicy.secondsRemaining(recordingElapsed);
  String get recordingElapsedLabel =>
      RecordingDurationPolicy.formatElapsed(recordingElapsed);

  String get _base =>
      '/api/recitation/${Uri.encodeComponent(widget.reference)}';
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final response = await context
          .read<Session>()
          .api
          .get('$_base/learning?profile=${widget.profile}');
      final history = await context
          .read<Session>()
          .api
          .get('$_base/attempts?profile=${widget.profile}');
      if (!mounted) return;
      final result = Map<String, dynamic>.from(response as Map);
      final attempts = (history as List? ?? const []);
      setState(() {
        data = result;
        activeWord = (result['current_word_order'] as int?) ?? 1;
        lastAttempt = attempts.isNotEmpty
            ? Map<String, dynamic>.from(attempts.first as Map)
            : null;
      });
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> _resume(int word) async {
    await context.read<Session>().api.post(
        '$_base/resume?profile=${widget.profile}',
        body: {'word_order': word});
    if (mounted) setState(() => activeWord = word);
  }

  Future<void> _bookmark(bool value) async {
    await context.read<Session>().api.put(
        '$_base/bookmark?profile=${widget.profile}',
        body: {'bookmarked': value});
    await _load();
  }

  Future<void> _listen(String? url, String label) async {
    if (url == null || url.isEmpty) {
      _message('$label audio is unavailable for ${widget.profile}.');
      return;
    }
    await player.setUrl(url);
    await player.play();
  }

  Future<void> _start(String mode, int wordOrder) async {
    try {
      if (!await recorder.hasPermission())
        throw Exception('Microphone permission denied');
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      if (kIsWeb) {
        path = null;
      } else {
        final dir = await getApplicationDocumentsDirectory();
        path = '${dir.path}/mantra_$timestamp.m4a';
      }
      attemptMode = mode;
      activeWord = wordOrder;
      final outputName = kIsWeb ? 'mantra_$timestamp.wav' : path!;
      await recorder.start(
          RecordConfig(encoder: kIsWeb ? AudioEncoder.wav : AudioEncoder.aacLc),
          path: outputName);
      recordingPreviewed = false;
      recordingStopwatch
        ..reset()
        ..start();
      recordingTick?.cancel();
      recordingTick = Timer.periodic(const Duration(milliseconds: 250), (_) {
        if (mounted && recording) setState(() {});
      });
      setState(() => recording = true);
    } catch (e) {
      _message(e.toString());
    }
  }

  Future<void> _stop() async {
    if (!minimumRecordingReached) {
      _message(
          'Keep recording for at least 2 seconds. ${recordingSecondsRemaining}s remaining.');
      return;
    }
    try {
      final value = await recorder.stop();
      if (kIsWeb && (value == null || !value.startsWith('blob:'))) {
        throw Exception(
            'The browser did not return the finished recording. Please record again.');
      }
      if (mounted)
        setState(() {
          recording = false;
          path = value ?? path;
          recordingPreviewed = false;
        });
      recordingTick?.cancel();
      recordingTick = null;
      recordingStopwatch
        ..stop()
        ..reset();
    } catch (e) {
      if (mounted) {
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
        _message('Could not finish the recording: $e');
      }
    }
  }

  Future<void> _playMine() async {
    final recordedPath = path;
    if (recordedPath == null) return;
    try {
      if (kIsWeb) {
        await player.setUrl(recordedPath);
      } else {
        await player.setFilePath(recordedPath);
      }
      await player.play();
      if (mounted) setState(() => recordingPreviewed = true);
    } catch (e) {
      _message('Could not play your recording: $e');
    }
  }

  Future<void> _submit() async {
    if (path == null) return;
    setState(() => busy = true);
    try {
      final result = await context.read<Session>().api.uploadMantraAttempt(
          widget.reference, path!,
          profile: widget.profile, mode: attemptMode, wordOrder: activeWord);
      if (mounted)
        setState(() {
          lastAttempt = result;
          path = null;
        });
      await _load();
    } catch (e) {
      _message(e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void _message(String value) {
    if (mounted)
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  void dispose() {
    recordingTick?.cancel();
    recorder.dispose();
    player.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final language = context.watch<LanguageService>();
    String t(String key) => language.progressive(key);
    if (error != null)
      return Scaffold(appBar: AppBar(), body: Center(child: Text(error!)));
    if (data == null)
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    final words = (data!['words'] as List? ?? const [])
        .map((x) => Map<String, dynamic>.from(x as Map))
        .toList();
    if (data!['status'] != 'available')
      return Scaffold(
          appBar: AppBar(title: Text(widget.reference)),
          body: Center(
              child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Text('${data!['reason']}'))));
    final selectedRows =
        words.where((x) => x['word_order'] == activeWord).toList();
    final selected = selectedRows.isEmpty ? null : selectedRows.first;
    final completed =
        (data!['completed_word_orders'] as List? ?? const []).cast<int>();
    var contiguous = 0;
    while (completed.contains(contiguous + 1)) {
      contiguous++;
    }
    final canCombine = contiguous >= 2 &&
        (data!['combined_passed'] != true || contiguous < words.length);
    return Scaffold(
      appBar: AppBar(
          title: Text('${widget.reference} · ${widget.profile}'),
          actions: [
            DropdownButton<String>(
                value: context.watch<LanguageService>().code,
                underline: const SizedBox.shrink(),
                items: LanguageService.supported
                    .map((item) => DropdownMenuItem(
                        value: item.code, child: Text(item.name)))
                    .toList(),
                onChanged: (value) {
                  if (value != null)
                    context.read<LanguageService>().select(value);
                }),
            IconButton(
                icon: Icon(data!['bookmarked'] == true
                    ? Icons.bookmark
                    : Icons.bookmark_border),
                onPressed: () => _bookmark(data!['bookmarked'] != true)),
          ]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text('Saṃhitā', style: Theme.of(context).textTheme.titleMedium),
        Text('${data!['samhita_form']}'),
        const SizedBox(height: 8),
        Text('Padapāṭha', style: Theme.of(context).textTheme.titleMedium),
        Text('${data!['padapatha_form']}'),
        const SizedBox(height: 12),
        Text(
            'Word ${data!['current_word_order']} · unlocked through ${data!['unlocked_word_order']} · ${completed.length}/${words.length} complete'),
        ...words.map((word) => Card(
            color: word['word_order'] == activeWord
                ? Theme.of(context).colorScheme.primaryContainer
                : null,
            child: ListTile(
              leading: Icon(word['completed'] == true
                  ? Icons.check_circle
                  : (word['unlocked'] == true
                      ? Icons.circle_outlined
                      : Icons.lock)),
              title: Text('${word['word_order']}. ${word['original_form']}'),
              subtitle: Text(word['audio_available'] == true
                  ? 'Word audio available'
                  : t('word_audio_missing')),
              trailing: IconButton(
                  icon: const Icon(Icons.volume_up),
                  onPressed: word['audio_available'] == true &&
                          word['unlocked'] == true
                      ? () => _listen(word['audio_url']?.toString(), 'Word')
                      : null),
              onTap: word['unlocked'] == true
                  ? () => _resume(word['word_order'] as int)
                  : null,
            ))),
        const SizedBox(height: 8),
        Text(data!['full_audio_available'] != true
            ? t('full_audio_missing')
            : (data!['combined_passed'] == true
                ? 'Full-mantra reference is available.'
                : 'Full-mantra playback unlocks after combined-word practice.')),
        OutlinedButton.icon(
            onPressed: data!['full_audio_available'] == true &&
                    data!['combined_passed'] == true
                ? () =>
                    _listen(data!['full_audio_url']?.toString(), 'Full mantra')
                : null,
            icon: const Icon(Icons.play_arrow),
            label: Text(t('listen_full'))),
        if (selected != null) ...[
          Text('Selected word: ${selected['original_form']}'),
          Text(selected['audio_available'] == true
              ? 'Listen, record, evaluate, and retry this word until the selected-profile evaluation passes.'
              : t('word_audio_missing')),
        ],
        FilledButton.icon(
          onPressed: recording
              ? (minimumRecordingReached ? _stop : null)
              : (selected != null && selected['unlocked'] == true
                  ? () => _start('word', activeWord)
                  : null),
          icon: Icon(recording
              ? (minimumRecordingReached ? Icons.stop : Icons.mic)
              : Icons.mic),
          label: Text(recording
              ? minimumRecordingReached
                  ? 'Stop recording · $recordingElapsedLabel'
                  : 'Keep recording · ${recordingSecondsRemaining}s left'
              : '${t('record_word')} $activeWord'),
        ),
        if (recording)
          Text('Recording $recordingElapsedLabel · minimum 00:02',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 12, color: Colors.black54)),
        if (path != null && !recording && attemptMode == 'word') ...[
          OutlinedButton.icon(
              onPressed: busy ? null : _playMine,
              icon: const Icon(Icons.play_arrow),
              label: Text(recordingPreviewed
                  ? 'Play my recording again'
                  : 'Play my recording')),
          FilledButton(
              onPressed: busy || !recordingPreviewed ? null : _submit,
              child: Text(busy ? 'Evaluating…' : t('evaluate_retry'))),
        ],
        if (canCombine) ...[
          const Divider(),
          Text(t('combine')),
          FilledButton.icon(
              onPressed: recording
                  ? (minimumRecordingReached ? _stop : null)
                  : () => _start('combined', contiguous),
              icon: Icon(recording
                  ? (minimumRecordingReached ? Icons.stop : Icons.mic)
                  : Icons.queue_music),
              label: Text(recording
                  ? (minimumRecordingReached
                      ? 'Stop recording · $recordingElapsedLabel'
                      : 'Keep recording · ${recordingSecondsRemaining}s left')
                  : '${t('record_combined')} 1–$contiguous')),
          if (path != null && !recording && attemptMode == 'combined') ...[
            OutlinedButton.icon(
                onPressed: busy ? null : _playMine,
                icon: const Icon(Icons.play_arrow),
                label: Text(recordingPreviewed
                    ? 'Play my recording again'
                    : 'Play my recording')),
            FilledButton(
                onPressed: busy || !recordingPreviewed ? null : _submit,
                child: Text(t('evaluate_combined'))),
          ],
        ],
        if (data!['combined_passed'] == true) ...[
          const Divider(),
          const Text(
              'Combined learned words passed. Recite the complete mantra for the final report.'),
          FilledButton.icon(
              onPressed: recording
                  ? (minimumRecordingReached ? _stop : null)
                  : () => _start('full_mantra', 0),
              icon: Icon(recording
                  ? (minimumRecordingReached ? Icons.stop : Icons.mic)
                  : Icons.record_voice_over),
              label: Text(recording
                  ? (minimumRecordingReached
                      ? 'Stop recording · $recordingElapsedLabel'
                      : 'Keep recording · ${recordingSecondsRemaining}s left')
                  : t('record_full'))),
          if (path != null && !recording && attemptMode == 'full_mantra') ...[
            OutlinedButton.icon(
                onPressed: busy ? null : _playMine,
                icon: const Icon(Icons.play_arrow),
                label: Text(recordingPreviewed
                    ? 'Play my recording again'
                    : 'Play my recording')),
            FilledButton(
                onPressed: busy || !recordingPreviewed ? null : _submit,
                child: Text(t('evaluate_full'))),
          ],
        ],
        if (lastAttempt != null)
          Card(
              child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                            lastAttempt!['passed'] == true
                                ? 'Evaluation passed'
                                : 'Evaluation: ${lastAttempt!['evaluation_status']} · ${lastAttempt!['passed'] == true ? 'passed' : 'not passed'}',
                            style: Theme.of(context).textTheme.titleMedium),
                        Builder(builder: (context) {
                          final report = Map<String, dynamic>.from(
                              (lastAttempt!['report'] as Map?) ?? const {});
                          final word = Map<String, dynamic>.from(
                              (report['word_accuracy'] as Map?) ?? const {});
                          final pronunciation = Map<String, dynamic>.from(
                              (report['pronunciation'] as Map?) ?? const {});
                          final pronunciationScore =
                              pronunciation['overall_percent'];
                          return Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                if (word['match_percent'] is num)
                                  Text(
                                      'Word match: ${(word['match_percent'] as num).toStringAsFixed(1)}% · ${word['pass_threshold_percent']}% required'),
                                Text(
                                    '${word['reason'] ?? 'No word evaluation evidence is available.'}'),
                                ...((word['correction_guidance'] as List? ??
                                        const [])
                                    .map((x) => Text(
                                        x is Map ? '${x['guidance']}' : '$x'))),
                                Text(
                                    'Forced alignment: ${((report['forced_alignment'] as Map?)?['status'] ?? 'unavailable')}'),
                                ...(((report['forced_alignment']
                                            as Map?)?['words'] as List? ??
                                        const [])
                                    .map((x) {
                                  final item =
                                      Map<String, dynamic>.from(x as Map);
                                  return Text(
                                      '${item['word_order']}. ${item['word']} · ${item['start_ms']}–${item['end_ms']} ms · confidence ${item['confidence']}');
                                })),
                                if (((report['guru_student_timing_comparison']
                                        as Map?)?['status'] ==
                                    'candidate_only')) ...[
                                  const SizedBox(height: 8),
                                  const Text(
                                      'Relative Guru timing comparison · preview only, not pronunciation errors'),
                                  ...(((report['guru_student_timing_comparison']
                                              as Map?)?['words'] as List? ??
                                          const [])
                                      .map((x) {
                                    final timing =
                                        Map<String, dynamic>.from(x as Map);
                                    final durationDelta =
                                        timing['normalized_duration_delta'];
                                    final pauseDelta =
                                        timing['pause_before_delta'];
                                    return Text(
                                        '${timing['word_order']}. ${timing['word']} · duration Δ ${durationDelta is num ? (durationDelta * 100).toStringAsFixed(1) : 'n/a'}pp · pause Δ ${pauseDelta is num ? (pauseDelta * 100).toStringAsFixed(1) : 'n/a'}pp');
                                  })),
                                ],
                                Text(
                                    'Phonetic feedback: ${pronunciation['status'] ?? 'unavailable'}${pronunciationScore is num ? ' · ${pronunciationScore.toStringAsFixed(1)}%' : ''}'),
                                Text('${report['acceptance_reason'] ?? ''}'),
                                ...(((report['pronunciation']
                                                as Map?)?['phonetic_evidence']
                                            as List? ??
                                        const [])
                                    .map((x) {
                                  final item =
                                      Map<String, dynamic>.from(x as Map);
                                  return Text(
                                      '${item['feature']}: ${item['reference_value']} → ${item['observed_value']} · confidence ${item['confidence']} · ${item['correction_guidance']}');
                                })),
                                Text(
                                    'Vedic accent: ${((report['svara'] as Map?)?['status'] ?? 'unavailable')}'),
                                if (lastAttempt!['mode'] == 'full_mantra')
                                  const Text(
                                      'This is the saved final full-mantra report.'),
                              ]);
                        }),
                        if (lastAttempt!['passed'] != true)
                          Text(t('retry_notice')),
                      ]))),
      ]),
    );
  }
}
