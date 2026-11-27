# PRD: Radar Legislativo (Bússola Pública)

> **Projeto:** Fase 1 (T02) - Projeto Integrador: Radar Legislativo
> **Programa:** Pós-Graduação em Engenharia de Dados & IA (Xperiun)
> **Cliente Fictício:** Bússola Pública (Consultoria de Inteligência Legislativa)
> **Janela do Desafio:** 16/11/2026 a 15/12/2026
> **Fonte de Dados:** API Dados Abertos da Câmara dos Deputados (`https://dadosabertos.camara.leg.br/api/v2`)

---

## 1. Visão Geral e Problema de Negócio

Toda semana, em Brasília, 513 deputados federais votam pautas com impacto direto sobre tributação, regulação de tecnologia e IA, trabalho, saúde e meio ambiente. Embora proposições, votações, partidos, parlamentares e despesas de cota parlamentar estejam disponíveis gratuitamente em API pública, o mercado ainda consome essas informações de forma manual.

A consultoria fictícia **Bússola Pública** vende relatórios semanais de inteligência legislativa por **R$ 15.000/mês por cliente** (escritórios de advocacia, áreas de Relações Governamentais e associações setoriais), mas sua operação atual não escala devido a 5 gargalos críticos:

1. **Ausência de base de dados centralizada:** Analistas armazenam coletas em planilhas pessoais locais.
2. **Inexistência de histórico estruturado:** Consultas realizadas no site da Câmara se perdem ao longo do tempo.
3. **Classificação temática inconsistente:** Cada analista rotula proposições de forma subjetiva (ex.: "Tecnologia" vs. "Inovação Financeira"), inviabilizando métricas confiáveis.
4. **Alertas dependentes de memória humana:** Projetos polêmicos protocolados na sexta-feira à noite podem passar despercebidos até a imprensa noticiar na segunda-feira, gerando risco direto de perda de contrato.
5. **Falta de indicadores analíticos:** Não há visibilidade quantitativa sobre volume semanal de proposições por tema, comportamento de voto por partido ou nível de atividade parlamentar.

---

## 2. Objetivo do Produto

Construir um **pipeline automatizado de Engenharia de Dados ponta a ponta (ETL + Camada de IA + Orquestração)** que capture continuamente os dados públicos da Câmara dos Deputados, valide e modele essas informações em um Data Warehouse dimensional na nuvem, aplique inteligência artificial para padronização temática e síntese executiva, e dispare entregas automáticas (relatórios e alertas críticos) sem intervenção manual.

---

## 3. Público-Alvo e Beneficiários

| Perfil | Necessidade Principal | Valor Entregue pelo Produto |
|---|---|---|
| **CEO da Bússola Pública** | Escalar receita sem aumentar equipe manual de leitura e evitar perda de clientes por atrasos | Operação autônoma diária, padronizada e auditável, pronta para empacotamento comercial |
| **Analistas de RelGov / Consultores** | Reduzir trabalho braçal de triagem no site da Câmara e focar em análise estratégica | Dados já limpos, deduplicados, classificados por tema e resumidos em linguagem de negócios |
| **Clientes Corporativos (Advocacia, RelGov, Associações)** | Previsibilidade regulatória e reação rápida a proposições críticas do seu setor | Alertas quase em tempo real (Telegram/E-mail) e resumos semanais acionáveis |
| **Recrutadores / Avaliadores Xperiun** | Avaliar maturidade prática em Engenharia de Dados, IA aplicada e automação | Portfólio real em produção (código limpo, PostgreSQL na nuvem, n8n funcional, README e pitch) |

---

## 4. Requisitos Funcionais (5 Etapas da Missão)

### RF-01: Exploração da API da Câmara
- Mapear os endpoints `/deputados`, `/proposicoes`, `/votacoes`, `/partidos` e sub-recursos de despesas parlamentares (`/deputados/{id}/despesas`) antes de codificar o pipeline definitivo.
- Documentar os campos selecionados, chaves de relacionamento e limitações de paginação/taxa da API.

### RF-02: Extração Resiliente em Python
- Coletar dados via HTTP (`requests`) respeitando paginação completa (loop `while` até o fim das páginas).
- Tratar falhas de rede, timeouts e códigos HTTP anômalos (`try/except` com logs claros).
- Persistir obrigatoriamente os payloads **JSON brutos localmente** antes de iniciar qualquer limpeza ou carga, garantindo reprocessamento sem novas chamadas à API.
- Adotar carga incremental segura: validar ponta a ponta com janela inicial de **7 dias** e escalar para o mínimo obrigatório de **30 dias** no banco final.

### RF-03: Transformação, Qualidade e Modelagem Dimensional
- Carregar e normalizar os JSONs com `pandas`.
- Aplicar validações obrigatórias de qualidade de dados:
  - Campos obrigatórios não nulos.
  - Datas dentro de faixas válidas.
  - Valores monetários positivos (rejeitar ou sinalizar despesas negativas/inconsistentes).
  - Deduplicação por identificadores únicos.
