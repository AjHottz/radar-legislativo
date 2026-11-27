# PLAN: Plano de Execução - Radar Legislativo (Bússola Pública)

> **Janela Oficial do Desafio:** 16/11/2026 a 15/12/2026
> **Data Base deste Plano:** 26/11/2026 (20 dias corridos restantes)
> **Meta:** Entregar pipeline completo em produção, banco populado (>= 30 dias), automação n8n, documentação de portfólio e pitch executivo antes de 15/12/2026.

---

## Cronograma Macro em 6 Ondas

| Onda | Etapa do Desafio | Foco Principal | Janela Sugerida | Status |
|---|---|---|---|---|
| **Onda 0** | Setup & Governança | Ambiente `.venv`, Git, `.gitignore`, `.env.example`, Supabase | 26/11 a 27/11 | Em andamento |
| **Onda 1** | Etapa 1: Exploração | Inspeção Swagger e respostas reais da API da Câmara | 28/11 a 29/11 | Pendente |
| **Onda 2** | Etapa 2: Extração | Script resiliente + paginação + JSON bruto local (`data/raw/`) | 30/11 a 02/12 | Pendente |
| **Onda 3** | Etapa 3: Transformação & Carga | Limpeza Pandas, Star Schema SQL, carga 7 dias -> 30 dias no Supabase | 03/12 a 06/12 | Pendente |
| **Onda 4** | Etapa 4: Camada de IA | Piloto 10 itens, embeddings `text-embedding-3-small`, cosseno e resumo | 07/12 a 09/12 | Pendente |
| **Onda 5** | Etapa 5: Automação n8n | Workflows cron 06h00, alerta Telegram e digest semanal + `.json` | 10/12 a 12/12 | Pendente |
| **Onda 6** | Empacotamento & Pitch | `README.md`, diagrama, prints, slides (até 6) e submissão na Xperiun | 13/12 a 15/12 | Pendente |

---

## Detalhamento Operacional por Onda

### Onda 0: Setup, Segurança e Infraestrutura Base
- [x] Criar ambiente virtual Python 3.11+ (`.venv`) dentro de `Data_CHallenge1` e gerar `requirements.txt` inicial.
- [x] Criar `.gitignore` cobrindo `.env`, `.venv/`, `__pycache__/`, `data/raw/`, logs e checkpoints.
- [x] Criar `.env.example` e configurar `.env` local (nunca versionado).
- [ ] Provisionar projeto gratuito no **Supabase** (PostgreSQL + `pgvector` habilitado) e testar conexão via `SQLAlchemy`/`psycopg2` (`src/check_env.py`).
- [ ] Fazer commit inicial da estrutura documental e de configuração após validar credenciais (repositório Git já inicializado com `git init -b main`).
- **Definition of Done (DoD):** `python -c "import requests, pandas, sqlalchemy, openai"` funciona na `.venv` e conexão com Supabase responde sem expor credenciais no Git.

### Onda 1: Exploração da API da Câmara (Etapa 1)
- [ ] Navegar pelo Swagger oficial (`https://dadosabertos.camara.leg.br/swagger/api.html`).
- [ ] Criar `notebooks/01_exploracao_api.ipynb` (ou `src/explore.py`) para testar chamadas reais aos endpoints:
  - `/partidos`
  - `/deputados`
  - `/deputados/{id}/despesas`
  - `/proposicoes`
  - `/votacoes`
- [ ] Mapear paginação (`links` -> `next`), limites de itens por página (100), parâmetros de filtro de data e campos com potencial nulo ou aninhado.
- [ ] Revisar e congelar o DDL final em `sql/01_schema_star.sql` com base nos campos reais observados.
- **DoD:** Dicionário de dados validado contra respostas reais da API e DDL criado sem campos inventados.

### Onda 2: Extração Resiliente em Python (Etapa 2)
- [ ] Implementar `src/config.py` carregando variáveis do `.env` e validando configurações obrigatórias.
- [ ] Implementar `src/extract.py` com:
  - Paginação completa via loop `while`.
  - Tratamento de erros (`try/except`), `timeout` e política simples de retentativa/backoff.
  - Controle de taxa específico para `/deputados/{id}/despesas` (evitando bloqueio HTTP 429/5xx).
  - Persistência obrigatória dos JSONs brutos em `data/raw/<entidade>/<data>.json`.
