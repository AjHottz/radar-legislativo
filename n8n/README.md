# Automação n8n - Radar Legislativo (Onda 5)

Este diretório contém o fluxo exportado [radar_legislativo_workflow.json](./radar_legislativo_workflow.json) pronto para importação no **n8n** (Docker local ou n8n Cloud).

## Fluxos Incluídos no JSON

1. **Ingestão Diária + Alerta Crítico (06h00 BRT):**
   - `Cron Diario 06h00` -> dispara diariamente às 06:00 (`0 6 * * *`).
   - `Executar Pipeline Python (ETL + IA)` -> executa `python -m src.main --step all --days 2 --limit 50`.
   - `Supabase: Buscar Temas Criticos (24h)` -> consulta proposições recém-classificadas em temas críticos (`Tecnologia, Dados e Inteligência Artificial`, `Sistema Tributário e Fiscal`, `Economia, Mercado Financeiro e Regulação`).
   - `Ha Proposicao Critica?` -> envia alerta imediato no Telegram quando há correspondência.

2. **Digest Semanal Executivo (Segunda-feira 08h00 BRT):**
   - `Cron Digest Semanal (Seg 08h00)` -> dispara semanalmente (`0 8 * * 1`).
   - `Supabase: Top 5 da Semana` -> seleciona as 5 proposições mais relevantes dos últimos 7 dias.
   - `Formatar Digest Top 5` -> consolida o boletim em Markdown.
   - `Telegram: Enviar Digest Semanal` -> publica o relatório semanal no canal da consultoria.

## Como Importar e Configurar

1. No n8n, acesse **Workflows -> Import from File** e selecione `n8n/radar_legislativo_workflow.json`.
2. Crie duas credenciais no n8n:
   - **Postgres (`Supabase Postgres - Radar Legislativo`):** host `db.<SEU_PROJETO>.supabase.co`, porta `5432`, banco `postgres`, usuário `postgres`, SSL habilitado.
   - **Telegram API (`Telegram Bot - Bussola Publica`):** token gerado pelo `@BotFather`, além da variável `TELEGRAM_CHAT_ID`.
3. Caso o n8n rode em container separado ou n8n Cloud, substitua o nó `Execute Command` por um nó `HTTP Request` apontando para um endpoint webhook que execute `src.main`.
4. Após executar manualmente um teste de sucesso, salve os prints em `docs/prints/` para evidência da entrega.
