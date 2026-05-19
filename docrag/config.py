import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DOCRAG_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "docrag.sqlite3"

EMBEDDING_MODEL = os.getenv("DOCRAG_EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("DOCRAG_CHAT_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

CHUNK_WORDS = int(os.getenv("DOCRAG_CHUNK_WORDS", "420"))
CHUNK_OVERLAP = int(os.getenv("DOCRAG_CHUNK_OVERLAP", "70"))
TOP_K = int(os.getenv("DOCRAG_TOP_K", "6"))


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
