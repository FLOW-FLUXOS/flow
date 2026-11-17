"""
Cria o Kanban do FLOW no GitHub Projects da organização FLOW-FLUXOS.

O que o script faz:
  1. Cria (ou reaproveita) o projeto "FLOW - Roadmap" na organização
  2. Cria os campos "Área" (API / Mobile / Backoffice / Infra & Docs) e "Prioridade"
  3. Cria as etiquetas area:* no repositório
  4. Cria uma issue por atividade (com descrição + checklist), adiciona ao
     projeto e preenche Status / Área / Prioridade
  Pode rodar de novo sem duplicar: issues com o mesmo título são reaproveitadas.

Pré-requisitos (uma vez só):
  winget install GitHub.cli          (ou https://cli.github.com)
  gh auth login
  gh auth refresh -s project,read:org

Rodar (na raiz do repositório):
  python scripts/criar_kanban.py --dry-run     # só mostra o que faria
  python scripts/criar_kanban.py
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

ORG = "FLOW-FLUXOS"
REPO = "FLOW-FLUXOS/flow"
TITULO_PROJETO = "FLOW - Roadmap"

AREAS = {  # nome no campo -> (etiqueta, cor)
    "API": ("area:api", "1D76DB"),
    "Mobile": ("area:mobile", "0E8A16"),
    "Backoffice": ("area:backoffice", "D93F0B"),
    "Infra & Docs": ("area:infra-docs", "5319E7"),
}
PRIORIDADES = ["Alta", "Média", "Baixa"]

# status: "Todo" | "In Progress" | "Done"
CARDS = [
    # ======================= API =======================
    {"area": "API", "status": "Done", "prioridade": "Alta",
     "titulo": "[API] Multi-empresa (SaaS) — Empresa como tenant",
     "corpo": """Transformar o sistema em multi-empresa: todo dado pertence a uma `Empresa` e cada usuário só enxerga a própria.

- [x] Model `Empresa` + FK em usuários, setores, modelos, instâncias e assinaturas
- [x] Migração que move os dados antigos para "Empresa Padrão"
- [x] Filtro por empresa em todos os endpoints e telas
- [x] Limite de usuários por plano (Freemium 1, Prata 5, Ouro 10, Diamante ilimitado)"""},
    {"area": "API", "status": "Done", "prioridade": "Alta",
     "titulo": "[API] Autenticação JWT (login, refresh, logout, registro)",
     "corpo": """Login do app via JWT (SimpleJWT).

- [x] `POST /api/v1/auth/login/` devolve access, refresh e dados do usuário
- [x] Refresh com rotação e blacklist no logout
- [x] `auth/registro/` cria empresa + admin no plano Freemium
- [x] `auth/me/` e `auth/trocar-senha/`"""},
    {"area": "API", "status": "Done", "prioridade": "Alta",
     "titulo": "[API] Endpoints de fluxos (criar, listar, pendentes, avançar, retornar)",
     "corpo": """Endpoints que o app usa no dia a dia.

- [x] `GET fluxos/pendentes/`: o que espera a minha aprovação
- [x] `GET fluxos/` com filtros `status`, `minhas`, `modelo` e busca
- [x] `POST fluxos/`: criar a partir de um modelo
- [x] `GET fluxos/{id}/`: etapas, histórico, `pode_aprovar`/`pode_retornar`
- [x] `POST fluxos/{id}/avancar/` e `retornar/` com comentário"""},
    {"area": "API", "status": "Done", "prioridade": "Alta",
     "titulo": "[API] Regras de aprovação por setor e perfil",
     "corpo": """Garantir que só quem deve aprove cada etapa (regra única em `SISTEMA/services.py`).

- [x] Usuário padrão só aprova etapas do próprio setor
- [x] Etapas "administrador" só admins aprovam
- [x] Só a etapa atual pode ser movimentada; não retorna da primeira
- [x] Testes automatizados cobrindo as regras"""},
    {"area": "API", "status": "Done", "prioridade": "Alta",
     "titulo": "[API] Mensageria com RabbitMQ + Celery",
     "corpo": """Eventos de fluxo publicados no broker e consumidos pelo worker.

