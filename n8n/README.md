# Automação n8n - Radar Legislativo (Onda 5)

Este diretório contém o fluxo exportado [radar_legislativo_workflow.json](./radar_legislativo_workflow.json) pronto para importação no **n8n** (execução local via `npx n8n`, Docker ou n8n Cloud).

## Fluxos Incluídos no JSON

1. **Ingestão Diária + Alerta Crítico (06h00 BRT):**
   - `Agendar pipeline diario 06h` -> dispara diariamente às 06:00 (`America/Sao_Paulo`).
   - `Executar pipeline Python (8085)` -> envia `POST http://127.0.0.1:8085/run-pipeline` para [webhook_runner.py](../src/webhook_runner.py) (`days=2`, `limit=20`, retry 3x).
   - `Consultar proposicoes criticas 24h` -> consulta proposições recém-processadas com `resumo_executivo IS NOT NULL` em temas críticos (`Tecnologia, Dados e Inteligência Artificial`, `Sistema Tributário e Fiscal`, `Economia, Mercado Financeiro e Regulação`).
   - `Agregar alertas criticos` + `Enviar alerta diario Telegram` -> consolida em HTML e envia o alerta no Telegram quando há correspondência.

2. **Digest Semanal Executivo (Segunda-feira 08h00 BRT):**
   - `Agendar resumo semanal Seg 08h` -> dispara semanalmente às segundas-feiras às 08:00 (`America/Sao_Paulo`).
   - `Consultar Top 5 semanal (7d)` -> seleciona as 5 proposições com `resumo_executivo IS NOT NULL` mais aderentes dos últimos 7 dias.
   - `Agregar Top 5 semanal` + `Enviar resumo semanal Telegram` -> consolida o Top 5 em HTML e envia o boletim no Telegram.

## Execução Local sem Docker (`npx n8n` + HTTP Runner)

Como o ambiente conta com Node.js, você pode subir tudo localmente em dois terminais:

1. **Terminal 1 (Runner Python do Pipeline):**
   ```powershell
   .\.venv\Scripts\python.exe -m src.webhook_runner
   ```
   *(Endpoint ativo em `http://127.0.0.1:8085`: `GET /health` e `POST /run-pipeline`.)*

2. **Terminal 2 (n8n local via npx, priorizando IPv4 no Windows):**
   ```powershell
   $env:N8N_PORT="5678"
   $env:GENERIC_TIMEZONE="America/Sao_Paulo"
   $env:NODE_OPTIONS="--dns-result-order=ipv4first"
   npx -y n8n start
   ```
   *(A flag `--dns-result-order=ipv4first` evita timeout em redes Windows onde o DNS IPv6 de `api.telegram.org` não responde.)*
   Acesse `http://localhost:5678`, vá em **Workflows -> Import from File** e selecione `n8n/radar_legislativo_workflow.json`.

## Credenciais Necessárias no n8n

1. **Postgres (`Supabase Postgres - Radar Legislativo`):**
   - **Host:** `aws-0-sa-east-1.pooler.supabase.com` *(Session Pooler IPv4 compatível com redes Windows)*
   - **Port:** `5432`
   - **Database:** `postgres`
   - **User:** `postgres.pibefrkcgoplmvkpagda`
   - **Password:** senha definida no Supabase
   - **SSL:** `Require` (ou `Allow`)
2. **Telegram API (`Telegram Bot - Bussola Publica`):**
   - Gere o token com `@BotFather` no Telegram.
   - Substitua `SEU_TELEGRAM_CHAT_ID` nos dois nós do Telegram pelo ID do seu chat/grupo (obtido via `@userinfobot` ou `getUpdates`).
3. Após executar manualmente um teste de sucesso, salve os prints em `docs/prints/` para evidência da entrega.
