import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/session.dart';
import '../core/language_service.dart';
import '../widgets/forms.dart';
import 'admin.dart';
import 'auth.dart';
import 'lesson.dart';
import 'progress.dart';
import 'profile.dart';
import 'progressive_mantras.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  List scriptures = [];
  String? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final session = context.read<Session>();
      final data = await context.read<Session>().api.get('/api/scriptures');
      try {
        final profile = await session.api.get('/api/profile') as Map;
        final preferred = '${profile['preferred_language'] ?? ''}';
        if (preferred.isNotEmpty) {
          final language = context.read<LanguageService>();
          language.selectContentLanguage(preferred);
          language.select(preferred);
        }
      } catch (_) {
        // A missing optional profile must not block the scripture list.
      }
      if (!mounted) return;
      setState(() {
        scriptures = data as List;
        loading = false;
      });
    } catch (e) {
      setState(() {
        error = e.toString();
        loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<Session>();
    final language = context.watch<LanguageService>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('Choose what to learn'),
        actions: [
          IconButton(
              icon: const Icon(Icons.insights),
              onPressed: () => Navigator.push(context,
                  MaterialPageRoute(builder: (_) => const ProgressPage()))),
          IconButton(
              icon: const Icon(Icons.person),
              tooltip: 'My profile',
              onPressed: () => Navigator.push(context,
                  MaterialPageRoute(builder: (_) => const ProfilePage()))),
          if (session.isAdmin)
            IconButton(
                icon: const Icon(Icons.admin_panel_settings),
                onPressed: () => Navigator.push(context,
                    MaterialPageRoute(builder: (_) => const AdminPage()))),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await session.logout();
              if (!context.mounted) return;
              Navigator.pushAndRemoveUntil(
                  context,
                  MaterialPageRoute(builder: (_) => const WelcomePage()),
                  (_) => false);
            },
          ),
        ],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? Center(child: Text(error!))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.person_outline),
                        title: const Text('Complete your learner profile'),
                        subtitle: const Text(
                            'Add your name, date of birth, phone, Nakshatra, Gotra and preferred language.'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                                builder: (_) => const ProfilePage())),
                      ),
                    ),
                    const Text('Scripture library',
                        style: TextStyle(
                            fontSize: 23, fontWeight: FontWeight.bold)),
                    Card(
                        child: ListTile(
                      leading: const Icon(Icons.record_voice_over),
                      title: Text(language.progressive('title')),
                      subtitle: Text(language.progressive('subtitle')),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                              builder: (_) => const ProgressiveMantrasPage())),
                    )),
                    const SizedBox(height: 8),
                    const Text(
                        'Only Guru-approved published lessons are listed. Empty scriptures are waiting for Guru content.'),
                    const SizedBox(height: 12),
                    ...scriptures.map((item) {
                      final map = item as Map;
                      final count = map['lesson_count'] ?? 0;
                      return Card(
                        child: ListTile(
                          leading: const Icon(Icons.menu_book),
                          title: Text('${map['title']}'),
                          subtitle: Text(count == 0
                              ? 'Content can be added when Guru-approved material is available'
                              : '$count starter lesson${count == 1 ? '' : 's'}'),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () {
                            if (count == 0) {
                              showMessage(context,
                                  'Content will be added when Guru-approved lessons are published.');
                              return;
                            }
                            Navigator.push(
                                context,
                                MaterialPageRoute(
                                    builder: (_) => LessonsPage(
                                        slug: map['slug'].toString(),
                                        title: map['title'].toString())));
                          },
                        ),
                      );
                    }),
                  ],
                ),
    );
  }
}

class LessonsPage extends StatefulWidget {
  const LessonsPage({super.key, required this.slug, required this.title});
  final String slug;
  final String title;
  @override
  State<LessonsPage> createState() => _LessonsPageState();
}

class _LessonsPageState extends State<LessonsPage> {
  List lessons = [];
  String? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await context
          .read<Session>()
          .api
          .get('/api/scriptures/${widget.slug}/lessons');
      await context.read<Session>().logLearningEvent(
          eventType: 'scripture_opened', scriptureSlug: widget.slug);
      if (!mounted) return;
      setState(() {
        lessons = data as List;
        loading = false;
      });
    } catch (e) {
      setState(() {
        error = e.toString();
        loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('${widget.title} lessons')),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? Center(child: Text(error!))
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: lessons.length,
                  itemBuilder: (context, i) {
                    final lesson = lessons[i] as Map;
                    return Card(
                      child: ListTile(
                        leading: CircleAvatar(child: Text('${i + 1}')),
                        title: Text('${lesson['title']}'),
                        subtitle: Text('${lesson['reference']}'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                                builder: (_) => LessonPage(
                                    slug: lesson['slug'].toString()))),
                      ),
                    );
                  },
                ),
    );
  }
}
