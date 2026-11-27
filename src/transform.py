"""Transformacao, limpeza e validacoes de qualidade com Pandas (Onda 3)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import Settings, load_settings


logging.basicConfig(
    level=logging.INFO
    , format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def resolve_raw_file(raw_dir: Path, entity: str, run_date: str | None = None) -> Path:
    """Localiza o arquivo JSON bruto da data informada ou o mais recente da entidade."""
    entity_dir = raw_dir / entity
    if run_date:
        target = entity_dir / f"{run_date}.json"
        if not target.exists():
            raise FileNotFoundError(f"Arquivo raw nao encontrado: {target}")
        return target

    candidates = sorted(
        [
            p
            for p in entity_dir.glob("*.json")
            if not p.name.endswith("_checkpoint.json")
        ]
    )
    if not candidates:
        raise FileNotFoundError(f"Nenhum arquivo raw encontrado em {entity_dir}")
    return candidates[-1]


def load_raw_records(file_path: Path) -> list[dict[str, Any]]:
    """Carrega a lista 'dados' de um JSON salvo pela camada de extracao."""
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return payload.get("dados", [])


def extract_trailing_int(uri: Any) -> int | None:
    """Extrai identificador numerico ao final de uma URI da API da Camara."""
    if not isinstance(uri, str) or not uri.strip():
        return None
    tail = uri.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


def transform_partidos(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, int]]:
    """Normaliza e valida dim_partidos."""
    raw_count = len(records)
    if not records:
        return pd.DataFrame(), {"lidos": 0, "rejeitados": 0, "deduplicados": 0, "validos": 0}

    df = pd.json_normalize(records)
    df = df.rename(columns={"id": "id_partido"})
    df["id_partido"] = pd.to_numeric(df.get("id_partido"), errors="coerce")
    df["sigla"] = df.get("sigla", "").astype(str).str.strip()
    df["nome"] = df.get("nome", "").astype(str).str.strip()
    df["uri"] = df.get("uri")

    valid_mask = df["id_partido"].notna() & (df["sigla"] != "") & (df["nome"] != "")
    rejeitados = int((~valid_mask).sum())
    df = df.loc[valid_mask, ["id_partido", "sigla", "nome", "uri"]].copy()
    df["id_partido"] = df["id_partido"].astype(int)

    before_dedup = len(df)
    df = df.drop_duplicates(subset=["id_partido"], keep="last").reset_index(drop=True)
    deduplicados = before_dedup - len(df)
    return df, {
        "lidos": raw_count
        , "rejeitados": rejeitados
        , "deduplicados": deduplicados
        , "validos": len(df)
    }


def transform_deputados(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, int]]:
    """Normaliza e valida dim_deputados."""
    raw_count = len(records)
    if not records:
        return pd.DataFrame(), {"lidos": 0, "rejeitados": 0, "deduplicados": 0, "validos": 0}

    df = pd.json_normalize(records)
    df = df.rename(
        columns={
            "id": "id_deputado"
            , "siglaPartido": "sigla_partido"
            , "siglaUf": "sigla_uf"
            , "urlFoto": "url_foto"
            , "idLegislatura": "id_legislatura"
        }
    )
    df["id_deputado"] = pd.to_numeric(df.get("id_deputado"), errors="coerce")
    df["id_partido"] = df.get("uriPartido", pd.Series(dtype=object)).apply(extract_trailing_int)
    df["id_legislatura"] = pd.to_numeric(df.get("id_legislatura"), errors="coerce")
    df["nome"] = df.get("nome", "").astype(str).str.strip()
    df["sigla_uf"] = df.get("sigla_uf", "").astype(str).str.strip().str.upper().str[:2]

    valid_mask = df["id_deputado"].notna() & (df["nome"] != "")
    rejeitados = int((~valid_mask).sum())

    cols = [
        "id_deputado"
        , "nome"
        , "id_partido"
        , "sigla_partido"
        , "sigla_uf"
        , "email"
        , "url_foto"
        , "id_legislatura"
        , "uri"
    ]
    for col in cols:
        if col not in df.columns:
            df[col] = None

    df = df.loc[valid_mask, cols].copy()
    df["id_deputado"] = df["id_deputado"].astype(int)
    df["id_partido"] = df["id_partido"].astype("Int64")
    df["id_legislatura"] = df["id_legislatura"].astype("Int64")

    before_dedup = len(df)
    df = df.drop_duplicates(subset=["id_deputado"], keep="last").reset_index(drop=True)
    deduplicados = before_dedup - len(df)
    return df, {
        "lidos": raw_count
        , "rejeitados": rejeitados
        , "deduplicados": deduplicados
        , "validos": len(df)
    }


def transform_proposicoes(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, int]]:
    """Normaliza e valida fato_proposicoes."""
    raw_count = len(records)
    if not records:
        return pd.DataFrame(), {"lidos": 0, "rejeitados": 0, "deduplicados": 0, "validos": 0}

    df = pd.json_normalize(records)
    df = df.rename(
        columns={
            "id": "id_proposicao"
            , "siglaTipo": "sigla_tipo"
            , "codTipo": "cod_tipo"
            , "dataApresentacao": "data_apresentacao"
        }
    )
    df["id_proposicao"] = pd.to_numeric(df.get("id_proposicao"), errors="coerce")
    df["cod_tipo"] = pd.to_numeric(df.get("cod_tipo"), errors="coerce")
    df["numero"] = pd.to_numeric(df.get("numero"), errors="coerce")
    df["ano"] = pd.to_numeric(df.get("ano"), errors="coerce")
    df["sigla_tipo"] = df.get("sigla_tipo", "").astype(str).str.strip()
    df["ementa"] = df.get("ementa", "").fillna("").astype(str).str.strip()
    df["data_apresentacao"] = pd.to_datetime(
        df.get("data_apresentacao")
        , errors="coerce"
    )

    max_allowed_dt = pd.Timestamp(date.today() + timedelta(days=2))
    valid_mask = (
        df["id_proposicao"].notna()
        & (df["sigla_tipo"] != "")
        & (df["ementa"] != "")
        & df["data_apresentacao"].notna()
        & (df["data_apresentacao"] <= max_allowed_dt)
    )
    rejeitados = int((~valid_mask).sum())

    cols = [
        "id_proposicao"
        , "sigla_tipo"
        , "cod_tipo"
        , "numero"
        , "ano"
        , "ementa"
        , "data_apresentacao"
        , "uri"
    ]
    df = df.loc[valid_mask, cols].copy()
    df["id_proposicao"] = df["id_proposicao"].astype(int)
    df["cod_tipo"] = df["cod_tipo"].astype("Int64")
    df["numero"] = df["numero"].astype("Int64")
    df["ano"] = df["ano"].astype("Int64")
    df["data_apresentacao"] = df["data_apresentacao"].dt.tz_localize(
        "America/Sao_Paulo"
        , ambiguous="NaT"
        , nonexistent="shift_forward"
    )

    before_dedup = len(df)
    df = df.drop_duplicates(subset=["id_proposicao"], keep="last").reset_index(drop=True)
    deduplicados = before_dedup - len(df)
    return df, {
        "lidos": raw_count
        , "rejeitados": rejeitados
        , "deduplicados": deduplicados
        , "validos": len(df)
    }


def transform_votacoes(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, int]]:
    """Normaliza e valida fato_votacoes."""
    raw_count = len(records)
    if not records:
        return pd.DataFrame(), {"lidos": 0, "rejeitados": 0, "deduplicados": 0, "validos": 0}

    df = pd.json_normalize(records)
    df = df.rename(
        columns={
            "id": "id_votacao"
            , "proposicaoObjeto": "proposicao_objeto"
            , "uriProposicaoObjeto": "uri_proposicao_objeto"
            , "data": "data_votacao"
            , "dataHoraRegistro": "data_hora_registro"
            , "siglaOrgao": "sigla_orgao"
        }
    )
    df["id_votacao"] = df.get("id_votacao", "").fillna("").astype(str).str.strip()
    df["id_proposicao"] = df.get("uri_proposicao_objeto", pd.Series(dtype=object)).apply(
        extract_trailing_int
    )
    df["data_votacao"] = pd.to_datetime(df.get("data_votacao"), errors="coerce").dt.date
    df["data_hora_registro"] = pd.to_datetime(df.get("data_hora_registro"), errors="coerce")
    df["aprovacao"] = pd.to_numeric(df.get("aprovacao"), errors="coerce")

    valid_mask = df["id_votacao"] != ""
    rejeitados = int((~valid_mask).sum())

    cols = [
        "id_votacao"
        , "id_proposicao"
        , "proposicao_objeto"
        , "uri_proposicao_objeto"
        , "data_votacao"
        , "data_hora_registro"
        , "sigla_orgao"
        , "descricao"
        , "aprovacao"
        , "uri"
    ]
    for col in cols:
        if col not in df.columns:
            df[col] = None

    df = df.loc[valid_mask, cols].copy()
    df["id_proposicao"] = df["id_proposicao"].astype("Int64")
    df["aprovacao"] = df["aprovacao"].astype("Int64")
    df["data_hora_registro"] = df["data_hora_registro"].dt.tz_localize(
        "America/Sao_Paulo"
        , ambiguous="NaT"
        , nonexistent="shift_forward"
    )

    before_dedup = len(df)
    df = df.drop_duplicates(subset=["id_votacao"], keep="last").reset_index(drop=True)
    deduplicados = before_dedup - len(df)
    return df, {
        "lidos": raw_count
        , "rejeitados": rejeitados
        , "deduplicados": deduplicados
        , "validos": len(df)
    }


def transform_despesas(
    records: list[dict[str, Any]]
    , valid_deputado_ids: set[int]
    , quarantine_path: Path | None = None
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Normaliza e valida fato_despesas, filtrando valores negativos para quarentena."""
    raw_count = len(records)
    if not records:
        return pd.DataFrame(), {
            "lidos": 0
            , "rejeitados_negativos": 0
            , "rejeitados_outros": 0
            , "rejeitados": 0
            , "deduplicados": 0
            , "validos": 0
        }

    df = pd.json_normalize(records)
    df["id_deputado"] = pd.to_numeric(df.get("idDeputado"), errors="coerce")
    df["ano"] = pd.to_numeric(df.get("ano"), errors="coerce")
    df["mes"] = pd.to_numeric(df.get("mes"), errors="coerce")
    df["valor_documento"] = pd.to_numeric(df.get("valorDocumento"), errors="coerce")
    df["valor_liquido"] = pd.to_numeric(df.get("valorLiquido"), errors="coerce")
    df["valor_glosa"] = pd.to_numeric(df.get("valorGlosa"), errors="coerce").fillna(0.0)
    df["parcela"] = pd.to_numeric(df.get("parcela"), errors="coerce").fillna(0).astype(int)
    df["cod_documento"] = df.get("codDocumento", "").fillna("").astype(str).str.strip()
    df["num_documento"] = df.get("numDocumento", "").fillna("").astype(str).str.strip()
    df["data_documento_dt"] = pd.to_datetime(df.get("dataDocumento"), errors="coerce")

    # Verificacao explicita exigida pelo SPEC: df[df['valorLiquido'] < 0]
    neg_mask = (df["valor_liquido"] < 0) | (df["valor_documento"] < 0)
    rejeitados_negativos = int(neg_mask.sum())

    if quarantine_path and rejeitados_negativos > 0:
        quarantine_sample = df.loc[
            neg_mask
            , ["id_deputado", "ano", "mes", "cod_documento", "num_documento", "valor_documento", "valor_liquido"]
        ].head(50)
        quarantine_path.write_text(
            quarantine_sample.to_json(orient="records", force_ascii=False, indent=2)
            , encoding="utf-8"
        )

    max_date = pd.Timestamp(date.today() + timedelta(days=30))
    date_valid = df["data_documento_dt"].isna() | (
        (df["data_documento_dt"] >= pd.Timestamp("2020-01-01"))
        & (df["data_documento_dt"] <= max_date)
    )

    valid_mask = (
        df["id_deputado"].isin(valid_deputado_ids)
        & df["ano"].notna()
        & df["mes"].between(1, 12)
        & df["valor_documento"].notna()
        & df["valor_liquido"].notna()
        & (df["valor_documento"] >= 0)
        & (df["valor_liquido"] >= 0)
        & (df["valor_glosa"] >= 0)
        & date_valid
    )

    rejeitados_total = int((~valid_mask).sum())
    rejeitados_outros = max(rejeitados_total - rejeitados_negativos, 0)

    df = df.loc[valid_mask].copy()
    df["id_deputado"] = df["id_deputado"].astype(int)
    df["ano"] = df["ano"].astype(int)
    df["mes"] = df["mes"].astype(int)
    df["data_documento"] = df["data_documento_dt"].dt.date
    df["valor_documento"] = df["valor_documento"].round(2)
    df["valor_liquido"] = df["valor_liquido"].round(2)
    df["valor_glosa"] = df["valor_glosa"].round(2)

    df = df.rename(
        columns={
            "tipoDespesa": "tipo_despesa"
            , "tipoDocumento": "tipo_documento"
            , "nomeFornecedor": "nome_fornecedor"
            , "cnpjCpfFornecedor": "cnpj_cpf_fornecedor"
            , "urlDocumento": "url_documento"
        }
    )

    cols = [
        "id_deputado"
        , "ano"
        , "mes"
        , "tipo_despesa"
        , "tipo_documento"
        , "cod_documento"
        , "num_documento"
        , "data_documento"
        , "nome_fornecedor"
        , "cnpj_cpf_fornecedor"
        , "valor_documento"
        , "valor_liquido"
        , "valor_glosa"
        , "parcela"
        , "url_documento"
    ]
    for col in cols:
        if col not in df.columns:
            df[col] = None

    df = df[cols].copy()
    before_dedup = len(df)
    df = df.drop_duplicates(
        subset=["id_deputado", "cod_documento", "num_documento", "parcela", "valor_liquido"]
        , keep="last"
    ).reset_index(drop=True)
    deduplicados = before_dedup - len(df)

    return df, {
        "lidos": raw_count
        , "rejeitados_negativos": rejeitados_negativos
        , "rejeitados_outros": rejeitados_outros
        , "rejeitados": rejeitados_total
        , "deduplicados": deduplicados
        , "validos": len(df)
    }


