"""Build the report from a round's search logs.

Two halves, and both are findings:

  what's missing    products that never surfaced, against the intents they
                    missed, each gap classified fixable / needs_evidence /
                    not_applicable
  what's working    products that already surface for an intent -- recorded as
                    `already_covered`, not left as an empty row

The second half is why the adapter can say "no change necessary" instead of
rewriting copy that is already doing its job.
"""
from __future__ import annotations

import datetime as _dt
from collections import defaultdict

from .. import store
from ..catalog import Catalog
from ..config import Config, load as load_config
from ..llm import get_client, map_parallel
from .searcher import load_round

CLUSTER_SYSTEM = """You group shopper search queries by what they are really about.

An intent is the underlying need, not the wording. "something airy for August"
and "won't cook my feet in summer" are one intent, not two.

Aim for 5-10 intents across the whole set. Every query must land in exactly one
intent. Label each intent as a short readable phrase a person would recognise
in a report -- "breathability in humidity", not "INTENT_3" or "thermal".

Return JSON: {"intents": [{"label": "...", "query_indexes": [0, 4, 9]}, ...]}
Query indexes refer to the numbered list you are given.
"""

CLASSIFY_SYSTEM = """You classify why a product failed to surface for a shopper intent.

You are given one product (its specs and its current description) and a list of
intents it never surfaced for. For each intent, decide:

  fixable          the specs genuinely support this, the description just never
                   says it. List the exact spec field names that support it.
  needs_evidence   plausible, but NOTHING in the product data backs it up.
                   Supporting spec fields must be empty.
  not_applicable   the product genuinely does not fit this intent. Say so
                   plainly; it is a product gap, not a copy gap.

Be strict. If you find yourself reaching for a spec field that only loosely
implies the claim, it is needs_evidence, not fixable. Claiming a spec supports
something it does not is the failure mode this whole exercise exists to catch.

Return JSON: {"gaps": [{"intent": "...", "type": "...",
"supporting_specs": ["field_name"], "rationale": "one sentence"}]}
"""

VALID_TYPES = {"fixable", "needs_evidence", "not_applicable", "already_covered"}


def _cluster_queries(rows: list[dict], client) -> list[dict]:
    queries = [r["query"] for r in rows]
    numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(queries))
    raw = client.json(CLUSTER_SYSTEM, f"Queries:\n{numbered}")

    intents = []
    claimed: set[int] = set()
    for item in raw.get("intents", []):
        idxs = [i for i in item.get("query_indexes", [])
                if isinstance(i, int) and 0 <= i < len(queries) and i not in claimed]
        if not idxs:
            continue
        claimed.update(idxs)
        intents.append({
            "label": str(item.get("label", "")).strip() or "unlabelled",
            "count": len(idxs),
            "query_indexes": sorted(idxs),
            "examples": [queries[i] for i in sorted(idxs)[:3]],
        })

    # Any query the model dropped still has to go somewhere -- losing queries
    # silently would understate the intents and the gaps.
    leftover = [i for i in range(len(queries)) if i not in claimed]
    if leftover:
        intents.append({
            "label": "unclustered",
            "count": len(leftover),
            "query_indexes": leftover,
            "examples": [queries[i] for i in leftover[:3]],
        })
    return intents


