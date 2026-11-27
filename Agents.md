# Agents.md - Regras da Casa (Projeto Radar Legislativo)

> Contrato operacional para qualquer agente de IA atuando em `POS_DATACHALLENGE/Data_CHallenge1`.
> **Projeto:** Fase 1 (T02) - Projeto Integrador: Radar Legislativo (Bússola Pública)

---

## 1. Objetivo

Guiar a execução técnica e documental do pipeline de Engenharia de Dados + IA da Bússola Pública de forma assertiva, resiliente, auditável e alinhada aos critérios de avaliação da Xperiun, sem retrabalho nem custos inesperados.

---

## 2. Ordem Obrigatória de Leitura e Contexto

Antes de propor alterações, gerar código ou executar comandos neste projeto, leia sempre nesta ordem:

1. [Agents.md](./Agents.md) (este arquivo de governança e guardrails).
2. [PRD.md](./PRD.md) (requisitos de negócio, escopo das 5 etapas, entregáveis e avaliação).
3. [SPEC.md](./SPEC.md) (arquitetura, stack, schema dimensional, fluxos e variáveis de ambiente).
4. [PLAN.md](./PLAN.md) (plano de execução por ondas, checklists e prazos).
5. [CHANGELOG.md](./CHANGELOG.md) (histórico do que já foi decidido e entregue).

Se houver qualquer ambiguidade de negócio ou dúvida sobre credenciais/ambiente, pergunte antes de assumir.

---

## 3. Mapa de Pastas e Artefatos do Projeto

- `src/`: Código Python modular do pipeline (`extract.py`, `transform.py`, `load.py`, `ai_enrichment.py`, `main.py`).
- `notebooks/`: Exploração inicial da API da Câmara (`01_exploracao_api.ipynb`).
- `sql/`: Scripts DDL idempotentes para PostgreSQL/Supabase (`01_schema_star.sql`).
- `data/raw/`: Armazenamento local obrigatório dos JSONs brutos extraídos da API (não versionar no Git).
- `data/cache/`: Cache local dos embeddings da taxonomia de temas.
- `n8n/`: Workflows exportados em `.json` e documentação dos fluxos automatizados.
- `docs/`: Diagramas, prints de evidência (Supabase, n8n, Telegram) e apresentação executiva (pitch até 6 slides).

---

## 4. Guardrails Inegociáveis (Regras de Ouro)

1. **Nunca invente dados ou contratos de API:** Sempre inspecione o retorno real da API da Câmara dos Deputados (`https://dadosabertos.camara.leg.br/api/v2`) antes de definir colunas ou transformações. Quando não conseguir obter alguma informação, reporte explicitamente.
2. **Curiosidade primeiro, código depois:** Não escreva o ETL definitivo sem concluir a Etapa 1 (Exploração dos endpoints `/deputados`, `/proposicoes`, `/votacoes`, `/partidos` e `/deputados/{id}/despesas`).
3. **Resiliência antes de transformação:** Salve sempre o JSON bruto em `data/raw/` antes de executar transformações Pandas ou cargas no banco. Nunca faça requisições repetidas à API por falha de transformação.
4. **Escala gradual de dados:** Valide o pipeline ponta a ponta com uma janela inicial de **7 dias**. Somente após validar integridade e idempotência, escale para os **30 dias** obrigatórios (nunca tente baixar anos de histórico na primeira execução).
5. **Controle rigoroso de custos de IA:** Nunca execute embeddings ou LLM sobre todo o volume de proposições na primeira rodada. Rode obrigatoriamente um piloto com **10 proposições**, verifique o consumo/custo real na OpenAI e só então libere o lote completo.
6. **Zero teatro de IA:** Toda classificação temática ou resumo gerado pela IA deve ser gravado no banco e consumido de fato nos alertas (Telegram/E-mail) ou relatórios semanais.
7. **Segurança absoluta de credenciais:** Nunca grave chaves reais (`OPENAI_API_KEY`, `DATABASE_URL`, tokens de Telegram) em código, notebooks ou commits. Mantenha `.env` no `.gitignore` e exponha apenas placeholders no `.env.example`.
8. **Versionamento disciplinado:** Faça commits atômicos e descritivos ao final de cada onda/etapa. É proibido entregar o projeto em um único commit final.

---

## 5. Padrões Técnicos e de Resposta

- **Idioma:** Português (Brasil) para documentação, comentários e respostas; identificadores de código e banco padronizados de forma clara e consistente.
- **Ambiente:** Python 3.11+ isolado em `.venv` na raiz de `Data_CHallenge1`.
- **Estilo de Código:**
  - Utilize **leading commas** (vírgula no início da linha) em listas multilinhas, arrays e colunas/consultas SQL.
  - Entregue sempre scripts completos e funcionais (sem placeholders quebrados ou trechos incompletos).
  - Não utilize o caractere de travessão (U+2014) em documentos, notas ou comentários; utilize vírgula, dois-pontos, parênteses ou ponto final.
- **Memória Viva (Workspace IA):** Ao concluir marcos relevantes, atualizar [CHANGELOG.md](./CHANGELOG.md), [PLAN.md](./PLAN.md) e registrar o progresso em `../../Segundo Cerebro/projetos/pos-graduacao-dados-ia.md` e `../../Segundo Cerebro/tasks/todo.md`.
