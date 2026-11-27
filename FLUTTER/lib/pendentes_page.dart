import 'package:flutter/material.dart';
import 'api.dart';
import 'detalhe_page.dart';
import 'login_page.dart';
import 'notificacoes_page.dart';
import 'novo_fluxo_page.dart';
import 'visual.dart';

/// Tela principal: fluxos que estão esperando a MINHA aprovação.
class PendentesPage extends StatefulWidget {
  const PendentesPage({super.key});

  @override
  State<PendentesPage> createState() => _PendentesPageState();
}

class _PendentesPageState extends State<PendentesPage> {
  List<dynamic> _fluxos = [];
  int _naoLidas = 0;
  bool _carregando = true;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      _fluxos = await Api.pendentes();
      _naoLidas = await Api.naoLidas();
    } on ApiErro catch (e) {
      _erro = e.mensagem;
    }
    if (mounted) setState(() => _carregando = false);
  }

  // Abre uma tela e, quando ela fechar, recarrega a lista.
  Future<void> _abrir(Widget tela) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => tela));
    _carregar();
  }

  String _nomeUsuario() {
    final primeiro = (Api.usuario?['first_name'] ?? '').toString();
    return primeiro.isNotEmpty ? primeiro : (Api.usuario?['username'] ?? '').toString();
  }

  void _sair() {
    Api.sair();
    Navigator.pushReplacement(
        context, MaterialPageRoute(builder: (_) => const LoginPage()));
  }

  @override
  Widget build(BuildContext context) {
    final admin = Api.usuario?['is_admin'] == true;
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            icone('flow', tamanho: 30),
            const SizedBox(width: 10),
            Flexible(
              child: Text('Olá, ${_nomeUsuario()}', overflow: TextOverflow.ellipsis),
            ),
            if (admin) ...[
              const SizedBox(width: 8),
              icone('crown', tamanho: 20), // coroa = administrador
            ],
          ],
        ),
        actions: [
          IconButton(
            icon: Badge(
              isLabelVisible: _naoLidas > 0,
              label: Text('$_naoLidas'),
              child: const Icon(Icons.notifications_outlined),
            ),
            onPressed: () => _abrir(const NotificacoesPage()),
          ),
          IconButton(
            tooltip: 'Sair',
            icon: icone('logout', tamanho: 24),
            onPressed: _sair,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: Cores.azul,
        foregroundColor: Colors.white,
        onPressed: () => _abrir(const NovoFluxoPage()),
        icon: icone('add', tamanho: 24),
        label: const Text('Novo fluxo'),
      ),
      body: _corpo(),
    );
  }

  Widget _corpo() {
    if (_carregando) return const Center(child: CircularProgressIndicator());
    if (_erro != null) return Center(child: Text(_erro!));
    if (_fluxos.isEmpty) {
      return const Center(child: Text('Nenhum fluxo aguardando sua aprovação.'));
    }
    return RefreshIndicator(
      onRefresh: _carregar,
      child: ListView.builder(
        padding: const EdgeInsets.only(top: 8, bottom: 90),
        itemCount: _fluxos.length,
        itemBuilder: (context, i) => _cartao(_fluxos[i]),
      ),
    );
  }

  Widget _cartao(Map<String, dynamic> f) {
    final etapa = f['etapa_atual']?['nome'] ?? '-';
    final setor = f['etapa_atual']?['setor'];
    final concluidas = ((f['progresso']?['concluidas']) ?? 0) as num;
    final total = ((f['progresso']?['total']) ?? 0) as num;
    final fracao = total > 0 ? concluidas / total : 0.0;

    return Card(
      color: Cores.superficie,
      shape: formaCartao(),
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: () => _abrir(DetalhePage(id: f['id'])),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(f['nome'],
                        style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
                    Text('${f['modelo']}',
                        style: const TextStyle(color: Cores.apagado)),
                    const SizedBox(height: 8),
                    linhaIcone('clock', 'Etapa: $etapa'),
                    if (setor != null) linhaIcone('department', '$setor'),
                    const SizedBox(height: 10),
                    LinearProgressIndicator(
                      value: fracao.toDouble(),
                      color: Cores.azulClaro,
                      backgroundColor: Cores.borda,
                    ),
                    const SizedBox(height: 4),
                    Text('$concluidas de $total etapas concluídas',
                        style: const TextStyle(color: Cores.apagado, fontSize: 12)),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              icone('eye', tamanho: 28), // olho azul = ver detalhes
            ],
          ),
        ),
      ),
    );
  }
}
