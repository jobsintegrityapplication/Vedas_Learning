import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/language_service.dart';
import '../state/session.dart';

class ProgressPage extends StatefulWidget {
  const ProgressPage({super.key});
  @override
  State<ProgressPage> createState() => _ProgressPageState();
}

class _ProgressPageState extends State<ProgressPage> {
  Map<String, dynamic>? data;
  String? error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final result = await context.read<Session>().api.get('/api/progress/me');
      setState(() => data = Map<String, dynamic>.from(result as Map));
    } catch (e) {
      setState(() => error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final language = context.watch<LanguageService>();
    return Scaffold(
      appBar: AppBar(title: Text(language.dashboardText('title')), actions: [DropdownButton<String>(value: language.code, underline: const SizedBox.shrink(), items: LanguageService.supported.map((item) => DropdownMenuItem(value: item.code, child: Text(item.name))).toList(), onChanged: (value) { if (value != null) language.select(value); })]),
      body: data == null
          ? Center(child: error == null ? const CircularProgressIndicator() : Text(error!))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Wrap(spacing: 12, runSpacing: 12, children: [
                  _stat('Published lessons', '${data!['lessons_published']}'),
                  _stat('Lessons practiced', '${data!['lessons_practiced']}'),
                  _stat('Recordings', '${data!['recordings']}'),
                  _stat('App time', _duration(data!['app_time_seconds'])),
                  _stat('Learning time', _duration(data!['learning_time_seconds'])),
                ]),
                const SizedBox(height: 20),
                Text(language.dashboardText('mantra_progress'), style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                if ((data!['progressive_recitation'] as List? ?? const []).isEmpty)
                  Padding(padding: const EdgeInsets.only(top: 12), child: Text(language.dashboardText('empty'))),
                ...((data!['progressive_recitation'] as List? ?? const []).map((raw) {
                  final profile = Map<String, dynamic>.from(raw as Map);
                  final mandalas = (profile['by_mandala'] as Map? ?? const {}).entries.toList()
                    ..sort((a, b) => int.parse(a.key).compareTo(int.parse(b.key)));
                  return Card(child: ExpansionTile(
                    title: Text('${profile['profile']} · ${profile['mantras_completed']} ${language.dashboardText('complete')}'),
                    subtitle: Text('${profile['mantras_started']} ${language.dashboardText('started')} · ${profile['words_completed']} ${language.dashboardText('words')} · ${profile['attempts']} ${language.dashboardText('attempts')} · ${profile['bookmarks']} ${language.dashboardText('bookmarks')}'),
                    children: mandalas.isEmpty ? [const ListTile(title: Text('No Maṇḍala progress yet'))] : mandalas.map((entry) {
                      final stats = Map<String, dynamic>.from(entry.value as Map);
                      return ListTile(title: Text('${language.dashboardText('mandala')} ${entry.key}'), subtitle: Text('${stats['mantras_completed']} ${language.dashboardText('complete')} · ${stats['mantras_started']} ${language.dashboardText('started')} · ${stats['words_completed']} ${language.dashboardText('words')}'));
                    }).toList(),
                  ));
                })),
                const SizedBox(height: 20),
                const Text('Courses', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                ...(data!['courses'] as List).map((row) {
                  final course = row as Map;
                  return Card(
                    child: ListTile(
                      title: Text('${course['title']}'),
                      subtitle: Text('${course['lessons_completed']} of ${course['lessons_total']} lessons complete'),
                      trailing: Icon(course['is_completed'] == true ? Icons.check_circle : Icons.school_outlined),
                    ),
                  );
                }),
                const SizedBox(height: 20),
                const Text('Learning history', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                if ((data!['history'] as List).isEmpty) const Padding(padding: EdgeInsets.only(top: 12), child: Text('No recitations submitted yet.')),
                ...(data!['history'] as List).map((row) {
                  final item = row as Map;
                  return Card(
                    child: ListTile(
                      title: Text('${item['title']}'),
                      subtitle: Text('${item['reference']} · ${item['attempts']} attempt(s) · ${_duration(item['time_spent_seconds'])} study time${item['completed_at'] == null ? '' : ' · complete'}'),
                    ),
                  );
                }),
              ],
            ),
    );
  }

  Widget _stat(String label, String value) {
    return SizedBox(
      width: 160,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(value, style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)),
            Text(label),
          ]),
        ),
      ),
    );
  }

  String _duration(Object? raw) {
    final seconds = int.tryParse('$raw') ?? 0;
    final hours = seconds ~/ 3600;
    final minutes = (seconds % 3600) ~/ 60;
    if (hours > 0) return '${hours}h ${minutes}m';
    return '${minutes}m';
  }
}
