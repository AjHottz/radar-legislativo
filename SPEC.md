# SPEC: Arquitetura e Especificação Técnica - Radar Legislativo

> **Projeto:** Fase 1 (T02) - Projeto Integrador: Radar Legislativo (Bússola Pública)
> **Versão:** 1.0.0
> **Referência de Negócio:** [PRD.md](./PRD.md)

---

## 1. Arquitetura do Pipeline (Ponta a Ponta)

O sistema segue uma arquitetura de pipeline **ELT/ETL modular em Python**, com persistência intermediária em disco (camada Raw) para resiliência, carga dimensional em **PostgreSQL na nuvem**, enriquecimento semântico via **OpenAI API** e orquestração automatizada via **n8n**.

```text
+-------------------------------------------------------------------------+
| 1. FONTE EXTERNA: API Dados Abertos Camara dos Deputados (REST v2)      |
|    /partidos | /deputados | /proposicoes | /votacoes | /despesas        |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| 2. EXTRACAO RESILIENTE (Python + requests)                              |
|    - Paginacao via while (ate 100 itens/pagina) + try/except + retry    |
|    - Persistencia obrigatoria em data/raw/YYYY-MM-DD/*.json             |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| 3. TRANSFORMACAO & QUALIDADE (Python + Pandas)                          |
|    - Normalizacao (json_normalize) + deduplicacao por ID                |
|    - Validacoes: nao-nulos, range de datas, valores monetarios >= 0     |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| 4. DATA WAREHOUSE EM NUVEM (PostgreSQL - Supabase / pgvector)           |
|    - Dimensoes: dim_partidos, dim_deputados                             |
|    - Fatos: fato_proposicoes, fato_votacoes, fato_despesas              |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| 5. CAMADA DE IA (OpenAI API + Piloto de Custo com 10 registros)         |
|    - Caminho A: text-embedding-3-small + Similaridade de Cosseno        |
|    - Caminho B: Resumo executivo (max 3 linhas) via gpt-4o-mini         |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| 6. AUTOMACAO & ENTREGA (n8n)                                            |
|    - Cron diario 06h00 (ingestao incremental)                           |
|    - Alerta imediato (Telegram) para tema critico + Digest semanal      |
+-------------------------------------------------------------------------+
```

---

## 2. Stack Tecnológica Definida

| Camada | Tecnologia | Justificativa |
|---|---|---|
| **Linguagem e Runtime** | Python 3.11+ (`.venv` isolada) | Padrão de mercado em Engenharia de Dados e compatível com todas as libs exigidas |
| **Ingestão HTTP** | `requests` | Controle explícito de paginação, headers, status codes, timeouts e retentativas |
| **Transformação e QA** | `pandas`, `numpy` | Manipulação tabular de JSONs aninhados, filtragem vetorial e deduplicação rápida |
| **Persistência Relacional** | `SQLAlchemy`, `psycopg2-binary` | Conexão padronizada com PostgreSQL e carga segura com transações/upsert |
| **Banco de Dados (Nuvem)** | PostgreSQL no **Supabase** (com `pgvector`) | Gratuito, hospedado na nuvem para vitrine de portfólio, SQL Editor visual e `pgvector` nativo |
| **Inteligência Artificial** | `openai` (`text-embedding-3-small` e `gpt-4o-mini`) | Baixíssimo custo por token, alta qualidade em PT-BR e aderência direta aos requisitos |
| **Cálculo Vetorial** | `numpy` (ou `scikit-learn` / `pgvector`) | Cálculo exato de similaridade de cosseno sem sobrecarga de infraestrutura |
| **Orquestração e Alertas** | **n8n** (Docker local ou Cloud) | Integração nativa com PostgreSQL/Supabase, Telegram, E-mail e agendamento Cron |
| **Configuração e Segurança** | `python-dotenv`, `.gitignore`, `.env.example` | Isolamento rigoroso de segredos fora do Git |

---

## 3. Análise de Decisões Arquiteturais (Prós e Contras)

