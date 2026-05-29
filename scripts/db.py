"""Database connection helper for Python scrapers."""
import os
import psycopg2
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv

# Ruta absoluta al .env.local en la raíz del proyecto
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env.local"
load_dotenv(dotenv_path=_ENV_PATH)


def get_conn():
    """Return a psycopg2 connection to Neon."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url or not url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError(
            "DATABASE_URL no está configurada. "
            "En GitHub Actions: Settings → Secrets → DATABASE_URL. "
            "En local: añádela a scripts/../.env.local"
        )
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
