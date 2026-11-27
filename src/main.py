"""Orquestrador CLI ponta a ponta do pipeline Radar Legislativo."""

from __future__ import annotations

import argparse
import json
import sys

from src.ai_enrichment import run_ai_enrichment
from src.config import load_settings
from src.extract import run_extraction
from src.load import run_load
from src.transform import run_transform


def parse_args() -> argparse.Namespace:
    """Interpreta argumentos de execucao do pipeline."""
    parser = argparse.ArgumentParser(description="Orquestrador Pipeline Radar Legislativo")
    parser.add_argument(
        "--step"
        , choices=["all", "extract", "transform", "load", "ai"]
        , default="all"
        , help="Etapa do pipeline a executar"
    )
    parser.add_argument("--days", type=int, default=None, help="Janela em dias (ex.: 7 ou 30)")
    parser.add_argument(
        "--max-deputados"
        , type=int
        , default=0
        , help="Limite opcional de deputados em despesas (0 = todos)"
    )
    parser.add_argument("--run-date", type=str, default=None, help="Data YYYY-MM-DD do lote")
    parser.add_argument("--limit", type=int, default=None, help="Limite de itens para IA")
    parser.add_argument(
        "--skip-ai"
        , action="store_true"
        , help="Pula a etapa de IA (util antes de configurar OPENAI_API_KEY)"
    )
    return parser.parse_args()


def main() -> int:
    """Executa o fluxo completo ou a etapa solicitada."""
    args = parse_args()
    settings = load_settings()
    days = args.days if args.days is not None else settings.ingestion_days_window
    limit = args.limit if args.limit is not None else settings.ai_batch_limit
    output: dict[str, object] = {}

    if args.step in ("all", "extract"):
        output["extract"] = run_extraction(
            settings=settings
            , days=days
            , max_deputados=args.max_deputados
            , run_date=args.run_date
        )

    if args.step in ("all", "transform", "load"):
        dataframes, qa_report = run_transform(settings=settings, run_date=args.run_date)
        output["transform_qa"] = qa_report

        if args.step in ("all", "load"):
            output["load"] = run_load(
                settings=settings
                , dataframes=dataframes
                , qa_report=qa_report
                , janela_dias=days
            )

    if args.step in ("all", "ai") and not args.skip_ai:
        if not settings.is_ai_configured() and args.step == "all":
            output["ai"] = {
                "status": "SKIPPED"
                , "motivo": "Chave de IA (GEMINI_API_KEY ou OPENAI_API_KEY) pendente no .env"
            }
        else:
            output["ai"] = run_ai_enrichment(settings=settings, limit=limit)

    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