- [x] Eventos criado/avançado/retornado/finalizado publicados após o commit
- [x] Filas `fluxo.eventos` e `notificacoes.push`
- [x] Worker cria `Notificacao` para aprovadores e criador
- [x] Endpoints de notificações (lista, contador, marcar lida)"""},
    {"area": "API", "status": "Todo", "prioridade": "Alta",
     "titulo": "[API] Validar a stack Docker localmente",
     "corpo": """Subir `docker compose up --build` e conferir tudo funcionando junto.

- [ ] Docker Desktop + WSL2 instalados em todas as máquinas do grupo
- [ ] web, worker, db e rabbitmq sobem sem erro
- [ ] `popular_demo` cria os dados de teste
- [ ] Aprovar um fluxo pelo Swagger e ver a notificação gerada pelo worker
- [ ] Ver as filas no painel do RabbitMQ (localhost:15672)"""},
    {"area": "API", "status": "Todo", "prioridade": "Média",
     "titulo": "[API] Push notifications com Firebase (FCM)",
     "corpo": """O worker já envia push se houver credencial. Falta configurar.

- [ ] Criar projeto no Firebase e gerar a conta de serviço (JSON)
- [ ] Configurar `FIREBASE_CREDENTIALS` no `.env` e montar o arquivo no container
- [ ] Testar envio para um dispositivo registrado em `dispositivos/`"""},
    {"area": "API", "status": "Todo", "prioridade": "Média",
     "titulo": "[API] Expiração automática de assinaturas (Celery Beat)",
     "corpo": """Hoje a validade é checada na leitura; falta uma rotina diária.

- [ ] Adicionar Celery Beat ao docker-compose
- [ ] Tarefa diária que marca como inativas as assinaturas vencidas
- [ ] Notificar o admin da empresa 3 dias antes de vencer"""},
    {"area": "API", "status": "Todo", "prioridade": "Média",
     "titulo": "[API] Anexos nos fluxos",
     "corpo": """Permitir anexar documentos (PDF, imagem) a um fluxo ou a uma movimentação.

- [ ] Model `Anexo` (arquivo, fluxo, etapa, usuário, data)
- [ ] Upload multipart em `fluxos/{id}/anexos/` com limite de tamanho e tipos permitidos
- [ ] Volume no Docker para os arquivos (`MEDIA_ROOT`)
- [ ] Listar anexos no detalhe do fluxo"""},
    {"area": "API", "status": "Todo", "prioridade": "Baixa",
     "titulo": "[API] Recuperação de senha por e-mail",
     "corpo": """- [ ] Configurar envio de e-mail (SMTP no `.env`)
- [ ] `auth/esqueci-senha/` envia link/código
- [ ] `auth/redefinir-senha/` valida o token e troca a senha
- [ ] Enviar o e-mail pelo worker Celery (não bloquear a requisição)"""},
    {"area": "API", "status": "Todo", "prioridade": "Média",
     "titulo": "[API] Endpoint de indicadores (dashboard)",
     "corpo": """Dados para o dashboard do backoffice e do app.

- [ ] Fluxos por status e por modelo
- [ ] Tempo médio por etapa e por fluxo
- [ ] Etapas com mais retornos (gargalos)
- [ ] Filtro por período"""},
    {"area": "API", "status": "Todo", "prioridade": "Média",
     "titulo": "[API] CI no GitHub Actions rodando os testes",
     "corpo": """- [ ] Workflow que roda `python manage.py test` a cada push/PR
- [ ] Rodar contra Postgres (service container)
- [ ] Badge de status no README"""},

    # ======================= MOBILE =======================
    {"area": "Mobile", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Mobile] Setup do projeto Flutter",
     "corpo": """Estrutura base do app.

