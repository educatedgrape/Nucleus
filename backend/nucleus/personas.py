"""Persona data model and storage.

A persona carries its own frozen `query`. Rounds 1 and 2 replay that exact
string rather than regenerating it, so the only thing that differs between
rounds is the product descriptions -- which is the whole point of the
comparison. Regenerating queries per round would let wording drift explain a
delta that had nothing to do with the rewrites.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from . import store
from .config import Config, load as load_config


@dataclass
class Persona:
    id: str
    seed_id: str
    origin: str                      # "real" | "synthetic"
    need: str
    must_have: list[str] = field(default_factory=list)
    prefer: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    angle: str = ""                  # what makes this variant different
    query: str = ""                  # frozen at spawn; replayed every round
    # Provenance for seed personas: the four raw onboarding answers, kept so
    # the user can see what their words were parsed into and correct it.
    source_answers: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "Persona":
        return cls(
            id=raw["id"], seed_id=raw.get("seed_id", ""),
            origin=raw.get("origin", "synthetic"), need=raw.get("need", ""),
            must_have=list(raw.get("must_have", [])),
            prefer=list(raw.get("prefer", [])),
            context=list(raw.get("context", [])),
            angle=raw.get("angle", ""), query=raw.get("query", ""),
            source_answers=dict(raw.get("source_answers", {})),
        )


class PersonaStore:
    def __init__(self, config: Config | None = None):
        self.config = config or load_config()

    def path(self, persona_id: str):
        return self.config.personas_dir / f"{persona_id}.json"

    def save(self, persona: Persona) -> None:
        store.write_json(self.path(persona.id), persona.to_dict())

    def save_all(self, personas: list[Persona]) -> None:
        for p in personas:
            self.save(p)

    def get(self, persona_id: str) -> Persona:
        raw = store.read_json(self.path(persona_id))
        if raw is None:
            raise KeyError(persona_id)
        return Persona.from_dict(raw)

    def seeds(self) -> list[Persona]:
        return [p for p in self.all() if p.origin == "real"]

    def synthetic(self) -> list[Persona]:
        return [p for p in self.all() if p.origin == "synthetic"]

    def all(self) -> list[Persona]:
        return [Persona.from_dict(r) for r in store.iter_json_dir(self.config.personas_dir)]

    def clear_synthetic(self) -> int:
        n = 0
        for p in self.synthetic():
            self.path(p.id).unlink(missing_ok=True)
            n += 1
        return n


class DuplicateAngles(ValueError):
    """build.md flags 'all personas ask the same thing' as a top failure mode.

    If every persona shares an angle the report has one finding and the adapter
    fixes it once, so this fails loudly at spawn rather than quietly at report.
    """


def assert_distinct_angles(personas: list[Persona]) -> None:
    seen: dict[str, list[str]] = {}
    for p in personas:
        seen.setdefault(p.angle.strip().lower(), []).append(p.id)
    dupes = {a: ids for a, ids in seen.items() if len(ids) > 1}
    if dupes:
        detail = "; ".join(f"{a!r}: {', '.join(ids)}" for a, ids in sorted(dupes.items()))
        raise DuplicateAngles(f"personas share an angle -- {detail}")
    blank = [p.id for p in personas if not p.angle.strip()]
    if blank:
        raise DuplicateAngles(f"personas with no angle: {', '.join(blank)}")


def assert_distinct_queries(personas: list[Persona]) -> None:
    seen: dict[str, list[str]] = {}
    for p in personas:
        seen.setdefault(p.query.strip().lower(), []).append(p.id)
    dupes = {q: ids for q, ids in seen.items() if len(ids) > 1}
    if dupes:
        detail = "; ".join(f"{q!r}: {', '.join(ids)}" for q, ids in sorted(dupes.items()))
        raise DuplicateAngles(f"personas share a query -- {detail}")
