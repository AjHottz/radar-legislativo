"""Validação do ambiente da Onda 0 (dependências, variáveis de ambiente e PostgreSQL)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


REQUIRED_MODULES: list[str] = [
    "requests"
    , "pandas"
    , "numpy"
    , "sqlalchemy"
    , "psycopg2"
    , "openai"
    , "dotenv"
]


def check_imports() -> bool:
    """Verifica se todas as dependências Python obrigatórias estão instaladas."""
    missing: list[str] = []
    for module_name in REQUIRED_MODULES:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)

    if missing:
        print(f"[ERRO] Módulos ausentes: {', '.join(missing)}")
        return False

    print("[OK] Todas as dependências Python foram importadas com sucesso.")
    return True


def is_placeholder(value: str | None) -> bool:
    """Identifica se uma variável ainda está ausente ou com texto de exemplo."""
    if not value:
        return True
    markers: tuple[str, ...] = (
        "SUA_SENHA"
        , "SEU_PROJETO"
        , "SUA_CHAVE_AQUI"
    )
    return any(marker in value for marker in markers)


def check_database(database_url: str | None) -> bool:
    """Testa conectividade com PostgreSQL e verifica disponibilidade da extensão vector."""
    if is_placeholder(database_url):
        print("[PENDENTE] DATABASE_URL não configurada no arquivo .env.")
        return False

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version();")).scalar_one()
            has_vector = conn.execute(
                text(
                    "SELECT EXISTS ("
                    " SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
                    ");"
                )
            ).scalar_one()
        print(f"[OK] Conexão PostgreSQL estabelecida: {version.split(',')[0]}")
        print(f"[INFO] Extensão pgvector disponível: {bool(has_vector)}")
        return True
    except SQLAlchemyError as exc:
        print(f"[ERRO] Falha ao conectar no PostgreSQL: {exc}")
        return False
    finally:
        engine.dispose()


def main() -> int:
    """Executa a bateria de verificação da Onda 0."""
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"

    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"[OK] Arquivo .env carregado de {env_path}")
    else:
        print("[AVISO] Arquivo .env não encontrado. Copie .env.example para .env.")

    imports_ok = check_imports()
    if not imports_ok:
        return 1

    openai_key = os.getenv("OPENAI_API_KEY")
    if is_placeholder(openai_key):
        print("[PENDENTE] OPENAI_API_KEY ainda não configurada no .env.")
    else:
        print("[OK] OPENAI_API_KEY detectada no .env (valor ocultado).")

    db_ok = check_database(os.getenv("DATABASE_URL"))
    return 0 if db_ok else 2


if __name__ == "__main__":
    sys.exit(main())