### Decisão 1: Hospedagem PostgreSQL (Supabase vs. Neon/Railway vs. Local)
- **Escolha:** **Supabase**.
- **Prós:** Plano gratuito generoso, banco acessível publicamente na nuvem (fácil demonstração para recrutadores e conexão direta do n8n), interface web (Table Editor/SQL Editor) e extensão `pgvector` pré-habilitada.
- **Contras:** Projetos gratuitos podem pausar após inatividade prolongada; requer atenção com RLS (Row Level Security) ou connection string segura (pooler vs. direta) para escrita via Python.

### Decisão 2: Estratégia da Camada de IA (Caminho A vs. Caminho A + B)
- **Escolha:** **Caminho A (Obrigatório) + Caminho B (Complementar controlado por custo)**.
- **Prós:** Embeddings (`text-embedding-3-small`) padronizam a classificação temática com determinismo matemático e custo praticamente irrisório; somar o resumo de 3 linhas (`gpt-4o-mini`) apenas para proposições filtradas ou dentro do orçamento transforma o alerta no Telegram e o digest semanal em produto executivo pronto para leitura.
- **Contras:** Executar LLM generativo em milhares de proposições irrelevantes eleva custo e latência; mitigado pelo piloto obrigatório de 10 itens e restrição de escopo à janela de 30 dias.

### Decisão 3: Integração Python + n8n
- **Escolha:** Pipeline Python modular acionado por CLI/script + n8n conectado diretamente ao PostgreSQL (Supabase) para consultas, alertas e disparo de rotina.
- **Prós:** Separação limpa entre processamento pesado em Python (requests/Pandas) e orquestração/notificações visuais no n8n.
- **Contras:** Se o n8n rodar em container/Cloud separado da máquina local, não conseguirá chamar scripts Python locais diretamente via `Execute Command` sem expor um endpoint HTTP (FastAPI/webhook) ou usar container unificado. Essa topologia deve ser decidida antes da Onda 5.

---

## 4. Contrato da Fonte de Dados (API Câmara v2)

- **Base URL:** `https://dadosabertos.camara.leg.br/api/v2`
- **Documentação Swagger:** `https://dadosabertos.camara.leg.br/swagger/api.html`
- **Headers padrão:** `Accept: application/json`

### Endpoints Previstos
1. `GET /partidos` (itens por página: até 100)
2. `GET /deputados` (listagem ativa + `/deputados/{id}` se necessário detalhamento)
3. `GET /deputados/{id}/despesas` (atenção: endpoint por deputado; requer controle de concorrência/rate limit e filtragem de ano/mês para os 30 dias do desafio)
4. `GET /proposicoes` (parâmetros `dataApresentacaoInicio`, `dataApresentacaoFim`, `itens=100`, paginação por `links` / `pagina`)
5. `GET /votacoes` (parâmetros `dataInicio`, `dataFim`, `itens=100`, além de votos se aplicável na exploração da Etapa 1)

> **Regra de Validação:** Os nomes exatos de campos JSON e tipos retornados devem ser inspecionados e validados na **Etapa 1 (Exploração)** antes de congelar o DDL final. Nunca assumir ou inventar campos sem inspecionar o retorno real da API.

---

## 5. Especificação Técnica por Etapa

### Etapa 1: Exploração (`notebooks/01_exploracao_api.ipynb` ou `src/explore.py`)
- Testar conectividade e latência dos 5 grupos de endpoints.
- Inspecionar estrutura de `dados` e `links` (paginação `next`).
- Definir o dicionário de campos selecionados e o mapeamento de chaves estrangeiras.

### Etapa 2: Extração Resiliente (`src/extract.py`)
- Implementar cliente HTTP com:
  - Sessão `requests.Session()` reutilizável.
  - Loop `while` seguindo o link `rel="next"` ou incrementando `pagina` até retorno vazio.
  - `timeout=30`, `try/except requests.RequestException` e backoff simples entre tentativas.
- Salvar arquivos brutos em `data/raw/<entidade>/<data_execucao>.json`.
- Parâmetro configurável de janela (`--days 7` para validação inicial, `--days 30` para carga oficial, `--days 1` ou `--days 2` para incremental diário).

