import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/language_service.dart';
import '../state/session.dart';
import '../widgets/forms.dart';
import 'home.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});
  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  final name = TextEditingController();
  final phone = TextEditingController();
  final rashi = TextEditingController();
  final nakshatra = TextEditingController();
  final gotra = TextEditingController();
  final profession = TextEditingController();
  DateTime? dateOfBirth;
  String gender = '';
  String profileEmail = '';
  String preferredLanguage = 'en';
  bool busy = false;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await context.read<Session>().api.get('/api/profile') as Map;
      name.text = '${data['name'] ?? ''}';
      phone.text = '${data['phone'] ?? ''}';
      rashi.text = '${data['rashi'] ?? ''}';
      nakshatra.text = '${data['nakshatra'] ?? ''}';
      gotra.text = '${data['gotra'] ?? ''}';
      preferredLanguage = '${data['preferred_language'] ?? 'en'}';
      final languages = context.read<LanguageService>();
      languages.selectContentLanguage(preferredLanguage);
      languages.select(preferredLanguage);
      profession.text = '${data['profession'] ?? ''}';
      gender = '${data['gender'] ?? ''}';
      profileEmail = '${data['email'] ?? ''}';
      final rawDob = '${data['date_of_birth'] ?? ''}';
      if (rawDob.isNotEmpty) dateOfBirth = DateTime.tryParse(rawDob);
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> save() async {
    setState(() => busy = true);
    try {
      await context.read<Session>().api.post('/api/profile', body: {
        'name': name.text.trim(),
        'date_of_birth': dateOfBirth == null
            ? ''
            : '${dateOfBirth!.year.toString().padLeft(4, '0')}-${dateOfBirth!.month.toString().padLeft(2, '0')}-${dateOfBirth!.day.toString().padLeft(2, '0')}',
        'gender': gender,
        'phone': phone.text.trim(),
        'rashi': rashi.text.trim(),
        'nakshatra': nakshatra.text.trim(),
        'gotra': gotra.text.trim(),
        'profession': profession.text.trim(),
        'preferred_language': preferredLanguage,
      });
      if (!mounted) return;
      final languages = context.read<LanguageService>();
      languages.selectContentLanguage(preferredLanguage);
      languages.select(preferredLanguage);
      Navigator.pushAndRemoveUntil(context,
          MaterialPageRoute(builder: (_) => const HomePage()), (_) => false);
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Learner profile')),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : FormBody(children: [
              labeledField(name, 'Name'),
              labeledField(phone, 'Phone'),
              Text(
                  'Email: ${profileEmail.isEmpty ? 'Not provided' : profileEmail}'),
              OutlinedButton.icon(
                onPressed: () async {
                  final picked = await showDatePicker(
                      context: context,
                      initialDate: dateOfBirth ?? DateTime(2000),
                      firstDate: DateTime(1900),
                      lastDate: DateTime.now());
                  if (picked != null) setState(() => dateOfBirth = picked);
                },
                icon: const Icon(Icons.calendar_month),
                label: Text(dateOfBirth == null
                    ? 'Select date of birth (optional)'
                    : '${dateOfBirth!.day}/${dateOfBirth!.month}/${dateOfBirth!.year}'),
              ),
              DropdownButtonFormField<String>(
                value: gender.isEmpty ? null : gender,
                decoration:
                    const InputDecoration(labelText: 'Gender (optional)'),
                items: const [
                  'Female',
                  'Male',
                  'Non-binary',
                  'Prefer not to say'
                ]
                    .map((v) => DropdownMenuItem(value: v, child: Text(v)))
                    .toList(),
                onChanged: (v) => setState(() => gender = v ?? ''),
              ),
              labeledField(rashi, 'Rashi (optional)'),
              labeledField(nakshatra, 'Nakshatra (optional)'),
              labeledField(gotra, 'Gotra (optional)'),
              DropdownButtonFormField<String>(
                value: preferredLanguage,
                decoration: const InputDecoration(
                    labelText: 'Preferred shloka language'),
                items: LanguageService.contentLanguages
                    .map((language) => DropdownMenuItem(
                          value: language.code,
                          child: Text(language.name),
                        ))
                    .toList(),
                onChanged: (value) =>
                    setState(() => preferredLanguage = value ?? 'en'),
              ),
              labeledField(profession, 'Profession (optional)'),
              FilledButton(
                  onPressed: busy ? null : save,
                  child: const Text('Save profile')),
              const Text(
                  'Date of birth, gender, Rashi, Nakshatra, Gotra and profession are optional.',
                  style: TextStyle(fontSize: 12)),
            ]),
    );
  }
}
