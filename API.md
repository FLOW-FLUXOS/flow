# FLOW — Arquitetura e APIs

## Visão geral

```
                         ┌──────────────── Gateway (nginx) :8000 ────────────────┐
 App Flutter / Web ────▶ │  /api/pagamentos/*  ──▶  API de Pagamentos (:8001)    │
                         │  todo o resto       ──▶  API principal + Web (:8000)  │
                         └───────────────────────────────────────────────────────┘

 API principal (monolito)                         API de Pagamentos (microserviço)
 ├ fluxos, usuários, setores, modelos             ├ cobranças, status, histórico
 ├ sistema web (todas as funções)                 ├ AbacatePay ou simulador
 ├ banco: Postgres "flow"                         ├ banco: Postgres "pagamentos"
 └ worker Celery: notificações de fluxo           └ publica eventos no RabbitMQ
                    ▲                                         │
                    │      RabbitMQ — exchange "pagamentos"   │
                    │      (topic, routing pagamento.<status>)▼
   consumidor "assinaturas"  ◀── pagamento.pago / reembolsado ┤
   (ativa ou cancela o plano)                                 │
                                   pagamento.* ──▶ consumidor "pagamentos-email"
                                                  (1 e-mail por status → Mailpit)
```

- **Dois serviços, dois bancos.** O monolito não acessa o banco de pagamentos, e o contrário também não acontece. Eles se falam só por **HTTP com JWT** e por **eventos no RabbitMQ**.
- **JWT compartilhado.** A API principal emite o token com `empresa_id`, `perfil`, `email` e `empresa_nome`. A API de Pagamentos confere a assinatura com a mesma `JWT_SIGNING_KEY` e lê esses dados direto do token, sem precisar de tabela de usuários.
- **Mensageria.** Tem duas trocas de mensagens no sistema:
  1. **Fluxos:** aprovar, retornar, criar ou finalizar um fluxo gera um evento, e o worker Celery cria as notificações de quem precisa agir.
  2. **Pagamentos:** cada mudança de status publica `pagamento.<status>` na exchange `pagamentos`. Cada fila recebe só o que interessa a ela.

### Eventos de pagamento

| Status | Routing key | Quem recebe | Efeito |
|---|---|---|---|
| Aguardando pagamento | `pagamento.pendente` | e-mail | "Pedido aguardando pagamento" + link PIX |
| Pago | `pagamento.pago` | e-mail + assinaturas | "Pagamento confirmado" + plano ativado por 30 dias |
| Expirado | `pagamento.expirado` | e-mail | "O link expirou" |
| Cancelado | `pagamento.cancelado` | e-mail | "Pagamento cancelado" |
| Reembolsado | `pagamento.reembolsado` | e-mail + assinaturas | "Reembolso" + plano cancelado (volta ao Freemium) |

Transições permitidas: `pendente → pago | expirado | cancelado` e `pago → reembolsado`. Todo evento fica registrado no histórico da cobrança. Webhook repetido é ignorado.

## Subindo

```
copy .env.example .env           (Linux/Mac: cp .env.example .env)
docker compose up --build
docker compose exec web python manage.py popular_demo
docker compose exec web python manage.py createsuperuser
```

| Endereço | O que é |
|---|---|
| http://localhost:8000 | Sistema web |
| http://localhost:8000/api/v1/docs/ | Swagger da API principal |
| http://localhost:8000/api/pagamentos/docs/ | Swagger da API de Pagamentos |
| http://localhost:8025 | **Mailpit**: os e-mails de pagamento aparecem aqui |
| http://localhost:15672 | Painel do RabbitMQ (flow / flow): exchanges, filas, mensagens |
| http://localhost:8000/admin/ | Admin da plataforma |

Usuários do `popular_demo` (senha `Flow@2026`): `demo.admin`, `demo.engenharia`, `demo.financeiro`.

| Container | Função |
|---|---|
| `gateway` | nginx, ponto de entrada único |
| `web` | API principal + sistema web |
| `worker` | Celery: notificações de fluxo |
| `assinaturas` | Consome `pagamento.pago` e `pagamento.reembolsado` |
| `pagamentos` | API de Pagamentos |
| `pagamentos-email` | Consome `pagamento.*` e envia os e-mails |
| `db`, `db_pagamentos` | Um Postgres para cada serviço |
| `rabbitmq`, `mailpit` | Broker e caixa de e-mails de teste |

### Demonstração do pagamento (sem AbacatePay)

