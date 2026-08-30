"""The approval path: what actually happens when a proposal is accepted.

No model involved -- proposals are fabricated on disk exactly as the adapter
would write them, so this covers the half of the dormant agent that mutates
the catalogue. The LLM only chooses WHAT to propose; everything here is what
the code does with that proposal, and it is the part that touches real data.
"""
from __future__ import annotations

import shutil

import pytest

from nucleus import store
from nucleus.agents import adapter
from nucleus.catalog import Catalog
from nucleus.config import ROOT, Config, LLMConfig

REAL_META = ROOT / "data" / "datasets" / "running_shoes" / "meta.yaml"

ORIGINAL = "A trainer with a padded collar and a flat lace."
REWRITTEN = (
    "A trainer with a padded collar and a flat lace. "
    "The engineered mesh upper is breathable, with airflow to keep feet cool."
)


@pytest.fixture
def cfg(tmp_path) -> Config:
    c = Config(dataset="t_set", search_k=3, persona_count=2,
               embedding_model="all-MiniLM-L6-v2",
               llm=LLMConfig("offline", "none", 0, 1024), root=tmp_path)
    c.ensure_dirs()
    c.dataset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(REAL_META, c.meta_path)
    store.write_json(c.products_dir / "t_001.json", {
        "id": "t_001", "name": "Quiet Mesh", "price": 110,
        "specs": {"upper": "engineered mesh", "weight_g": 205},
        "description": ORIGINAL, "edit_history": [], "semantic_links": [],
    })
    return c


def _write_proposal(cfg: Config, **fields) -> str:
    pid = fields.get("id", "prop_001")
    store.write_json(cfg.proposals_dir / f"{pid}.json", {
        "id": pid, "gap_id": "gap_001", "product_id": "t_001",
        "created_at": "2026-01-01T00:00:00Z", "status": "pending",
        "based_on": [], "reason": "", **fields,
    })
    return pid


def test_approving_a_rewrite_updates_the_description(cfg):
    pid = _write_proposal(cfg, action="rewrite", intent="breathability",
                          new_description=REWRITTEN,
                          based_on=["upper: engineered mesh"])

    prop = adapter.approve(pid, cfg)

    assert prop["status"] == "approved"
    assert prop["applied"] == "description_updated"
    product = Catalog(cfg).get("t_001")
    assert product.description == REWRITTEN


def test_approving_a_rewrite_records_edit_history(cfg):
    pid = _write_proposal(cfg, action="rewrite", intent="breathability",
                          new_description=REWRITTEN,
                          based_on=["upper: engineered mesh"])
    adapter.approve(pid, cfg)

    product = Catalog(cfg).get("t_001")
    assert len(product.edit_history) == 1
    entry = product.edit_history[0]
    assert entry["added"] == REWRITTEN
    assert entry["replaced"] == ORIGINAL, "the previous copy must be recoverable"
    assert entry["based_on"] == ["upper: engineered mesh"]
    assert entry["proposal_id"] == pid


def test_no_change_records_a_link_and_touches_nothing_else(cfg):
    """The honest-no-op path: confirm the link, leave the copy alone."""
    pid = _write_proposal(
        cfg, action="no_change", intent="breathability in humidity",
        new_description=None,
        link={"intent": "breathability in humidity", "round": 1,
              "evidenced_by": "airy shoe for summer", "rank": 2})

    prop = adapter.approve(pid, cfg)

    assert prop["applied"] == "semantic_link_recorded"
    product = Catalog(cfg).get("t_001")
    assert product.description == ORIGINAL, "no_change must not alter the copy"
    assert product.edit_history == [], "no_change must not add an edit entry"
    assert product.semantic_links[0]["intent"] == "breathability in humidity"

    links = store.read_json(cfg.links_path, {})
    assert links["t_001"][0]["evidenced_by"] == "airy shoe for summer"


def test_confirming_the_same_link_twice_does_not_duplicate_it(cfg):
    link = {"intent": "breathability in humidity", "round": 1,
            "evidenced_by": "airy shoe", "rank": 2}
    adapter.approve(_write_proposal(cfg, id="prop_001", action="no_change",
                                    intent=link["intent"],
                                    new_description=None, link=link), cfg)
    adapter.approve(_write_proposal(cfg, id="prop_002", action="no_change",
                                    intent=link["intent"],
                                    new_description=None, link=link), cfg)

    assert len(Catalog(cfg).get("t_001").semantic_links) == 1
    assert len(store.read_json(cfg.links_path, {})["t_001"]) == 1


@pytest.mark.parametrize("action", ["flag", "skip"])
def test_flag_and_skip_never_touch_the_product(cfg, action):
    """These are the agent reporting back, not work to apply."""
    pid = _write_proposal(cfg, action=action, intent="wide toe box",
                          new_description=None,
                          reason="nothing in the specs supports this")

    prop = adapter.approve(pid, cfg)

    assert prop["applied"] == "acknowledged"
    product = Catalog(cfg).get("t_001")
    assert product.description == ORIGINAL
    assert product.edit_history == []
    assert product.semantic_links == []


def test_rejecting_leaves_everything_alone(cfg):
    pid = _write_proposal(cfg, action="rewrite", intent="breathability",
                          new_description=REWRITTEN, based_on=["upper"])

    prop = adapter.reject(pid, cfg)

    assert prop["status"] == "rejected"
    product = Catalog(cfg).get("t_001")
    assert product.description == ORIGINAL
    assert product.edit_history == []