- [ ] Criar o projeto e definir a arquitetura de pastas (ex.: Clean Architecture por feature)
- [ ] Escolher a gerência de estado (ex.: Riverpod) e o client HTTP (ex.: dio)
- [ ] Configurar a URL base por ambiente (emulador: `http://10.0.2.2:8000`)
- [ ] Tema com as cores e o logo do FLOW"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Mobile] Models e client da API a partir do OpenAPI",
     "corpo": """- [ ] Baixar o schema em `/api/v1/schema/`
- [ ] Gerar o client (openapi-generator `dart-dio`) ou escrever os models manualmente
- [ ] Tratar a paginação `{count, next, previous, results}`
- [ ] Mapear erros 400/401/403/404 para mensagens amigáveis"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Mobile] Login e sessão (JWT + refresh automático)",
     "corpo": """- [ ] Tela de login (usuário e senha)
- [ ] Guardar access/refresh com armazenamento seguro (ex.: flutter_secure_storage)
- [ ] Interceptor: em 401, chamar `auth/refresh/` e repetir a requisição
- [ ] Manter o usuário logado ao reabrir o app
- [ ] Logout chamando `auth/logout/`"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Mobile] Tela inicial: fluxos pendentes",
     "corpo": """Home do app: o que está esperando a minha aprovação.

- [ ] Lista de `fluxos/pendentes/` com nome, modelo, etapa atual e progresso
- [ ] Puxar para atualizar e paginação infinita
- [ ] Estado vazio ("Nada pendente")
- [ ] Sininho com contador de `notificacoes/nao-lidas/`"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Mobile] Detalhe do fluxo (timeline e histórico)",
     "corpo": """- [ ] Timeline das etapas com status concluída / atual / pendente
- [ ] Setor e perfil aprovador de cada etapa
- [ ] Histórico de movimentações (quem, quando, ação, comentário)
- [ ] Barra de progresso"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Mobile] Aprovar e retornar fluxo",
     "corpo": """- [ ] Botões Aprovar/Retornar visíveis conforme `pode_aprovar` / `pode_retornar`
- [ ] Modal com comentário (obrigatório no retorno, por decisão de UX)
- [ ] Enviar `etapa_id` para evitar aprovar uma etapa que já mudou
- [ ] Feedback de sucesso e atualizar a tela"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Mobile] Criar fluxo a partir de um modelo",
     "corpo": """- [ ] Listar modelos (`modelos/`) mostrando as etapas
- [ ] Formulário: modelo + nome + comentário inicial
- [ ] `POST fluxos/` e abrir o detalhe do fluxo criado"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Média",
     "titulo": "[Mobile] Lista de fluxos (andamento / finalizados / meus)",
     "corpo": """- [ ] Abas Em andamento / Finalizados (`?status=`)
- [ ] Filtro "Criados por mim" (`?minhas=true`)
- [ ] Busca por nome (`?search=`)"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Média",
     "titulo": "[Mobile] Central de notificações",
     "corpo": """- [ ] Lista de notificações com destaque nas não lidas
- [ ] Tocar abre o fluxo e marca como lida (`notificacoes/{id}/ler/`)
- [ ] "Marcar todas como lidas"
- [ ] Atualizar o contador por polling enquanto o push não estiver pronto"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Média",
     "titulo": "[Mobile] Push notifications (firebase_messaging)",
     "corpo": """Depende do card de FCM da API.

- [ ] Configurar o Firebase no app (Android)
- [ ] Após o login, registrar o token em `POST dispositivos/`
- [ ] Ao tocar no push, abrir o fluxo (`fluxo_instancia_id` vem no payload)
- [ ] Remover o token no logout"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Baixa",
     "titulo": "[Mobile] Perfil do usuário",
     "corpo": """- [ ] Mostrar nome, e-mail, setor, empresa e plano
- [ ] Editar nome/e-mail (`PATCH auth/me/`)
- [ ] Trocar senha"""},
    {"area": "Mobile", "status": "Todo", "prioridade": "Média",
     "titulo": "[Mobile] Build do APK para apresentação",
     "corpo": """- [ ] Ícone e splash com o logo do FLOW
