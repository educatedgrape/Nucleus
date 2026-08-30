"""Claim traceability -- enforced in code, not in the prompt.

build.md is explicit about why this exists: an agent told to make products
match will otherwise invent claims. A prompt asking it not to is not a control;
this module is.

The rule every rewritten description must satisfy:

  1. A sentence carried over verbatim from the original description is fine.
  2. Any NEW sentence must be cited in `claims` with one or more spec fields.
  3. Every cited spec field must actually exist on that product.
  4. The sentence must be positively justified, either by using a term those
     cited fields license, or by restating a cited field's value verbatim
     ("the upper is engineered mesh" when upper IS engineered mesh).
  5. The sentence must contain NO claim term this product's specs fail to
     license -- the denial rule.
  6. Every number must appear somewhere in the product's specs, including
     inside string values like "5mm aggressive lugs".

Rule 2 is deliberately strict: neutral-sounding filler is not waved through,
because "great for sweaty summer mornings" contains no term in any licence list
and would otherwise smuggle an unsupported claim past the check. If the agent
wants neutral prose it must carry the original sentence over unchanged.

Rule 5 is what makes rule 4's verbatim-restatement path safe. Without it,
"The upper is engineered mesh, and it is fully waterproof" would pass on the
strength of the true half while smuggling the false half. Allow-listing alone
is not enough once a sentence can contain more than one claim.

A single failing sentence downgrades the WHOLE proposal to `flag`. No partial
acceptance -- a description that is half-justified is not justified.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .catalog import DatasetMeta, Product


@dataclass
class SentenceVerdict:
    sentence: str
    ok: bool
    cited_specs: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class Verification:
    ok: bool
    verdicts: list[SentenceVerdict]
    supporting_specs: list[str]

    @property
    def failures(self) -> list[SentenceVerdict]:
        return [v for v in self.verdicts if not v.ok]

    @property
    def reason(self) -> str:
        return "; ".join(f"{v.reason}" for v in self.failures)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _term_present(term: str, sentence: str) -> bool:
    """Match a licensed term as a whole word, tolerating hyphen/space variants."""
    pattern = re.escape(term).replace(r"\-", r"[\s\-]?").replace(r"\ ", r"[\s\-]?")
    return re.search(rf"\b{pattern}", sentence, re.IGNORECASE) is not None


def verify(
    product: Product,
    meta: DatasetMeta,
    new_description: str,
    claims: list[dict],
) -> Verification:
    """Check a proposed description against the product's actual specs."""
    licensed = meta.licensed_terms(product.specs)          # term -> [spec fields]
    original = {_normalise(s) for s in split_sentences(product.description)}

    by_sentence: dict[str, dict] = {}
    for c in claims or []:
        if isinstance(c, dict) and c.get("sentence"):
            by_sentence[_normalise(str(c["sentence"]))] = c

    # Every claim term the dataset knows about. Anything in here that this
    # product does NOT license is forbidden outright (the denial rule).
    all_terms = {t for rule in meta.claim_rules for t in rule.licenses}
    forbidden = all_terms - set(licensed)

    # Numbers this product may legitimately quote. Harvested from the numeric
    # fields AND from digits inside string values -- `outsole: "5mm aggressive
    # lugs"` genuinely entitles the copy to say "5mm".
    numeric_values: set[str] = set()
    for fieldname in meta.numeric_fields:
        val = product.specs.get(fieldname)
        if val is None and fieldname == "price":
            val = product.price
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            numeric_values.add(_fmt_number(val))
    for val in list(product.specs.values()) + [product.price]:
        if isinstance(val, str):
            numeric_values.update(_NUMBER.findall(val))
        elif isinstance(val, (int, float)) and not isinstance(val, bool):
            numeric_values.add(_fmt_number(val))

    verdicts: list[SentenceVerdict] = []
    supporting: set[str] = set()

    for sentence in split_sentences(new_description):
        key = _normalise(sentence)

        if key in original:
            verdicts.append(SentenceVerdict(sentence, True, reason="carried over unchanged"))
            continue

        claim = by_sentence.get(key)
        if claim is None:
            verdicts.append(SentenceVerdict(
                sentence, False,
                reason=f"new sentence with no claim citing any spec field: {sentence!r}"))
            continue

        cited = [str(s) for s in (claim.get("spec_fields") or [])]
        if not cited:
            verdicts.append(SentenceVerdict(
                sentence, False, reason=f"claim cites no spec fields: {sentence!r}"))
            continue

        missing = [s for s in cited if s not in product.specs]
        if missing:
            verdicts.append(SentenceVerdict(
                sentence, False, cited_specs=cited,
                reason=(f"cites spec field(s) this product does not have: "
                        f"{', '.join(missing)}")))
            continue

        # The denial rule, checked FIRST: a claim term this product's specs do
        # not license may never appear, however well-justified the rest of the
        # sentence is. This is what stops a true clause carrying a false one.
        smuggled = sorted(t for t in forbidden if _term_present(t, sentence))
        if smuggled:
            verdicts.append(SentenceVerdict(
                sentence, False, cited_specs=cited,
                reason=(f"claims {', '.join(smuggled)}, which this product's "
                        f"specs do not support: {sentence!r}")))
            continue

        # Positive justification: a licensed term from a cited field, or a
        # verbatim restatement of a cited field's value. Restating the spec is
        # the most traceable thing copy can do -- it quotes the data.
        matched = [t for t, specs in licensed.items()
                   if any(s in cited for s in specs) and _term_present(t, sentence)]
        restated = [s for s in cited if _restates(s, product, sentence)]
        if not matched and not restated:
            verdicts.append(SentenceVerdict(
                sentence, False, cited_specs=cited,
                reason=(f"nothing in {', '.join(cited)} licenses any claim made by: "
                        f"{sentence!r}")))
            continue

        # Numbers must reconcile against a numeric spec value.
        bad_numbers = [n for n in _NUMBER.findall(sentence)
                       if _fmt_number(float(n)) not in numeric_values]
        if bad_numbers:
            verdicts.append(SentenceVerdict(
                sentence, False, cited_specs=cited, matched_terms=matched,
                reason=(f"quotes number(s) {', '.join(bad_numbers)} not present in "
                        f"this product's specs")))
            continue

        supporting.update(cited)
        verdicts.append(SentenceVerdict(sentence, True, cited, matched,
                                        reason="traced to specs"))

    return Verification(
        ok=all(v.ok for v in verdicts) and bool(verdicts),
        verdicts=verdicts,
        supporting_specs=sorted(supporting),
    )


def _restates(spec_field: str, product: Product, sentence: str) -> bool:
    """True when the sentence says "<field> is <value>" for a real spec.

    BOTH the field and its value must appear. Matching the value alone is not
    enough: short generic values like cushioning "low" or "high" collide with
    ordinary English ("a low carbon footprint", "high arches") and would wave
    through claims that have nothing to do with the spec.
    """
    value = product.specs.get(spec_field)
    if not isinstance(value, str) or not value.strip():
        return False
    if not _term_present(value, sentence):
        return False
    # Any reasonably distinctive token of the field name, so `weight_g` is
    # satisfied by "weight" and `stack_height_mm` by "stack" or "height".
    tokens = [t for t in spec_field.split("_") if len(t) >= 4]
    return any(_term_present(t, sentence) for t in tokens)


def _fmt_number(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def describe_specs(product: Product, meta: DatasetMeta) -> list[str]:
    """Human-readable `field: value` lines, for prompts and `based_on`."""
    return [f"{k}: {product.specs[k]}" for k in sorted(product.specs)]
