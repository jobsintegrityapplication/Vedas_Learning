import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session.dart';
import 'word_audio_timing_editor.dart';

class AdminPage extends StatefulWidget {
  const AdminPage({super.key});
  @override
  State<AdminPage> createState() => _AdminPageState();
}

class _AdminPageState extends State<AdminPage> {
  List lessons = [];
  List activity = [];
  Map<String, dynamic>? insights;
  String? error;
  String? insightsError;
  String? activityError;
  bool activityLoading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await context.read<Session>().api.get('/api/admin/lessons');
      if (mounted) setState(() => lessons = data as List);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
    try {
      final data = await context.read<Session>().api.get('/api/admin/customer-insights');
      if (mounted) setState(() => insights = Map<String, dynamic>.from(data as Map));
    } catch (e) {
      if (mounted) setState(() => insightsError = e.toString());
    }
    try {
      final data = await context.read<Session>().api.get('/api/admin/customer-activity?limit=50');
      if (mounted) setState(() {
        activity = data as List;
        activityLoading = false;
      });
    } catch (e) {
      if (mounted) setState(() {
        activityError = e.toString();
        activityLoading = false;
      });
    }
  }

  Widget _metric(String title, Object? value) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('$value', style: const TextStyle(fontSize: 25, fontWeight: FontWeight.bold)),
            Text(title),
          ]),
        ),
      );

  String _duration(Object? raw) {
    final seconds = int.tryParse('$raw') ?? 0;
    final hours = seconds ~/ 3600;
    final minutes = (seconds % 3600) ~/ 60;
    if (hours > 0) return '${hours}h ${minutes}m';
    return '${minutes}m';
  }

  String _when(Object? raw) {
    final value = DateTime.tryParse('$raw')?.toLocal();
    if (value == null) return 'Time unavailable';
    final hour = value.hour.toString().padLeft(2, '0');
    final minute = value.minute.toString().padLeft(2, '0');
    return '${value.day}/${value.month}/${value.year} $hour:$minute';
  }

  Widget _breakdown(String title, Map data) => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            if (data.isEmpty) const Text('No profile data yet.'),
            ...data.entries.map((entry) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(children: [Expanded(child: Text('${entry.key}')), Text('${entry.value}')]),
                )),
          ]),
        ),
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Admin · Guru content')),
      body: error != null
          ? Center(child: Text(error!))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                const Text('Customer overview', style: TextStyle(fontSize: 23, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                const Text('Aggregate learner data only. Names, email addresses and phone numbers are not shown here.'),
                if (insightsError != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text('Customer summary unavailable: $insightsError')),
                if (insights == null && insightsError == null) const LinearProgressIndicator(),
                if (insights != null) ...[
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    SizedBox(width: 155, child: _metric('Registered customers', insights!['registered_customers'])),
                    SizedBox(width: 155, child: _metric('Signed in · ever', insights!['logged_in_ever'])),
                    SizedBox(width: 155, child: _metric('Signed in · 7 days', insights!['logged_in_last_7_days'])),
                    SizedBox(width: 155, child: _metric('Signed in · 30 days', insights!['logged_in_last_30_days'])),
                    SizedBox(width: 155, child: _metric('App time total', _duration(insights!['total_app_time_seconds']))),
                    SizedBox(width: 155, child: _metric('Avg. app session', _duration(insights!['average_session_seconds']))),
                    SizedBox(width: 155, child: _metric('Learning time total', _duration(insights!['total_learning_time_seconds']))),
                    SizedBox(width: 155, child: _metric('Lesson completions', insights!['lessons_completed'])),
                    SizedBox(width: 155, child: _metric('Course completions', insights!['course_completions'])),
                  ]),
                  _breakdown('Age range', insights!['age_bands'] as Map),
                  _breakdown('Gender', insights!['genders'] as Map),
                  _breakdown('Profession (top 10)', insights!['professions'] as Map),
                  _breakdown('Recorded customer activity', insights!['activity_events'] as Map),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('Course completion patterns', style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 8),
                        ...(insights!['course_completions_by_scripture'] as List).map((row) {
                          final course = row as Map;
                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Row(children: [
                              Expanded(child: Text('${course['title']}')),
                              Text('${course['completions']} complete · avg ${_duration(course['average_period_seconds'])}'),
                            ]),
                          );
                        }),
                      ]),
                    ),
                  ),
                  Text('Average time from the first lesson opened in a scripture to completing all its published lessons: ${_duration(insights!['average_course_period_seconds'])}.', style: const TextStyle(fontSize: 12)),
                  const Text('Sign-in counts reflect successful sign-ins since activity tracking was added. Earlier login history is not available.', style: TextStyle(fontSize: 12)),
                ],
                const SizedBox(height: 16),
                const Text('Recent customer activity', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                const Text('Latest 50 recorded events. Customer email addresses and phone numbers are not included.'),
                if (activityError != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text('Activity log unavailable: $activityError')),
                if (activityLoading) const Padding(padding: EdgeInsets.all(12), child: LinearProgressIndicator()),
                if (activity.isEmpty && !activityLoading && activityError == null) const Text('No activity has been recorded yet.'),
                ...activity.map((row) {
                  final event = row as Map;
                  final eventType = '${event['event_type']}'.replaceAll('_', ' ');
                  final detail = [event['scripture'], event['lesson']].where((value) => value != null && '$value'.isNotEmpty).join(' · ');
                  final seconds = int.tryParse('${event['duration_seconds']}') ?? 0;
                  return Card(
                    child: ListTile(
                      title: Text('${event['customer']} · $eventType'),
                      subtitle: Text([_when(event['occurred_at']), if (detail.isNotEmpty) detail, if (seconds > 0) '${_duration(seconds)} recorded'].join(' · ')),
                      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => CustomerActivityPage(userId: event['user_id'].toString()))),
                    ),
                  );
                }),
                const Divider(height: 32),
                const Text(
                  'Sanskrit, meanings and reference audio are Guru-approved source material. This panel does not generate verses. Text edits require an explicit confirmation on the API.',
                ),
                const SizedBox(height: 12),
                if (lessons.isEmpty) const Text('Loading or no lessons found.'),
                ...lessons.map((row) {
                  final item = row as Map;
                  return Card(
                    child: ListTile(
                      title: Text('${item['title']}'),
                      subtitle: Text('${item['canonical_reference']} · ${item['word_audio_timings'] is List ? 'word timing saved' : 'word timing needed'}'),
                      trailing: const Icon(Icons.graphic_eq),
                      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => WordAudioTimingEditorPage(
                        lessonId: item['id'].toString(),
                        slug: item['slug'].toString(),
                        title: item['title'].toString(),
                      ))),
                    ),
                  );
                }),
                const SizedBox(height: 12),
                const Text('Select a lesson to mark each word’s start and end in its Guru recording. Learners can then tap a word to hear that segment.', style: TextStyle(fontSize: 12)),
              ],
            ),
    );
  }
}

