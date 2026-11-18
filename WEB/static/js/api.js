/*
 * FLOW — cliente das APIs usado por todas as telas do web.
 *
 * Toda informação que aparece na tela vem daqui: o navegador chama a
 * API principal (/api/v1/) e a API de pagamentos (/api/pagamentos/)
 * com o token JWT do usuário, do mesmo jeito que o app Flutter.
 */
const FLOW = (() => {
  const cfg = document.documentElement.dataset;
  const API = cfg.api || "";              // ex.: "" (mesmo endereço, via gateway)
  const PAG = cfg.pagamentos || "";

  const K_ACCESS = "flow.access", K_REFRESH = "flow.refresh", K_USUARIO = "flow.usuario", K_AVISO = "flow.aviso";

  // ---------------- sessão ----------------
  const sessao = {
    get access() { return localStorage.getItem(K_ACCESS); },
    get refresh() { return localStorage.getItem(K_REFRESH); },
    get usuario() {
      try { return JSON.parse(localStorage.getItem(K_USUARIO)) || null; } catch { return null; }
    },
    salvar({ access, refresh, usuario }) {
      if (access) localStorage.setItem(K_ACCESS, access);
      if (refresh) localStorage.setItem(K_REFRESH, refresh);
      if (usuario) localStorage.setItem(K_USUARIO, JSON.stringify(usuario));
    },
    limpar() { [K_ACCESS, K_REFRESH, K_USUARIO].forEach((k) => localStorage.removeItem(k)); },
  };

  class ErroAPI extends Error {
    constructor(status, dados) {
      super(mensagemDeErro(status, dados));
      this.status = status;
      this.dados = dados;
    }
  }

  // Transforma a resposta de erro do Django REST Framework numa frase legível
  function mensagemDeErro(status, dados) {
    if (!dados) return status ? `Erro ${status}` : "Sem conexão com a API.";
    if (typeof dados === "string") return dados;
    if (dados.detail) return Array.isArray(dados.detail) ? dados.detail.join(" ") : dados.detail;
    const partes = [];
    for (const [campo, msgs] of Object.entries(dados)) {
      const texto = Array.isArray(msgs) ? msgs.join(" ") : (typeof msgs === "object" ? JSON.stringify(msgs) : msgs);
      partes.push(campo === "non_field_errors" ? texto : `${campo}: ${texto}`);
    }
    return partes.join(" | ") || `Erro ${status}`;
  }

  let renovando = null;
  async function renovarToken() {
    if (!sessao.refresh) return false;
    if (!renovando) {
      renovando = fetch(`${API}/api/v1/auth/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: sessao.refresh }),
      }).then(async (r) => {
        if (!r.ok) return false;
        sessao.salvar(await r.json());
        return true;
      }).catch(() => false).finally(() => { setTimeout(() => (renovando = null), 0); });
    }
    return renovando;
  }

  // ---------------- requisição ----------------
  async function requisitar(base, caminho, { method = "GET", body, auth = true, tentouRenovar = false } = {}) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && sessao.access) headers.Authorization = `Bearer ${sessao.access}`;

    let resp;
    try {
      resp = await fetch(base + caminho, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
    } catch (e) {
      throw new ErroAPI(0, null);
    }

    if (resp.status === 401 && auth && !tentouRenovar) {
      if (await renovarToken()) return requisitar(base, caminho, { method, body, auth, tentouRenovar: true });
      sessao.limpar();
      irParaLogin();
      throw new ErroAPI(401, { detail: "Sessão expirada. Faça login novamente." });
    }

    const texto = await resp.text();
    let dados = null;
    try { dados = texto ? JSON.parse(texto) : null; } catch { dados = texto; }
    if (!resp.ok) throw new ErroAPI(resp.status, dados);
    return dados;
  }

  const v1 = (caminho, opts) => requisitar(API, `/api/v1${caminho}`, opts);
  const pagamentos = (caminho, opts) => requisitar(PAG, `/api/pagamentos${caminho}`, opts);

  // Listas: pede até 100 itens de uma vez e devolve só o array "results"
  const comPagina = (c) => c + (c.includes("?") ? "&" : "?") + "page_size=100";
  const resultados = (d) => (Array.isArray(d) ? d : d.results);
  const listar = async (caminho) => resultados(await v1(comPagina(caminho)));
  const listarPagamentos = async (caminho) => resultados(await pagamentos(comPagina(caminho)));

  // ---------------- login / logout ----------------
  async function login(username, password) {
    const dados = await v1("/auth/login/", { method: "POST", body: { username, password }, auth: false });
    sessao.salvar(dados);
    return dados.usuario;
  }

  async function logout() {
    try {
      if (sessao.refresh) await v1("/auth/logout/", { method: "POST", body: { refresh: sessao.refresh }, auth: false });
    } catch { /* token já inválido: tudo bem */ }
    sessao.limpar();
    location.href = "/login/";
  }

  async function atualizarUsuario() {
    const usuario = await v1("/auth/me/");
    sessao.salvar({ usuario });
    return usuario;
  }

  function irParaLogin() {
    if (location.pathname !== "/login/") {
      location.href = `/login/?proximo=${encodeURIComponent(location.pathname + location.search)}`;
    }
  }

  // Chamado no início de toda tela protegida
  function exigirLogin({ admin = false } = {}) {
    if (!sessao.access || !sessao.usuario) { irParaLogin(); return false; }
    if (admin && !sessao.usuario.is_admin) {
      avisar("Apenas administradores podem acessar essa área.", "erro");
      location.href = "/";
      return false;
    }
    return true;
  }

  // ---------------- avisos entre telas ----------------
  function avisar(texto, tipo = "ok") { sessionStorage.setItem(K_AVISO, JSON.stringify({ texto, tipo })); }
  function pegarAviso() {
    const a = sessionStorage.getItem(K_AVISO);
    sessionStorage.removeItem(K_AVISO);
    try { return a ? JSON.parse(a) : null; } catch { return null; }
  }

  // ---------------- formatação ----------------
  const data = (iso) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "—");
  const dataHora = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—");
  const dinheiro = (centavos) => (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const perfil = (p) => (p === "administrador" ? "Administrador" : "Colaborador");
  const statusCobranca = { pendente: "Aguardando pagamento", pago: "Pago", expirado: "Expirado", cancelado: "Cancelado", reembolsado: "Reembolsado" };

  return {
    v1, pagamentos, listar, listarPagamentos, login, logout, atualizarUsuario, exigirLogin, avisar, pegarAviso, sessao, ErroAPI,
    fmt: { data, dataHora, dinheiro, perfil, statusCobranca },
  };
})();

// Componente da moldura (menu lateral, contador de notificações, avisos)
function moldura() {
  return {
    usuario: FLOW.sessao.usuario || {},
    naoLidas: 0,
    aviso: FLOW.pegarAviso(),
    async iniciar() {
      this.contar();
      setInterval(() => this.contar(), 30000);
      window.addEventListener("flow:notificacoes", () => this.contar());
    },
    async contar() {
      if (!FLOW.sessao.access) return;
      try { this.naoLidas = (await FLOW.v1("/notificacoes/nao-lidas/")).nao_lidas; } catch { /* sem login */ }
    },
    mostrar(texto, tipo = "ok") { this.aviso = { texto, tipo }; window.scrollTo(0, 0); },
    sair() { FLOW.logout(); },
  };
}

// Atalho para as telas: mostra a mensagem no topo
function avisarNaTela(texto, tipo = "ok") {
  window.dispatchEvent(new CustomEvent("flow:aviso", { detail: { texto, tipo } }));
}
