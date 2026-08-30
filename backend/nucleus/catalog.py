"""The product catalogue and its dataset descriptor.

All category-specific knowledge -- spec labels, claim traceability rules, which
attributes the catalogue records no spec for -- is read from the dataset's
`meta.yaml`. This module knows nothing about running shoes specifically, which
is what makes swapping datasets a config change rather than a code change.
"""
from __future__ import annotations

import dataclasses
import functools
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from . import store
from .config import Config, load as load_config


@dataclass
class Product:
    id: str
    name: str
    price: float
    specs: dict[str, Any]
    description: str
    edit_history: list[dict] = field(default_factory=list)
    semantic_links: list[dict] = field(default_factory=list)

    @property
    def search_text(self) -> str:
        """What the search index embeds.

        The description ONLY -- deliberately not the name. Product names leak
        attributes the description withholds ("Trail Runner Lite" implies light,
        "Halcyon Breeze" implies airflow), which would mask exactly the gaps
        this project exists to find. build.md says "embed every product
        description"; this is that, literally.
        """
        return self.description

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ClaimRule:
    """One licence to make a claim, granted by a spec value.

    `spec` must be present on the product and its value must satisfy `when`;
    the rule then licenses the terms in `licenses`.
    """
    spec: str
    when: dict[str, Any]
    licenses: tuple[str, ...]

    def holds_for(self, specs: dict[str, Any]) -> bool:
        if self.spec not in specs:
            return False
        value = specs[self.spec]
        if value is None:
            return False
        for op, operand in self.when.items():
            if op == "matches":
                if not isinstance(value, str):
                    return False
                if not re.search(operand, value, re.IGNORECASE):
                    return False
            elif op == "equals":
                if value != operand:
                    return False
            elif op == "below":
                if not _numeric(value) or float(value) >= float(operand):
                    return False
            elif op == "at_or_below":
                if not _numeric(value) or float(value) > float(operand):
                    return False
            elif op == "at_or_above":
                if not _numeric(value) or float(value) < float(operand):
                    return False
            elif op == "above":
                if not _numeric(value) or float(value) <= float(operand):
                    return False
            else:
                raise ValueError(f"unknown claim-rule operator: {op!r}")
        return True


def _numeric(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


@dataclass
class DatasetMeta:
    category: str
    display_name: str
    category_phrase: str
    currency: str
    spec_labels: dict[str, str]
    claim_rules: tuple[ClaimRule, ...]
    numeric_fields: tuple[str, ...]
    unsupported_attributes: tuple[str, ...]
    probes: tuple[dict[str, Any], ...] = ()
    unsupported_claims: tuple[str, ...] = ()
    supported_claim_example: dict[str, Any] | None = None

    @classmethod
    def load(cls, path: pathlib.Path) -> "DatasetMeta":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        rules = tuple(
            ClaimRule(spec=r["spec"], when=dict(r["when"]),
                      licenses=tuple(t.lower() for t in r["licenses"]))
            for r in raw.get("claim_rules", [])
        )
        return cls(
            category=raw["category"],
            display_name=raw.get("display_name", raw["category"]),
            category_phrase=raw.get("category_phrase", raw["category"]),
            currency=raw.get("currency", "$"),
            spec_labels=dict(raw.get("spec_labels", {})),
            claim_rules=rules,
            numeric_fields=tuple(raw.get("numeric_fields", [])),
            unsupported_attributes=tuple(raw.get("unsupported_attributes", [])),
            probes=tuple(
                {"query": p["query"],
                 "expect": list(p.get("expect", [])),
                 "blind": list(p.get("blind", []))}
                for p in raw.get("probes", [])
            ),
            unsupported_claims=tuple(raw.get("unsupported_claims", [])),
            supported_claim_example=(
                dict(raw["supported_claim_example"])
                if raw.get("supported_claim_example") else None
            ),
        )

    def licensed_terms(self, specs: dict[str, Any]) -> dict[str, list[str]]:
        """Terms this product's specs permit -> the spec fields licensing them.

        This is the whole basis of claim traceability. A term absent from this
        mapping cannot appear in a rewritten description.
        """
        out: dict[str, list[str]] = {}
        for rule in self.claim_rules:
            if rule.holds_for(specs):
                for term in rule.licenses:
                    out.setdefault(term, []).append(rule.spec)
        return out

    def spec_label(self, key: str) -> str:
        return self.spec_labels.get(key, key.replace("_", " "))


class Catalog:
    """All products for the configured dataset, plus its descriptor."""

    def __init__(self, config: Config | None = None):
        self.config = config or load_config()
        self.meta = DatasetMeta.load(self.config.meta_path)
        self._products: dict[str, Product] = {}
        self.reload()

    def reload(self) -> None:
        self._products = {}
        for raw in store.iter_json_dir(self.config.products_dir):
            p = Product(
                id=raw["id"], name=raw["name"], price=raw["price"],
                specs=raw.get("specs", {}), description=raw.get("description", ""),
                edit_history=raw.get("edit_history", []),
                semantic_links=raw.get("semantic_links", []),
            )
            self._products[p.id] = p

    # -- access ------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._products)

    def __iter__(self):
        return iter(self.products)

    @property
    def products(self) -> list[Product]:
        return [self._products[k] for k in sorted(self._products)]

    @property
    def ids(self) -> list[str]:
        return sorted(self._products)

    def get(self, product_id: str) -> Product:
        return self._products[product_id]

    def path_for(self, product_id: str) -> pathlib.Path:
        return self.config.products_dir / f"{product_id}.json"

    # -- mutation ----------------------------------------------------------
    def save(self, product: Product) -> None:
        store.write_json(self.path_for(product.id), product.to_dict())
        self._products[product.id] = product
