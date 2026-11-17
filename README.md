# PI-4-SEMESTRE

📌 README.md – FLOW | Fluxo de Aprovação Sequencial
🧩 Sobre o Projeto

O FLOW é um sistema desenvolvido para tornar mais ágil, transparente e confiável o processo de aprovações internas dentro de empresas. Ele elimina falhas comuns de controles manuais, oferecendo um fluxo sequencial digitalizado e rastreável, com etapas hierárquicas e gestão completa.

Projeto desenvolvido para o Projeto Integrador – 4° Semestre
Disciplina: Laboratório de Desenvolvimento Web
Professor: Fernando Bryan Frizzarin

👥 Integrantes

Davi Samuel Schwartz – RA: 2901392413041

João Paulo Mussarelli Carossine – RA: 2901392413021

Júlio Ryan Marsola – RA: 2901392413014

🎯 Missão

O FLOW foi criado para resolver:

Atrasos em processos de aprovação

Falta de rastreabilidade

Retrabalho

Falhas por processos manuais e descentralizados

✅ O sistema oferece:

Fluxo sequencial automático

Histórico completo de cada ação

Interface simples e intuitiva

Redução de papel (ESG)

Controle administrativo centralizado

🧠 Como Funciona

O usuário cria um modelo padrão de fluxo

O fluxo é gerado automaticamente seguindo a hierarquia

Aprovadores recebem cada etapa na ordem correta

Cada ação é registrada (aprovar, rejeitar, ajustes)

Administradores veem todos os fluxos (ativos e concluídos)

Ao final, o processo é encerrado e arquivado

📌 Escopo do Projeto
🔧 Requisitos Funcionais

CRUD de usuários

CRUD de fluxos padrão

Movimentação de fluxos

Sistema de assinaturas (Freemium + Premium)

Rastreabilidade completa

🛠 Requisitos Não Funcionais – Técnicos

Linguagem: Python

Framework: Django

Banco de dados: PostgreSQL (SQLite em desenvolvimento)

Arquitetura: API REST (Django REST Framework + JWT) + backoffice MVT

Mensageria: RabbitMQ + Celery

Sistema de pagamento: AbacatePay

💼 Requisitos Não Funcionais – Não Técnicos

Disponibilidade mínima: 99%

Segurança com controle de sessões

Interface intuitiva e simples

🏗 Arquitetura e Tecnologias

Backend: Python + Django + Django REST Framework (API em /api/v1/, documentação Swagger em /api/v1/docs/)

Mobile: Flutter consumindo a API (JWT)

Sistema web: Django Templates com todas as funções (colaboradores aprovam pelo web; gestão só para administradores)

Banco de Dados: PostgreSQL

Mensageria: RabbitMQ (broker) + Celery (notificações de fluxo) + eventos de pagamento com e-mail por status

Microserviço de Pagamentos: API separada com banco próprio (pasta PAGAMENTOS), atrás de um gateway nginx

Multi-empresa (SaaS): cada empresa só vê os próprios dados

📘 Arquitetura, eventos e endpoints: [API.md](API.md)

💼 Plano de Negócios
🎯 Nicho de Mercado

Empresas que precisam formalizar e digitalizar processos internos de aprovação.

👥 Público-Alvo

Pequenas, médias e grandes empresas

Escritórios

Startups

Gestores e coordenadores

💰 Monetização
Plano	Preço	Limite
Freemium	Gratuito	1 usuário
Prata	R$ 89,90/mês	até 5 usuários
Ouro	R$ 119,90/mês	até 10 usuários
Diamante	Sob demanda	empresas maiores
🚀 Expansões Futuras

Integração com ERPs

Versão mobile

Dashboards avançados

🧑‍💼 Cliente Real

O projeto é desenvolvido em parceria com a CHAMPION Projetos e Equipamentos Industriais, empresa do setor metalúrgico que atua no desenvolvimento, fabricação e montagem de equipamentos industriais para o segmento de cerâmicas.

🔗 Aderência ao Cliente

O FLOW auxilia a empresa através de:

Digitalização completa de aprovações

Rastreabilidade

Redução de tempo e burocracia

Padronização e segurança interna

✔ Critérios de Aceitação e Status

Todos os requisitos funcionais e não funcionais foram entregues e validados:

CRUDs funcionando

Sistema de assinaturas

Rastreabilidade completa

Autenticação com sessões

Interface clara e intuitiva

🗓 Cronograma

(Baseado na documentação. Se quiser, posso gerar a tabela visualizada.)

🖼 Apresentação do Sistema (Telas)
🔐 Login

Tela inicial para autenticação do usuário.

📂 Dashboard + Sidebar

Menu lateral para navegação rápida entre os módulos.

🔄 Fluxos em Andamento

Listagem de fluxos ativos

Botões: Detalhes, Excluir, Adicionar Novo

Pesquisa rápida

Aba para fluxos finalizados

📊 Detalhes do Fluxo

Visualização completa das etapas:

Datas

Setores envolvidos

Ações registradas

🔁 Movimentação entre Etapas

Esferas representam etapas

“Check” para etapas concluídas

Avançar e Retornar entre etapas

➕ Criar Novo Fluxo

Criação rápida utilizando modelos prontos.

🧩 Modelos de Fluxo

CRUD e visualização de modelos reutilizáveis.

👤 Usuários

CRUD completo de usuários.

🏭 Setores

CRUD de setores.

💳 Assinaturas

Página para gerenciamento dos planos Freemium/Premium.

🧷 Instalação e Execução

Com Docker (recomendado): `cp .env.example .env && docker compose up --build`. Detalhes em [API.md](API.md).

Sem Docker:
# Clone o repositório
git clone https://github.com/usuario/projeto-flow.git
cd projeto-flow

# Crie o ambiente virtual
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Instale as dependências
pip install -r requirements.txt

# Rode as migrações
cd FLUXO_APROVACAO
python manage.py migrate

# Execute o servidor
python manage.py runserver


Acesse em:
http://127.0.0.1:8000/

📜 Licença

Este projeto é acadêmico e desenvolvido para fins educacionais.
Caso deseje, posso gerar uma licença MIT, GPL ou outra.

🤝 Contribuição

Pull requests são bem-vindos!
Para grandes mudanças, abra uma issue primeiro para discussão.

📧 Contato

Caso precise de suporte ou melhorias, entre em contato com os desenvolvedores ou abra uma issue no repositório.