- [ ] Apontar para a URL da API de demonstração
- [ ] Gerar o APK release e testar num celular físico"""},

    # ======================= BACKOFFICE =======================
    {"area": "Backoffice", "status": "Done", "prioridade": "Alta",
     "titulo": "[Backoffice] Restringir o web a administradores e por empresa",
     "corpo": """- [x] Login do web só para administradores (padrão é direcionado ao app)
- [x] Todas as telas filtram pela empresa do usuário
- [x] Movimentação usa a mesma regra da API
- [x] Django Admin configurado para o dono da plataforma"""},
    {"area": "Backoffice", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Backoffice] Dashboard inicial com indicadores",
     "corpo": """Trocar a home atual (só boas-vindas) por um painel. Depende do endpoint de indicadores.

- [ ] Cards: fluxos em andamento, finalizados no mês, pendentes há mais de X dias
- [ ] Gráfico de fluxos por status/modelo
- [ ] Lista dos gargalos (etapas com mais retornos)"""},
    {"area": "Backoffice", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Backoffice] Editar modelos de fluxo",
     "corpo": """Hoje só dá para criar e excluir.

- [ ] Tela de edição do modelo (nome, descrição)
- [ ] Adicionar/remover/reordenar etapas
- [ ] Editar setor e perfil aprovador de cada etapa
- [ ] Avisar que fluxos já em andamento não mudam"""},
    {"area": "Backoffice", "status": "Todo", "prioridade": "Alta",
     "titulo": "[Backoffice] Tela de dados da empresa",
     "corpo": """Necessária para o checkout enviar os dados do cliente ao AbacatePay.

- [ ] Editar nome, CNPJ, e-mail e telefone da empresa
- [ ] Validar o formato do CNPJ e do telefone
- [ ] Link na sidebar"""},
    {"area": "Backoffice", "status": "Todo", "prioridade": "Média",
     "titulo": "[Backoffice] Tela de cadastro de nova empresa",
     "corpo": """Versão web do `auth/registro/`.

- [ ] Formulário: empresa, CNPJ, usuário admin, e-mail, senha
- [ ] Link "Criar conta" na tela de login
- [ ] Logar automaticamente após o cadastro"""},
    {"area": "Backoffice", "status": "Todo", "prioridade": "Média",
     "titulo": "[Backoffice] Melhorar a tela de usuários",
     "corpo": """- [ ] Mostrar setor, perfil e se está ativo
- [ ] Mostrar "X de Y usuários do plano" e bloquear o botão no limite
- [ ] Redefinir a senha de um usuário"""},
    {"area": "Backoffice", "status": "Todo", "prioridade": "Baixa",
     "titulo": "[Backoffice] Histórico de pagamentos na tela de planos",
     "corpo": """- [ ] Listar os pagamentos da empresa (data, plano, valor, método)
- [ ] Mostrar a data de vencimento do plano atual"""},
    {"area": "Backoffice", "status": "Todo", "prioridade": "Baixa",
     "titulo": "[Backoffice] Ajustes de layout e responsividade",
     "corpo": """- [ ] `sidebar.html` referencia `css/sidebar.css`, que não existe (criar ou remover)
- [ ] Trocar caminhos `\\static\\img\\...` por `{% static %}`
- [ ] Padronizar mensagens de sucesso/erro em todas as telas
- [ ] Revisar a responsividade em telas menores"""},

    # ======================= INFRA & DOCS =======================
    {"area": "Infra & Docs", "status": "Todo", "prioridade": "Média",
     "titulo": "[Docs] Atualizar a documentação do PI",
     "corpo": """- [ ] Diagrama de casos de uso com o app mobile
- [ ] Diagrama de arquitetura (API, worker, RabbitMQ, Postgres, app, backoffice)
- [ ] DER atualizado com Empresa, Notificacao e DispositivoPush
- [ ] Revisar o README e o API.md"""},
    {"area": "Infra & Docs", "status": "Todo", "prioridade": "Média",
     "titulo": "[Infra] Ambiente de demonstração",
     "corpo": """- [ ] Decidir onde roda a demo (máquina local + ngrok ou VPS)
