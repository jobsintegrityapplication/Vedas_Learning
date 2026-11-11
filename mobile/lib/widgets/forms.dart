import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class FormBody extends StatelessWidget {
  const FormBody({super.key, required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: children.map((w) => Padding(padding: const EdgeInsets.only(bottom: 14), child: w)).toList(),
      ),
    );
  }
}

Widget labeledField(
  TextEditingController controller,
  String label, {
  bool obscure = false,
  TextInputType? type,
  List<TextInputFormatter>? formatters,
  ValueChanged<String>? onChanged,
}) {
  return TextField(
    controller: controller,
    obscureText: obscure,
    keyboardType: type,
    inputFormatters: formatters,
    onChanged: onChanged,
    decoration: InputDecoration(labelText: label),
  );
}

void showMessage(BuildContext context, String text) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
}
