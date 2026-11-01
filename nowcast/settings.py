"""Project paths and credential loading shared by every nowcast module."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT_DIR / "nowcast"
CONFIG_DIR = PACKAGE_DIR / "config"
DOCS_DIR = ROOT_DIR / "docs"
DATA_DIR = ROOT_DIR / "data"
RAW_CACHE_DIR = DATA_DIR / "raw_cache"

# Pause any download when free space on the data drive drops below this.
MIN_FREE_GB = 15.0


def load_dotenv(path: Path = ROOT_DIR / ".env") -> None:
    """Load KEY=VALUE lines from .env without overriding variables already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def mosdac_credentials() -> tuple[str, str]:
    load_dotenv()
    user = os.environ.get("MOSDAC_USERNAME", "").strip()
    password = os.environ.get("MOSDAC_PASSWORD", "").strip()
    if not user or not password:
        raise RuntimeError("MOSDAC_USERNAME / MOSDAC_PASSWORD are not set in .env or the environment.")
    return user, password


def free_gb(path: Path = ROOT_DIR) -> float:
    """Free space on the drive holding `path`; works before the folder exists."""
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    return shutil.disk_usage(path).free / 1e9
