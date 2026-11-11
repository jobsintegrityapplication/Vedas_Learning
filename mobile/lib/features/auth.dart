import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../data/api_client.dart';
import '../core/url_cleaner.dart';
import '../state/session.dart';
import '../widgets/forms.dart';
import 'home.dart';

class WelcomePage extends StatelessWidget {
  const WelcomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Icon(Icons.self_improvement,
                  size: 76, color: Theme.of(context).colorScheme.primary),
              const SizedBox(height: 18),
              const Text('Vedas Learning',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold)),
              const Text('Listen • Learn • Recite • Improve',
                  textAlign: TextAlign.center),
              const SizedBox(height: 32),
              FilledButton(
                  onPressed: () => Navigator.push(context,
                      MaterialPageRoute(builder: (_) => const RegisterPage())),
                  child: const Text('Create account')),
              OutlinedButton(
                  onPressed: () => Navigator.push(context,
                      MaterialPageRoute(builder: (_) => const LoginPage())),
                  child: const Text('Login')),
              TextButton(
                  onPressed: () => Navigator.push(context,
                      MaterialPageRoute(builder: (_) => const ForgotPage())),
                  child: const Text('Forgot password')),
            ],
          ),
        ),
      ),
    );
  }
}

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});
  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final email = TextEditingController();
  final phone = TextEditingController();
  final password = TextEditingController();
  final confirmPassword = TextEditingController();
  bool busy = false;

  @override
  void dispose() {
    email.dispose();
    phone.dispose();
    password.dispose();
    confirmPassword.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    final emailValue = email.text.trim();
    final phoneValue = phone.text.trim();
    final isEmail = RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(emailValue);
    if (!isEmail) {
      showMessage(context, 'Enter a valid email address.');
      return;
    }
    final phoneDigits = phoneValue.replaceAll(RegExp(r'\D'), '');
    if (phoneDigits.length < 10 || phoneDigits.length > 15) {
      showMessage(context, 'Enter a valid phone number with 10 to 15 digits.');
      return;
    }
    if (password.text.length < 8) {
      showMessage(context, 'Password must be at least 8 characters.');
      return;
    }
    if (password.text != confirmPassword.text) {
      showMessage(context, 'Passwords do not match.');
      return;
    }
    setState(() => busy = true);
    try {
      await context.read<Session>().registerDirect(
            email: emailValue,
            phone: phoneValue,
            password: password.text,
            confirmPassword: confirmPassword.text,
          );
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => LoginPage(
            email: emailValue,
            info: 'Account created. Log in with your email or mobile number.',
          ),
        ),
      );
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create account')),
      body: FormBody(children: [
        const Text(
            'Create your account with an email address, phone number, and password. Email verification is temporarily turned off.'),
        labeledField(email, 'Email address', type: TextInputType.emailAddress),
        labeledField(phone, 'Phone number', type: TextInputType.phone),
        labeledField(password, 'Password', obscure: true),
        labeledField(confirmPassword, 'Confirm password', obscure: true),
        FilledButton(
            onPressed: busy ? null : submit,
            child: Text(busy ? 'Creating account…' : 'Create account')),
      ]),
    );
  }
}

class VerificationSentPage extends StatefulWidget {
  const VerificationSentPage({super.key, required this.email});
  final String email;
  @override
  State<VerificationSentPage> createState() => _VerificationSentPageState();
}

class _VerificationSentPageState extends State<VerificationSentPage> {
  bool busy = false;

  Future<void> resend() async {
    setState(() => busy = true);
    try {
      await context.read<Session>().startSignup(widget.email);
      if (mounted)
        showMessage(context,
            'A new verification link was sent to ' + widget.email + '.');
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Check your email')),
        body: FormBody(children: [
          const Icon(Icons.mark_email_read_outlined, size: 54),
          Text('We sent a verification link to ' +
              widget.email +
              '. Open it to verify your address and set your password. The link expires in 24 hours.'),
          FilledButton(
              onPressed: busy ? null : resend,
              child: Text(busy ? 'Sending…' : 'Resend verification link')),
          TextButton(
            onPressed: () => Navigator.pushAndRemoveUntil(
                context,
                MaterialPageRoute(
                    builder: (_) => LoginPage(email: widget.email)),
                (_) => false),
            child: const Text('Go to login'),
          ),
        ]),
      );
}

class CompleteSignupPage extends StatefulWidget {
  const CompleteSignupPage(
      {super.key, required this.email, required this.verificationToken});
  final String email;
  final String verificationToken;
  @override
  State<CompleteSignupPage> createState() => _CompleteSignupPageState();
}

class _CompleteSignupPageState extends State<CompleteSignupPage> {
  final fullName = TextEditingController();
  final phone = TextEditingController();
  final password = TextEditingController();
  final confirm = TextEditingController();
  bool checkingLink = true;
  bool linkValid = false;
  String? linkError;
  bool busy = false;

  @override
  void initState() {
    super.initState();
    unawaited(_verifyLink());
  }

