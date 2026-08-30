"""The search agent: run every persona's frozen query and log what came back.

No model is involved. Queries were frozen at spawn time, so a round is a pure
replay -- which is what makes round 2 comparable to round 1. The only thing
that changes between rounds is the product descriptions.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import store
from ..config import Config, load as load_config
from ..personas import Persona, PersonaStore
from ..search import SearchIndex


class BaselineWouldBeInvalid(RuntimeError):
    """Re-running round 1 against a catalogue the agent has already rewritten.

    Round 1 is the BEFORE measurement. Once approved rewrites are in the product
    JSON, re-running it measures the improved copy, round 1 becomes identical to
    round 2, and the delta silently collapses to zero -- with no error and no
    obvious sign anything is wrong. That is the single easiest way to destroy
    the result, so it is refused rather than warned about.
    """


@dataclass
class RoundResult:
    round_no: int
    rows: list[dict]
    never_returned: list[str]
    returned_any: list[str]

    @property
    def query_count(self) -> int:
        return len(self.rows)


def run_round(
    round_no: int,
    config: Config | None = None,
    index: SearchIndex | None = None,
    progress=None,
    force: bool = False,
) -> RoundResult:
    """Run every synthetic persona's query and write logs/round_N.jsonl."""
    config = config or load_config()
    index = index or SearchIndex(config=config)
    index.build()                       # pick up any approved rewrites

    if round_no == 1 and not force:
        rewritten = [p.id for p in index.catalog.products if p.edit_history]
        if rewritten:
            raise BaselineWouldBeInvalid(
                f"{len(rewritten)} product(s) have already been rewritten "
                f"({', '.join(rewritten[:5])}"
                f"{', ...' if len(rewritten) > 5 else ''}), so re-running round 1 "
                f"would measure the improved copy and wipe out the before/after.\n"
                f"  For a genuinely fresh run:  pipeline reset --yes\n"
                f"  To re-measure deliberately anyway, pass force."
            )

    personas: list[Persona] = PersonaStore(config).synthetic()
    if not personas:
        raise ValueError(
            "no synthetic personas on disk -- run persona spawning first")

    all_ids = set(index.catalog.ids)
    returned_any: set[str] = set()
    rows: list[dict] = []

    for i, persona in enumerate(personas, start=1):
        hits = index.search(persona.query, config.search_k)
        returned = [h.product_id for h in hits]
        returned_any.update(returned)
        rows.append({
            "persona_id": persona.id,
            "round": round_no,
            "angle": persona.angle,
            "query": persona.query,
            "returned": returned,
            # kept for scoring/report: which rank each product landed at
            "scores": {h.product_id: round(h.score, 4) for h in hits},
        })
        if progress:
            progress(i, len(personas), persona)

    # never_returned is the set difference between all products and everything
    # returned across ALL queries in the round -- a round-level quantity.
    never_returned = sorted(all_ids - returned_any)
    for row in rows:
        row["never_returned"] = never_returned

    store.write_jsonl(config.log_path(round_no), rows)
    return RoundResult(round_no, rows, never_returned, sorted(returned_any))


def load_round(round_no: int, config: Config | None = None) -> list[dict]:
    config = config or load_config()
    return store.read_jsonl(config.log_path(round_no))
