# Arquitetura do Pipeline - Radar Legislativo (Bússola Pública)

## 1. Fluxo Ponta a Ponta

```mermaid
flowchart LR
    API["API Camara v2\n(/partidos, /deputados,\n/proposicoes, /votacoes,\n/deputados/{id}/despesas)"]
    EXT["Extracao Python\n(src/extract.py)\nPaginacao while + retry/backoff"]
    RAW["Camada Raw Local\n(data/raw/<entidade>/*.json)"]
    TRF["Transformacao & QA\n(src/transform.py)\nPandas + quarentena negativos"]
    SUPA[("Supabase PostgreSQL\n+ pgvector\nStar Schema (5 tabelas + log)")]
    IA["Camada de IA\n(src/ai_enrichment.py)\ngemini-embedding-001 (1536d)\n+ cosseno + gemini-3.5-flash-lite"]
    N8N["Orquestracao n8n\nCron 06h00 + Runner 8085\n+ Alerta Critico + Top 5 Semanal"]
    TG["Telegram Bot API\n(Consultores e Clientes)"]

    API --> EXT --> RAW --> TRF --> SUPA
    SUPA <--> IA
    N8N --> EXT
    SUPA --> N8N --> TG
```

## 2. Modelo Dimensional (Star Schema)

```mermaid
erDiagram
    dim_partidos {
        int id_partido PK
        varchar sigla
        varchar nome
        text uri
        timestamptz atualizado_em
    }
    dim_deputados {
        int id_deputado PK
        varchar nome
        int id_partido
        varchar sigla_partido
        char sigla_uf
        varchar email
        text url_foto
        int id_legislatura
    }
    fato_proposicoes {
        bigint id_proposicao PK
        varchar sigla_tipo
        int numero
        int ano
        text ementa
        timestamptz data_apresentacao
        varchar tema_ia
        numeric similaridade_tema
        text resumo_executivo
        vector embedding
        timestamptz processado_ia_em
    }
    fato_votacoes {
        varchar id_votacao PK
        bigint id_proposicao
        varchar proposicao_objeto
        date data_votacao
        timestamptz data_hora_registro
        varchar sigla_orgao
        text descricao
        smallint aprovacao
    }
    fato_despesas {
        bigserial id_despesa PK
        int id_deputado FK
        int ano
        int mes
        varchar tipo_despesa
        varchar cod_documento
        varchar num_documento
        date data_documento
        numeric valor_documento
        numeric valor_liquido
        int parcela
    }

    dim_deputados ||--o{ fato_despesas : "possui"
    fato_proposicoes ||--o{ fato_votacoes : "referencia logica"
```

> Para exportar `docs/arquitetura.png`, renderize os diagramas acima via Mermaid CLI (`mmdc`) ou [mermaid.live](https://mermaid.live) e salve a imagem em `docs/arquitetura.png`.
