"""End-to-end plumbing, with no model involved.

Builds a throwaway 4-product dataset in a temp directory and drives the
key-independent half of the loop: index -> round 1 -> edit a description ->
re-index -> round 2 -> score -> compare.

These edit the product directly rather than going through the approval flow,
because what they exercise is search and the comparison maths. The approval
path itself -- what `adapter.approve()` writes to the product, the edit
history and links.json -- is covered in test_approval.py.

This also doubles as the swap-dataset check: nothing here touches the real
running_shoes catalogue, and no code change is needed to point at another one.
"""
from __future__ import annotations

import json
import shutil

import pytest

from nucleus import results as results_mod
from nucleus import store
from nucleus.agents import searcher
from nucleus.catalog import Catalog
from nucleus.config import ROOT, Config, LLMConfig
from nucleus.personas import Persona, PersonaStore
from nucleus.scoring import Scores
from nucleus.search import SearchIndex

REAL_META = ROOT / "data" / "datasets" / "running_shoes" / "meta.yaml"

PRODUCTS = [
    # copy already states breathability -- should surface for the airy query
    dict(id="t_001", name="Airy One", price=100,
         specs={"upper": "engineered mesh", "weight_g": 200, "waterproof": False},
         description="A breathable summer trainer with excellent airflow across the forefoot."),
    # specs support breathability, copy is silent -- the gap
    dict(id="t_002", name="Quiet Mesh", price=110,
         specs={"upper": "engineered mesh", "weight_g": 205, "waterproof": False},
         description="A trainer with a padded collar and a flat lace."),
    # Deliberately NOT weather-adjacent. An earlier version of this fixture
    # described this product as waterproof "in heavy rain", and it outranked the
    # explicitly-breathable product for the airy query -- MiniLM matched on
    # weather generally, not breathability. That is a real property of small
    # corpora (sku_025 does the same thing in the full catalogue), but it makes
    # a 4-product fixture useless as an instrument, so the confound is removed.
    dict(id="t_003", name="Firm Post", price=130,
         specs={"upper": "ripstop", "weight_g": 300, "waterproof": True},
         description="A stability shoe with a firm medial post for overpronation."),
    dict(id="t_004", name="Plain Jane", price=90,
         specs={"upper": "synthetic", "weight_g": 280, "waterproof": False},
         description="A simple everyday shoe in three colourways."),
]

AIRY = "breathable airy shoe for hot humid summer weather"


@pytest.fixture
def cfg(tmp_path) -> Config:
    c = Config(dataset="t_set", search_k=2, persona_count=2,
               embedding_model="all-MiniLM-L6-v2",
               llm=LLMConfig("offline", "none", 0, 1024), root=tmp_path)
    c.ensure_dirs()
    c.dataset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(REAL_META, c.meta_path)
    for p in PRODUCTS:
        store.write_json(c.products_dir / f"{p['id']}.json",
                         {**p, "edit_history": [], "semantic_links": []})
    return c


@pytest.fixture
def personas(cfg) -> list[Persona]:
    ps = [
        Persona(id="p_001", seed_id="seed_01", origin="synthetic",
                need="something airy", angle="heat_wave", query=AIRY),
        Persona(id="p_002", seed_id="seed_01", origin="synthetic",
                need="support", angle="overpronator",
                query="stability shoe with support for overpronation"),
    ]
    PersonaStore(cfg).save_all(ps)
    return ps


def test_round_one_leaves_the_silent_product_unsurfaced(cfg, personas):
    res = searcher.run_round(1, cfg)
    assert res.query_count == 2
    # t_002 has the specs but says nothing, so it should not surface
    assert "t_002" in res.never_returned
    # t_001 says it, so it should
    assert "t_001" in res.returned_any


def test_rewrite_then_reindex_makes_the_silent_product_surface(cfg, personas):
    searcher.run_round(1, cfg)

    catalog = Catalog(cfg)
    product = catalog.get("t_002")
    product.description = (
        "A trainer with a padded collar and a flat lace. "
        "The engineered mesh upper is breathable, with airflow to keep feet cool."
    )
    product.edit_history.append({"at": "test", "added": "breathability",
                                 "based_on": ["upper: engineered mesh"]})
    catalog.save(product)

    stats = SearchIndex(config=cfg).build()
    assert stats["encoded"] == 1, "only the changed description should re-encode"
    assert stats["reused"] == 3

    res2 = searcher.run_round(2, cfg)
    assert "t_002" in res2.returned_any, "rewritten product should now surface"
    assert "t_002" not in res2.never_returned


