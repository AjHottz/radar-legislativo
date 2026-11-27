"""Camada de IA aplicada: classificacao por embeddings e resumo executivo (Onda 4)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI
from sqlalchemy import create_engine, text

from src.config import Settings, TAXONOMIA_TEMAS, load_settings
from src.load import log_pipeline_execution


logging.basicConfig(
    level=logging.INFO
    , format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Precos publicos de referencia por 1M tokens (USD)
PRICING_USD_PER_1M = {
    "text-embedding-3-small": {"input": 0.02, "output": 0.0}
    , "gpt-4o-mini": {"input": 0.15, "output": 0.60}
}

SUMMARY_SYSTEM_PROMPT = (
    "Voce e um analista senior de inteligencia legislativa da consultoria Bussola Publica. "
    "Resuma a proposicao legislativa abaixo em NO MAXIMO 3 linhas, usando portugues claro "
    "de negocios (nao juridiques), destacando impacto regulatorio, setor afetado e risco ou "
    "oportunidade para empresas."
)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Calcula a similaridade de cosseno entre dois vetores."""
    norm_a = float(np.linalg.norm(vec_a))
    norm_b = float(np.linalg.norm(vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def estimate_cost_usd(
    model: str
    , prompt_tokens: int
    , completion_tokens: int = 0
) -> float:
    """Calcula custo estimado em dolares americanos para auditoria."""
    rates = PRICING_USD_PER_1M.get(model, {"input": 0.0, "output": 0.0})
    return (
        (prompt_tokens / 1_000_000.0) * rates["input"]
        + (completion_tokens / 1_000_000.0) * rates["output"]
    )


def get_or_build_theme_embeddings(
    client: OpenAI
    , cache_dir: Path
    , embedding_model: str
) -> tuple[list[dict[str, Any]], int, float]:
    """Carrega embeddings dos 10 temas do cache local ou gera via OpenAI."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "temas_embeddings.json"

    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if (
            cached.get("model") == embedding_model
            and len(cached.get("temas", [])) == len(TAXONOMIA_TEMAS)
        ):
            logger.info("Embeddings dos temas carregados do cache local: %s", cache_file.name)
            return cached["temas"], 0, 0.0

    inputs = [f"{item['tema']}: {item['descricao']}" for item in TAXONOMIA_TEMAS]
    resp = client.embeddings.create(model=embedding_model, input=inputs)

    temas_com_vetor: list[dict[str, Any]] = []
    for item, data_item in zip(TAXONOMIA_TEMAS, resp.data):
        temas_com_vetor.append(
            {
                "tema": item["tema"]
                , "descricao": item["descricao"]
                , "embedding": data_item.embedding
            }
        )

    prompt_tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
    cost = estimate_cost_usd(embedding_model, prompt_tokens)

    payload = {
        "model": embedding_model
        , "temas": temas_com_vetor
    }
    cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "Embeddings dos %s temas gerados e salvos em cache (%s tokens).", len(temas_com_vetor), prompt_tokens
    )
    return temas_com_vetor, prompt_tokens, cost


def generate_executive_summary(
    client: OpenAI
    , model: str
    , sigla_tipo: str
    , numero: int | None
    , ano: int | None
    , ementa: str
    , tema_ia: str
) -> tuple[str, int, int]:
    """Gera resumo executivo em ate 3 linhas focando impacto de negocio."""
    user_prompt = (
        f"Proposicao: {sigla_tipo} {numero or ''}/{ano or ''}\n"
        f"Tema classificado: {tema_ia}\n"
        f"Ementa oficial: {ementa}"
    )
    resp = client.chat.completions.create(
        model=model
        , temperature=0.2
        , max_tokens=180
        , messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT}
            , {"role": "user", "content": user_prompt}
        ]
    )
    content = (resp.choices[0].message.content or "").strip()
    usage = resp.usage
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    return content, prompt_tokens, completion_tokens


def run_ai_enrichment(
    settings: Settings
    , limit: int = 10
    , skip_summary: bool = False
) -> dict[str, Any]:
    """Classifica proposicoes pendentes (tema_ia IS NULL) e gera resumos executivos."""
    settings.validate_database()
    settings.validate_openai()

    client = OpenAI(api_key=settings.openai_api_key)
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    try:
        temas, cache_tokens, cache_cost = get_or_build_theme_embeddings(
            client=client
            , cache_dir=settings.cache_dir
            , embedding_model=settings.openai_embedding_model
        )
        theme_vectors = [(t["tema"], np.array(t["embedding"], dtype=float)) for t in temas]

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id_proposicao, sigla_tipo, numero, ano, ementa "
                    "FROM fato_proposicoes "
                    "WHERE tema_ia IS NULL "
                    "ORDER BY data_apresentacao DESC NULLS LAST, id_proposicao DESC "
                    "LIMIT :limit;"
                )
                , {"limit": limit}
            ).mappings().all()

        if not rows:
            logger.info("Nenhuma proposicao pendente de classificacao (tema_ia IS NULL).")
            return {
                "processadas": 0
                , "tokens_totais": cache_tokens
                , "custo_estimado_usd": round(cache_cost, 6)
            }

        ementas = [row["ementa"] for row in rows]
        emb_resp = client.embeddings.create(
            model=settings.openai_embedding_model
            , input=ementas
        )
        emb_tokens = getattr(emb_resp.usage, "prompt_tokens", 0) or 0
        total_tokens = cache_tokens + emb_tokens
        total_cost = cache_cost + estimate_cost_usd(settings.openai_embedding_model, emb_tokens)

        resultados: list[dict[str, Any]] = []
        with engine.begin() as conn:
            for row, emb_data in zip(rows, emb_resp.data):
                prop_vec = np.array(emb_data.embedding, dtype=float)
                best_theme = ""
                best_score = -1.0
                for theme_name, theme_vec in theme_vectors:
                    score = cosine_similarity(prop_vec, theme_vec)
                    if score > best_score:
                        best_score = score
                        best_theme = theme_name

                resumo = None
                if not skip_summary:
                    resumo, p_tok, c_tok = generate_executive_summary(
                        client=client
                        , model=settings.openai_summary_model
                        , sigla_tipo=row["sigla_tipo"]
                        , numero=row["numero"]
                        , ano=row["ano"]
                        , ementa=row["ementa"]
                        , tema_ia=best_theme
                    )
                    total_tokens += p_tok + c_tok
                    total_cost += estimate_cost_usd(settings.openai_summary_model, p_tok, c_tok)

                vector_literal = "[" + ",".join(f"{v:.8f}" for v in emb_data.embedding) + "]"
                conn.execute(
                    text(
                        "UPDATE fato_proposicoes "
                        "SET tema_ia = :tema_ia "
                        "  , similaridade_tema = :similaridade "
                        "  , resumo_executivo = :resumo "
                        "  , embedding = CAST(:embedding AS vector) "
                        "  , processado_ia_em = NOW() "
                        "  , atualizado_em = NOW() "
                        "WHERE id_proposicao = :id_proposicao;"
                    )
                    , {
                        "tema_ia": best_theme
                        , "similaridade": round(best_score, 4)
                        , "resumo": resumo
                        , "embedding": vector_literal
                        , "id_proposicao": row["id_proposicao"]
                    }
                )
                resultados.append(
                    {
                        "id_proposicao": row["id_proposicao"]
                        , "tema_ia": best_theme
                        , "similaridade_tema": round(best_score, 4)
                    }
                )

        summary_report = {
            "processadas": len(resultados)
            , "tokens_totais": total_tokens
            , "custo_estimado_usd": round(total_cost, 6)
            , "amostra": resultados[:10]
        }
        log_pipeline_execution(
            engine=engine
            , etapa="ai_enrichment"
            , janela_dias=None
            , lidos=len(rows)
            , rejeitados=0
            , carregados=len(resultados)
            , tokens_ia=total_tokens
            , custo_usd=total_cost
            , status="SUCCESS"
            , detalhes=summary_report
        )
        logger.info(
            "Enriquecimento IA concluido: %s proposicoes | %s tokens | US$ %.6f"
            , len(resultados)
            , total_tokens
            , total_cost
        )
        return summary_report
    finally:
        engine.dispose()


def parse_args() -> argparse.Namespace:
    """Interpreta argumentos CLI."""
    parser = argparse.ArgumentParser(description="Camada de IA (Embeddings + Resumo)")
    parser.add_argument(
        "--limit"
        , type=int
        , default=None
        , help="Maximo de proposicoes por lote (padrao: AI_BATCH_LIMIT=10 para piloto)"
    )
    parser.add_argument(
        "--skip-summary"
        , action="store_true"
        , help="Executa apenas classificacao por embeddings (Caminho A)"
    )
    return parser.parse_args()


def main() -> int:
    """Ponto de entrada CLI da camada de IA."""
    args = parse_args()
    settings = load_settings()
    limit = args.limit if args.limit is not None else settings.ai_batch_limit
    report = run_ai_enrichment(
        settings=settings
        , limit=limit
        , skip_summary=args.skip_summary
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