def build(
    round_no: int = 1,
    config: Config | None = None,
    progress=None,
) -> dict:
    config = config or load_config()
    catalog = Catalog(config)
    client = get_client(config)

    rows = load_round(round_no, config)
    if not rows:
        raise ValueError(f"no log for round {round_no} -- run the search agent first")

    intents = _cluster_queries(rows, client)

    # Which products surfaced for which intent, and which never surfaced at all.
    returned_by_intent: dict[str, set[str]] = defaultdict(set)
    for intent in intents:
        for qi in intent["query_indexes"]:
            returned_by_intent[intent["label"]].update(rows[qi]["returned"])

    never_returned = set(rows[0].get("never_returned", []))
    all_ids = set(catalog.ids)
    surfaced = all_ids - never_returned

    # ---- half one: what's already working -------------------------------
    gaps: list[dict] = []
    gap_n = 0
    for label, product_ids in returned_by_intent.items():
        for pid in sorted(product_ids):
            gap_n += 1
            row = next((r for r in rows
                        if pid in r["returned"] and _intent_of(r, intents, rows) == label), None)
            gaps.append({
                "id": f"gap_{gap_n:03d}",
                "product_id": pid,
                "intent": label,
                "type": "already_covered",
                "supporting_specs": [],
                "rationale": "Already surfaces for this intent; the description "
                             "is doing its job.",
                "evidenced_by": row["query"] if row else "",
                "rank": (row["returned"].index(pid) + 1) if row else None,
            })

    # ---- half two: what's missing ---------------------------------------
    never_surfaced: list[dict] = []
    intent_labels = [i["label"] for i in intents]

    # Stated to the classifier as a fact about the dataset. Enforcement still
    # lives in traceability.py; this only stops the classifier calling a gap
    # `fixable` when no spec could possibly support it.
    unsupported = "\n".join(f"  - {a}" for a in catalog.meta.unsupported_attributes)
    unsupported_note = (
        "\n\nThis catalogue records NO spec for any of the following. An intent "
        "about one of them cannot be `fixable`, however well the product seems "
        "to fit -- there is nothing to cite:\n" + unsupported
    ) if unsupported else ""

    def classify(pid: str) -> dict:
        product = catalog.get(pid)
        spec_lines = "\n".join(f"  {k}: {v}" for k, v in sorted(product.specs.items()))
        user = (
            f"Product: {product.name} ({product.id})\n"
            f"Price: {catalog.meta.currency}{product.price}\n"
            f"Specs:\n{spec_lines}\n\n"
            f"Current description:\n  {product.description}\n\n"
            f"It never surfaced for any of these intents:\n"
            + "\n".join(f"  - {label}" for label in intent_labels)
            + unsupported_note
        )
        return client.json(CLASSIFY_SYSTEM, user)

    # One call per never-surfaced product, run with bounded parallelism -- this
    # is the slowest part of a run. Results come back in input order and are
    # consumed below in sorted-id order, so gap ids stay deterministic.
    ordered = sorted(never_returned)
    classified = map_parallel(
        classify, ordered, config.llm.max_concurrency,
        progress=(lambda i, n: progress(i, n, "classifying")) if progress else None,
    )

    for pid, raw in zip(ordered, classified):
        product = catalog.get(pid)
        missed: list[str] = []
        for g in raw.get("gaps", []):
            label = str(g.get("intent", "")).strip()
            gtype = str(g.get("type", "")).strip()
            if label not in intent_labels or gtype not in VALID_TYPES:
                continue
            specs = [s for s in (g.get("supporting_specs") or [])
                     if s in product.specs]
            # A `fixable` verdict that cites no REAL spec field is not fixable.
            # The model does not get the last word on this.
            if gtype == "fixable" and not specs:
                gtype = "needs_evidence"
            if gtype == "needs_evidence":
                specs = []

            gap_n += 1
            gaps.append({
                "id": f"gap_{gap_n:03d}",
                "product_id": pid,
                "intent": label,
                "type": gtype,
                "supporting_specs": specs,
                "rationale": str(g.get("rationale", "")).strip(),
            })
            if gtype in ("fixable", "needs_evidence"):
                missed.append(label)

        if missed:
            never_surfaced.append({"product_id": pid, "missed": missed})

    report = {
        "round": round_no,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "dataset": config.dataset,
        "search_k": config.search_k,
        "totals": {
            "products": len(all_ids),
            "queries": len(rows),
            "surfaced": len(surfaced),
            "never_surfaced": len(never_returned),
        },
        "intents": [{k: v for k, v in i.items() if k != "query_indexes"} for i in intents],
        "never_surfaced": never_surfaced,
        "gaps": gaps,
    }
    store.write_json(config.report_path, report)
    return report


def _intent_of(row: dict, intents: list[dict], rows: list[dict]) -> str:
    idx = rows.index(row)
    for intent in intents:
        if idx in intent["query_indexes"]:
            return intent["label"]
    return ""


def load(config: Config | None = None) -> dict | None:
    config = config or load_config()
    return store.read_json(config.report_path)


def summarise(report: dict) -> str:
    by_type: dict[str, int] = defaultdict(int)
    for g in report["gaps"]:
        by_type[g["type"]] += 1
    t = report["totals"]
    lines = [
        f"Round {report['round']} - {t['products']} products, {t['queries']} queries",
        f"  surfaced       {t['surfaced']}",
        f"  never surfaced {t['never_surfaced']}",
        f"  intents        {len(report['intents'])}",
        "  gaps:",
    ]
    for k in ("fixable", "needs_evidence", "not_applicable", "already_covered"):
        lines.append(f"    {k:<16} {by_type.get(k, 0)}")
    return "\n".join(lines)
