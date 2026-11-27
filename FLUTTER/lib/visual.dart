import 'package:flutter/material.dart';

/// Cores do site (WEB/static/css/style.css).
class Cores {
  static const fundo = Color(0xFF2D3B49);
  static const superficie = Color(0xFF24303B);
  static const borda = Color(0xFF3C4D5E);
  static const azul = Color(0xFF1D4BBD);
  static const azulClaro = Color(0xFF2F7DF4);
  static const verde = Color(0xFF48B96D);
  static const vermelho = Color(0xFFFF3B3B);
  static const amarelo = Color(0xFFFFC700);
  static const apagado = Color(0xFF9FB3C8);
}

/// Mostra um ícone da pasta assets/img. Se passar [cor], pinta o ícone dessa cor.
Widget icone(String nome, {double tamanho = 22, Color? cor}) {
  return Image.asset(
    'assets/img/$nome.png',
    width: tamanho,
    height: tamanho,
    color: cor,
    colorBlendMode: cor == null ? null : BlendMode.srcIn,
  );
}

/// Linha pequena: ícone + texto (usada nos cartões).
Widget linhaIcone(String nomeIcone, String texto) {
  return Padding(
    padding: const EdgeInsets.only(top: 4),
    child: Row(
      children: [
        icone(nomeIcone, tamanho: 16, cor: Cores.apagado),
        const SizedBox(width: 6),
        Expanded(child: Text(texto, style: const TextStyle(color: Cores.apagado))),
      ],
    ),
  );
}

/// Seta de voltar do site, para a barra de cima.
Widget botaoVoltar(BuildContext context) {
  return IconButton(
    icon: icone('back', tamanho: 26),
    onPressed: () => Navigator.pop(context),
  );
}

/// Campo de texto no estilo do site: fundo escuro e borda azul.
InputDecoration campo(String rotulo) {
  OutlineInputBorder borda(Color c) => OutlineInputBorder(
        borderRadius: BorderRadius.circular(6),
        borderSide: BorderSide(color: c, width: 2),
      );
  return InputDecoration(
    labelText: rotulo,
    filled: true,
    fillColor: const Color(0x66000000),
    labelStyle: const TextStyle(color: Cores.apagado),
    enabledBorder: borda(Cores.azul),
    focusedBorder: borda(Cores.azulClaro),
  );
}

/// Cartão padrão do app.
ShapeBorder formaCartao() => RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(10),
      side: const BorderSide(color: Cores.borda),
    );
