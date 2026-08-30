"""Before versus after -- the actual result.

Primary metric: correct products that never surfaced in round 1 and now do.

Supporting metrics, per scope.md:
  - products still never surfacing after adaptation
  - how many gaps were fixable from specs versus needing evidence
  - whether wrong products stopped surfacing

Reported honestly, including when a number is small. A modest delta alongside a
set of confirmed links is a real finding; inflating it would defeat the point.
"""
from __future__ import annotations

from collections import defaultdict

from . import store
from .catalog import Catalog
from .config import Config, load as load_config
from .scoring import RIGHT, WRONG, Scores
from .agents.searcher import load_round


def _returned_pairs(rows: list[dict], intent_of: dict[str, str]) -> set[tuple[str, str]]:
    """(product_id, intent) pairs that surfaced in a round."""
    pairs = set()
    for row in rows:
        intent = intent_of.get(row["persona_id"], "")
        for pid in row["returned"]:
            pairs.add((pid, intent))
    return pairs


def compare(config: Config | None = None) -> dict:
    config = config or load_config()
    catalog = Catalog(config)
    scores = Scores(config)
    report = store.read_json(config.report_path, {}) or {}

    r1 = load_round(1, config)
    r2 = load_round(2, config)
    if not r1:
        raise ValueError("round 1 has not been run")
    if not r2:
        raise ValueError("round 2 has not been run")

    # Map persona -> intent using the report's clustering of round 1 queries.
    query_to_intent: dict[str, str] = {}
    for intent in report.get("intents", []):
        for ex in intent.get("examples", []):
            query_to_intent[ex.strip().lower()] = intent["label"]
    intent_of: dict[str, str] = {}
    for row in r1:
        intent_of[row["persona_id"]] = query_to_intent.get(
            row["query"].strip().lower(), "")

    before = _returned_pairs(r1, intent_of)
    after = _returned_pairs(r2, intent_of)

    never_1 = set(r1[0].get("never_returned", []))
    never_2 = set(r2[0].get("never_returned", []))

    # ---- primary ---------------------------------------------------------
    newly = sorted({(p, i) for (p, i) in after - before
                    if scores.verdict(p, i) == RIGHT})
    lost = sorted({(p, i) for (p, i) in before - after
                   if scores.verdict(p, i) == RIGHT})

    # ---- supporting ------------------------------------------------------
    wrong_before = {(p, i) for (p, i) in before if scores.verdict(p, i) == WRONG}
    wrong_after = {(p, i) for (p, i) in after if scores.verdict(p, i) == WRONG}
    wrong_stopped = sorted(wrong_before - wrong_after)

    by_type: dict[str, int] = defaultdict(int)
    for g in report.get("gaps", []):
        by_type[g["type"]] += 1

    links = store.read_json(config.links_path, {}) or {}
    confirmed = [{"product_id": pid, "name": catalog.get(pid).name, **entry}
                 for pid, entries in sorted(links.items()) for entry in entries]

    unscored = sorted({(p, i) for (p, i) in after - before
                       if scores.verdict(p, i) is None})

    return {
        "dataset": config.dataset,
        "search_k": config.search_k,
        "primary": {
            "newly_surfacing_correct": [
                {"product_id": p, "name": catalog.get(p).name, "intent": i}
                for p, i in newly],
            "count": len(newly),
        },
        "supporting": {
            "still_never_surfacing": sorted(never_2),
            "still_never_surfacing_count": len(never_2),
            "never_surfacing_before": len(never_1),
            "closed": sorted(never_1 - never_2),
            "wrong_products_stopped": [
                {"product_id": p, "name": catalog.get(p).name, "intent": i}
                for p, i in wrong_stopped],
            "correct_products_lost": [
                {"product_id": p, "name": catalog.get(p).name, "intent": i}
                for p, i in lost],
            "gap_types": dict(by_type),
        },
        "confirmed_links": confirmed,
        "needs_scoring": [{"product_id": p, "intent": i} for p, i in unscored],
        "totals": {
            "products": len(catalog),
            "scored_pairs": scores.count,
        },
    }


def summarise(result: dict) -> str:
    p, s = result["primary"], result["supporting"]
    lines = [
        "BEFORE / AFTER",
        f"  correct products newly surfacing : {p['count']}",
    ]
    for row in p["newly_surfacing_correct"]:
        lines.append(f"      {row['product_id']}  {row['name']}  <- {row['intent']}")
    lines += [
        f"  never surfacing  {s['never_surfacing_before']} -> "
        f"{s['still_never_surfacing_count']}  (closed {len(s['closed'])})",
        f"  wrong products that stopped      : {len(s['wrong_products_stopped'])}",
        f"  correct products lost            : {len(s['correct_products_lost'])}",
        f"  confirmed semantic links         : {len(result['confirmed_links'])}",
        "  gap types:",
    ]
    for k in ("fixable", "needs_evidence", "not_applicable", "already_covered"):
        lines.append(f"      {k:<16} {s['gap_types'].get(k, 0)}")
    if result["needs_scoring"]:
        lines.append(f"  newly surfaced but unscored      : {len(result['needs_scoring'])}")
    return "\n".join(lines)