### Etapa 3: Transformação, Qualidade e Modelagem Dimensional (`src/transform.py` & `src/load.py`)

#### Regras de Qualidade (Pandas)
- Descartar ou logar em quarentena registros sem chave primária (`id`).
- Padronizar datas em ISO-8601 (`YYYY-MM-DD` / timestamp UTC) e rejeitar datas futuras inválidas ou nulas críticas.
- Garantir `valor_documento >= 0` e `valor_liquido >= 0` em despesas (`df[df['valorLiquido'] < 0]` como verificação explícita).
- Deduplicar DataFrames por chave única antes da carga (`drop_duplicates`).

#### Modelo Dimensional Conceitual (Star Schema no PostgreSQL)

> Nota: Os atributos abaixo representam a estrutura alvo mínima; ajustes finos de nomes/tipos serão confirmados após a Etapa 1. Todo SQL segue o padrão de **leading commas**.

```sql
-- Habilitar extensao vetorial (nativa no Supabase)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS dim_partidos (
    id_partido INTEGER PRIMARY KEY
    , sigla VARCHAR(20) NOT NULL
    , nome VARCHAR(255) NOT NULL
    , uri TEXT
    , atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dim_deputados (
    id_deputado INTEGER PRIMARY KEY
    , nome VARCHAR(255) NOT NULL
    , sigla_partido VARCHAR(20)
    , sigla_uf CHAR(2)
    , email VARCHAR(255)
    , url_foto TEXT
    , id_legislatura INTEGER
    , atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fato_proposicoes (
    id_proposicao BIGINT PRIMARY KEY
    , sigla_tipo VARCHAR(20) NOT NULL
    , numero INTEGER
    , ano INTEGER
    , ementa TEXT NOT NULL
    , data_apresentacao DATE
    , uri TEXT
    , tema_ia VARCHAR(100)
    , similaridade_tema NUMERIC(6, 4)
    , resumo_executivo TEXT
    , embedding VECTOR(1536)
    , processado_ia_em TIMESTAMPTZ
    , atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fato_votacoes (
    id_votacao VARCHAR(100) PRIMARY KEY
    , id_proposicao BIGINT REFERENCES fato_proposicoes(id_proposicao)
    , data_hora_registro TIMESTAMPTZ
    , sigla_orgao VARCHAR(50)
    , descricao TEXT
    , aprovacao SMALLINT
    , atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fato_despesas (
    id_despesa BIGSERIAL PRIMARY KEY
    , id_deputado INTEGER NOT NULL REFERENCES dim_deputados(id_deputado)
    , ano INTEGER NOT NULL
    , mes INTEGER NOT NULL
    , tipo_despesa VARCHAR(255)
    , nome_fornecedor VARCHAR(255)
    , cnpj_cpf_fornecedor VARCHAR(20)
    , cod_documento BIGINT
    , num_documento VARCHAR(100)
    , data_documento DATE
    , valor_documento NUMERIC(12, 2) NOT NULL CHECK (valor_documento >= 0)
    , valor_liquido NUMERIC(12, 2) NOT NULL CHECK (valor_liquido >= 0)
    , atualizado_em TIMESTAMPTZ DEFAULT NOW()
    , CONSTRAINT uq_despesa_doc UNIQUE (id_deputado, cod_documento, num_documento, valor_liquido)
);
```

- **Carga Idempotente:** Utilizar `INSERT ... ON CONFLICT (...) DO UPDATE` via SQLAlchemy/psycopg2 para permitir reprocessamentos sem duplicação.

### Etapa 4: Camada de IA (`src/ai_enrichment.py`)

#### Taxonomia Oficial (~10 Temas)
1. Saúde Pública
2. Sistema Tributário e Fiscal
3. Trabalho e Previdência
4. Tecnologia, Dados e Inteligência Artificial
5. Meio Ambiente, Energia e Clima
6. Economia, Mercado Financeiro e Regulação
7. Segurança Pública e Justiça
8. Educação, Ciência e Cultura
9. Infraestrutura, Transportes e Cidades
10. Agronegócio e Desenvolvimento Regional

