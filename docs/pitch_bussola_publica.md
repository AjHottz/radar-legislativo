# Pitch Executivo - Radar Legislativo (Bússola Pública)

> Apresentação executiva em **6 slides** (estrutura pronta para exportação em PDF/PPTX em `docs/pitch_bussola_publica.pdf`).

---

## Slide 1: O Problema da Bússola Pública
- **Contexto:** A consultoria fatura **R$ 15.000/mês por cliente** entregando inteligência legislativa semanal, mas opera de forma artesanal sobre dados públicos da Câmara dos Deputados.
- **5 Gargalos Críticos:**
  1. Coletas dispersas em planilhas locais sem banco centralizado.
  2. Perda de histórico estruturado de proposições, votações e despesas.
  3. Classificação temática subjetiva entre analistas.
  4. Alertas dependentes de memória humana (risco de perder pautas de sexta à noite).
  5. Ausência de indicadores quantitativos de atividade parlamentar.

---

## Slide 2: A Solução - Radar Legislativo
- **Proposta de Valor:** Pipeline autônomo de Engenharia de Dados + IA aplicada que transforma dados brutos da Câmara em alertas regulatórios e digests executivos prontos para o cliente.
- **Benefícios Imediatos:**
  - Base única em nuvem (Supabase PostgreSQL + `pgvector`), consultável via SQL e conectores de BI.
  - Classificação temática padronizada em **10 temas oficiais** sem intervenção manual.
  - Redução drástica do tempo de triagem dos analistas de RelGov.

---

## Slide 3: Arquitetura e Modelagem Dimensional (Star Schema)
- **Pipeline Modular em 5 Camadas:**
  1. **Extração Resiliente (`src/extract.py`):** Paginação `while`, backoff exponencial em HTTP 429/5xx, checkpoint retomável para 513 deputados e persistência obrigatória em `data/raw/`.
  2. **Qualidade Pandas (`src/transform.py`):** Normalização, deduplicação por chave única, quarentena explícita de despesas com `valorLiquido < 0` e validação de datas.
  3. **Data Warehouse (Supabase):** `dim_partidos`, `dim_deputados`, `fato_proposicoes`, `fato_votacoes`, `fato_despesas` e `log_execucoes_pipeline`, com carga idempotente (`ON CONFLICT DO UPDATE`).

---

## Slide 4: IA Aplicada com Governança de Custos
- **Caminho A (Classificação Determinística):** Embeddings `text-embedding-3-small` com cache local dos 10 temas oficiais (`data/cache/temas_embeddings.json`) e atribuição por similaridade de cosseno.
- **Caminho B (Síntese Executiva):** `gpt-4o-mini` gera resumo de até 3 linhas em linguagem de negócios (impacto regulatório e risco setorial), consumido diretamente nos alertas.
- **Controle Financeiro:** Processamento incremental (`WHERE tema_ia IS NULL`) com piloto obrigatório de 10 itens (`--limit 10`) e registro de tokens/custo em USD no banco.

---

## Slide 5: Automação Autônoma (n8n) e Evidências
- **Workflow Diário (06h00 BRT):** Dispara ingestão incremental, consulta proposições recém-classificadas em temas críticos (Tributário, Tecnologia/IA, Economia) e envia alerta imediato no Telegram.
- **Digest Semanal (Segundas 08h00 BRT):** Seleciona o Top 5 da semana no Supabase e entrega boletim formatado.
- **Evidências:** `[Inserir prints do Supabase Table Editor, execução no n8n e mensagem no Telegram em docs/prints/]`.

---

## Slide 6: Impacto no Negócio e Próximos Passos
- **Impacto:** Escala comercial sem aumento linear da equipe de leitura, eliminação de atrasos em pautas críticas e histórico auditável para novos produtos analíticos.
- **Próximos Passos (Fase 2):**
  1. Captura de votos nominais por parlamentar (`/votacoes/{id}/votos`).
  2. Inclusão de dados do Senado Federal e Diário Oficial da União.
  3. Painel executivo de atendimento em Power BI / Streamlit conectado diretamente ao Supabase.
