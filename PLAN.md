# PLAN: Plano de Execução - Radar Legislativo (Bússola Pública)

> **Janela Oficial do Desafio:** 16/11/2026 a 15/12/2026
> **Data Base deste Plano:** 26/11/2026 (20 dias corridos restantes)
> **Meta:** Entregar pipeline completo em produção, banco populado (>= 30 dias), automação n8n, documentação de portfólio e pitch executivo antes de 15/12/2026.

---

## Cronograma Macro em 6 Ondas

| Onda | Etapa do Desafio | Foco Principal | Janela Sugerida | Status |
|---|---|---|---|---|
| **Onda 0** | Setup & Governança | Ambiente `.venv`, Git, `.gitignore`, `.env.example`, Supabase | 26/11 a 27/11 | Concluída (apenas `OPENAI_API_KEY` pendente para Onda 4) |
| **Onda 1** | Etapa 1: Exploração | Inspeção Swagger e respostas reais da API da Câmara | 28/11 a 29/11 | Concluída |
| **Onda 2** | Etapa 2: Extração | Script resiliente + paginação + JSON bruto local (`data/raw/`) | 30/11 a 02/12 | Concluída (piloto 7d validado) |
| **Onda 3** | Etapa 3: Transformação & Carga | Limpeza Pandas, Star Schema SQL, carga 7 dias -> 30 dias no Supabase | 03/12 a 06/12 | Em andamento (piloto 7d + idempotência OK; aguarda carga 30d) |
| **Onda 4** | Etapa 4: Camada de IA | Piloto 10 itens, embeddings `text-embedding-3-small`, cosseno e resumo | 07/12 a 09/12 | Código pronto (aguarda `OPENAI_API_KEY`) |
| **Onda 5** | Etapa 5: Automação n8n | Workflows cron 06h00, alerta Telegram e digest semanal + `.json` | 10/12 a 12/12 | Parcial (`.json` e runner prontos; sem Docker/n8n local) |
| **Onda 6** | Empacotamento & Pitch | `README.md`, diagrama, prints, slides (até 6) e submissão na Xperiun | 13/12 a 15/12 | Em andamento (`README.md`, diagrama e roteiro prontos) |

---

## Detalhamento Operacional por Onda

### Onda 0: Setup, Segurança e Infraestrutura Base
- [x] Criar ambiente virtual Python 3.11+ (`.venv`) dentro de `Data_CHallenge1` e gerar `requirements.txt` inicial.
- [x] Criar `.gitignore` cobrindo `.env`, `.venv/`, `__pycache__/`, `data/raw/`, logs e checkpoints.
- [x] Criar `.env.example` e configurar `.env` local (nunca versionado).
- [x] Provisionar projeto gratuito no **Supabase** (`radar-legislativo` / `pibefrkcgoplmvkpagda`, PostgreSQL 17.12 + `pgvector` habilitado) e validar conexão via `SQLAlchemy`/`psycopg2` (`src/check_env.py` aprovado).
- [x] Fazer commit inicial da estrutura documental e de configuração (`5a6f45b`, repositório Git inicializado com `git init -b main` e conectado a `AjHottz/radar-legislativo`).
- **Definition of Done (DoD):** `python -c "import requests, pandas, sqlalchemy, openai"` funciona na `.venv` e conexão com Supabase responde sem expor credenciais no Git.

### Onda 1: Exploração da API da Câmara (Etapa 1)
- [x] Navegar e inspecionar endpoints reais da API oficial (`https://dadosabertos.camara.leg.br/api/v2`).
- [x] Criar `notebooks/01_exploracao_api.ipynb` e `src/explore.py` testando chamadas reais aos endpoints:
  - `/partidos`
  - `/deputados`
  - `/deputados/{id}/despesas`
  - `/proposicoes`
  - `/votacoes`
- [x] Mapear paginação (`links` -> `next`), limites de itens por página (100), parâmetros de filtro de data e campos com potencial nulo ou aninhado (`ano=0`, `valorLiquido < 0`, `codDocumento` string).
- [x] Revisar e congelar o DDL final em `sql/01_schema_star.sql` com base nos campos reais observados.
- **DoD:** Dicionário de dados validado contra respostas reais da API e DDL criado sem campos inventados.

### Onda 2: Extração Resiliente em Python (Etapa 2)
- [x] Implementar `src/config.py` carregando variáveis do `.env` e validando configurações obrigatórias.
- [x] Implementar `src/extract.py` com:
  - Paginação completa via loop `while`.
  - Tratamento de erros (`try/except`), `timeout` e política simples de retentativa/backoff (incluindo HTTP 429).
  - Controle de taxa específico para `/deputados/{id}/despesas` com checkpoint retomável.
  - Persistência obrigatória dos JSONs brutos em `data/raw/<entidade>/<data>.json`.
- [x] Executar extração piloto de **7 dias** e validar integridade dos JSONs salvos (`21` partidos, `513` deputados, `1.716` proposições, `284` votações, `12.210` despesas).
- **DoD:** Script extrai todos os endpoints configurados para 7 dias sem quebrar e grava os JSONs brutos em disco; commit atômico realizado.