1. Entre no web como `demo.admin` → **Planos** → **Assinar Prata**.
2. Abre o **simulador**. Clique em **Pagar**, **Cancelar**, **Expirar** ou, depois de pago, **Reembolsar**.
3. Veja os e-mails chegando no **Mailpit**, as mensagens passando no painel do **RabbitMQ** e o plano mudando na tela de Planos.

Com `ABACATEPAY_API_KEY` no `.env`, o simulador é desligado e o link vira um PIX de verdade. O webhook do AbacatePay vai em `/api/pagamentos/webhook/abacatepay/?secret=<WEBHOOK_SECRET>`.

## Sistema web: quem vê o quê

| Função | Colaborador | Admin |
|---|---|---|
| Criar fluxo, acompanhar, "Minhas aprovações" | ✔ | ✔ |
| Aprovar ou retornar (etapa do seu setor) | ✔ | ✔ (qualquer etapa) |
| Notificações (sininho) | ✔ | ✔ |
| Excluir fluxo | | ✔ |
| Usuários, setores, modelos de fluxo | | ✔ |
| Planos e pagamentos | | ✔ |

## API principal: `/api/v1/`

Login: `POST auth/login/` com `{"username", "password"}`, que devolve `access`, `refresh` e `usuario`. Envie `Authorization: Bearer <access>` em toda chamada. Quando der 401, use `POST auth/refresh/` com `{"refresh"}`. **O mesmo token vale na API de Pagamentos.**

| Método | Rota | Descrição |
|---|---|---|
| POST | `auth/login/`, `auth/refresh/`, `auth/logout/` | Sessão |
| POST | `auth/registro/` | Cria empresa + admin (Freemium) |
| GET/PATCH | `auth/me/` · POST `auth/trocar-senha/` | Perfil |
| GET | `fluxos/pendentes/` | **Aguardando a minha aprovação** |
| GET | `fluxos/?status=em_andamento\|finalizado&minhas=true` | Lista |
| POST | `fluxos/` | `{"modelo": 1, "nome": "...", "comentario": ""}` |
| GET | `fluxos/{id}/` | Etapas, histórico, `pode_aprovar`, `pode_retornar` |
| POST | `fluxos/{id}/avancar/` · `fluxos/{id}/retornar/` | `{"comentario": "", "etapa_id": 12}` |
| GET | `notificacoes/` · `notificacoes/nao-lidas/` | Notificações |
| POST | `notificacoes/{id}/ler/` · `notificacoes/ler-todas/` | Marcar lidas |
| CRUD | `setores/`, `usuarios/`, `modelos/` | Leitura: todos · escrita: admin |
| GET/PATCH | `empresa/` · GET `assinatura/` | Empresa e plano atual |

## API de Pagamentos: `/api/pagamentos/`

| Método | Rota | Descrição |
|---|---|---|
| GET | `planos/` | Planos e preços (público) |
| GET | `cobrancas/` | Cobranças da minha empresa |
| POST | `cobrancas/` | `{"plano": "prata"}` (admin). Devolve `checkout_url` para abrir no navegador |
| GET | `cobrancas/{id}/` | Detalhe + histórico de status |
| POST | `webhook/abacatepay/?secret=` | Webhook do gateway de pagamento |

## Erros (as duas APIs)

| Código | Quando |
|---|---|
| 400 | Regra de negócio: `{"detail": "..."}` |
| 401 | Token ausente, expirado ou assinado com outra chave |
| 403 | Sem permissão (etapa de outro setor, colaborador tentando contratar plano) |
| 404 | Não existe ou é de outra empresa |

## Sem Docker

```
pip install -r requirements.txt
cd FLUXO_APROVACAO && python manage.py migrate && python manage.py runserver 8000
cd PAGAMENTOS && python manage.py migrate && python manage.py runserver 8001
```

Sem RabbitMQ configurado, os eventos de fluxo rodam na hora e os de pagamento vão para um broker em memória (os e-mails não saem). Para ver a mensageria funcionando, use o Docker.

Testes: `python manage.py test api` (FLUXO_APROVACAO, 27 testes) e `python manage.py test cobrancas` (PAGAMENTOS, 13 testes).

## Flutter

- Base URL única: `http://10.0.2.2:8000` no emulador Android (é o gateway).
- Plano: `POST /api/pagamentos/cobrancas/` e abrir o `checkout_url` com `url_launcher`.
- Notificações: polling de `/api/v1/notificacoes/nao-lidas/`.
