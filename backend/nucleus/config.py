"""Configuration. One `config.yaml` at the repo root, loaded once.

Nothing else in the codebase reads the YAML directly, and nothing hardcodes a
path -- so pointing `dataset` at a different catalogue is genuinely a one-line
change.
"""
from __future__ import annotations

import functools
import os
import pathlib
from dataclasses import dataclass

import yaml

# backend/nucleus/config.py -> backend/nucleus -> backend -> <repo root>
ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.yaml"


def _load_dotenv(path: pathlib.Path) -> None:
    """Read `.env` into the environment without clobbering real env vars.

    Keeps the API key out of the shell profile and out of version control
    (`.env` is gitignored). An already-exported variable always wins, so CI or
    a terminal export overrides the file.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: float = 90.0
    requests_per_minute: int = 120
    max_concurrency: int = 4
    max_retries: int = 5
    retry_base_seconds: float = 1.0
    retry_max_seconds: float = 30.0
    price_per_1m_input: float = 0.0
    price_per_1m_output: float = 0.0


@dataclass(frozen=True)
class Config:
    dataset: str
    search_k: int
    persona_count: int
    embedding_model: str
    llm: LLMConfig
    root: pathlib.Path

    # -- dataset-scoped ----------------------------------------------------
    @property
    def data_dir(self) -> pathlib.Path:
        return self.root / "data"

    @property
    def dataset_dir(self) -> pathlib.Path:
        return self.data_dir / "datasets" / self.dataset

    @property
    def products_dir(self) -> pathlib.Path:
        return self.dataset_dir / "products"

    @property
    def meta_path(self) -> pathlib.Path:
        return self.dataset_dir / "meta.yaml"

    # -- run artefacts -----------------------------------------------------
    @property
    def personas_dir(self) -> pathlib.Path:
        return self.data_dir / "personas"

    @property
    def logs_dir(self) -> pathlib.Path:
        return self.data_dir / "logs"

    @property
    def proposals_dir(self) -> pathlib.Path:
        return self.data_dir / "proposals"

    @property
    def index_dir(self) -> pathlib.Path:
        return self.data_dir / "index"

    @property
    def scores_path(self) -> pathlib.Path:
        return self.data_dir / "scores.json"

    @property
    def links_path(self) -> pathlib.Path:
        return self.data_dir / "links.json"

    @property
    def report_path(self) -> pathlib.Path:
        return self.data_dir / "report.json"

    def log_path(self, round_no: int) -> pathlib.Path:
        return self.logs_dir / f"round_{round_no}.jsonl"

    def ensure_dirs(self) -> None:
        for d in (self.personas_dir, self.logs_dir, self.proposals_dir,
                  self.index_dir, self.products_dir):
            d.mkdir(parents=True, exist_ok=True)


def _load(path: pathlib.Path | None = None) -> Config:
    path = path or CONFIG_PATH
    root = path.resolve().parent
    _load_dotenv(root / ".env")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    llm_raw = raw.get("llm", {})
    return Config(
        dataset=raw["dataset"],
        search_k=int(raw["search_k"]),
        persona_count=int(raw["persona_count"]),
        embedding_model=raw["embedding_model"],
        llm=LLMConfig(
            provider=llm_raw.get("provider", "openai"),
            model=llm_raw.get("model", "gpt-4.1-2025-04-14"),
            temperature=float(llm_raw.get("temperature", 0)),
            max_output_tokens=int(llm_raw.get("max_output_tokens", 4096)),
            timeout_seconds=float(llm_raw.get("timeout_seconds", 90)),
            requests_per_minute=int(llm_raw.get("requests_per_minute", 120)),
            max_concurrency=int(llm_raw.get("max_concurrency", 4)),
            max_retries=int(llm_raw.get("max_retries", 5)),
            retry_base_seconds=float(llm_raw.get("retry_base_seconds", 1.0)),
            retry_max_seconds=float(llm_raw.get("retry_max_seconds", 30.0)),
            price_per_1m_input=float(llm_raw.get("price_per_1m_input", 0.0)),
            price_per_1m_output=float(llm_raw.get("price_per_1m_output", 0.0)),
        ),
        root=root,
    )


@functools.lru_cache(maxsize=1)
def load() -> Config:
    """The process-wide config. Cached; call `load.cache_clear()` in tests."""
    return _load()