  Future<void> _verifyLink() async {
    try {
      await context
          .read<Session>()
          .verifySignupLink(widget.email, widget.verificationToken);
      if (mounted)
        setState(() {
          checkingLink = false;
          linkValid = true;
        });
    } catch (e) {
      if (mounted)
        setState(() {
          checkingLink = false;
          linkError = e.toString();
        });
    }
  }

  Future<void> submit() async {
    if (fullName.text.trim().isEmpty) {
      showMessage(context, 'Enter your full name.');
      return;
    }
    if (password.text.length < 8) {
      showMessage(context, 'Password must be at least 8 characters.');
      return;
    }
    if (password.text != confirm.text) {
      showMessage(context, 'Passwords do not match.');
      return;
    }
    setState(() => busy = true);
    try {
      await context.read<Session>().completeSignup(
            email: widget.email,
            verificationToken: widget.verificationToken,
            fullName: fullName.text.trim(),
            phone: phone.text.trim(),
            password: password.text,
          );
      if (!mounted) return;
      clearSignupTokenFromUrl();
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
    if (checkingLink) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!linkValid) {
      return Scaffold(
        appBar: AppBar(title: const Text('Verification link')),
        body: FormBody(children: [
          Text(linkError ?? 'This verification link is invalid.'),
          FilledButton(
            onPressed: () => Navigator.pushReplacement(
                context,
                MaterialPageRoute(
                    builder: (_) => VerificationSentPage(email: widget.email))),
            child: const Text('Request a new link'),
          ),
        ]),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Set your password')),
      body: FormBody(children: [
        Text('Verified email: ' + widget.email),
        const Text(
            'Set a password to finish creating your account. You can sign in with this email or the phone number you add here.'),
        labeledField(fullName, 'Full name'),
        labeledField(phone, 'Phone number (optional)',
            type: TextInputType.phone),
        labeledField(password, 'Password', obscure: true),
        labeledField(confirm, 'Confirm password', obscure: true),
        FilledButton(
            onPressed: busy ? null : submit,
            child: Text(busy ? 'Saving…' : 'Set password and continue')),
      ]),
    );
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, this.email, this.info});
  final String? email;
  final String? info;
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  late final TextEditingController identifier;
  final password = TextEditingController();
  bool busy = false;

  @override
  void initState() {
    super.initState();
    identifier = TextEditingController(text: widget.email ?? '');
  }

  Future<void> login() async {
    setState(() => busy = true);
    try {
      await context
          .read<Session>()
          .login(identifier.text.trim(), password.text);
      if (!mounted) return;
      Navigator.pushAndRemoveUntil(context,
          MaterialPageRoute(builder: (_) => const HomePage()), (_) => false);
    } on ApiException catch (e) {
      if (mounted) showMessage(context, e.toString());
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Login')),
      body: FormBody(children: [
        if (widget.info != null)
          Text(widget.info!,
              style: TextStyle(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.w600)),
        labeledField(identifier, 'Email or mobile number',
            type: TextInputType.emailAddress),
        labeledField(password, 'Password', obscure: true),
        FilledButton(
            onPressed: busy ? null : login, child: const Text('Login')),
      ]),
    );
  }
}

class ForgotPage extends StatefulWidget {
  const ForgotPage({super.key});
  @override
  State<ForgotPage> createState() => _ForgotPageState();
}

class _ForgotPageState extends State<ForgotPage> {
  final email = TextEditingController();
  final otp = TextEditingController();
  final password = TextEditingController();
  bool sent = false;
  bool busy = false;

  Future<void> send() async {
    setState(() => busy = true);
    try {
      await context.read<Session>().forgot(email.text.trim());
      setState(() => sent = true);
      if (mounted)
        showMessage(context,
            'If an account exists, a reset code was sent to ${email.text.trim()}.');
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> reset() async {
    setState(() => busy = true);
    try {
      await context
          .read<Session>()
          .reset(email.text.trim(), otp.text.trim(), password.text);
      if (!mounted) return;
      Navigator.pushAndRemoveUntil(
        context,
        MaterialPageRoute(
            builder: (_) => LoginPage(
                email: email.text.trim(),
                info: 'Password updated. Please log in.')),
        (_) => false,
      );
    } catch (e) {
      if (mounted) showMessage(context, e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reset password')),
      body: FormBody(children: [
        labeledField(email, 'Email address', type: TextInputType.emailAddress),
        if (!sent)
          FilledButton(
              onPressed: busy ? null : send,
              child: const Text('Send reset code')),
        if (sent) ...[
          Text('Enter the 6-digit code sent to ${email.text.trim()}.'),
          labeledField(otp, 'Reset code',
              type: TextInputType.number,
              formatters: [FilteringTextInputFormatter.digitsOnly]),
          labeledField(password, 'New password', obscure: true),
          FilledButton(
              onPressed: busy ? null : reset,
              child: const Text('Update password')),
        ],
      ]),
    );
  }
}
