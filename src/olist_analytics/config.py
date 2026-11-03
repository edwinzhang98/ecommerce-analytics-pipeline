"""Project configuration.

Resolution order for every setting (highest wins):
  1. environment variable (OLIST_RAW_DIR, DUCKDB_PATH, CACHE_DIR)
  2. `.env` file in the repo root
  3. `config.yaml` in the repo root

Relative paths are resolved from the repository root, and `~` is expanded,
so no personal absolute path is hard-coded anywhere in the code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]

_ENV_KEYS = {
    "raw_data_dir": "OLIST_RAW_DIR",
    "duckdb_path": "DUCKDB_PATH",
    "cache_dir": "CACHE_DIR",
}


def _resolve(value: str) -> Path:
    path = Path(os.path.expanduser(value))
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


@dataclass(frozen=True)
class Settings:
    raw_data_dir: Path
    duckdb_path: Path
    cache_dir: Path

    @property
    def dbt_dir(self) -> Path:
        return REPO_ROOT / "dbt"

    @property
    def artifacts_dir(self) -> Path:
        """Copies of dbt artifacts (manifest, run results) used by the app."""
        return self.cache_dir / "dbt_artifacts"


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    values = {key: os.environ.get(env, raw.get(key)) for key, env in _ENV_KEYS.items()}
    missing = [k for k, v in values.items() if not v]
    if missing:
        raise ValueError(f"Missing settings in config.yaml / environment: {missing}")
    return Settings(**{k: _resolve(str(v)) for k, v in values.items()})