def run_transform(
    settings: Settings
    , run_date: str | None = None
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Executa todas as transformacoes a partir da camada raw e grava relatorio de QA."""
    settings.cache_dir.mkdir(parents=True, exist_ok=True)

    p_file = resolve_raw_file(settings.raw_dir, "partidos", run_date)
    d_file = resolve_raw_file(settings.raw_dir, "deputados", run_date)
    pr_file = resolve_raw_file(settings.raw_dir, "proposicoes", run_date)
    v_file = resolve_raw_file(settings.raw_dir, "votacoes", run_date)
    desp_file = resolve_raw_file(settings.raw_dir, "despesas", run_date)

    resolved_date = run_date or p_file.stem

    df_partidos, qa_partidos = transform_partidos(load_raw_records(p_file))
    df_deputados, qa_deputados = transform_deputados(load_raw_records(d_file))
    df_proposicoes, qa_proposicoes = transform_proposicoes(load_raw_records(pr_file))
    df_votacoes, qa_votacoes = transform_votacoes(load_raw_records(v_file))

    valid_dep_ids = set(df_deputados["id_deputado"].tolist()) if not df_deputados.empty else set()
    quarantine_file = settings.cache_dir / f"quarantine_despesas_{resolved_date}.json"
    df_despesas, qa_despesas = transform_despesas(
        load_raw_records(desp_file)
        , valid_deputado_ids=valid_dep_ids
        , quarantine_path=quarantine_file
    )

    qa_report = {
        "run_date": resolved_date
        , "entidades": {
            "dim_partidos": qa_partidos
            , "dim_deputados": qa_deputados
            , "fato_proposicoes": qa_proposicoes
            , "fato_votacoes": qa_votacoes
            , "fato_despesas": qa_despesas
        }
    }
    qa_path = settings.cache_dir / f"transform_qa_{resolved_date}.json"
    qa_path.write_text(json.dumps(qa_report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Transformacao concluida. Relatorio QA salvo em %s", qa_path)

    dataframes = {
        "dim_partidos": df_partidos
        , "dim_deputados": df_deputados
        , "fato_proposicoes": df_proposicoes
        , "fato_votacoes": df_votacoes
        , "fato_despesas": df_despesas
    }
    return dataframes, qa_report


def parse_args() -> argparse.Namespace:
    """Interpreta argumentos CLI."""
    parser = argparse.ArgumentParser(description="Transformacao Pandas e QA")
    parser.add_argument("--run-date", type=str, default=None, help="Data YYYY-MM-DD do raw")
    return parser.parse_args()


def main() -> int:
    """Ponto de entrada CLI da transformacao."""
    args = parse_args()
    settings = load_settings()
    _, qa_report = run_transform(settings=settings, run_date=args.run_date)
    print(json.dumps(qa_report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
