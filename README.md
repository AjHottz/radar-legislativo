# Radar Legislativo (Bússola Pública)

> Pipeline ponta a ponta de Engenharia de Dados, Modelagem Dimensional, IA Aplicada e Automação para Inteligência Legislativa sobre a API Dados Abertos da Câmara dos Deputados.

---

## 1. Contexto de Negócio

A consultoria **Bússola Pública** entrega inteligência legislativa semanal para escritórios de advocacia, áreas de Relações Governamentais e associações setoriais. Antes deste projeto, a operação sofria com 5 gargalos críticos:

1. Coletas manuais dispersas em planilhas locais.
2. Ausência de histórico estruturado de proposições, votações e despesas.
3. Classificação temática subjetiva e inconsistente entre analistas.
4. Alertas críticos dependentes de memória humana.
5. Falta de visibilidade quantitativa sobre volume legislativo e gastos parlamentares.

O **Radar Legislativo** resolve esses 5 pontos com ingestão resiliente em Python, armazenamento em Data Warehouse dimensional na nuvem (Supabase PostgreSQL + `pgvector`), classificação temática por embeddings com resumo executivo via OpenAI e orquestração automatizada no n8n.

---

## 2. Arquitetura do Pipeline

```text
API Camara v2 (/partidos, /deputados, /proposicoes, /votacoes, /despesas)
   |
   v
[Extracao Resiliente - src/extract.py]
   - Paginacao via link rel="next" + retry/backoff exponencial (HTTP 429/5xx)
   - Checkpoint retomavel por deputado + persistencia em data/raw/<entidade>/<data>.json
   |
   v
[Transformacao & Qualidade - src/transform.py]
   - Normalizacao Pandas (pd.json_normalize) + deduplicacao por chave unica
   - Quarentena explicita de despesas negativas (valorLiquido < 0) e validacao de datas
   |
   v
[Data Warehouse Cloud - Supabase PostgreSQL + pgvector]
   - Star Schema: dim_partidos, dim_deputados, fato_proposicoes, fato_votacoes, fato_despesas
   - Carga idempotente (INSERT ... ON CONFLICT DO UPDATE) + tabela log_execucoes_pipeline
   |
   v
[Camada de IA - src/ai_enrichment.py]
   - Caminho A: text-embedding-3-small + similaridade de cosseno (10 temas em cache)
   - Caminho B: gpt-4o-mini para resumo executivo (max 3 linhas)
   |
   v
[Orquestracao n8n - n8n/radar_legislativo_workflow.json]
   - Cron diario 06h00 BRT + Alerta critico imediato (Telegram) + Digest semanal (Top 5)
```

Diagramas detalhados em [docs/arquitetura.md](./docs/arquitetura.md).

---

## 3. Modelo Dimensional (Star Schema)

DDL completo e idempotente em [sql/01_schema_star.sql](./sql/01_schema_star.sql):

| Tabela | Tipo | Chave Primária | Papel no Modelo |
|---|---|---|---|
| `dim_partidos` | Dimensão | `id_partido` | Cadastro de partidos políticos ativos |
| `dim_deputados` | Dimensão | `id_deputado` | Cadastro dos 513 deputados, UF, partido e legislatura |
| `fato_proposicoes` | Fato | `id_proposicao` | Proposições protocoladas + `tema_ia`, `similaridade_tema`, `resumo_executivo` e `embedding` (`VECTOR(1536)`) |
| `fato_votacoes` | Fato | `id_votacao` | Votações em plenário/comissões e referência lógica `id_proposicao` |
| `fato_despesas` | Fato | `id_despesa` (`uq_despesa_doc`) | Despesas CEAP validadas (`valor_documento >= 0`, `valor_liquido >= 0`) |
| `log_execucoes_pipeline` | Governança | `id_execucao` | Auditoria de registros lidos, rejeitados, carregados, tokens e custo USD |

---

## 4. Decisões Técnicas e Descobertas da API Real

- **Exploração prévia antes do ETL (`src/explore.py` e `notebooks/01_exploracao_api.ipynb`):**
  - Emendas e substitutivos (`SBT`, `EMC`, `PRL`) retornam `ano = 0` na API; o pipeline preserva esses registros em vez de descartá-los erroneamente.
  - Votações recentes frequentemente referenciam proposições protocoladas em anos anteriores; por isso `fato_votacoes.id_proposicao` é indexada sem `FOREIGN KEY` bloqueante.
  - Na coleta piloto de 7 dias (`2026-11-19` a `2026-11-26`), foram extraídos **21 partidos**, **513 deputados**, **1.716 proposições** (1.680 válidas após filtro de qualidade), **284 votações** e **12.210 registros de despesas** (com **11.685** registros negativos em `valorLiquido` identificados pela regra de qualidade e separados em quarentena antes da carga).
- **Resiliência HTTP:** O endpoint `/deputados/{id}/despesas` aplica limitação de taxa (`HTTP 429`) sob concorrência; o extrator usa `ThreadPoolExecutor`, backoff exponencial e checkpoint local retomável.

---

## 5. Camada de IA e Controle de Custos

- **Taxonomia Oficial (10 Temas):** Saúde Pública; Sistema Tributário e Fiscal; Trabalho e Previdência; Tecnologia, Dados e Inteligência Artificial; Meio Ambiente, Energia e Clima; Economia, Mercado Financeiro e Regulação; Segurança Pública e Justiça; Educação, Ciência e Cultura; Infraestrutura, Transportes e Cidades; Agronegócio e Desenvolvimento Regional.
- **Prompt do Resumo Executivo (`gpt-4o-mini`):**
  > "Voce e um analista senior de inteligencia legislativa da consultoria Bussola Publica. Resuma a proposicao legislativa abaixo em NO MAXIMO 3 linhas, usando portugues claro de negocios (nao juridiques), destacando impacto regulatorio, setor afetado e risco ou oportunidade para empresas."
- **Controle Financeiro:** Cache local dos embeddings dos 10 temas em `data/cache/temas_embeddings.json`, seleção incremental apenas onde `tema_ia IS NULL` e piloto obrigatório com `--limit 10`.

---

## 6. Como Executar

### Pré-requisitos
- Python 3.11+
- Projeto PostgreSQL no Supabase (com extensão `pgvector`)
- Chave da OpenAI (`OPENAI_API_KEY`) para a etapa de enriquecimento (Onda 4)

### Instalação e Configuração
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Preencha DATABASE_URL e OPENAI_API_KEY no arquivo .env
python src\check_env.py
```

### Execução do Pipeline
```powershell
# 1. Exploracao da API (Onda 1)
python -m src.explore

# 2. Pipeline completo piloto de 7 dias (sem IA caso OPENAI_API_KEY ainda nao esteja preenchida)
python -m src.main --step all --days 7 --skip-ai

# 3. Carga oficial de 30 dias (Etapa 3)
python -m src.main --step extract --days 30
python -m src.main --step load --days 30

# 4. Piloto obrigatorio de IA com 10 proposicoes (Onda 4)
python -m src.main --step ai --limit 10
```

---

## 7. Automação n8n e Pitch Executivo

- Workflow exportado em [n8n/radar_legislativo_workflow.json](./n8n/radar_legislativo_workflow.json) e guia de importação em [n8n/README.md](./n8n/README.md).
- Runner HTTP opcional (stdlib) para acionamento remoto por n8n em Docker/Cloud: `python -m src.webhook_runner`.
- Roteiro do Pitch Executivo (6 slides) em [docs/pitch_bussola_publica.md](./docs/pitch_bussola_publica.md).
