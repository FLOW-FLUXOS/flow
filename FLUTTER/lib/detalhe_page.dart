import 'package:flutter/material.dart';
import 'api.dart';
import 'visual.dart';

/// Detalhe de um fluxo: etapas, histórico e botões Aprovar / Retornar.
class DetalhePage extends StatefulWidget {
  final int id;
  const DetalhePage({super.key, required this.id});

  @override
  State<DetalhePage> createState() => _DetalhePageState();
}

class _DetalhePageState extends State<DetalhePage> {
  Map<String, dynamic>? _fluxo;
  bool _carregando = true;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      _fluxo = await Api.fluxo(widget.id);
    } on ApiErro catch (e) {
      _erro = e.mensagem;
    }
    if (mounted) setState(() => _carregando = false);
  }

  // Pergunta um comentário e depois aprova ou retorna.
  Future<void> _mover({required bool aprovar}) async {
    final campoTexto = TextEditingController();
    final confirmou = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: Cores.superficie,
        title: Text(aprovar ? 'Aprovar etapa' : 'Retornar etapa'),
        content: TextField(
          controller: campoTexto,
          maxLines: 3,
          decoration: campo('Comentário (opcional)'),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar')),
          FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: aprovar ? Cores.verde : Cores.vermelho),
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(aprovar ? 'Aprovar' : 'Retornar')),
        ],
      ),
    );
    if (confirmou != true) return;

    final etapaId = _fluxo!['etapa_atual']?['id'];
    try {
      if (aprovar) {
        await Api.aprovar(widget.id, campoTexto.text.trim(), etapaId);
      } else {
        await Api.retornar(widget.id, campoTexto.text.trim(), etapaId);
      }
      if (!mounted) return;
      Navigator.pop(context); // volta para a lista (ela recarrega sozinha)
    } on ApiErro catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.mensagem)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: botaoVoltar(context),
        title: const Text('Detalhe do fluxo'),
      ),
      body: _corpo(),
      bottomNavigationBar: _botoes(),
    );
  }

  Widget _corpo() {
    if (_carregando) return const Center(child: CircularProgressIndicator());
    if (_erro != null) return Center(child: Text(_erro!));

    final f = _fluxo!;
    final etapas = f['etapas'] as List;
    final historico = f['movimentacoes'] as List;
    final finalizado = f['finalizado'] == true;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(f['nome'],
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
        const SizedBox(height: 4),
        Text(
          '${f['modelo']} · ${finalizado ? 'Finalizado' : 'Em andamento'}',
          style: TextStyle(
              color: finalizado ? Cores.verde : Cores.azulClaro,
              fontWeight: FontWeight.w600),
        ),
        linhaIcone('users',
            'Criado por ${f['criado_por']['nome']} em ${formatarData(f['criado_em'])}'),
        const SizedBox(height: 24),
        const Text('Etapas', style: TextStyle(fontSize: 18)),
        const SizedBox(height: 4),
        for (final e in etapas) _etapa(e),
        const SizedBox(height: 24),
        const Text('Histórico', style: TextStyle(fontSize: 18)),
        const SizedBox(height: 4),
        if (historico.isEmpty)
          const Text('Nenhuma movimentação ainda.',
              style: TextStyle(color: Cores.apagado)),
        for (final m in historico) _movimentacao(m),
        const SizedBox(height: 16),
      ],
    );
  }

  // Uma etapa: check verde (feita), relógio azul (atual) ou relógio cinza (pendente).
  Widget _etapa(Map<String, dynamic> e) {
    final status = e['status'];
    final Widget iconeEtapa;
    if (status == 'concluida') {
      iconeEtapa = icone('checkcircle', tamanho: 28, cor: Cores.verde);
    } else if (status == 'atual') {
      iconeEtapa = icone('clock', tamanho: 28, cor: Cores.azulClaro);
    } else {
      iconeEtapa = icone('clock', tamanho: 28, cor: Cores.apagado);
    }
    final setor = e['setor_detalhe']?['nome'] ??
        (e['perfil_aprovador'] == 'administrador' ? 'Administrador' : '-');

    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: iconeEtapa,
      title: Text(e['nome'],
          style: TextStyle(
              fontWeight: status == 'atual' ? FontWeight.bold : FontWeight.normal)),
      subtitle: Text('$setor', style: const TextStyle(color: Cores.apagado)),
      trailing: status == 'atual'
          ? const Text('Atual', style: TextStyle(color: Cores.azulClaro))
          : null,
    );
  }

  Widget _movimentacao(Map<String, dynamic> m) {
    final comentario = (m['comentario'] ?? '').toString();
    return Card(
      color: Cores.superficie,
      shape: formaCartao(),
      margin: const EdgeInsets.only(top: 8),
      child: ListTile(
        title: Text('${m['acao']} · ${m['etapa'] ?? ''}'),
        subtitle: Text(
          '${m['usuario']?['nome'] ?? ''} · ${formatarData(m['data_acao'])}'
          '${comentario.isEmpty ? '' : '\n$comentario'}',
          style: const TextStyle(color: Cores.apagado),
        ),
      ),
    );
  }

  // Os botões só aparecem se a API disser que EU posso aprovar/retornar.
  Widget? _botoes() {
    final f = _fluxo;
    if (f == null || (f['pode_aprovar'] != true && f['pode_retornar'] != true)) {
      return null;
    }
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            if (f['pode_retornar'] == true)
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Cores.vermelho,
                    side: const BorderSide(color: Cores.vermelho),
                    minimumSize: const Size.fromHeight(48),
                  ),
                  onPressed: () => _mover(aprovar: false),
                  icon: icone('back', tamanho: 18, cor: Cores.vermelho),
                  label: const Text('Retornar'),
                ),
              ),
            if (f['pode_retornar'] == true && f['pode_aprovar'] == true)
              const SizedBox(width: 12),
            if (f['pode_aprovar'] == true)
              Expanded(
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(
                    backgroundColor: Cores.verde,
                    minimumSize: const Size.fromHeight(48),
                  ),
                  onPressed: () => _mover(aprovar: true),
                  icon: icone('checkcircle', tamanho: 18, cor: Colors.white),
                  label: const Text('Aprovar'),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
