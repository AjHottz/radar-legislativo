# Pitch Executivo - Radar Legislativo (Bússola Pública)

> Apresentação executiva em **6 slides** (versão final exportada em [docs/pitch_bussola_publica.pdf](./pitch_bussola_publica.pdf)).

---

## Slide 1: O Problema da Bússola Pública
- **Contexto:** A consultoria fatura **R$ 15.000/mês por cliente** entregando inteligência legislativa semanal, mas operava de forma artesanal sobre dados públicos da Câmara dos Deputados.
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
  - Base única em nuvem (Supabase PostgreSQL 17.12 + `pgvector`), consultável via SQL e conectores de BI.
  - Classificação temática padronizada em **10 temas oficiais** sem intervenção manual.
  - Redução drástica do tempo de triagem dos analistas de RelGov com custo zero de inferência na etapa piloto/MVP.

---

## Slide 3: Arquitetura e Modelagem Dimensional (Star Schema)
- **Pipeline Modular em 5 Camadas ([docs/arquitetura.png](./arquitetura.png)):**
  1. **Extração Resiliente (`src/extract.py`):** Paginação `while`, backoff exponencial em HTTP 429/5xx, checkpoint retomável para 513 deputados e persistência obrigatória em `data/raw/`.
  2. **Qualidade Pandas (`src/transform.py`):** Normalização, deduplicação por chave única, quarentena explícita de despesas negativas (`18.387` registros retidos na carga de 30 dias) e preservação de emendas `ano = 0`.
  3. **Data Warehouse (Supabase):** `dim_partidos` (`21`), `dim_deputados` (`513` / 27 UFs), `fato_proposicoes` (`7.430`), `fato_votacoes` (`2.004`), `fato_despesas` (`1.768` válidas) e `log_execucoes_pipeline` (`9` logs), com carga idempotente (`ON CONFLICT DO UPDATE`).

---

## Slide 4: IA Aplicada com Governança de Custos
- **Caminho A (Classificação Determinística):** Embeddings `gemini-embedding-001` (1.536 dimensões normalizadas, compatível com `text-embedding-3-small`), cache local dos 10 temas oficiais ([data/cache/temas_embeddings.json](../data/cache/temas_embeddings.json)) e atribuição por similaridade de cosseno.
- **Caminho B (Síntese Executiva):** `gemini-3.5-flash-lite` (com fallback e trava anti-alucinação) gera resumo de até 3 linhas em linguagem de negócios (impacto regulatório, setor afetado e risco/oportunidade).
- **Resultados e Controle Financeiro:** Piloto obrigatório de 10 itens escalado de forma incremental (`WHERE tema_ia IS NULL`) para **368 proposições classificadas** (`100%` dos `PL`, `PLP`, `PEC` e `MPV` dos 30 dias) e **80 resumos executivos**, com custo total registrado de **US$ 0.00** no Gemini Free Tier.

---

## Slide 5: Automação Autônoma (n8n) e Evidências
- **Workflow Publicado (`Pbtgkim2DNO5Hgc0`):**
  - **Fluxo Diário (06h00 BRT):** Aciona `POST http://127.0.0.1:8085/run-pipeline` -> Supabase (`Consultar proposicoes criticas 24h`) -> `Aggregate` -> alerta HTML no Telegram. Validado ao vivo na execução `ID#4` (`3m 51.875s`, `20/20` novos resumos IA e `10` alertas críticos entregues no `message_id: 5`).
  - **Digest Semanal (Segundas 08h00 BRT):** Seleciona Top 5 da semana no Supabase e entrega boletim HTML. Validado ao vivo na execução `ID#3` (`1.558s`, `5` proposições entregues no `message_id: 4`).
- **Evidências Visuais em `docs/prints/`:**
  - `docs/prints/n8n_canvas.png`, `docs/prints/n8n_execucao_diaria.png`, `docs/prints/n8n_execucao_semanal.png` e `docs/prints/telegram_alertas.jpg`.

---

## Slide 6: Impacto no Negócio e Próximos Passos
- **Impacto:** Escala comercial mantendo receita de R$ 15 mil/cliente sem aumento linear da equipe, eliminação de atrasos em pautas críticas e histórico auditável no Supabase.
- **Próximos Passos (Fase 2):**
  1. Captura de votos nominais por parlamentar (`/votacoes/{id}/votos`).
  2. Inclusão de dados do Senado Federal e Diário Oficial da União.
  3. Painel executivo de atendimento em Power BI / Streamlit conectado ao Supabase.
