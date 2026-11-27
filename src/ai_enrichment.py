"""Camada de IA aplicada: classificacao por embeddings e resumo executivo (Onda 4)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from google import genai
from google.genai import _interactions_errors as genai_interactions_errors
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from openai import OpenAI
from sqlalchemy import create_engine, text

from src.config import Settings, TAXONOMIA_TEMAS, load_settings
from src.load import log_pipeline_execution


logging.basicConfig(
    level=logging.INFO
    , format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 1536

# Precos publicos de referencia por 1M tokens (USD) no tier pago (Free Tier Gemini = US$ 0)
PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "text-embedding-3-small": {"input": 0.02, "output": 0.0}
    , "gpt-4o-mini": {"input": 0.15, "output": 0.60}
    , "gemini-embedding-001": {"input": 0.0, "output": 0.0}
    , "gemini-3.5-flash-lite": {"input": 0.0, "output": 0.0}
    , "gemini-3.8-flash": {"input": 0.0, "output": 0.0}
    , "gemini-4-hydrogen": {"input": 0.0, "output": 0.0}
}

SUMMARY_SYSTEM_PROMPT = (
    "Voce e um analista senior de inteligencia legislativa da consultoria Bussola Publica. "
    "Baseie-se EXCLUSIVAMENTE na ementa oficial informada. Nunca invente ou suponha o merito "
    "de um projeto citado apenas por numero. Se a ementa for puramente procedimental (sem "
    "descrever o merito da materia), responda em 1 frase objetiva informando que se trata de "
    "tramite/parecer sem merito detalhado na ementa. Caso haja merito descrito, resuma em NO "
    "MAXIMO 3 linhas corridas (sem titulo nem markdown excessivo), em portugues claro de negocios, "
    "destacando impacto regulatorio, setor afetado e risco ou oportunidade para empresas."
)

SUBSTANTIVE_TYPES: tuple[str, ...] = (
    "PL"
    , "PLP"
    , "PEC"
    , "MPV"
    , "PDL"
    , "RIC"
    , "REQ"
)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Calcula a similaridade de cosseno entre dois vetores."""
    norm_a = float(np.linalg.norm(vec_a))
    norm_b = float(np.linalg.norm(vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def normalize_l2(vec: list[float]) -> list[float]:
    """Normaliza vetor em norma L2 unitaria (recomendado para dimensoes reduzidas)."""
    arr = np.array(vec, dtype=float)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return vec
    return (arr / norm).tolist()


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


def build_ai_client(settings: Settings, provider: str) -> tuple[Any, str, str]:
    """Instancia o cliente oficial e resolve os modelos do provedor selecionado."""
    if provider == "gemini":
        return (
            genai.Client(api_key=settings.gemini_api_key)
            , settings.gemini_embedding_model
            , settings.gemini_summary_model
        )
    return (
        OpenAI(api_key=settings.openai_api_key)
        , settings.openai_embedding_model
        , settings.openai_summary_model
    )


def embed_texts(
    provider: str
    , client: Any
    , model: str
    , texts: list[str]
) -> tuple[list[list[float]], int]:
    """Gera embeddings de 1536 dimensoes via Gemini ou OpenAI."""
    if provider == "gemini":
        resp = client.models.embed_content(
            model=model
            , contents=texts
            , config=genai_types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS
            )
        )
        vectors = [normalize_l2(list(item.values)) for item in resp.embeddings]
        approx_tokens = sum(max(len(t.split()), 1) for t in texts)
        return vectors, approx_tokens

    resp = client.embeddings.create(model=model, input=texts)
    vectors = [list(item.embedding) for item in resp.data]
    tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
    return vectors, tokens


def get_or_build_theme_embeddings(
    provider: str
    , client: Any
    , cache_dir: Path
    , embedding_model: str
) -> tuple[list[dict[str, Any]], int, float]:
    """Carrega embeddings dos 10 temas do cache local ou gera via API."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "temas_embeddings.json"

    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if (
            cached.get("provider") == provider
            and cached.get("model") == embedding_model
            and cached.get("dimensions") == EMBEDDING_DIMENSIONS
            and len(cached.get("temas", [])) == len(TAXONOMIA_TEMAS)
        ):
            logger.info("Embeddings dos temas carregados do cache local: %s", cache_file.name)
            return cached["temas"], 0, 0.0

    inputs = [f"{item['tema']}: {item['descricao']}" for item in TAXONOMIA_TEMAS]
    vectors, prompt_tokens = embed_texts(
        provider=provider
        , client=client
        , model=embedding_model
        , texts=inputs
    )

    temas_com_vetor: list[dict[str, Any]] = []
    for item, vec in zip(TAXONOMIA_TEMAS, vectors):
        temas_com_vetor.append(
            {
                "tema": item["tema"]
                , "descricao": item["descricao"]
                , "embedding": vec
            }
        )

    cost = estimate_cost_usd(embedding_model, prompt_tokens)
    payload = {
        "provider": provider
        , "model": embedding_model
        , "dimensions": EMBEDDING_DIMENSIONS
        , "temas": temas_com_vetor
    }
    cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "Embeddings dos %s temas gerados (%s/%s) e salvos em cache (%s tokens)."
        , len(temas_com_vetor)
        , provider
        , embedding_model
        , prompt_tokens
    )
    return temas_com_vetor, prompt_tokens, cost


def generate_executive_summary(
    provider: str
    , client: Any
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

    if provider == "gemini":
        fallback_models = [model] + [
            m
            for m in ("gemini-3.8-flash", "gemini-4-hydrogen")
            if m != model
        ]
        last_exc: Exception | None = None
        for current_model in fallback_models:
            for attempt in range(1, 3):
                try:
                    interaction = client.interactions.create(
                        model=current_model
                        , input=user_prompt
                        , system_instruction=SUMMARY_SYSTEM_PROMPT
                        , store=False
                        , generation_config={
                            "temperature": 0.2
                            , "max_output_tokens": 1500
                            , "thinking_level": "low"
                        }
                    )
                    content = (interaction.output_text or "").strip()
                    usage = interaction.usage
                    p_tok = (getattr(usage, "total_input_tokens", 0) or 0) if usage else 0
                    c_tok = (getattr(usage, "total_output_tokens", 0) or 0) if usage else 0
                    return content, p_tok, c_tok
                except (genai_errors.APIError, genai_interactions_errors.APIError) as exc:
                    last_exc = exc
                    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                    if status_code == 429 and attempt < 2:
                        wait_s = 10 * attempt
                        logger.warning(
                            "Rate limit Gemini (429) em %s (tentativa %s/2). Aguardando %ss..."
                            , current_model
                            , attempt
                            , wait_s
                        )
                        time.sleep(wait_s)
                        continue
                    if status_code in (500, 502, 503, 504):
                        logger.warning(
                            "Indisponibilidade HTTP %s em %s. Alternando para proximo fallback..."
                            , status_code
                            , current_model
                        )
                        break
                    raise
        raise RuntimeError(f"Todos os modelos Gemini de resumo falharam: {last_exc}")

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
    provider = settings.validate_ai()

    client, embedding_model, summary_model = build_ai_client(settings, provider)
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    try:
        temas, cache_tokens, cache_cost = get_or_build_theme_embeddings(
            provider=provider
            , client=client
            , cache_dir=settings.cache_dir
            , embedding_model=embedding_model
        )
        theme_vectors = [(t["tema"], np.array(t["embedding"], dtype=float)) for t in temas]

        substantive_sql = ", ".join(f"'{t}'" for t in SUBSTANTIVE_TYPES)
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id_proposicao, sigla_tipo, numero, ano, ementa "
                    "FROM fato_proposicoes "
                    "WHERE tema_ia IS NULL "
                    f"ORDER BY CASE WHEN sigla_tipo IN ({substantive_sql}) THEN 0 ELSE 1 END "
                    "  , data_apresentacao DESC NULLS LAST, id_proposicao DESC "
                    "LIMIT :limit;"
                )
                , {"limit": limit}
            ).mappings().all()

        if not rows:
            logger.info("Nenhuma proposicao pendente de classificacao (tema_ia IS NULL).")
            return {
                "provider": provider
                , "processadas": 0
                , "tokens_totais": cache_tokens
                , "custo_estimado_usd": round(cache_cost, 6)
            }

        ementas = [row["ementa"] for row in rows]
        prop_vectors, emb_tokens = embed_texts(
            provider=provider
            , client=client
            , model=embedding_model
            , texts=ementas
        )
        total_tokens = cache_tokens + emb_tokens
        total_cost = cache_cost + estimate_cost_usd(embedding_model, emb_tokens)

        resultados: list[dict[str, Any]] = []
        with engine.begin() as conn:
            for row, vec in zip(rows, prop_vectors):
                prop_vec = np.array(vec, dtype=float)
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
                        provider=provider
                        , client=client
                        , model=summary_model
                        , sigla_tipo=row["sigla_tipo"]
                        , numero=row["numero"]
                        , ano=row["ano"]
                        , ementa=row["ementa"]
                        , tema_ia=best_theme
                    )
                    total_tokens += p_tok + c_tok
                    total_cost += estimate_cost_usd(summary_model, p_tok, c_tok)
                    if provider == "gemini":
                        time.sleep(0.5)

                vector_literal = "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
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
                        , "resumo_executivo": resumo
                    }
                )

        summary_report = {
            "provider": provider
            , "embedding_model": embedding_model
            , "summary_model": None if skip_summary else summary_model
            , "processadas": len(resultados)
            , "tokens_totais": total_tokens
            , "custo_estimado_usd": round(total_cost, 6)
            , "amostra": resultados[:10]
        }
        log_pipeline_execution(
            engine=engine
            , etapa=f"ai_enrichment_{provider}"
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
            "Enriquecimento IA (%s) concluido: %s proposicoes | %s tokens | US$ %.6f"
            , provider
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
