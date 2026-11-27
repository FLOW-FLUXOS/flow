import 'package:flutter/material.dart';
import 'api.dart';
import 'visual.dart';

/// Criar um fluxo novo a partir de um modelo.
class NovoFluxoPage extends StatefulWidget {
  const NovoFluxoPage({super.key});

  @override
  State<NovoFluxoPage> createState() => _NovoFluxoPageState();
}

class _NovoFluxoPageState extends State<NovoFluxoPage> {
  final _nome = TextEditingController();
  final _comentario = TextEditingController();
  List<dynamic> _modelos = [];
  int? _modeloId;
  bool _carregando = true;
  bool _salvando = false;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregarModelos();
  }

  Future<void> _carregarModelos() async {
    try {
      _modelos = await Api.modelos();
    } on ApiErro catch (e) {
      _erro = e.mensagem;
    }
    if (mounted) setState(() => _carregando = false);
  }

  Future<void> _salvar() async {
    if (_modeloId == null || _nome.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Escolha um modelo e informe o nome.')));
      return;
    }
    setState(() => _salvando = true);
    try {
      await Api.criarFluxo(_modeloId!, _nome.text.trim(), _comentario.text.trim());
      if (!mounted) return;
      Navigator.pop(context);
    } on ApiErro catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.mensagem)));
      setState(() => _salvando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: botaoVoltar(context),
        title: const Text('Novo fluxo'),
      ),
      body: _carregando
          ? const Center(child: CircularProgressIndicator())
          : _erro != null
              ? Center(child: Text(_erro!))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    DropdownButtonFormField<int>(
                      isExpanded: true,
                      dropdownColor: Cores.superficie,
                      decoration: campo('Modelo de fluxo'),
                      items: [
                        for (final m in _modelos)
                          DropdownMenuItem<int>(value: m['id'], child: Text(m['nome'])),
                      ],
                      onChanged: (v) => setState(() => _modeloId = v),
                    ),
                    const SizedBox(height: 16),
                    TextField(controller: _nome, decoration: campo('Nome do fluxo')),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _comentario,
                      maxLines: 3,
                      decoration: campo('Comentário (opcional)'),
                    ),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                      onPressed: _salvando ? null : _salvar,
                      icon: icone('add', tamanho: 20, cor: Colors.white),
                      label: Text(_salvando ? 'Criando...' : 'Criar fluxo'),
                    ),
                  ],
                ),
    );
  }
}
