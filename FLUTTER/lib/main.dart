import 'package:flutter/material.dart';
import 'login_page.dart';
import 'visual.dart';

void main() {
  runApp(const FlowApp());
}

class FlowApp extends StatelessWidget {
  const FlowApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FLOW',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: Cores.fundo,
        colorScheme: const ColorScheme.dark(
          primary: Cores.azulClaro,
          surface: Cores.superficie,
        ),
        // Barra de cima igual à lateral do site: fundo escuro + linha azul embaixo
        appBarTheme: const AppBarTheme(
          backgroundColor: Cores.superficie,
          scrolledUnderElevation: 0,
          shape: Border(bottom: BorderSide(color: Cores.azul, width: 1)),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: Cores.azul,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          ),
        ),
      ),
      home: const LoginPage(),
    );
  }
}