### Onda 3: Transformação Pandas e Carga Dimensional no Supabase (Etapa 3)
- [x] Aplicar `sql/01_schema_star.sql` no banco PostgreSQL do Supabase (`pibefrkcgoplmvkpagda`, migração `init_star_schema`).
- [x] Implementar `src/transform.py` com `pandas`:
  - Normalização de JSONs (`pd.json_normalize`).
  - Validações explícitas: campos obrigatórios não nulos, datas em faixa válida, `valor_documento >= 0` e `valor_liquido >= 0` (com quarentena explícita de negativos), deduplicação por chave única.
  - Registro de métricas de qualidade (`data/cache/transform_qa_<data>.json`).
- [x] Implementar `src/load.py` (e `src/main.py`) com carga idempotente (`ON CONFLICT DO UPDATE`) respeitando a ordem referencial (Dimensões -> Fatos).
- [x] Validar carga piloto de **7 dias** e idempotência no Supabase (`2026-11-26-piloto7d`, 2 execuções sem duplicatas: `21` partidos, `513` deputados, `1.680` proposições, `284` votações, `525` despesas).
- [ ] Executar carga oficial de **30 dias** no Supabase (`python -m src.main --step load --days 30 --run-date 2026-11-26`) e validar contagens finais no banco.
- **DoD:** Todas as 5 tabelas (`dim_partidos`, `dim_deputados`, `fato_proposicoes`, `fato_votacoes`, `fato_despesas`) populadas no Supabase com >= 30 dias de dados reais e zero duplicatas após reexecução.

### Onda 4: Camada de IA Aplicada com Controle de Custos (Etapa 4)
- [x] Definir lista final de ~10 temas oficiais da Bússola Pública (`TAXONOMIA_TEMAS` em `src/config.py`).
- [x] Implementar `src/ai_enrichment.py`:
  - Geração e cache local dos embeddings da taxonomia de temas (`text-embedding-3-small`).
  - Seleção incremental de proposições ainda não classificadas (`WHERE tema_ia IS NULL`).
  - Cálculo de similaridade de cosseno e atribuição de `tema_ia` e `similaridade_tema`.
  - (Caminho B) Geração de `resumo_executivo` (máximo 3 linhas, foco em negócios) com prompt documentado.
- [ ] Executar **piloto obrigatório com 10 proposições** (após preencher `OPENAI_API_KEY` no `.env`), verificar faturamento/tokens na OpenAI, validar qualitativamente as classificações e só então processar o lote de 30 dias.
- **DoD:** Proposições dos últimos 30 dias classificadas e resumidas no Supabase, com registro documentado do custo real do piloto e do lote completo.

### Onda 5: Orquestração Autônoma com n8n (Etapa 5)
- [ ] Subir ambiente n8n (Docker local ou n8n Cloud) e configurar credenciais PostgreSQL (Supabase) e Telegram/E-mail.
- [x] Construir Workflow de **Ingestão Diária (06h00)** e **Alerta Crítico + Digest Semanal** em `n8n/radar_legislativo_workflow.json` (plus `src/webhook_runner.py` e `n8n/README.md`).
- [ ] Testar execução completa, capturar prints de sucesso e salvar em `docs/prints/`.
- **DoD:** Execução end-to-end no n8n comprovada por print e arquivo `.json` versionado no GitHub.

### Onda 6: Documentação de Portfólio, Pitch e Entrega Final
- [x] Criar diagrama de arquitetura do pipeline em Mermaid (`docs/arquitetura.md`, pendente exportação PNG em `docs/arquitetura.png` se desejado).
- [x] Redigir `README.md` de alto impacto contendo contexto, arquitetura, modelo de dados, decisões técnicas, prompts de IA e instruções de execução (atualizar ao final com prints e link de leitura do Supabase).
- [x] Produzir roteiro da apresentação executiva (6 slides) em `docs/pitch_bussola_publica.md` (exportar para `docs/pitch_bussola_publica.pdf` após incluir prints finais).
- [ ] Realizar revisão final do repositório (conferir se `.env` e `data/raw/` não vazaram no histórico Git) e push para o GitHub.
- [ ] Submeter entrega na plataforma Xperiun antes de **15/12/2026**.
- **DoD:** Todos os 5 entregáveis validados contra as 5 dimensões de avaliação da Xperiun.

---

## Matriz de Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Lentidão ou bloqueio na API da Câmara ao buscar `/deputados/{id}/despesas` para 513 deputados | Alta | Alto | Salvar JSON bruto por deputado, implementar retry/sleep suave, limitar janela a 30 dias (mês corrente/anterior) e permitir retomada por checkpoint |
| Estouro ou gasto inesperado na API da OpenAI | Média | Médio | Piloto obrigatório com `--limit 10`, cache local dos embeddings dos temas e processamento incremental apenas onde `tema_ia IS NULL` |
| Dificuldade do n8n Cloud acionar script Python local | Média | Médio | Preferir n8n em Docker local na mesma rede/host ou expor runner HTTP leve (FastAPI/webhook), mantendo queries de alerta conectadas diretamente ao Supabase |
| Vazamento acidental de API key no GitHub | Baixa | Crítico | Configurar `.gitignore` na Onda 0 antes do primeiro commit e revisar `git status` / `git diff` antes de cada push |