#### Fluxo e Controle de Custo
- Gerar e armazenar em cache local (ex.: `data/cache/temas_embeddings.json`) os embeddings dos 10 temas usando `text-embedding-3-small` (evitando recalcular a cada execução).
- Buscar no banco apenas `fato_proposicoes` onde `tema_ia IS NULL` (processamento incremental).
- **Modo Piloto Obrigatório (`--limit 10`):** Rodar inicialmente com 10 proposições, registrar tokens consumidos e custo estimado em USD, e validar a coerência das classificações antes de processar o lote completo.
- Calcular similaridade de cosseno:

$$\text{cosine\_similarity}(A, B) = \frac{A \cdot B}{\|A\|\|B\|}$$

- (Caminho B) Para o resumo executivo, usar prompt restrito (máximo de 3 linhas, foco em impacto de negócios e risco regulatório, linguagem não-jurídica) e registrar o prompt exato no `README.md`.

### Etapa 5: Automação n8n e Versionamento (`n8n/` & GitHub)
- **Workflow 1 (Alerta Crítico / Digest):** Conectar nó PostgreSQL (Supabase) ao n8n para consultar proposições recém-classificadas em temas críticos (ex.: `Tecnologia, Dados e Inteligência Artificial` ou `Sistema Tributário e Fiscal`) com `resumo_executivo` e disparar mensagem formatada no Telegram e/ou E-mail.
- **Workflow 2 (Ingestão Agendada 06h00):** Cron Trigger diário às 06:00 BRT acionando a rotina ETL + IA (via HTTP/Webhook para microserviço Python ou CLI local em Docker).
- Exportar workflows para `n8n/radar_legislativo_workflow.json`.

---

## 6. Estrutura de Diretórios Prevista

```text
Data_CHallenge1/
|-- Agents.md
|-- PRD.md
|-- SPEC.md
|-- PLAN.md
|-- CHANGELOG.md
|-- README.md
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- data/
|   |-- raw/                  # JSONs brutos (ignorado no git)
|   `-- cache/                # Cache de embeddings dos temas
|-- docs/
|   |-- arquitetura.png       # Diagrama do pipeline (Excalidraw/Mermaid)
|   |-- prints/               # Evidencias do Supabase, n8n e alertas
|   `-- pitch_bussola_publica.pdf
|-- n8n/
|   `-- radar_legislativo_workflow.json
|-- notebooks/
|   `-- 01_exploracao_api.ipynb
|-- sql/
|   `-- 01_schema_star.sql
`-- src/
    |-- __init__.py
    |-- config.py
    |-- extract.py
    |-- transform.py
    |-- load.py
    |-- ai_enrichment.py
    `-- main.py
```

---

## 7. Variáveis de Ambiente (`.env.example`) e `.gitignore`

### Conteúdo Base do `.env.example`
```dotenv
# Banco de Dados PostgreSQL (Supabase / Neon / Railway)
DATABASE_URL=postgresql://postgres:SUA_SENHA@db.SEU_PROJETO.supabase.co:5432/postgres

# OpenAI API (Embeddings e Resumos)
OPENAI_API_KEY=sk-proj-SUA_CHAVE_AQUI
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_SUMMARY_MODEL=gpt-4o-mini

# Configuracoes do Pipeline
CAMARA_API_BASE_URL=https://dadosabertos.camara.leg.br/api/v2
INGESTION_DAYS_WINDOW=30
AI_BATCH_LIMIT=10

# Alertas (Opcional se disparado via script ou usado no n8n)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### Itens Obrigatórios no `.gitignore`
- `.env` e `.env.*` (exceto `.env.example`)
- `.venv/`, `venv/`, `__pycache__/`, `*.pyc`
- `data/raw/` (dados brutos volumosos não devem poluir o Git)
- `.ipynb_checkpoints/`, `.DS_Store`, `*.log`
