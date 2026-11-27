"""Extrator resiliente da API Dados Abertos da Camara dos Deputados (Onda 2)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from src.config import Settings, load_settings


logging.basicConfig(
    level=logging.INFO
    , format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Accept": "application/json"
    , "User-Agent": "RadarLegislativo-BussolaPublica/1.0"
}


def request_with_retry(
    session: requests.Session
    , url: str
    , params: dict[str, Any] | None = None
    , max_retries: int = 4
    , timeout: int = 30
) -> dict[str, Any]:
    """Executa requisicao GET com retentativas e backoff exponencial."""
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(
                url
                , params=params
                , headers=DEFAULT_HEADERS
                , timeout=timeout
            )
            if response.status_code in (429, 500, 502, 503, 504):
                wait_seconds = min(2 ** attempt, 16)
                logger.warning(
                    "HTTP %s em %s (tentativa %s/%s). Aguardando %ss..."
                    , response.status_code
                    , url
                    , attempt
                    , max_retries
                    , wait_seconds
                )
                time.sleep(wait_seconds)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            wait_seconds = min(2 ** attempt, 16)
            logger.warning(
                "Erro na requisicao %s (tentativa %s/%s): %s. Aguardando %ss..."
                , url
                , attempt
                , max_retries
                , exc
                , wait_seconds
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"Falha definitiva ao consultar {url}: {last_exc}")


def fetch_all_pages(
    session: requests.Session
    , url: str
    , params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Percorre todas as paginas seguindo o link rel='next' em loop while."""
    all_records: list[dict[str, Any]] = []
    next_url: str | None = url
    next_params: dict[str, Any] | None = dict(params or {})
    page_count = 0

    while next_url:
        payload = request_with_retry(session, next_url, params=next_params)
        dados = payload.get("dados", [])
        if not dados:
            break
        all_records.extend(dados)
        page_count += 1

        links = payload.get("links", [])
        next_href = next((link.get("href") for link in links if link.get("rel") == "next"), None)
        next_url = next_href
        next_params = None

    logger.debug("Coleta concluida em %s (%s paginas, %s itens)", url, page_count, len(all_records))
    return all_records


def save_raw_json(
    raw_dir: Path
    , entity: str
    , run_date: str
    , records: list[dict[str, Any]]
    , metadata: dict[str, Any] | None = None
) -> Path:
    """Persiste payload bruto em data/raw/<entidade>/<data>.json antes do Transform."""
    target_dir = raw_dir / entity
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{run_date}.json"
    content = {
        "entidade": entity
        , "run_date": run_date
        , "total_registros": len(records)
        , "metadata": metadata or {}
        , "dados": records
    }
    target_file.write_text(
        json.dumps(content, ensure_ascii=False, indent=2)
        , encoding="utf-8"
    )
    return target_file


def month_pairs_for_window(start_date: date, end_date: date) -> list[tuple[int, int]]:
    """Retorna pares (ano, mes) que cobrem a janela informada e o mes anterior de fallback."""
    pairs: set[tuple[int, int]] = set()
    cursor = start_date.replace(day=1)
    end_month = end_date.replace(day=1)
    while cursor <= end_month:
        pairs.add((cursor.year, cursor.month))
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)

    prev_month = start_date.replace(day=1) - timedelta(days=1)
    pairs.add((prev_month.year, prev_month.month))
    return sorted(pairs)


def extract_deputy_expenses(
    base_url: str
    , dep_id: int
    , month_pairs: list[tuple[int, int]]
) -> tuple[int, list[dict[str, Any]]]:
    """Coleta despesas CEAP de um deputado para os pares (ano, mes) selecionados."""
    items: list[dict[str, Any]] = []
    with requests.Session() as session:
        for ano, mes in month_pairs:
            records = fetch_all_pages(
                session
                , f"{base_url}/deputados/{dep_id}/despesas"
                , params={"ano": ano, "mes": mes, "itens": 100}
            )
            for rec in records:
                rec["idDeputado"] = dep_id
            items.extend(records)
            time.sleep(0.05)
    return dep_id, items


