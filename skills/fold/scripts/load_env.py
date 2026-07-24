"""
Resolve FASTFOLD_API_KEY for skill scripts without requiring a shell export.

Order:
1. FASTFOLD_API_KEY already in the environment
2. .env in cwd / parents (and SANDWALK_SESSION_WORKSPACE when set)
3. $SANDWALK_CONFIG_DIR/config.json → api.fastfold_cloud_key (when set)
4. Legacy home-config fallbacks (non-Sandwalk agents only)
"""

import json
import os
from pathlib import Path


def load_dotenv() -> None:
    """Load .env from workspace / cwd parents. Does not override existing env vars."""
    search_dirs: list[str] = []
    workspace = str(os.environ.get("SANDWALK_SESSION_WORKSPACE") or "").strip()
    if workspace:
        search_dirs.append(workspace)
    d = os.getcwd()
    while d and d != os.path.dirname(d):
        if d not in search_dirs:
            search_dirs.append(d)
        d = os.path.dirname(d)
    for dirpath in search_dirs:
        env_path = os.path.join(dirpath, ".env")
        if os.path.isfile(env_path):
            _parse_and_set(env_path)
            return


def _api_key_from_config(config_path: Path) -> str | None:
    if not config_path.exists():
        return None
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        cfg_key = str(raw.get("api.fastfold_cloud_key") or "").strip()
        return cfg_key or None
    except Exception:
        return None


def _config_candidates() -> list[Path]:
    """Prefer env-pointed config dir; fall back to common install locations."""
    out: list[Path] = []
    config_dir = str(os.environ.get("SANDWALK_CONFIG_DIR") or "").strip()
    if config_dir:
        out.append(Path(config_dir).expanduser() / "config.json")
    # Fallbacks for agents that do not inject SANDWALK_CONFIG_DIR.
    out.append(Path.home() / ".sandwalk" / "config.json")
    out.append(Path.home() / ".fastfold-cli" / "config.json")
    # Dedupe while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for path in out:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def resolve_fastfold_api_key() -> str | None:
    """
    Resolve FASTFOLD_API_KEY from environment / .env / host config.

    Agents should rely on FASTFOLD_API_KEY (and optional SANDWALK_* path envs).
    Home-directory config paths are implementation fallbacks only.
    """
    api_key = (os.environ.get("FASTFOLD_API_KEY") or "").strip()
    if api_key:
        return api_key

    load_dotenv()
    api_key = (os.environ.get("FASTFOLD_API_KEY") or "").strip()
    if api_key:
        return api_key

    for config_path in _config_candidates():
        cfg_key = _api_key_from_config(config_path)
        if cfg_key:
            os.environ["FASTFOLD_API_KEY"] = cfg_key
            return cfg_key
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
