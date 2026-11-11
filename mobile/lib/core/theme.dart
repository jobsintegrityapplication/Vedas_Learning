import 'package:flutter/material.dart';

ThemeData buildTheme() {
  const seed = Color(0xFF8B4A20);
  return ThemeData(
    colorScheme: ColorScheme.fromSeed(seedColor: seed),
    useMaterial3: true,
    visualDensity: VisualDensity.adaptivePlatformDensity,
    inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
  );
}