- [ ] Executar extração piloto de **7 dias** e validar integridade dos JSONs salvos.
- **DoD:** Script extrai todos os endpoints configurados para 7 dias sem quebrar e grava os JSONs brutos em disco; commit atômico realizado.

### Onda 3: Transformação Pandas e Carga Dimensional no Supabase (Etapa 3)
- [ ] Aplicar `sql/01_schema_star.sql` no banco PostgreSQL do Supabase.
- [ ] Implementar `src/transform.py` com `pandas`:
  - Normalização de JSONs (`pd.json_normalize`).
  - Validações explícitas: campos obrigatórios não nulos, datas em faixa válida, `valor_documento >= 0` e `valor_liquido >= 0`, deduplicação por chave única.
  - Registro de métricas de qualidade (lidos, rejeitados, deduplicados).
- [ ] Implementar `src/load.py` com carga idempotente (`ON CONFLICT DO UPDATE`) respeitando a ordem referencial (Dimensões -> Fatos).
- [ ] Validar fluxo completo com a amostra de **7 dias** e, após validação, escalar a janela para **30+ dias**.
- **DoD:** Todas as 5 tabelas (`dim_partidos`, `dim_deputados`, `fato_proposicoes`, `fato_votacoes`, `fato_despesas`) populadas no Supabase com >= 30 dias de dados reais e zero duplicatas após reexecução.

### Onda 4: Camada de IA Aplicada com Controle de Custos (Etapa 4)
- [ ] Definir lista final de ~10 temas oficiais da Bússola Pública.
- [ ] Implementar `src/ai_enrichment.py`:
  - Geração e cache local dos embeddings da taxonomia de temas (`text-embedding-3-small`).
  - Seleção incremental de proposições ainda não classificadas (`WHERE tema_ia IS NULL`).
  - Cálculo de similaridade de cosseno e atribuição de `tema_ia` e `similaridade_tema`.
  - (Caminho B) Geração de `resumo_executivo` (máximo 3 linhas, foco em negócios) com prompt documentado.
- [ ] Executar **piloto obrigatório com 10 proposições**, verificar faturamento/tokens na OpenAI, validar qualitativamente as classificações e só então processar o lote de 30 dias.
- **DoD:** Proposições dos últimos 30 dias classificadas e resumidas no Supabase, com registro documentado do custo real do piloto e do lote completo.

### Onda 5: Orquestração Autônoma com n8n (Etapa 5)
- [ ] Subir ambiente n8n (Docker local ou n8n Cloud) e configurar credenciais PostgreSQL (Supabase) e Telegram/E-mail.
- [ ] Construir Workflow de **Ingestão Diária (06h00)** acionando o pipeline incremental (`extract -> transform -> load -> ai_enrichment`).
- [ ] Construir Workflow de **Alerta Crítico + Digest Semanal**:
  - Consulta direta no Supabase filtrando proposições recentes de temas críticos com `tema_ia` e `resumo_executivo`.
  - Disparo automático para Telegram (alerta imediato) e/ou E-mail (Top 5 da semana).
- [ ] Testar execução completa, capturar prints de sucesso e exportar workflow(s) para `n8n/radar_legislativo_workflow.json`.
- **DoD:** Execução end-to-end no n8n comprovada por print e arquivo `.json` versionado no GitHub.

### Onda 6: Documentação de Portfólio, Pitch e Entrega Final
- [ ] Criar diagrama de arquitetura do pipeline (Excalidraw ou Mermaid renderizado em `docs/arquitetura.png`).
- [ ] Redigir `README.md` de alto impacto contendo: contexto de negócio, arquitetura, modelo de dados, decisões técnicas, prompts de IA, estimativa de custos, instruções de execução, link/instruções de leitura do Supabase e prints (banco, n8n, Telegram).
- [ ] Produzir apresentação executiva (máximo **6 slides**) estilo pitch para a Bússola Pública.
- [ ] Realizar revisão final do repositório (conferir se `.env` e `data/raw/` não vazaram no histórico Git).
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

