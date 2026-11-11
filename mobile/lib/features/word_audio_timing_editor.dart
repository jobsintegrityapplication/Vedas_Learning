import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:provider/provider.dart';

import '../state/session.dart';
import '../widgets/forms.dart';

class WordAudioTimingEditorPage extends StatefulWidget {
  const WordAudioTimingEditorPage({super.key, required this.lessonId, required this.slug, required this.title});
  final String lessonId;
  final String slug;
  final String title;

  @override
  State<WordAudioTimingEditorPage> createState() => _WordAudioTimingEditorPageState();
}

class _WordMark {
  _WordMark(this.word, {this.startMs, this.endMs});
  final String word;
  int? startMs;
  int? endMs;
}

class _WordAudioTimingEditorPageState extends State<WordAudioTimingEditorPage> {
  final AudioPlayer _player = AudioPlayer();
  final AudioPlayer _previewPlayer = AudioPlayer();
  List<_WordMark> _words = [];
  Duration _duration = Duration.zero;
  int _selectedIndex = 0;
  bool _loading = true;
  bool _saving = false;
  String? _error;
  late final Session _session;

  String get _audioAsset => 'assets/audio/guru_reference/${widget.slug}.ogg';

  @override
  void initState() {
    super.initState();
    _session = context.read<Session>();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = Map<String, dynamic>.from(await _session.api.get('/api/admin/lessons/${widget.lessonId}') as Map);
      final text = data['sanskrit_text']?.toString() ?? '';
      final tokens = text
          .split(RegExp(r'\s+'))
          .map((word) => word.replaceAll(RegExp(r'[।॥,;:!?]+$'), ''))
          .where((word) => word.isNotEmpty)
          .toList();
      final existing = data['word_audio_timings'] is List ? data['word_audio_timings'] as List : const [];
      _words = [
        for (var i = 0; i < tokens.length; i++)
          _WordMark(
            tokens[i],
            startMs: i < existing.length && existing[i] is Map ? int.tryParse('${existing[i]['start_ms']}') : null,
            endMs: i < existing.length && existing[i] is Map ? int.tryParse('${existing[i]['end_ms']}') : null,
          ),
      ];
      await _player.setAsset(_audioAsset);
      _duration = _player.duration ?? Duration.zero;
      if (mounted) setState(() => _loading = false);
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  String _clock(Duration value) {
    final seconds = value.inMilliseconds / 1000;
    return '${seconds.toStringAsFixed(2)}s';
  }

  Future<void> _setStart() async {
    final now = _player.position.inMilliseconds;
    setState(() => _words[_selectedIndex].startMs = now);
  }

  Future<void> _setEnd() async {
    final now = _player.position.inMilliseconds;
    final mark = _words[_selectedIndex];
    if (mark.startMs == null || now <= mark.startMs!) {
      showMessage(context, 'Set this word’s start first, then mark an end after it.');
      return;
    }
    setState(() {
      mark.endMs = now;
      if (_selectedIndex + 1 < _words.length) _selectedIndex++;
    });
  }

  Future<void> _previewSelectedWord() async {
    final mark = _words[_selectedIndex];
    if (mark.startMs == null || mark.endMs == null || mark.endMs! <= mark.startMs!) {
      showMessage(context, 'Mark a valid start and end for this word before previewing it.');
      return;
    }
    try {
      await _previewPlayer.setAsset(_audioAsset);
      await _previewPlayer.seek(Duration(milliseconds: mark.startMs!));
      final reachedEnd = _previewPlayer.positionStream.firstWhere((position) => position.inMilliseconds >= mark.endMs!);
      final playback = _previewPlayer.play();
      await reachedEnd.timeout(const Duration(seconds: 15));
      await _previewPlayer.pause();
      await playback;
    } catch (e) {
      if (mounted) showMessage(context, 'Could not preview this word: $e');
    }
  }

  Future<void> _playFull() async {
    await _player.setAsset(_audioAsset);
    await _player.seek(Duration.zero);
    await _player.play();
  }

  Future<void> _save() async {
    if (_words.any((word) => word.startMs == null || word.endMs == null)) {
      showMessage(context, 'Mark start and end for every word before saving.');
      return;
    }
    var previousEnd = 0;
    for (final word in _words) {
      if (word.endMs! <= word.startMs! || word.startMs! < previousEnd || word.endMs! > _duration.inMilliseconds) {
        showMessage(context, 'Check the word boundaries: they must be ordered, non-overlapping, and inside the recording.');
        return;
      }
      previousEnd = word.endMs!;
    }
    setState(() => _saving = true);
    try {
      await _session.api.put('/api/admin/lessons/${widget.lessonId}/word-audio-timings', body: {
        'words': [
          for (var i = 0; i < _words.length; i++)
            {'word_order': i, 'word': _words[i].word, 'start_ms': _words[i].startMs, 'end_ms': _words[i].endMs},
        ],
      });
      if (mounted) showMessage(context, 'Word timings saved. Learners can now tap each word.');
    } catch (e) {
      if (mounted) showMessage(context, 'Could not save word timings: $e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  void dispose() {
    _player.dispose();
    _previewPlayer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return Scaffold(appBar: AppBar(title: const Text('Word audio timing')), body: const Center(child: CircularProgressIndicator()));
    if (_error != null) return Scaffold(appBar: AppBar(title: const Text('Word audio timing')), body: Center(child: Text(_error!)));
    final maxMs = math.max(1, _duration.inMilliseconds);
    return Scaffold(
      appBar: AppBar(title: Text('Word audio · ${widget.title}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('Play the full Guru recording. Select each Sanskrit word, then mark its start and end while it is spoken. These boundaries power tap-to-play and sequential highlighting for learners.'),
          const SizedBox(height: 12),
          Card(child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(children: [
              StreamBuilder<Duration>(
                stream: _player.positionStream,
                initialData: _player.position,
                builder: (context, snapshot) {
                  final position = snapshot.data ?? Duration.zero;
                  final value = position.inMilliseconds.clamp(0, maxMs).toDouble();
                  return Column(children: [
                    Slider(value: value, max: maxMs.toDouble(), onChanged: (next) => _player.seek(Duration(milliseconds: next.round()))),
                    Text('${_clock(position)} / ${_clock(_duration)}'),
                  ]);
                },
              ),
              Wrap(alignment: WrapAlignment.center, spacing: 8, children: [
                StreamBuilder<bool>(
                  stream: _player.playingStream,
                  initialData: _player.playing,
                  builder: (context, snapshot) => FilledButton.icon(
                    onPressed: () => snapshot.data == true ? _player.pause() : _player.play(),
                    icon: Icon(snapshot.data == true ? Icons.pause : Icons.play_arrow),
                    label: Text(snapshot.data == true ? 'Pause recording' : 'Play recording'),
                  ),
                ),
                OutlinedButton.icon(onPressed: _playFull, icon: const Icon(Icons.replay), label: const Text('Restart from beginning')),
              ]),
            ]),
          )),
          Card(child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text('Word ${_selectedIndex + 1} of ${_words.length}: ${_words[_selectedIndex].word}', style: Theme.of(context).textTheme.titleLarge, textAlign: TextAlign.center),
              const SizedBox(height: 8),
              Text('Start: ${_words[_selectedIndex].startMs == null ? 'not marked' : _clock(Duration(milliseconds: _words[_selectedIndex].startMs!))} · End: ${_words[_selectedIndex].endMs == null ? 'not marked' : _clock(Duration(milliseconds: _words[_selectedIndex].endMs!))}', textAlign: TextAlign.center),
              const SizedBox(height: 8),
              Wrap(alignment: WrapAlignment.center, spacing: 8, children: [
                OutlinedButton.icon(onPressed: _setStart, icon: const Icon(Icons.flag), label: const Text('Mark word start')),
                FilledButton.icon(onPressed: _setEnd, icon: const Icon(Icons.flag_circle), label: const Text('Mark word end · next')),
                OutlinedButton.icon(onPressed: _previewSelectedWord, icon: const Icon(Icons.volume_up), label: const Text('Preview selected word')),
              ]),
            ]),
          )),
          Text('Word boundaries', style: Theme.of(context).textTheme.titleMedium),
          ...List.generate(_words.length, (index) {
            final mark = _words[index];
            return Card(child: ListTile(
              selected: index == _selectedIndex,
              leading: CircleAvatar(child: Text('${index + 1}')),
              title: Text(mark.word, textDirection: TextDirection.rtl, textAlign: TextAlign.left),
              subtitle: Text('${mark.startMs == null ? '—' : _clock(Duration(milliseconds: mark.startMs!))} → ${mark.endMs == null ? '—' : _clock(Duration(milliseconds: mark.endMs!))}'),
              onTap: () => setState(() => _selectedIndex = index),
            ));
          }),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: _saving ? null : _save,
            icon: const Icon(Icons.save),
            label: Text(_saving ? 'Saving…' : 'Save word timings'),
          ),
        ],
      ),
    );
  }
}
