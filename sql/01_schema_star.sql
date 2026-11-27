-- ============================================================================
-- Radar Legislativo (Bussola Publica) - DDL Star Schema (PostgreSQL / Supabase)
-- Congelado apos exploracao real da API Camara v2 (Onda 1)
-- Convencao: leading commas
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ----------------------------------------------------------------------------
-- Dimensao: Partidos Politicos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_partidos (
    id_partido INTEGER PRIMARY KEY
    , sigla VARCHAR(20) NOT NULL
    , nome VARCHAR(255) NOT NULL
    , uri TEXT
    , atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Dimensao: Deputados Federais
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_deputados (
    id_deputado INTEGER PRIMARY KEY
    , nome VARCHAR(255) NOT NULL
    , id_partido INTEGER
    , sigla_partido VARCHAR(20)
    , sigla_uf CHAR(2)
    , email VARCHAR(255)
    , url_foto TEXT
    , id_legislatura INTEGER
    , uri TEXT
    , atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_deputados_partido
    ON dim_deputados (sigla_partido);

CREATE INDEX IF NOT EXISTS idx_dim_deputados_uf
    ON dim_deputados (sigla_uf);

-- ----------------------------------------------------------------------------
-- Fato: Proposicoes Legislativas + Enriquecimento de IA
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_proposicoes (
    id_proposicao BIGINT PRIMARY KEY
    , sigla_tipo VARCHAR(20) NOT NULL
    , cod_tipo INTEGER
    , numero INTEGER
    , ano INTEGER
    , ementa TEXT NOT NULL
    , data_apresentacao TIMESTAMPTZ
    , uri TEXT
    , tema_ia VARCHAR(100)
    , similaridade_tema NUMERIC(6, 4)
    , resumo_executivo TEXT
    , embedding VECTOR(1536)
    , processado_ia_em TIMESTAMPTZ
    , atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fato_proposicoes_data
    ON fato_proposicoes (data_apresentacao DESC);

CREATE INDEX IF NOT EXISTS idx_fato_proposicoes_tema_ia
    ON fato_proposicoes (tema_ia);

-- ----------------------------------------------------------------------------
-- Fato: Votacoes em Plenario e Comissoes
-- Nota: id_proposicao permanece sem FK estrita porque votacoes recentes
-- frequentemente referenciam proposicoes protocoladas em anos anteriores.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_votacoes (
    id_votacao VARCHAR(100) PRIMARY KEY
    , id_proposicao BIGINT
    , proposicao_objeto VARCHAR(255)
    , uri_proposicao_objeto TEXT
    , data_votacao DATE
    , data_hora_registro TIMESTAMPTZ
    , sigla_orgao VARCHAR(50)
    , descricao TEXT
    , aprovacao SMALLINT
    , uri TEXT
    , atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fato_votacoes_data
    ON fato_votacoes (data_hora_registro DESC);

CREATE INDEX IF NOT EXISTS idx_fato_votacoes_proposicao
    ON fato_votacoes (id_proposicao);

-- ----------------------------------------------------------------------------
-- Fato: Despesas da Cota Parlamentar (CEAP)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_despesas (
    id_despesa BIGSERIAL PRIMARY KEY
    , id_deputado INTEGER NOT NULL REFERENCES dim_deputados(id_deputado)
    , ano INTEGER NOT NULL
    , mes INTEGER NOT NULL
    , tipo_despesa VARCHAR(255)
    , tipo_documento VARCHAR(100)
    , cod_documento VARCHAR(100) NOT NULL DEFAULT ''
    , num_documento VARCHAR(100) NOT NULL DEFAULT ''
    , data_documento DATE
    , nome_fornecedor VARCHAR(255)
    , cnpj_cpf_fornecedor VARCHAR(20)
    , valor_documento NUMERIC(12, 2) NOT NULL CHECK (valor_documento >= 0)
    , valor_liquido NUMERIC(12, 2) NOT NULL CHECK (valor_liquido >= 0)
    , valor_glosa NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (valor_glosa >= 0)
    , parcela INTEGER NOT NULL DEFAULT 0
    , url_documento TEXT
    , atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
    , CONSTRAINT uq_despesa_doc UNIQUE (id_deputado, cod_documento, num_documento, parcela, valor_liquido)
);

CREATE INDEX IF NOT EXISTS idx_fato_despesas_deputado_ym
    ON fato_despesas (id_deputado, ano, mes);

-- ----------------------------------------------------------------------------
-- Governanca: Tabela de Execucoes do Pipeline (Observabilidade / Auditoria)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_execucoes_pipeline (
    id_execucao BIGSERIAL PRIMARY KEY
    , etapa VARCHAR(50) NOT NULL
    , janela_dias INTEGER
    , registros_lidos INTEGER NOT NULL DEFAULT 0
    , registros_rejeitados INTEGER NOT NULL DEFAULT 0
    , registros_carregados INTEGER NOT NULL DEFAULT 0
    , tokens_ia INTEGER NOT NULL DEFAULT 0
    , custo_estimado_usd NUMERIC(10, 6) NOT NULL DEFAULT 0
    , status VARCHAR(20) NOT NULL
    , detalhes JSONB
    , executado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Seguranca Supabase: Habilitar RLS em tabelas expostas no schema public
-- Com acesso via role postgres (SQLAlchemy / n8n) e politicas de leitura
-- publica controlada para vitrine de portfolio, se habilitado.
-- ----------------------------------------------------------------------------
ALTER TABLE dim_partidos ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_deputados ENABLE ROW LEVEL SECURITY;
ALTER TABLE fato_proposicoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE fato_votacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE fato_despesas ENABLE ROW LEVEL SECURITY;
ALTER TABLE log_execucoes_pipeline ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'dim_partidos'
        , 'dim_deputados'
        , 'fato_proposicoes'
        , 'fato_votacoes'
        , 'fato_despesas'
    ]
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = tbl
              AND policyname = 'leitura_publica_portfolio'
        ) THEN
            EXECUTE format(
                'CREATE POLICY leitura_publica_portfolio ON public.%I FOR SELECT TO anon, authenticated USING (true);'
                , tbl
            );
        END IF;
    END LOOP;
END $$;
