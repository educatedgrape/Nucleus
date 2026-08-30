"""Natural-language search over product descriptions.

sentence-transformers embeddings + cosine similarity. Vectors are cached to
disk keyed by a hash of the exact text embedded, so re-indexing after a
description rewrite only re-encodes what actually changed.

`k` comes from config and must not change after round 1 -- it defines what
counts as "never returned", which is the headline number.
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass

import numpy as np

from .catalog import Catalog
from .config import Config, load as load_config

_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[str, object] = {}


def _get_model(name: str):
    """Load the encoder once per process. Import is deferred because loading
    torch costs seconds, and most CLI paths never touch it."""
    with _MODEL_LOCK:
        if name not in _MODEL_CACHE:
            from sentence_transformers import SentenceTransformer
            _MODEL_CACHE[name] = SentenceTransformer(name)
        return _MODEL_CACHE[name]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class Hit:
    product_id: str
    score: float
    rank: int


class SearchIndex:
    def __init__(self, catalog: Catalog | None = None, config: Config | None = None):
        self.config = config or load_config()
        self.catalog = catalog or Catalog(self.config)
        self._ids: list[str] = []
        self._hashes: dict[str, str] = {}
        self._vectors: np.ndarray | None = None

    @property
    def cache_path(self):
        return self.config.index_dir / f"{self.config.dataset}.npz"

    # -- building ----------------------------------------------------------
    def _load_cache(self) -> dict[str, np.ndarray]:
        if not self.cache_path.exists():
            return {}
        blob = np.load(self.cache_path, allow_pickle=False)
        if str(blob.get("model", "")) and str(blob["model"]) != self.config.embedding_model:
            return {}  # different encoder -- cached vectors are meaningless
        ids = [str(x) for x in blob["ids"]]
        hashes = [str(x) for x in blob["hashes"]]
        vectors = blob["vectors"]
        return {f"{i}:{h}": v for i, h, v in zip(ids, hashes, vectors)}

    def build(self, force: bool = False) -> dict[str, int]:
        """(Re)build the index. Returns {'encoded': n, 'reused': n}."""
        self.catalog.reload()
        products = self.catalog.products
        cached = {} if force else self._load_cache()

        texts_to_encode, keys_to_encode = [], []
        plan: list[tuple[str, str, np.ndarray | None]] = []
        for p in products:
            h = text_hash(p.search_text)
            key = f"{p.id}:{h}"
            vec = cached.get(key)
            plan.append((p.id, h, vec))
            if vec is None:
                texts_to_encode.append(p.search_text)
                keys_to_encode.append(p.id)

        encoded: dict[str, np.ndarray] = {}
        if texts_to_encode:
            model = _get_model(self.config.embedding_model)
            arr = model.encode(texts_to_encode, normalize_embeddings=True,
                               show_progress_bar=False)
            arr = np.asarray(arr, dtype=np.float32)
            encoded = dict(zip(keys_to_encode, arr))

        self._ids = [pid for pid, _, _ in plan]
        self._hashes = {pid: h for pid, h, _ in plan}
        self._vectors = np.vstack([
            encoded[pid] if vec is None else vec for pid, _, vec in plan
        ]).astype(np.float32)

        self.config.index_dir.mkdir(parents=True, exist_ok=True)
        np.savez(self.cache_path,
                 ids=np.array(self._ids),
                 hashes=np.array([self._hashes[i] for i in self._ids]),
                 vectors=self._vectors,
                 model=np.array(self.config.embedding_model))
        return {"encoded": len(texts_to_encode),
                "reused": len(plan) - len(texts_to_encode)}

    def ensure_built(self) -> None:
        if self._vectors is None:
            self.build()

    # -- querying ----------------------------------------------------------
    def search(self, query: str, k: int | None = None) -> list[Hit]:
        """Ranked product ids for a natural-language query."""
        self.ensure_built()
        k = self.config.search_k if k is None else k
        model = _get_model(self.config.embedding_model)
        qv = np.asarray(
            model.encode([query], normalize_embeddings=True, show_progress_bar=False),
            dtype=np.float32,
        )[0]
        # vectors are L2-normalised, so the dot product IS cosine similarity
        sims = self._vectors @ qv
        order = np.argsort(-sims)[:k]
        return [Hit(product_id=self._ids[i], score=float(sims[i]), rank=rank)
                for rank, i in enumerate(order, start=1)]
