"""Exploracao inicial da API Dados Abertos da Camara dos Deputados (Onda 1)."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
HEADERS = {"Accept": "application/json"}


def fetch_sample(
    session: requests.Session
    , endpoint: str
    , params: dict[str, Any]
) -> dict[str, Any]:
    """Executa uma chamada GET de inspecao e retorna o payload JSON."""
    url = f"{BASE_URL}{endpoint}"
    response = session.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.json()


def summarize_endpoint(name: str, payload: dict[str, Any]) -> None:
    """Imprime diagnostico estrutural de chaves, tipos e paginacao."""
    dados = payload.get("dados", [])
    links = payload.get("links", [])
    print(f"\n=== {name.upper()} ===")
    print(f"Itens retornados na amostra: {len(dados)}")
    print(f"Links de paginacao: {[link.get('rel') for link in links]}")

    if not dados:
        print("Amostra vazia para os parametros informados.")
        return

    sample = dados[0]
    print(f"Campos ({len(sample)}): {list(sample.keys())}")
    tipos = {k: type(v).__name__ for k, v in sample.items()}
    print(f"Tipos na amostra[0]: {json.dumps(tipos, ensure_ascii=False)}")
    print(f"Exemplo[0]: {json.dumps(sample, ensure_ascii=False)[:500]}")


def main() -> int:
    """Executa a exploracao dos 5 grupos de endpoints previstos no PRD/SPEC."""
    hoje = date.today()
    inicio_7d = (hoje - timedelta(days=7)).isoformat()
    fim = hoje.isoformat()

    report: dict[str, Any] = {
        "data_exploracao": fim
        , "janela_teste": {"inicio": inicio_7d, "fim": fim}
        , "endpoints": {}
    }

    with requests.Session() as session:
        endpoints_cfg: list[tuple[str, str, dict[str, Any]]] = [
            ("partidos", "/partidos", {"itens": 100, "pagina": 1})
            , ("deputados", "/deputados", {"itens": 100, "pagina": 1})
            , (
                "proposicoes"
                , "/proposicoes"
                , {
                    "dataApresentacaoInicio": inicio_7d
                    , "dataApresentacaoFim": fim
                    , "itens": 100
                    , "pagina": 1
                }
            )
            , (
                "votacoes"
                , "/votacoes"
                , {
                    "dataInicio": inicio_7d
                    , "dataFim": fim
                    , "itens": 100
                    , "pagina": 1
                }
            )
        ]

        dep_id: int | None = None
        for name, endpoint, params in endpoints_cfg:
            payload = fetch_sample(session, endpoint, params)
            summarize_endpoint(name, payload)
            dados = payload.get("dados", [])
            report["endpoints"][name] = {
                "count_page_1": len(dados)
                , "keys": list(dados[0].keys()) if dados else []
                , "links": payload.get("links", [])
            }
            if name == "deputados" and dados:
                dep_id = dados[0].get("id")

        if dep_id is not None:
            mes_anterior = (hoje.replace(day=1) - timedelta(days=1))
            desp_params = {
                "ano": mes_anterior.year
                , "mes": mes_anterior.month
                , "itens": 100
                , "pagina": 1
            }
            desp_payload = fetch_sample(session, f"/deputados/{dep_id}/despesas", desp_params)
            summarize_endpoint(f"despesas_dep_{dep_id}", desp_payload)
            desp_dados = desp_payload.get("dados", [])
            negativos = sum(
                1
                for item in desp_dados
                if (item.get("valorLiquido") or 0) < 0 or (item.get("valorDocumento") or 0) < 0
            )
            print(f"Registros com valor negativo na amostra de despesas: {negativos}")
            report["endpoints"]["despesas"] = {
                "deputado_teste": dep_id
                , "ano": mes_anterior.year
                , "mes": mes_anterior.month
                , "count_page_1": len(desp_dados)
                , "negativos_na_amostra": negativos
                , "keys": list(desp_dados[0].keys()) if desp_dados else []
            }

    cache_dir = Path(__file__).resolve().parent.parent / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_file = cache_dir / "api_exploracao_resumo.json"
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Resumo de exploracao salvo em {out_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
