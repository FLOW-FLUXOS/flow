import 'package:flutter/material.dart';
import 'api.dart';
import 'detalhe_page.dart';
import 'visual.dart';

class NotificacoesPage extends StatefulWidget {
  const NotificacoesPage({super.key});

  @override
  State<NotificacoesPage> createState() => _NotificacoesPageState();
}

class _NotificacoesPageState extends State<NotificacoesPage> {
  List<dynamic> _itens = [];
  bool _carregando = true;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      _itens = await Api.notificacoes();
    } on ApiErro catch (e) {
      _erro = e.mensagem;
    }
    if (mounted) setState(() => _carregando = false);
  }

  Future<void> _marcarTodas() async {
    await Api.marcarTodasLidas();
    _carregar();
  }

  Future<void> _abrir(Map<String, dynamic> n) async {
    if (n['lida'] != true) await Api.marcarLida(n['id']);
    if (!mounted) return;
    if (n['fluxo_instancia'] != null) {
      await Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => DetalhePage(id: n['fluxo_instancia'])),
      );
    }
    _carregar();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: botaoVoltar(context),
        title: const Text('Notificações'),
        actions: [
          IconButton(
            tooltip: 'Marcar todas como lidas',
            icon: const Icon(Icons.done_all),
            onPressed: _marcarTodas,
          ),
        ],
      ),
      body: _carregando
          ? const Center(child: CircularProgressIndicator())
          : _erro != null
              ? Center(child: Text(_erro!))
              : _itens.isEmpty
                  ? const Center(child: Text('Você não tem notificações.'))
                  : ListView.builder(
                      itemCount: _itens.length,
                      itemBuilder: (context, i) {
                        final n = _itens[i];
                        final lida = n['lida'] == true;
                        return ListTile(
                          leading: Icon(
                            lida ? Icons.notifications_none : Icons.notifications_active,
                            color: lida ? Cores.apagado : Cores.azulClaro,
                          ),
                          title: Text(n['titulo'],
                              style: TextStyle(
                                  fontWeight: lida ? FontWeight.normal : FontWeight.bold)),
                          tileColor: lida ? null : Cores.azul.withOpacity(0.25),
                          subtitle: Text('${n['mensagem']}\n${formatarData(n['criado_em'])}'),
                          isThreeLine: true,
                          onTap: () => _abrir(n),
                        );
                      },
                    ),
    );
  }
}