- Estruturar o banco em **modelo dimensional simples (Star Schema)** no PostgreSQL em nuvem (Supabase recomendado; Neon ou Railway como alternativas):
  - **Tabelas Fato:** `votacoes`, `proposicoes`, `despesas`.
  - **Tabelas Dimensão:** `deputados`, `partidos`.

### RF-04: Camada de IA Aplicada (Sem "Teatro de IA")
A IA deve alterar diretamente a saída entregue ao negócio (relatórios, consultas e alertas):
- **Caminho A (Obrigatório/Prioritário - Classificação Temática Padronizada):**
  - Gerar embeddings das ementas das proposições (`text-embedding-3-small`, OpenAI).
  - Gerar embeddings para uma taxonomia fixa de ~10 temas oficiais (ex.: Saúde, Tributário, Trabalho, Tecnologia e IA, Meio Ambiente, Segurança Pública, Educação, Infraestrutura, Agronegócio, Economia e Finanças).
  - Classificar cada proposição via similaridade de cosseno para o tema mais próximo e gravar na tabela `proposicoes`.
- **Caminho B (Complementar Recomendado - Resumo Executivo):**
  - Gerar resumo de até 3 linhas em linguagem clara para executivos (não-juristas) e persistir na tabela `proposicoes` para consumo nos alertas e no digest semanal.
- **Governança de Custo:** Realizar teste piloto obrigatório com **10 proposições**, medir consumo/custo na plataforma da OpenAI e projetar o orçamento antes de processar o lote completo.

### RF-05: Automação com n8n e Versionamento
- Configurar workflow(s) no **n8n** para operar o pipeline de forma autônoma:
  - Ingestão incremental agendada (ex.: diariamente às 06h00).
  - Alerta imediato (Telegram e/ou E-mail) quando uma proposição for classificada em tema crítico monitorado.
  - Relatório semanal consolidado com as 5 proposições mais relevantes da semana.
- Exportar o(s) workflow(s) em `.json` no repositório com evidência visual (print) de execução bem-sucedida.
- Versionar todo o código no GitHub com histórico de commits frequentes e descritivos.

---

## 5. Requisitos Não-Funcionais

- **Segurança:** Nenhuma chave de API ou credencial de banco pode ser versionada. Uso estrito de `.env` local ignorado pelo `.gitignore` e documentado via `.env.example`.
- **Idempotência:** Reexecuções do pipeline para o mesmo período não podem gerar registros duplicados no PostgreSQL.
- **Observabilidade:** Logs estruturados por etapa (quantidade de páginas extraídas, registros validados/descartados, registros carregados e custo/tokens da etapa de IA).
- **Portabilidade:** Ambiente Python 3.11+ isolado com `requirements.txt` fixado e instruções claras de execução no `README.md`.

---

## 6. Entregáveis Obrigatórios e Avaliação

### Entregáveis
1. **Repositório no GitHub** completo, organizado, com `README.md` de nível de portfólio, `.gitignore` e `requirements.txt`.
2. **Banco PostgreSQL na nuvem** populado com no mínimo **30 dias de dados** reais e instrução/link de acesso em modo leitura no `README.md`.
3. **Workflow n8n exportado (`.json`)** salvo no repositório com print de execução bem-sucedida.
4. **Documentação técnica objetiva** (no `README.md` ou `docs/`): diagrama de arquitetura do pipeline, modelo das tabelas e relacionamentos, justificativa das decisões técnicas e prompts exatos utilizados.
5. **Apresentação executiva (até 6 slides)** no estilo pitch: problema da Bússola Pública, solução técnica, demonstração (prints do banco, n8n e entregas) e próximos passos.

### Critérios de Avaliação (5 Dimensões)
1. **Funcionamento:** Pipeline executa ponta a ponta sem quebrar.
2. **Modelagem:** Coerência do modelo dimensional (fatos e dimensões).
3. **IA Aplicada:** Impacto mensurável e útil nos produtos finais (não decorativo).
4. **Automação:** Workflows do n8n configurados, testados e funcionais.
5. **Comunicação:** Clareza do `README.md` e poder de convencimento do pitch executivo.

---

## 7. Fora de Escopo (Fase 1) e Premissas

- **Fora de Escopo:** Desenvolvimento de frontend web completo (SaaS multi-tenant), autenticação de usuários finais, raspagem de texto integral em PDF fora da API oficial caso não esteja estruturado, e ingestão histórica plurianual (4+ anos) nesta entrega inicial.
- **Premissas:** Disponibilidade da API pública da Câmara dos Deputados, conta ativa na OpenAI (com créditos mínimos para embeddings/resumos) e instância PostgreSQL gratuita em nuvem (Supabase/Neon/Railway) + n8n (local Docker ou Cloud).
