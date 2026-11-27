import 'package:flutter/material.dart';
import 'api.dart';
import 'pendentes_page.dart';
import 'visual.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _usuario = TextEditingController();
  final _senha = TextEditingController();
  bool _carregando = false;
  String? _erro;

  Future<void> _entrar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      await Api.login(_usuario.text.trim(), _senha.text);
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const PendentesPage()),
      );
    } on ApiErro catch (e) {
      setState(() => _erro = e.mensagem);
    }
    if (mounted) setState(() => _carregando = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SingleChildScrollView(
        child: Column(
          children: [
            // Ondas azuis no topo, como na tela de login do site
            Image.asset(
              'assets/img/waves.png',
              width: double.infinity,
              height: 170,
              fit: BoxFit.cover,
            ),
            Image.asset('assets/img/logo.png', height: 170),
            const Text('Faça seu Login', style: TextStyle(fontSize: 24)),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 24, 24, 24),
              child: Column(
                children: [
                  TextField(
                    controller: _usuario,
                    decoration: campo('Usuário'),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _senha,
                    obscureText: true,
                    decoration: campo('Senha'),
                  ),
                  if (_erro != null) ...[
                    const SizedBox(height: 12),
                    Text(_erro!, style: const TextStyle(color: Cores.vermelho)),
                  ],
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: FilledButton(
                      onPressed: _carregando ? null : _entrar,
                      child: Text(_carregando ? 'Entrando...' : 'Entrar'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
