"""Persona spawning: one seed -> N synthetic personas.

Generated from the seed and the category name ONLY. The catalogue is never
shown to this agent: personas built from the product data ask about what the
catalogue already covers, nothing fails to surface, and the whole exercise
produces a report with no findings in it.

Each persona gets a distinct `angle` and a frozen `query`. Both are asserted,
because "all personas ask the same thing" collapses the report to one finding.
"""
from __future__ import annotations

from ..catalog import Catalog
from ..config import Config, load as load_config
from ..llm import get_client
from ..personas import (Persona, PersonaStore, assert_distinct_angles,
                        assert_distinct_queries)

SYSTEM = """You generate synthetic shopper personas from one real seed persona.

These are NOT copies of the seed and NOT different people. They are the same
shopper in different situations: a tighter budget, a sudden deadline, a first
attempt versus a fifth, a different aspect of the same underlying need, a
different season, a different level of confidence in their own knowledge.

Rules:
- The spread matters more than the realism of any one persona. If they all ask
  about the same attribute, the exercise is worthless.
- Every persona needs a DISTINCT `angle`: a short snake_case label naming what
  makes this variant different (budget_conscious, race_deadline, first_timer,
  heat_wave, injury_returning, ...). No two may share an angle.
- Every persona needs a DISTINCT `query`: how that person would actually type
  their search in plain English. Natural and specific, not keyword soup.
  Vary length and phrasing; some people write a sentence, some write five words.
- Stay anchored to the seed's stated needs and constraints. Do not invent a
  different shopper.
- You will NOT be shown any products. Do not try to guess a catalogue.

Return JSON: {"personas": [{"need", "must_have", "prefer", "context", "angle",
"query"}, ...]}
"""


#: Personas per call. Asking for all 30 at once overflowed the output cap and
#: came back as truncated JSON; smaller batches also keep the spread honest,
#: because a model listing 30 in one breath starts repeating itself near the end.
BATCH_SIZE = 10
MAX_ATTEMPTS = 6


def spawn(
    seed: Persona,
    count: int | None = None,
    config: Config | None = None,
    progress=None,
) -> list[Persona]:
    """Generate `count` synthetic personas from `seed`. Does not save.

    Generated in batches, each told which angles and queries are already taken,
    so distinctness holds across the whole set rather than only within a call.
    """
    config = config or load_config()
    count = count or config.persona_count
    catalog = Catalog(config)          # for the category phrase ONLY
    client = get_client(config)

    seed_block = (
        f"Category: {catalog.meta.category_phrase}\n\n"
        f"Seed persona (a real person):\n"
        f"  need: {seed.need}\n"
        f"  must_have: {seed.must_have}\n"
        f"  prefer: {seed.prefer}\n"
        f"  context: {seed.context}\n"
    )

    personas: list[Persona] = []
    seen_angles: set[str] = set()
    seen_queries: set[str] = set()
    attempts = 0

    while len(personas) < count and attempts < MAX_ATTEMPTS:
        attempts += 1
        want = min(BATCH_SIZE, count - len(personas))
        taken = ""
        if seen_angles:
            taken = (
                "\n\nAngles already used -- do NOT reuse any of these, and do "
                "not produce a near-synonym of one:\n"
                + "\n".join(f"  - {a}" for a in sorted(seen_angles))
            )
        user = (
            f"{seed_block}{taken}\n\n"
            f"Generate exactly {want} synthetic personas, each with a distinct "
            f"angle and a distinct query."
        )
        raw = client.json(SYSTEM, user)
        rows = raw.get("personas", raw if isinstance(raw, list) else [])

        for r in rows:
            if len(personas) >= count:
                break
            angle = str(r.get("angle", "")).strip()
            query = str(r.get("query", "")).strip()
            akey, qkey = angle.lower(), query.lower()
            # Dedupe here rather than failing the whole run: a repeated angle
            # is the model drifting, not a reason to throw away 20 good personas.
            if not angle or not query or akey in seen_angles or qkey in seen_queries:
                continue
            seen_angles.add(akey)
            seen_queries.add(qkey)
            personas.append(Persona(
                id=f"p_{len(personas) + 1:03d}", seed_id=seed.id,
                origin="synthetic",
                need=str(r.get("need", "")).strip(),
                must_have=[str(x) for x in r.get("must_have", [])],
                prefer=[str(x) for x in r.get("prefer", [])],
                context=[str(x) for x in r.get("context", [])],
                angle=angle, query=query,
            ))
        if progress:
            progress(len(personas), count, f"batch {attempts}")

    if len(personas) < count:
        raise ValueError(
            f"asked for {count} distinct personas but only got {len(personas)} "
            f"after {attempts} batches -- the model kept repeating angles. "
            f"Lower persona_count, or widen the seed persona.")

    # Fail loudly here rather than quietly at report time.
    assert_distinct_angles(personas)
    assert_distinct_queries(personas)
    return personas


def spawn_and_freeze(
    seed: Persona,
    count: int | None = None,
    config: Config | None = None,
    replace: bool = False,
    progress=None,
) -> list[Persona]:
    """Spawn and write to disk. Frozen once generated -- never regenerate
    implicitly, or round 2 stops being comparable to round 1."""
    config = config or load_config()
    store = PersonaStore(config)
    existing = store.synthetic()
    if existing and not replace:
        raise FileExistsError(
            f"{len(existing)} synthetic personas already exist and are frozen. "
            "Pass replace=True only if you intend to invalidate existing rounds."
        )
    if replace:
        store.clear_synthetic()

    personas = spawn(seed, count, config, progress=progress)
    store.save_all(personas)
    return personas