def run_extraction(
    settings: Settings
    , days: int = 7
    , max_deputados: int = 0
    , max_workers: int = 4
    , run_date: str | None = None
) -> dict[str, Any]:
    """Executa a extracao completa dos 5 grupos de endpoints e salva JSONs brutos."""
    today = date.today()
    exec_date = run_date or today.isoformat()
    start_date = today - timedelta(days=days)
    start_str = start_date.isoformat()
    end_str = today.isoformat()
    base_url = settings.camara_base_url

    logger.info("Iniciando extracao (janela=%s dias: %s a %s)", days, start_str, end_str)

    summary: dict[str, Any] = {
        "run_date": exec_date
        , "janela_dias": days
        , "inicio": start_str
        , "fim": end_str
        , "arquivos": {}
        , "contagens": {}
    }

    with requests.Session() as session:
        # 1. Partidos
        partidos = fetch_all_pages(session, f"{base_url}/partidos", {"itens": 100})
        p_path = save_raw_json(settings.raw_dir, "partidos", exec_date, partidos)
        summary["arquivos"]["partidos"] = str(p_path)
        summary["contagens"]["partidos"] = len(partidos)
        logger.info("Partidos extraidos: %s -> %s", len(partidos), p_path.name)

        # 2. Deputados
        deputados = fetch_all_pages(session, f"{base_url}/deputados", {"itens": 100})
        d_path = save_raw_json(settings.raw_dir, "deputados", exec_date, deputados)
        summary["arquivos"]["deputados"] = str(d_path)
        summary["contagens"]["deputados"] = len(deputados)
        logger.info("Deputados extraidos: %s -> %s", len(deputados), d_path.name)

        # 3. Proposicoes
        proposicoes = fetch_all_pages(
            session
            , f"{base_url}/proposicoes"
            , {
                "dataApresentacaoInicio": start_str
                , "dataApresentacaoFim": end_str
                , "itens": 100
                , "ordem": "DESC"
                , "ordenarPor": "id"
            }
        )
        pr_path = save_raw_json(
            settings.raw_dir
            , "proposicoes"
            , exec_date
            , proposicoes
            , metadata={"inicio": start_str, "fim": end_str}
        )
        summary["arquivos"]["proposicoes"] = str(pr_path)
        summary["contagens"]["proposicoes"] = len(proposicoes)
        logger.info("Proposicoes extraidas: %s -> %s", len(proposicoes), pr_path.name)

        # 4. Votacoes
        votacoes = fetch_all_pages(
            session
            , f"{base_url}/votacoes"
            , {
                "dataInicio": start_str
                , "dataFim": end_str
                , "itens": 100
            }
        )
        v_path = save_raw_json(
            settings.raw_dir
            , "votacoes"
            , exec_date
            , votacoes
            , metadata={"inicio": start_str, "fim": end_str}
        )
        summary["arquivos"]["votacoes"] = str(v_path)
        summary["contagens"]["votacoes"] = len(votacoes)
        logger.info("Votacoes extraidas: %s -> %s", len(votacoes), v_path.name)

    # 5. Despesas por deputado com checkpoint resumivel
    dep_ids = [int(d["id"]) for d in deputados if d.get("id")]
    if max_deputados > 0:
        dep_ids = dep_ids[:max_deputados]

    month_pairs = month_pairs_for_window(start_date, today)
    despesas_dir = settings.raw_dir / "despesas"
    despesas_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = despesas_dir / f"{exec_date}_checkpoint.json"

    completed_by_dep: dict[str, list[dict[str, Any]]] = {}
    if checkpoint_file.exists():
        try:
            completed_by_dep = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            logger.info(
                "Retomando checkpoint de despesas: %s deputados ja coletados."
                , len(completed_by_dep)
            )
        except ValueError:
            completed_by_dep = {}

    pending_ids = [dep_id for dep_id in dep_ids if str(dep_id) not in completed_by_dep]
    logger.info(
        "Extraindo despesas para %s deputados pendentes (meses=%s, workers=%s)..."
        , len(pending_ids)
        , month_pairs
        , max_workers
    )

    if pending_ids:
        processed_since_save = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(extract_deputy_expenses, base_url, dep_id, month_pairs): dep_id
                for dep_id in pending_ids
            }
            for future in as_completed(futures):
                dep_id, items = future.result()
                completed_by_dep[str(dep_id)] = items
                processed_since_save += 1
                if processed_since_save % 50 == 0:
                    checkpoint_file.write_text(
                        json.dumps(completed_by_dep, ensure_ascii=False)
                        , encoding="utf-8"
                    )
                    logger.info(
                        "Progresso despesas: %s/%s deputados concluidos."
                        , len(completed_by_dep)
                        , len(dep_ids)
                    )

        checkpoint_file.write_text(
            json.dumps(completed_by_dep, ensure_ascii=False)
            , encoding="utf-8"
        )

    all_despesas: list[dict[str, Any]] = []
    for dep_id in dep_ids:
        all_despesas.extend(completed_by_dep.get(str(dep_id), []))

    desp_path = save_raw_json(
        settings.raw_dir
        , "despesas"
        , exec_date
        , all_despesas
        , metadata={"meses": month_pairs, "deputados_coletados": len(dep_ids)}
    )
    summary["arquivos"]["despesas"] = str(desp_path)
    summary["contagens"]["despesas"] = len(all_despesas)
    logger.info("Despesas extraidas: %s -> %s", len(all_despesas), desp_path.name)

    return summary


def parse_args() -> argparse.Namespace:
    """Interpreta argumentos de linha de comando."""
    parser = argparse.ArgumentParser(description="Extrator API Camara v2")
    parser.add_argument("--days", type=int, default=None, help="Janela em dias (ex.: 7 ou 30)")
    parser.add_argument(
        "--max-deputados"
        , type=int
        , default=0
        , help="Limite opcional de deputados para testes rapidos (0 = todos)"
    )
    parser.add_argument("--workers", type=int, default=4, help="Workers paralelos para despesas")
    parser.add_argument("--run-date", type=str, default=None, help="Data YYYY-MM-DD do lote")
    return parser.parse_args()


def main() -> int:
    """Ponto de entrada CLI do extrator."""
    args = parse_args()
    settings = load_settings()
    days = args.days if args.days is not None else settings.ingestion_days_window
    summary = run_extraction(
        settings=settings
        , days=days
        , max_deputados=args.max_deputados
        , max_workers=args.workers
        , run_date=args.run_date
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