class CustomerActivityPage extends StatefulWidget {
  const CustomerActivityPage({super.key, required this.userId});
  final String userId;

  @override
  State<CustomerActivityPage> createState() => _CustomerActivityPageState();
}

class _CustomerActivityPageState extends State<CustomerActivityPage> {
  Map<String, dynamic>? data;
  String? error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final result = await context.read<Session>().api.get('/api/admin/customers/${widget.userId}/activity');
      if (mounted) setState(() => data = Map<String, dynamic>.from(result as Map));
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  String _duration(Object? raw) {
    final seconds = int.tryParse('$raw') ?? 0;
    final hours = seconds ~/ 3600;
    final minutes = (seconds % 3600) ~/ 60;
    return hours > 0 ? '${hours}h ${minutes}m' : '${minutes}m';
  }

  String _when(Object? raw) {
    final value = DateTime.tryParse('$raw')?.toLocal();
    if (value == null) return 'Time unavailable';
    return '${value.day}/${value.month}/${value.year} ${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(data == null ? 'Customer activity' : '${data!['customer']} activity')),
      body: data == null
          ? Center(child: error == null ? const CircularProgressIndicator() : Text(error!))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('Username: ${data!['username'] ?? 'not set'}'),
                Text('Last sign-in: ${_when(data!['last_login_at'])}'),
                Text('App time: ${_duration(data!['total_app_time_seconds'])} · Learning time: ${_duration(data!['total_learning_time_seconds'])}'),
                Text('Completed lessons: ${data!['lessons_completed']} · Completed courses: ${data!['course_completions']}'),
                const SizedBox(height: 16),
                const Text('Courses', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                ...(data!['courses'] as List).map((row) {
                  final course = row as Map;
                  final dates = [
                    if (course['first_started_at'] != null) 'started ${_when(course['first_started_at'])}',
                    if (course['completed_at'] != null) 'completed ${_when(course['completed_at'])}',
                  ].join(' · ');
                  return ListTile(
                    title: Text('${course['title']} · ${course['lessons_completed']}/${course['lessons_total']} lessons'),
                    subtitle: Text(dates.isEmpty ? 'Not started' : dates),
                    trailing: Icon(course['is_completed'] == true ? Icons.check_circle : Icons.school_outlined),
                  );
                }),
                const SizedBox(height: 16),
                const Text('Recent app sessions', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                ...(data!['sessions'] as List).map((row) {
                  final item = row as Map;
                  return ListTile(title: Text(_when(item['started_at'])), subtitle: Text('${_duration(item['active_seconds'])} active'));
                }),
                const SizedBox(height: 16),
                const Text('Activity history', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                ...(data!['activity'] as List).map((row) {
                  final event = row as Map;
                  final title = '${event['event_type']}'.replaceAll('_', ' ');
                  final target = [event['scripture'], event['lesson']].where((value) => value != null).join(' · ');
                  final seconds = int.tryParse('${event['duration_seconds']}') ?? 0;
                  return ListTile(
                    title: Text(title),
                    subtitle: Text([_when(event['occurred_at']), if (target.isNotEmpty) target, if (seconds > 0) _duration(seconds)].join(' · ')),
                  );
                }),
                const Text('Contact details are intentionally omitted from activity reports.'),
              ],
            ),
    );
  }
}
