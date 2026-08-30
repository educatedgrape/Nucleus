"""The dormant agent.

Idle until a report exists, then reads it and decides what to do per gap:

  fixable          rewrite the description, recording which spec fields justify
                   each sentence
  needs_evidence   flag it, propose no change
  not_applicable   skip, note it as a product gap
  already_covered  confirm the semantic link, change nothing

Two things are enforced in code rather than asked for in the prompt:

  1. Every sentence of a rewrite must trace to a real spec field
     (see nucleus/traceability.py). A proposal that fails is automatically
     downgraded to `flag` -- the model does not get to overrule this.
  2. `no_change` is a real outcome. A product that already surfaces is left
     alone and its link recorded, rather than being rewritten to look busy.
"""
from __future__ import annotations

import datetime as _dt

from .. import store
from ..catalog import Catalog, Product
from ..config import Config, load as load_config
from ..llm import get_client
from ..traceability import verify

class StaleProposal(RuntimeError):
    """A rewrite whose starting copy has since changed underneath it."""


REWRITE_SYSTEM = """You rewrite one product description so it says what the specs
already support -- and nothing more.

You are given a product's specs, its current description, and a shopper intent
it failed to surface for.

Hard rules:
- Every NEW sentence you write must be justified by a specific spec field, and
  you must cite that field in `claims`. Sentences you keep unchanged from the
  original need no citation, and keeping them is encouraged.
- You may only state what the specs support. If the intent asks about something
  the specs do not record, DO NOT WRITE IT. Say so instead, by returning
  action "flag". Refusing is a correct and valuable answer here.
- Never invent a number. Quote only numbers that appear in the specs.
- Keep the voice of the original. You are adding what was missing, not writing
  an advert. Two or three sentences added at most.

Write the BENEFIT, not the spec sheet. The shopper searched for what the product
does for them, so name that, anchored to the spec:

  weak   "The upper is made from engineered mesh."
  good   "The engineered mesh upper is breathable, moving air over the foot on
          humid runs."

  weak   "Features a Pebax midsole."
  good   "The Pebax midsole is responsive and returns energy at tempo."

A bare restatement of a spec is allowed, but it rarely helps the shopper and it
rarely helps the product surface -- the search matches on what the copy MEANS.

NEVER put citation markup in the description itself. No "[upper]", no
"(weight_g)", no bracketed field names anywhere in `new_description`. Citations
belong only in the `claims` array. The description must read as clean product
copy that a customer would see.

Return JSON:
{
  "action": "rewrite" | "flag",
  "new_description": "the full new description, or null if flagging",
  "claims": [{"sentence": "exact sentence from new_description",
              "spec_fields": ["weight_g"]}],
  "reason": "one sentence -- if flagging, what evidence is missing"
}
"""


def _next_id(config: Config) -> str:
    existing = list(config.proposals_dir.glob("prop_*.json"))
    return f"prop_{len(existing) + 1:03d}"


def _proposal(config: Config, **fields) -> dict:
    p = {"id": _next_id(config),
         "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
         "status": "pending", **fields}
    store.write_json(config.proposals_dir / f"{p['id']}.json", p)
    return p


def run(
    report: dict,
    config: Config | None = None,
    progress=None,
) -> list[dict]:
    """Produce one proposal per gap. Returns the proposals."""
    config = config or load_config()
    config.proposals_dir.mkdir(parents=True, exist_ok=True)
    catalog = Catalog(config)
    client = get_client(config)

    proposals: list[dict] = []
    gaps = report.get("gaps", [])

    for n, gap in enumerate(gaps, start=1):
        gtype = gap["type"]
        product = catalog.get(gap["product_id"])
        common = dict(gap_id=gap["id"], product_id=product.id, intent=gap["intent"])

        if gtype == "already_covered":
            proposals.append(_proposal(
                config, **common, action="no_change", new_description=None,
                based_on=[],
                reason="Already surfaces for this intent; the description is "
                       "doing its job. No change necessary.",
                link={"intent": gap["intent"], "round": report.get("round", 1),
                      "evidenced_by": gap.get("evidenced_by", ""),
                      "rank": gap.get("rank")}))

        elif gtype == "not_applicable":
            proposals.append(_proposal(
                config, **common, action="skip", new_description=None,
                based_on=[],
                reason=gap.get("rationale")
                or "The product genuinely does not fit this intent."))

        elif gtype == "needs_evidence":
            proposals.append(_proposal(
                config, **common, action="flag", new_description=None,
                based_on=[],
                reason=gap.get("rationale")
                or "Plausible, but nothing in the product data supports it."))

        elif gtype == "fixable":
            proposals.append(_rewrite(client, config, catalog, product, gap, common))

        if progress:
            progress(n, len(gaps), gap)

    return proposals