- [ ] `.env` de demo com `DJANGO_DEBUG=False` e uma `SECRET_KEY` própria
- [ ] Webhook do AbacatePay apontando para a URL pública
- [ ] Roteiro da apresentação: criar fluxo no app → aprovar → notificação"""},
]


def gh(args, dry=False, parse_json=False):
    print("  $ gh " + " ".join(a if " " not in a else f'"{a}"' for a in args))
    if dry:
        return {} if parse_json else ""
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stderr.strip())
        raise SystemExit(f"Falhou: gh {' '.join(args[:3])}...")
    return json.loads(r.stdout or "{}") if parse_json else r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="só mostra os comandos")
    dry = ap.parse_args().dry_run

    print(f"\n== Projeto '{TITULO_PROJETO}' em {ORG}")
    projetos = gh(["project", "list", "--owner", ORG, "--format", "json", "--limit", "100"], dry, True)
    proj = next((p for p in projetos.get("projects", []) if p["title"] == TITULO_PROJETO), None)
    if not proj:
        proj = gh(["project", "create", "--owner", ORG, "--title", TITULO_PROJETO, "--format", "json"], dry, True)
        if not dry:
            gh(["project", "link", str(proj["number"]), "--owner", ORG, "--repo", REPO])
    num, proj_id = str(proj.get("number", "N")), proj.get("id", "PROJ_ID")

    print("\n== Campos")
    campos = {f["name"]: f for f in gh(["project", "field-list", num, "--owner", ORG, "--format", "json"], dry, True).get("fields", [])}
    for nome, opcoes in (("Área", list(AREAS)), ("Prioridade", PRIORIDADES)):
        if nome not in campos:
            gh(["project", "field-create", num, "--owner", ORG, "--name", nome,
                "--data-type", "SINGLE_SELECT", "--single-select-options", ",".join(opcoes)], dry)
    campos = {f["name"]: f for f in gh(["project", "field-list", num, "--owner", ORG, "--format", "json"], dry, True).get("fields", [])}

    def opcao(campo, valor):
        if dry:
            return ("FIELD", "OPT")
        f = campos[campo]
        opt = next((o for o in f.get("options", []) if o["name"].lower() == valor.lower()), None)
        if not opt:
            raise SystemExit(f"Opção '{valor}' não encontrada no campo {campo}: {[o['name'] for o in f.get('options', [])]}")
        return f["id"], opt["id"]

    print("\n== Etiquetas")
    for etiqueta, cor in AREAS.values():
        gh(["label", "create", etiqueta, "--repo", REPO, "--color", cor, "--force"], dry)

    print("\n== Issues")
    existentes = {} if dry else {
        i["title"]: i["url"] for i in json.loads(gh(["issue", "list", "--repo", REPO, "--state", "all",
                                                     "--limit", "500", "--json", "title,url"]) or "[]")}
    for card in CARDS:
        print(f"\n- {card['titulo']}")
        url = existentes.get(card["titulo"])
        if not url:
            with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
                tmp.write(card["corpo"])
            try:
                url = gh(["issue", "create", "--repo", REPO, "--title", card["titulo"],
                          "--body-file", tmp.name, "--label", AREAS[card["area"]][0]], dry) or "URL"
            finally:
                os.unlink(tmp.name)
            if card["status"] == "Done" and not dry:
                gh(["issue", "close", url, "--reason", "completed"])
        item = gh(["project", "item-add", num, "--owner", ORG, "--url", url, "--format", "json"], dry, True)
        item_id = item.get("id", "ITEM_ID")
        for campo, valor in (("Status", card["status"]), ("Área", card["area"]), ("Prioridade", card["prioridade"])):
            fid, oid = opcao(campo, valor)
            gh(["project", "item-edit", "--id", item_id, "--project-id", proj_id,
                "--field-id", fid, "--single-select-option-id", oid], dry)

    print(f"\nPronto! {len(CARDS)} cards. Abra: https://github.com/orgs/{ORG}/projects/{num}")
    print("Para ver como Kanban: '+ New view' -> Board (agrupa por Status).")


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
