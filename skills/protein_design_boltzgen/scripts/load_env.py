"""
Load environment variables from a local .env file and resolve FASTFOLD_API_KEY.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def load_dotenv() -> None:
    """Load .env from CWD or parent directories without overriding existing vars."""
    search_dirs: list[str] = []
    directory = os.getcwd()
    while directory and directory != os.path.dirname(directory):
        search_dirs.append(directory)
        directory = os.path.dirname(directory)

    for dirpath in search_dirs:
        env_path = os.path.join(dirpath, ".env")
        if os.path.isfile(env_path):
            _parse_and_set(env_path)
            return


def resolve_fastfold_api_key() -> str | None:
    """
    Resolve FASTFOLD_API_KEY from:
    1) current environment
    2) .env in CWD/parents
    3) ~/.fastfold-cli/config.json key: api.fastfold_cloud_key
    """
    api_key = (os.environ.get("FASTFOLD_API_KEY") or "").strip()
    if api_key:
        return api_key

    load_dotenv()
    api_key = (os.environ.get("FASTFOLD_API_KEY") or "").strip()
    if api_key:
        return api_key

    config_path = Path.home() / ".fastfold-cli" / "config.json"
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        cfg_key = str(payload.get("api.fastfold_cloud_key") or "").strip()
        if not cfg_key:
            return None
        os.environ["FASTFOLD_API_KEY"] = cfg_key
        return cfg_key
    except Exception:
        return None


def _parse_and_set(path: str) -> None:
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            if not key:
                continue
            if len(value) >= 2 and (
                (value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))
            ):
                value = value[1:-1]
            if key not in os.environ and value:
                os.environ[key] = value
