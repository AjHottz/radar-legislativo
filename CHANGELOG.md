# Changelog

Todas as mudanças relevantes do projeto **Radar Legislativo (Bússola Pública)** serão documentadas neste arquivo.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento semântico.

## [Unreleased]

### Added
- Onda 1: Criados `src/explore.py`, `notebooks/01_exploracao_api.ipynb`, `data/cache/api_exploracao_resumo.json` e DDL Star Schema congelado em `sql/01_schema_star.sql` com suporte `pgvector`, RLS e `log_execucoes_pipeline`.
- Onda 2: Criados `src/config.py` e `src/extract.py` com paginação `while`, backoff exponencial para HTTP 429/5xx, checkpoint retomável em despesas e coleta piloto de 7 dias validada (`21` partidos, `513` deputados, `1.716` proposições, `284` votações, `12.210` despesas).
- Onda 3 (parcial): Criados `src/transform.py`, `src/load.py` e `src/main.py`; transformação Pandas validada no piloto de 7 dias com quarentena explícita de `11.685` registros negativos em `valorLiquido`.
- Onda 4 (código pronto): Criado `src/ai_enrichment.py` com taxonomia de 10 temas, cache local de embeddings (`text-embedding-3-small`), similaridade de cosseno e resumo executivo (`gpt-4o-mini`), aguardando preenchimento de `OPENAI_API_KEY`.
- Onda 5 (artefatos prontos): Criados `n8n/radar_legislativo_workflow.json`, `n8n/README.md` e `src/webhook_runner.py`.
- Onda 6 (parcial): Criados `README.md`, `docs/arquitetura.md` (diagramas Mermaid) e roteiro de 6 slides em `docs/pitch_bussola_publica.md`.
- Onda 0 (concluída): Projeto Supabase `radar-legislativo` (`pibefrkcgoplmvkpagda`, `sa-east-1`) provisionado, `sql/01_schema_star.sql` aplicado via migração `init_star_schema`, conexão `src/check_env.py` validada (`PostgreSQL 17.12`, `pgvector` ativo) e repositório público `AjHottz/radar-legislativo` sincronizado no GitHub.
- Onda 3 (piloto 7d validado): Corrigidos `ensure_schema()` (cursor DBAPI) e `clean_records()` (`pd.isna(value)` para `NaT`) em `src/load.py`; carga piloto de 7 dias (`2026-11-26-piloto7d`) executada 2 vezes no Supabase comprovando idempotência (`21` partidos, `513` deputados, `1.680` proposições, `284` votações, `525` despesas e `2` registros em `log_execucoes_pipeline`).
- Onda 2 & 3 (30 dias raw/transform): Extração completa de 30 dias (`2026-10-27` a `2026-11-26`) e validação Pandas executadas em disco (`21` partidos, `513` deputados, `7.430` proposições válidas, `2.000` votações, `1.768` despesas válidas e `18.387` despesas negativas separadas em quarentena).

### Planned
- Onda 3 (carga completa 30d): Executar `python -m src.main --step load --days 30 --run-date 2026-11-26` após autorização e validar contagens finais no Supabase.
- Onda 4 (execução): Preencher `OPENAI_API_KEY` no `.env`, rodar piloto obrigatório de 10 itens (`--limit 10`) e processar lote completo.
- Onda 5/6 (evidências): Importar e testar workflow no n8n (Docker/Cloud), capturar prints em `docs/prints/`, gerar `docs/pitch_bussola_publica.pdf` e submeter na Xperiun até 15/12/2026.

## [0.1.0] - 2026-11-26

### Changed
- **Alinhamento completo de `PRD.md`:** Substituído o rascunho genérico de "Chat RAG interno da Xperiun" pela especificação oficial do **Fase 1 (T02): Projeto Integrador - Radar Legislativo (Bússola Pública)**, incorporando os 5 gargalos operacionais, API da Câmara dos Deputados, janela de dados (7 dias -> 30+ dias), entregáveis e critérios de avaliação extraídos de `DataCast.m4a` e da plataforma Xperiun.
- **Alinhamento completo de `SPEC.md`:** Substituída a stack incorreta (LangChain + Streamlit + Chroma efêmero + modelo inexistente "claude opus 5.5") pela arquitetura real do desafio: Python 3.11+, `requests`, `pandas`, modelo dimensional Star Schema (`dim_partidos`, `dim_deputados`, `fato_proposicoes`, `fato_votacoes`, `fato_despesas`) em PostgreSQL na nuvem (Supabase com `pgvector`), camada de IA via OpenAI (`text-embedding-3-small` + similaridade de cosseno e `gpt-4o-mini` com piloto de 10 itens), orquestração n8n e contrato de `.env.example` / `.gitignore`.
- **Revisão de `Agents.md`:** Corrigidos erros de digitação, links relativos quebrados e referências inexistentes (`docs/`, `contexto/`), adicionando os guardrails oficiais do desafio (exploração prévia, JSON bruto antes do transform, escala 7 -> 30 dias, piloto de custo de 10 proposições, segurança de segredos e padrões de código com leading commas).

### Added
- Criado `PLAN.md` com cronograma em 6 ondas até 15/12/2026, tarefas atômicas, critérios de pronto (DoD) e matriz de riscos.
- Criado `CHANGELOG.md` para rastreabilidade contínua das entregas do projeto.

