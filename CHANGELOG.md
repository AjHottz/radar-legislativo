# Changelog

Todas as mudanças relevantes do projeto **Radar Legislativo (Bússola Pública)** serão documentadas neste arquivo.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento semântico.

## [Unreleased]

### Added
- Onda 0 (parcial): Criada estrutura base de pastas (`src/`, `notebooks/`, `sql/`, `n8n/`, `docs/prints/`, `data/raw/`, `data/cache/`), `.gitignore`, `.env.example`, `.env` local (não rastreado), `requirements.txt`, `src/check_env.py`, ambiente virtual `.venv` (Python 3.14.7) validado e `git init -b main`.

### Planned
- Onda 0 (conclusão): Configurar `DATABASE_URL` (Supabase) e `OPENAI_API_KEY` no `.env`, validar `src/check_env.py` e realizar commit inicial.
- Onda 1: Notebook de exploração da API Dados Abertos da Câmara dos Deputados e congelamento do `sql/01_schema_star.sql`.
- Onda 2: Extrator resiliente em Python com persistência local de JSON bruto.
- Onda 3: Transformação Pandas, validações de qualidade e carga Star Schema (7 dias -> 30 dias).
- Onda 4: Camada de IA (piloto 10 itens, embeddings `text-embedding-3-small` + similaridade de cosseno + resumo executivo).
- Onda 5: Automação no n8n (ingestão às 06h00 + alertas Telegram/E-mail) e exportação `.json`.
- Onda 6: `README.md` final, diagrama, prints e pitch executivo (até 6 slides).

## [0.1.0] - 2026-11-26

### Changed
- **Alinhamento completo de `PRD.md`:** Substituído o rascunho genérico de "Chat RAG interno da Xperiun" pela especificação oficial do **Fase 1 (T02): Projeto Integrador - Radar Legislativo (Bússola Pública)**, incorporando os 5 gargalos operacionais, API da Câmara dos Deputados, janela de dados (7 dias -> 30+ dias), entregáveis e critérios de avaliação extraídos de `DataCast.m4a` e da plataforma Xperiun.
- **Alinhamento completo de `SPEC.md`:** Substituída a stack incorreta (LangChain + Streamlit + Chroma efêmero + modelo inexistente "claude opus 5.5") pela arquitetura real do desafio: Python 3.11+, `requests`, `pandas`, modelo dimensional Star Schema (`dim_partidos`, `dim_deputados`, `fato_proposicoes`, `fato_votacoes`, `fato_despesas`) em PostgreSQL na nuvem (Supabase com `pgvector`), camada de IA via OpenAI (`text-embedding-3-small` + similaridade de cosseno e `gpt-4o-mini` com piloto de 10 itens), orquestração n8n e contrato de `.env.example` / `.gitignore`.
- **Revisão de `Agents.md`:** Corrigidos erros de digitação, links relativos quebrados e referências inexistentes (`docs/`, `contexto/`), adicionando os guardrails oficiais do desafio (exploração prévia, JSON bruto antes do transform, escala 7 -> 30 dias, piloto de custo de 10 proposições, segurança de segredos e padrões de código com leading commas).

### Added
- Criado `PLAN.md` com cronograma em 6 ondas até 15/12/2026, tarefas atômicas, critérios de pronto (DoD) e matriz de riscos.
- Criado `CHANGELOG.md` para rastreabilidade contínua das entregas do projeto.

