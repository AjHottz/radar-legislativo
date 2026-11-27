"""Configuracoes centrais e taxonomia oficial do Radar Legislativo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


TAXONOMIA_TEMAS: list[dict[str, str]] = [
    {
        "tema": "Saúde Pública"
        , "descricao": "SUS, hospitais, medicamentos, vacinas, vigilancia sanitaria, planos de saude, profissionais de saude e doencas."
    }
    , {
        "tema": "Sistema Tributário e Fiscal"
        , "descricao": "Impostos, tributos, reforma tributaria, IBS, CBS, ICMS, IRPF, isencoes fiscais, orcamento publico e divida publica."
    }
    , {
        "tema": "Trabalho e Previdência"
        , "descricao": "CLT, salario minimo, jornada de trabalho, aposentadoria, INSS, FGTS, sindicatos, seguro-desemprego e direitos trabalhistas."
    }
    , {
        "tema": "Tecnologia, Dados e Inteligência Artificial"
        , "descricao": "Inteligencia artificial, protecao de dados, LGPD, ciberseguranca, redes sociais, telecomunicacoes, inovacao digital e plataformas."
    }
    , {
        "tema": "Meio Ambiente, Energia e Clima"
        , "descricao": "Desmatamento, mudancas climaticas, licenciamento ambiental, energia eletrica, petroleo, renovaveis, agua e saneamento."
    }
    , {
        "tema": "Economia, Mercado Financeiro e Regulação"
        , "descricao": "Bancos, credito, juros, mercado de capitais, CVM, Banco Central, empresas, concorrencia, defesa do consumidor e comercio."
    }
    , {
        "tema": "Segurança Pública e Justiça"
        , "descricao": "Codigo Penal, policia, sistema prisional, combate ao crime organizado, armas, processo judicial, direitos humanos e violencia."
    }
    , {
        "tema": "Educação, Ciência e Cultura"
        , "descricao": "Escolas, universidades, ENEM, FUNDEB, professores, pesquisa cientifica, bolsas de estudo, cultura, patrimonio e esportes."
    }
    , {
        "tema": "Infraestrutura, Transportes e Cidades"
        , "descricao": "Rodovias, ferrovias, portos, aeroportos, mobilidade urbana, habitacao, obras publicas, transito e desenvolvimento urbano."
    }
    , {
        "tema": "Agronegócio e Desenvolvimento Regional"
        , "descricao": "Agricultura, pecuaria, credito rural, reforma agraria, cooperativas agricolas, exportacao de commodities e desenvolvimento regional."
    }
]


def is_placeholder(value: str | None) -> bool:
    """Retorna True se a variavel estiver vazia ou ainda com valor de exemplo."""
    if not value or not value.strip():
        return True
    markers: tuple[str, ...] = (
        "SUA_SENHA"
        , "SEU_PROJETO"
        , "SUA_CHAVE_AQUI"
    )
    return any(marker in value for marker in markers)


def normalize_database_url(url: str | None) -> str:
    """Padroniza prefixos Postgres/psycopg v3 para o driver psycopg2 instalado."""
    if not url:
        return ""
    cleaned = url.strip()
    if cleaned.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg2://" + cleaned[len("postgresql+psycopg://"):]
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg2://" + cleaned[len("postgres://"):]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg2://" + cleaned[len("postgresql://"):]
    return cleaned


@dataclass(frozen=True)
class Settings:
    """Parametros consolidados do pipeline carregados a partir do .env."""

    project_root: Path
    raw_dir: Path
    cache_dir: Path
    sql_dir: Path
    camara_base_url: str
    database_url: str
    ai_provider: str
    gemini_api_key: str
    gemini_embedding_model: str
    gemini_summary_model: str
    openai_api_key: str
    openai_embedding_model: str
    openai_summary_model: str
    ingestion_days_window: int
    ai_batch_limit: int
    telegram_bot_token: str
    telegram_chat_id: str

    def validate_database(self) -> None:
        """Valida se DATABASE_URL foi configurada antes de operacoes no Postgres."""
        if is_placeholder(self.database_url):
            raise RuntimeError(
                "DATABASE_URL nao configurada no .env. Preencha a string de conexao do Supabase."
            )

    def resolved_ai_provider(self) -> str:
        """Resolve o provedor ativo de IA ('gemini' ou 'openai')."""
        explicit = self.ai_provider.strip().lower()
        if explicit in ("gemini", "openai"):
            return explicit
        if not is_placeholder(self.gemini_api_key):
            return "gemini"
        if not is_placeholder(self.openai_api_key):
            return "openai"
        return "gemini"

    def is_ai_configured(self) -> bool:
        """Retorna True se a chave do provedor de IA ativo estiver preenchida."""
        provider = self.resolved_ai_provider()
        if provider == "gemini":
            return not is_placeholder(self.gemini_api_key)
        return not is_placeholder(self.openai_api_key)

    def validate_ai(self) -> str:
        """Valida a chave do provedor ativo e retorna o nome do provedor."""
        provider = self.resolved_ai_provider()
        if provider == "gemini" and is_placeholder(self.gemini_api_key):
            raise RuntimeError(
                "GEMINI_API_KEY nao configurada no .env. Preencha sua chave do Google AI Studio."
            )
        if provider == "openai" and is_placeholder(self.openai_api_key):
            raise RuntimeError(
                "OPENAI_API_KEY nao configurada no .env. Preencha sua chave da OpenAI ou use AI_PROVIDER=gemini."
            )
        return provider


def load_settings() -> Settings:
    """Carrega .env da raiz do projeto e retorna objeto Settings tipado."""
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    return Settings(
        project_root=project_root
        , raw_dir=project_root / "data" / "raw"
        , cache_dir=project_root / "data" / "cache"
        , sql_dir=project_root / "sql"
        , camara_base_url=os.getenv(
            "CAMARA_API_BASE_URL"
            , "https://dadosabertos.camara.leg.br/api/v2"
        ).rstrip("/")
        , database_url=normalize_database_url(os.getenv("DATABASE_URL", ""))
        , ai_provider=os.getenv("AI_PROVIDER", "")
        , gemini_api_key=os.getenv("GEMINI_API_KEY", "")
        , gemini_embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
        , gemini_summary_model=os.getenv("GEMINI_SUMMARY_MODEL", "gemini-3.5-flash-lite")
        , openai_api_key=os.getenv("OPENAI_API_KEY", "")
        , openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        , openai_summary_model=os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")
        , ingestion_days_window=int(os.getenv("INGESTION_DAYS_WINDOW", "7"))
        , ai_batch_limit=int(os.getenv("AI_BATCH_LIMIT", "10"))
        , telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "")
        , telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "")
    )
