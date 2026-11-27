import 'dart:convert';
import 'package:http/http.dart' as http;

// Endereço da API. No emulador Android, 10.0.2.2 significa "o localhost do meu PC".
// (O gateway do Docker responde na porta 8000.)
const String baseUrl = 'http://10.0.2.2:8000/api/v1';

/// Erro com uma mensagem pronta para mostrar ao usuário.
class ApiErro implements Exception {
  final String mensagem;
  ApiErro(this.mensagem);

  @override
  String toString() => mensagem;
}

/// Tudo o que o app pede para a API fica nesta classe.
class Api {
  static String? token; // token JWT guardado na memória
  static Map<String, dynamic>? usuario; // dados de quem fez login

  // ---------- função base: faz a chamada e trata os erros ----------
  static Future<dynamic> _chamar(
    String metodo,
    String caminho, {
    Map<String, dynamic>? corpo,
    bool comToken = true,
  }) async {
    final url = Uri.parse('$baseUrl$caminho');
    final headers = {'Content-Type': 'application/json'};
    if (comToken && token != null) headers['Authorization'] = 'Bearer $token';

    http.Response? resposta;
    try {
      if (metodo == 'GET') {
        resposta = await http.get(url, headers: headers);
      } else {
        resposta = await http.post(url, headers: headers, body: jsonEncode(corpo ?? {}));
      }
    } catch (_) {
      throw ApiErro('Não foi possível conectar à API. O Docker está rodando?');
    }
    final res = resposta;

    final texto = utf8.decode(res.bodyBytes);
    final dados = texto.isEmpty ? null : jsonDecode(texto);

    if (res.statusCode >= 200 && res.statusCode < 300) return dados;

    if (res.statusCode == 401 && comToken) {
      throw ApiErro('Sessão expirada. Saia e entre novamente.');
    }
    if (dados is Map && dados['detail'] != null) {
      throw ApiErro(dados['detail'].toString());
    }
    throw ApiErro('Erro ${res.statusCode} ao falar com a API.');
  }

  // ---------- login ----------
  static Future<void> login(String username, String senha) async {
    try {
      final dados = await _chamar('POST', '/auth/login/',
          corpo: {'username': username, 'password': senha}, comToken: false);
      token = dados['access'];
      usuario = dados['usuario'];
    } on ApiErro catch (e) {
      if (e.mensagem.contains('conectar')) rethrow;
      throw ApiErro('Usuário ou senha inválidos.');
    }
  }

  static void sair() {
    token = null;
    usuario = null;
  }

  // ---------- fluxos ----------
  static Future<List<dynamic>> pendentes() async {
    final dados = await _chamar('GET', '/fluxos/pendentes/?page_size=50');
    return dados['results'];
  }

  static Future<Map<String, dynamic>> fluxo(int id) async {
    return await _chamar('GET', '/fluxos/$id/');
  }

  static Future<void> aprovar(int id, String comentario, int? etapaId) async {
    await _chamar('POST', '/fluxos/$id/avancar/',
        corpo: {'comentario': comentario, if (etapaId != null) 'etapa_id': etapaId});
  }

  static Future<void> retornar(int id, String comentario, int? etapaId) async {
    await _chamar('POST', '/fluxos/$id/retornar/',
        corpo: {'comentario': comentario, if (etapaId != null) 'etapa_id': etapaId});
  }

  static Future<List<dynamic>> modelos() async {
    final dados = await _chamar('GET', '/modelos/?page_size=100');
    return dados['results'];
  }

  static Future<void> criarFluxo(int modeloId, String nome, String comentario) async {
    await _chamar('POST', '/fluxos/',
        corpo: {'modelo': modeloId, 'nome': nome, 'comentario': comentario});
  }

  // ---------- notificações ----------
  static Future<List<dynamic>> notificacoes() async {
    final dados = await _chamar('GET', '/notificacoes/?page_size=50');
    return dados['results'];
  }

  static Future<int> naoLidas() async {
    final dados = await _chamar('GET', '/notificacoes/nao-lidas/');
    return dados['nao_lidas'];
  }

  static Future<void> marcarLida(int id) async {
    await _chamar('POST', '/notificacoes/$id/ler/');
  }

  static Future<void> marcarTodasLidas() async {
    await _chamar('POST', '/notificacoes/ler-todas/');
  }
}

/// Transforma "2026-11-22T10:30:00-03:00" em "22/11/2026 10:30".
String formatarData(dynamic texto) {
  final d = DateTime.tryParse(texto?.toString() ?? '')?.toLocal();
  if (d == null) return '';
  String dois(int n) => n.toString().padLeft(2, '0');
  return '${dois(d.day)}/${dois(d.month)}/${d.year} ${dois(d.hour)}:${dois(d.minute)}';
}
