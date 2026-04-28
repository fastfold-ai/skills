"""
Resolve FASTFOLD_API_KEY from environment, a .env file, or the FastFold CLI config.

Usage:
    from load_env import resolve_fastfold_api_key
    api_key = resolve_fastfold_api_key()

Resolution order:
1. FASTFOLD_API_KEY already in environment.
2. .env in current directory or any parent directory.
3. ~/.fastfold-cli/config.json -> api.fastfold_cloud_key
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def load_dotenv() -> None:
    """Load .env from current directory or any parent directory. Does not override existing env vars."""
    search_dirs = []
    d = os.getcwd()
    while d and d != os.path.dirname(d):
        search_dirs.append(d)
        d = os.path.dirname(d)
    for dirpath in search_dirs:
        env_path = os.path.join(dirpath, ".env")
        if os.path.isfile(env_path):
            _parse_and_set(env_path)
            return


def resolve_fastfold_api_key() -> str | None:
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
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        cfg_key = str(raw.get("api.fastfold_cloud_key") or "").strip()
        if not cfg_key:
            return None
        os.environ["FASTFOLD_API_KEY"] = cfg_key
        return cfg_key
    except Exception:
        return None


def _parse_and_set(env_path: str) -> None:
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
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