def test_rewrite_improves_the_products_rank(cfg, personas):
    """The mechanism itself, independent of where the k cutoff happens to fall.

    Asserting only "lands in top-k" makes the test hostage to corpus size and
    to whichever unrelated product the encoder happens to like; rank movement
    is the thing the rewrite actually causes.
    """
    index = SearchIndex(config=cfg)
    index.build()
    before = [h.product_id for h in index.search(AIRY, k=len(PRODUCTS))]
    rank_before = before.index("t_002")

    catalog = Catalog(cfg)
    product = catalog.get("t_002")
    product.description = (
        "A trainer with a padded collar and a flat lace. "
        "The engineered mesh upper is breathable, with airflow to keep feet cool."
    )
    catalog.save(product)

    index = SearchIndex(config=cfg)
    index.build()
    after = [h.product_id for h in index.search(AIRY, k=len(PRODUCTS))]
    rank_after = after.index("t_002")

    assert rank_after < rank_before, (
        f"stating the attribute should move t_002 up the ranking, "
        f"but it went from position {rank_before + 1} to {rank_after + 1}")


def test_scores_are_reused_not_re_asked(cfg):
    scores = Scores(cfg)
    scores.set("t_001", "breathability", "right")
    assert scores.is_scored("t_001", "breathability")
    # same product, different intent -- genuinely unscored
    assert not scores.is_scored("t_001", "waterproofing")
    # verdicts are per-intent, so they can differ
    scores.set("t_001", "waterproofing", "wrong")
    assert Scores(cfg).verdict("t_001", "breathability") == "right"
    assert Scores(cfg).verdict("t_001", "waterproofing") == "wrong"


def test_results_report_the_delta(cfg, personas):
    searcher.run_round(1, cfg)

    catalog = Catalog(cfg)
    product = catalog.get("t_002")
    product.description = (
        "A trainer with a padded collar and a flat lace. "
        "The engineered mesh upper is breathable, with airflow to keep feet cool."
    )
    catalog.save(product)
    SearchIndex(config=cfg).build()
    searcher.run_round(2, cfg)

    # minimal report supplying the query -> intent mapping
    store.write_json(cfg.report_path, {
        "round": 1,
        "intents": [{"label": "breathability in humidity", "count": 1,
                     "examples": [AIRY]}],
        "gaps": [],
    })
    Scores(cfg).set("t_002", "breathability in humidity", "right")

    out = results_mod.compare(cfg)
    assert out["primary"]["count"] == 1
    assert out["primary"]["newly_surfacing_correct"][0]["product_id"] == "t_002"
    assert "t_002" in out["supporting"]["closed"]


def test_run_is_stable_across_repeats(cfg, personas):
    """build.md flags 'numbers move between runs' -- frozen queries plus a
    pinned k should make a round byte-identical when nothing changed."""
    a = searcher.run_round(1, cfg)
    first = json.dumps([r["returned"] for r in a.rows], sort_keys=True)
    b = searcher.run_round(1, cfg)
    second = json.dumps([r["returned"] for r in b.rows], sort_keys=True)
    assert first == second
    assert a.never_returned == b.never_returned


def test_round_one_refuses_to_run_after_rewrites(cfg, personas):
    """The baseline guard.

    Re-running round 1 once the agent's rewrites are live measures the improved
    copy, makes round 1 identical to round 2, and collapses the delta to zero --
    silently, with no error. This actually happened during development, so it is
    refused rather than warned about.
    """
    searcher.run_round(1, cfg)

    catalog = Catalog(cfg)
    product = catalog.get("t_002")
    product.description = "Now mentions breathable mesh and airflow."
    product.edit_history.append({"at": "test", "added": "breathability",
                                 "based_on": ["upper: engineered mesh"]})
    catalog.save(product)

    with pytest.raises(searcher.BaselineWouldBeInvalid) as excinfo:
        searcher.run_round(1, cfg)
    assert "t_002" in str(excinfo.value)
    assert "reset" in str(excinfo.value), "the refusal must say how to proceed"


def test_round_two_is_never_blocked(cfg, personas):
    """Round 2 is SUPPOSED to run against rewritten copy -- that is the point."""
    searcher.run_round(1, cfg)
    catalog = Catalog(cfg)
    product = catalog.get("t_002")
    product.description = "Now mentions breathable mesh and airflow."
    product.edit_history.append({"at": "test", "added": "x", "based_on": []})
    catalog.save(product)

    res = searcher.run_round(2, cfg)
    assert res.query_count == 2


def test_force_allows_a_deliberate_rerun(cfg, personas):
    searcher.run_round(1, cfg)
    catalog = Catalog(cfg)
    product = catalog.get("t_002")
    product.edit_history.append({"at": "test", "added": "x", "based_on": []})
    catalog.save(product)

    res = searcher.run_round(1, cfg, force=True)
    assert res.query_count == 2
