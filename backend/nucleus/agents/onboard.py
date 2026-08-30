"""Onboarding: four answers from a real person -> one structured seed persona.

The parsed persona is returned for the user to correct before it is saved.
Their words are kept verbatim in `source_answers` so the parse stays auditable.
"""
from __future__ import annotations

from ..catalog import Catalog
from ..config import Config, load as load_config
from ..llm import get_client
from ..personas import Persona, PersonaStore

QUESTIONS = {
    "last_bought": "What did you last buy?",
    "almost_bought": "What did you almost buy instead?",
    "why_not": "Why didn't you?",
    "never_compromise": "What would you never compromise on?",
}

SYSTEM = """You turn a shopper's own words into a structured persona.

Work only from what they actually said. Do not invent budgets, brands or
constraints they did not mention. If they did not state something, leave it out
rather than guessing -- an invented constraint will send every synthetic
persona chasing something the real person never cared about.

Return JSON with exactly these keys:
  need              one sentence, what they are actually shopping for
  must_have         list of hard constraints, their words where possible
  prefer            list of soft preferences
  context           list of situational facts (climate, mileage, body, terrain)
  query             one natural-language search query this person would type
"""


def parse_answers(answers: dict[str, str], config: Config | None = None) -> Persona:
    """Parse the four onboarding answers into a seed persona (unsaved)."""
    config = config or load_config()
    catalog = Catalog(config)
    client = get_client(config)

    lines = [f"{QUESTIONS[k]}\n  {answers.get(k, '').strip()}" for k in QUESTIONS]
    user = (
        f"Category: {catalog.meta.category_phrase}\n\n"
        f"The shopper's answers:\n\n" + "\n\n".join(lines)
    )
    raw = client.json(SYSTEM, user)

    return Persona(
        id="seed_01", seed_id="seed_01", origin="real",
        need=str(raw.get("need", "")).strip(),
        must_have=[str(x) for x in raw.get("must_have", [])],
        prefer=[str(x) for x in raw.get("prefer", [])],
        context=[str(x) for x in raw.get("context", [])],
        angle="seed",
        query=str(raw.get("query", "")).strip(),
        source_answers={k: answers.get(k, "") for k in QUESTIONS},
    )


def save_seed(persona: Persona, config: Config | None = None) -> Persona:
    """Persist a seed persona after the user has reviewed/corrected it."""
    PersonaStore(config or load_config()).save(persona)
    return persona