def _rewrite(client, config: Config, catalog: Catalog, product: Product,
             gap: dict, common: dict) -> dict:
    spec_lines = "\n".join(f"  {k}: {v}" for k, v in sorted(product.specs.items()))
    user = (
        f"Product: {product.name} ({product.id})\n"
        f"Specs:\n{spec_lines}\n\n"
        f"Current description:\n  {product.description}\n\n"
        f"Shopper intent it failed to surface for:\n  {gap['intent']}\n\n"
        f"The report believes these spec fields may support it: "
        f"{', '.join(gap.get('supporting_specs') or []) or '(none identified)'}"
    )
    raw = client.json(REWRITE_SYSTEM, user)

    action = str(raw.get("action", "")).strip()
    new_description = raw.get("new_description")
    claims = raw.get("claims") or []

    # The model chose to refuse. That is a valid, and often correct, answer.
    if action == "flag" or not new_description:
        return _proposal(
            config, **common, action="flag", new_description=None, based_on=[],
            reason=str(raw.get("reason", "")).strip()
            or "The agent could not support this claim from the specs.")

    # Enforced in code: every sentence must trace to a real spec field.
    result = verify(product, catalog.meta, str(new_description), claims)
    if not result.ok:
        return _proposal(
            config, **common, action="flag", new_description=None, based_on=[],
            reason="Downgraded automatically: proposed copy could not be traced "
                   "to the specs.",
            downgraded_from="rewrite",
            rejected_description=str(new_description),
            traceability_failures=[v.reason for v in result.failures])

    return _proposal(
        config, **common, action="rewrite",
        new_description=str(new_description).strip(),
        based_on=[f"{s}: {product.specs[s]}" for s in result.supporting_specs],
        reason=str(raw.get("reason", "")).strip() or "Description now states what "
               "the specs already supported.",
        # The copy this rewrite was built on. A product with several fixable
        # gaps gets several proposals, each written against the ORIGINAL text;
        # approving them blindly in sequence would silently discard whichever
        # was applied first. Recorded so approval can detect that.
        from_description=product.description,
        claims=claims)


# --------------------------------------------------------------------- approval
def load_proposals(config: Config | None = None, status: str | None = None) -> list[dict]:
    config = config or load_config()
    rows = list(store.iter_json_dir(config.proposals_dir))
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return sorted(rows, key=lambda r: r["id"])


def set_status(proposal_id: str, status: str, config: Config | None = None) -> dict:
    config = config or load_config()
    path = config.proposals_dir / f"{proposal_id}.json"
    prop = store.read_json(path)
    if prop is None:
        raise KeyError(proposal_id)
    prop["status"] = status
    store.write_json(path, prop)
    return prop


def approve(proposal_id: str, config: Config | None = None) -> dict:
    """Apply an approved proposal.

    `rewrite`   writes the new description, appends to edit_history, and the
                caller must re-index.
    `no_change` records the confirmed semantic link and touches nothing else --
                no description change, no edit_history entry, no re-index.
    """
    config = config or load_config()
    prop = set_status(proposal_id, "approved", config)
    catalog = Catalog(config)
    product = catalog.get(prop["product_id"])

    if prop["action"] == "rewrite":
        # Refuse to apply a rewrite composed against copy that has since moved.
        # Silently clobbering an earlier approved change would make the product
        # JSON disagree with its own edit_history.
        origin = prop.get("from_description")
        if origin is not None and origin != product.description:
            set_status(prop["id"], "pending", config)
            raise StaleProposal(
                f"{prop['id']} was written against an earlier version of "
                f"{product.id}'s description, which has since been rewritten. "
                f"Applying it would discard that change. Re-run `adapt` to "
                f"regenerate proposals against the current copy."
            )
        product.edit_history.append({
            "at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "added": prop["new_description"],
            "replaced": product.description,
            "based_on": prop.get("based_on", []),
            "proposal_id": prop["id"],
        })
        product.description = prop["new_description"]
        catalog.save(product)
        prop["applied"] = "description_updated"

    elif prop["action"] == "no_change":
        link = dict(prop.get("link") or {})
        link.setdefault("intent", prop.get("intent", ""))
        if not any(l.get("intent") == link["intent"] for l in product.semantic_links):
            product.semantic_links.append(link)
            catalog.save(product)
        _record_link(config, product.id, link)
        prop["applied"] = "semantic_link_recorded"

    else:  # flag / skip -- acknowledged, nothing to write to the product
        prop["applied"] = "acknowledged"

    store.write_json(config.proposals_dir / f"{prop['id']}.json", prop)
    return prop


def reject(proposal_id: str, config: Config | None = None) -> dict:
    return set_status(proposal_id, "rejected", config)


def _record_link(config: Config, product_id: str, link: dict) -> None:
    links = store.read_json(config.links_path, default={}) or {}
    entries = links.setdefault(product_id, [])
    if not any(e.get("intent") == link.get("intent") for e in entries):
        entries.append(link)
    store.write_json(config.links_path, links)
