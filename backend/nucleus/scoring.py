"""Ground truth: the user marks each returned product right or wrong.

Scored once per (product, intent) and reused across rounds. A product marked
wrong for "lightweight humid weather" stays wrong for that intent in round 2,
which gives a fixed baseline to measure against without asking anyone to score
the same thing twice. Only genuinely unscored pairs enter the queue.

Stored nested by product then intent -- build.md's example shape allows one
intent per product, but scope.md requires the verdict to be per-intent, so the
score for a product that surfaces under two intents can differ.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from . import store
from .config import Config, load as load_config

RIGHT, WRONG = "right", "wrong"
VERDICTS = {RIGHT, WRONG}


@dataclass
class ScoreItem:
    product_id: str
    intent: str
    verdict: str | None = None


class Scores:
    def __init__(self, config: Config | None = None):
        self.config = config or load_config()
        self._data: dict[str, dict] = store.read_json(self.config.scores_path, {}) or {}

    # -- read --------------------------------------------------------------
    def verdict(self, product_id: str, intent: str) -> str | None:
        entry = self._data.get(product_id, {}).get(intent)
        return entry["verdict"] if entry else None

    def is_scored(self, product_id: str, intent: str) -> bool:
        return self.verdict(product_id, intent) is not None

    def right_products(self, intent: str | None = None) -> set[str]:
        out = set()
        for pid, intents in self._data.items():
            for label, entry in intents.items():
                if entry["verdict"] == RIGHT and (intent is None or label == intent):
                    out.add(pid)
        return out

    @property
    def count(self) -> int:
        return sum(len(v) for v in self._data.values())

    def as_dict(self) -> dict:
        return self._data

    # -- write -------------------------------------------------------------
    def set(self, product_id: str, intent: str, verdict: str) -> None:
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VERDICTS)}, got {verdict!r}")
        self._data.setdefault(product_id, {})[intent] = {
            "verdict": verdict,
            "scored_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        self.save()

    def save(self) -> None:
        store.write_json(self.config.scores_path, self._data)


def queue(report: dict, config: Config | None = None) -> list[ScoreItem]:
    """(product, intent) pairs that surfaced and have not been scored yet."""
    scores = Scores(config)
    seen: set[tuple[str, str]] = set()
    out: list[ScoreItem] = []
    for gap in report.get("gaps", []):
        if gap["type"] != "already_covered":
            continue
        key = (gap["product_id"], gap["intent"])
        if key in seen or scores.is_scored(*key):
            continue
        seen.add(key)
        out.append(ScoreItem(product_id=key[0], intent=key[1]))
    return out
