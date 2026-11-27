"""Carga idempotente em PostgreSQL/Supabase com SQLAlchemy e psycopg2 (Onda 3)."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from src.config import Settings, load_settings
from src.transform import run_transform


logging.basicConfig(
    level=logging.INFO
    , format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def clean_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Converte DataFrame Pandas em lista de dicts com None no lugar de NaN/NaT."""
    if df.empty:
        return []
    records = df.to_dict(orient="records")
    cleaned: list[dict[str, Any]] = []
    for row in records:
        clean_row: dict[str, Any] = {}
        for key, value in row.items():
            if value is None or value is pd.NA:
                clean_row[key] = None
            elif isinstance(value, float) and math.isnan(value):
                clean_row[key] = None
            elif isinstance(value, pd.Timestamp):
                clean_row[key] = None if pd.isna(value) else value.to_pydatetime()
            else:
                clean_row[key] = value
        cleaned.append(clean_row)
    return cleaned


def ensure_schema(engine: Engine, sql_file: Path) -> None:
    """Executa o DDL idempotente sql/01_schema_star.sql caso as tabelas nao existam."""
    if not sql_file.exists():
        raise FileNotFoundError(f"Arquivo DDL nao encontrado: {sql_file}")
    ddl_sql = sql_file.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl_sql)
    logger.info("DDL verificado/aplicado a partir de %s", sql_file.name)


def upsert_dataframe(
    engine: Engine
    , table: Table
    , df: pd.DataFrame
    , conflict_cols: list[str]
    , chunk_size: int = 500
) -> int:
    """Executa INSERT ... ON CONFLICT DO UPDATE em lotes transacionais."""
    records = clean_records(df)
    if not records:
        return 0

    update_cols = [
        col.name
        for col in table.columns
        if col.name not in conflict_cols and col.name not in ("id_despesa",)
    ]

    total = 0
    with engine.begin() as conn:
        for idx in range(0, len(records), chunk_size):
            batch = records[idx:idx + chunk_size]
            stmt = pg_insert(table).values(batch)
            update_map = {
                col: getattr(stmt.excluded, col)
                for col in update_cols
                if col in batch[0]
            }
            if "atualizado_em" in table.columns:
                update_map["atualizado_em"] = text("NOW()")
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_cols
                , set_=update_map
            )
            conn.execute(stmt)
            total += len(batch)
    return total


def log_pipeline_execution(
    engine: Engine
    , etapa: str
    , janela_dias: int | None
    , lidos: int
    , rejeitados: int
    , carregados: int
    , status: str
    , detalhes: dict[str, Any]
    , tokens_ia: int = 0
    , custo_usd: float = 0.0
) -> None:
    """Registra metricas de observabilidade na tabela log_execucoes_pipeline."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO log_execucoes_pipeline ("
                " etapa, janela_dias, registros_lidos, registros_rejeitados"
                " , registros_carregados, tokens_ia, custo_estimado_usd, status, detalhes"
                ") VALUES ("
                " :etapa, :janela_dias, :lidos, :rejeitados"
                " , :carregados, :tokens_ia, :custo_usd, :status, CAST(:detalhes AS JSONB)"
                ");"
            )
            , {
                "etapa": etapa
                , "janela_dias": janela_dias
                , "lidos": lidos
                , "rejeitados": rejeitados
                , "carregados": carregados
                , "tokens_ia": tokens_ia
                , "custo_usd": custo_usd
                , "status": status
                , "detalhes": json.dumps(detalhes, ensure_ascii=False)
            }
        )


def run_load(
    settings: Settings
    , dataframes: dict[str, pd.DataFrame]
    , qa_report: dict[str, Any]
    , janela_dias: int | None = None
) -> dict[str, int]:
    """Carrega dimensoes e fatos em ordem referencial no Supabase/PostgreSQL."""
    settings.validate_database()
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    try:
        ensure_schema(engine, settings.sql_dir / "01_schema_star.sql")

        metadata = MetaData()
        metadata.reflect(
            bind=engine
            , only=[
                "dim_partidos"
                , "dim_deputados"
                , "fato_proposicoes"
                , "fato_votacoes"
                , "fato_despesas"
            ]
        )

        load_plan: list[tuple[str, list[str]]] = [
            ("dim_partidos", ["id_partido"])
            , ("dim_deputados", ["id_deputado"])
            , ("fato_proposicoes", ["id_proposicao"])
            , ("fato_votacoes", ["id_votacao"])
            , (
                "fato_despesas"
                , ["id_deputado", "cod_documento", "num_documento", "parcela", "valor_liquido"]
            )
        ]

        loaded_counts: dict[str, int] = {}
        for table_name, conflict_cols in load_plan:
            df = dataframes.get(table_name, pd.DataFrame())
            count = upsert_dataframe(
                engine=engine
                , table=metadata.tables[table_name]
                , df=df
                , conflict_cols=conflict_cols
            )
            loaded_counts[table_name] = count
            logger.info("Carga idempotente %s: %s registros processados.", table_name, count)

        entidades_qa = qa_report.get("entidades", {})
        total_lidos = sum(item.get("lidos", 0) for item in entidades_qa.values())
        total_rejeitados = sum(item.get("rejeitados", 0) for item in entidades_qa.values())
        total_carregados = sum(loaded_counts.values())

        log_pipeline_execution(
            engine=engine
            , etapa="etl_carga_star_schema"
            , janela_dias=janela_dias
            , lidos=total_lidos
            , rejeitados=total_rejeitados
            , carregados=total_carregados
            , status="SUCCESS"
            , detalhes={"qa": qa_report, "carregados": loaded_counts}
        )
        return loaded_counts
    finally:
        engine.dispose()


def parse_args() -> argparse.Namespace:
    """Interpreta argumentos CLI."""
    parser = argparse.ArgumentParser(description="Carga Star Schema no Supabase")
    parser.add_argument("--run-date", type=str, default=None, help="Data YYYY-MM-DD do lote raw")
    parser.add_argument("--days", type=int, default=None, help="Janela em dias usada no lote")
    return parser.parse_args()


def main() -> int:
    """Ponto de entrada CLI de transformacao + carga."""
    args = parse_args()
    settings = load_settings()
    dataframes, qa_report = run_transform(settings=settings, run_date=args.run_date)
    loaded = run_load(
        settings=settings
        , dataframes=dataframes
        , qa_report=qa_report
        , janela_dias=args.days or settings.ingestion_days_window
    )
    print(json.dumps(loaded, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
