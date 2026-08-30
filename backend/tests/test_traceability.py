"""Tests for claim traceability.

These guard the project's central claim: the adapter cannot invent product
attributes. Every case here is a way an agent might try to make a product match
a query it doesn't legitimately answer.
"""
from __future__ import annotations

import pytest

from nucleus.catalog import Product
from nucleus.traceability import verify


@pytest.fixture(scope="module")
def meta(shoes_catalog):
    """Pinned to running_shoes: the fixture below is a shoe, built from that
    dataset's spec vocabulary. Swapping config.dataset must not change what
    these mechanism tests assert."""
    return shoes_catalog.meta


@pytest.fixture
def mesh_shoe():
    """Mesh upper, 210g, no waterproofing, no width spec recorded."""
    return Product(
        id="sku_test", name="Test Runner", price=150,
        specs={"weight_g": 210, "drop_mm": 6, "stack_height_mm": 24,
               "upper": "engineered mesh", "midsole": "EVA",
               "outsole": "4mm lugs", "plate": "none",
               "surface": "trail", "waterproof": False, "cushioning": "low"},
        description="A pared-back off-road silhouette. Finished with a moulded heel clip.",
    )


# --------------------------------------------------------------- the happy path
def test_claim_traceable_to_a_real_spec_survives(mesh_shoe, meta):
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. The engineered mesh upper is breathable.",
        [{"sentence": "The engineered mesh upper is breathable.",
          "spec_fields": ["upper"]}],
    )
    assert v.ok, v.reason
    assert "upper" in v.supporting_specs


def test_carried_over_sentences_need_no_claim(mesh_shoe, meta):
    v = verify(mesh_shoe, meta, mesh_shoe.description, [])
    assert v.ok, v.reason


# ------------------------------------------------------------ the refusal paths
def test_citing_a_spec_field_the_product_lacks_fails(mesh_shoe, meta):
    """The flag path: no width/last spec exists, so 'wide toe box' cannot be written."""
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. It has a generously wide toe box.",
        [{"sentence": "It has a generously wide toe box.",
          "spec_fields": ["toe_box_width"]}],
    )
    assert not v.ok
    assert "does not have" in v.reason


def test_claim_unsupported_by_the_cited_field_fails(mesh_shoe, meta):
    """Citing a real field that licenses nothing resembling the claim.

    Caught by the denial rule: this shoe is waterproof:False, so "waterproof"
    is forbidden vocabulary for it no matter which field the agent cites.
    """
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. Fully waterproof in heavy rain.",
        [{"sentence": "Fully waterproof in heavy rain.",
          "spec_fields": ["upper"]}],
    )
    assert not v.ok
    assert "do not support" in v.reason


def test_claim_contradicting_the_spec_value_fails(mesh_shoe, meta):
    """waterproof is False, so the waterproof rule never licenses these terms."""
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. Keeps your feet dry in the rain.",
        [{"sentence": "Keeps your feet dry in the rain.",
          "spec_fields": ["waterproof"]}],
    )
    assert not v.ok


def test_new_sentence_with_no_claim_at_all_fails(mesh_shoe, meta):
    """Neutral-sounding filler is not waved through -- it is how claims smuggle in."""
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. Perfect for sweaty summer mornings.",
        [],
    )
    assert not v.ok
    assert "no claim" in v.reason


def test_invented_number_fails(mesh_shoe, meta):
    """The shoe is 210g; the agent may not round it to a nicer number."""
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. At just 180g it is exceptionally light.",
        [{"sentence": "At just 180g it is exceptionally light.",
          "spec_fields": ["weight_g"]}],
    )
    assert not v.ok
    assert "180" in v.reason


def test_real_number_survives(mesh_shoe, meta):
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. At 210g it is a light trail option.",
        [{"sentence": "At 210g it is a light trail option.",
          "spec_fields": ["weight_g"]}],
    )
    assert v.ok, v.reason


def test_one_bad_sentence_sinks_the_whole_proposal(mesh_shoe, meta):
    """No partial acceptance: half-justified is not justified."""
    v = verify(
        mesh_shoe, meta,
        "The engineered mesh upper is breathable. It is also fully waterproof.",
        [{"sentence": "The engineered mesh upper is breathable.",
          "spec_fields": ["upper"]},
         {"sentence": "It is also fully waterproof.",
          "spec_fields": ["waterproof"]}],
    )
    assert not v.ok
    assert len(v.failures) == 1          # one sentence failed
    assert not v.ok                       # but the whole proposal is rejected


# ------------------------------------------------------- the real catalogue case
def test_flag_path_product_cannot_claim_toe_box_width(shoes_catalog):
    """sku_026 exists precisely so this path is exercised against real data."""
    catalog = shoes_catalog
    product = catalog.get("sku_026")
    v = verify(
        product, catalog.meta,
        product.description + " Built on a generously wide last with a roomy toe box.",
        [{"sentence": "Built on a generously wide last with a roomy toe box.",
          "spec_fields": ["upper"]}],
    )
    assert not v.ok, "the catalogue records no width spec; this must not be writable"


def test_flag_path_product_can_still_claim_what_it_does_support(shoes_catalog):
    """The refusal must be specific to the unsupported claim, not blanket."""
    catalog = shoes_catalog
    product = catalog.get("sku_026")
    v = verify(
        product, catalog.meta,
        product.description + " The engineered mesh upper is breathable.",
        [{"sentence": "The engineered mesh upper is breathable.",
          "spec_fields": ["upper"]}],
    )
    assert v.ok, v.reason


# ------------------------------------------- spec restatement and the denial rule
def test_verbatim_spec_restatement_is_allowed(mesh_shoe, meta):
    """Quoting the spec value is the most traceable thing copy can do."""
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. The upper is engineered mesh.",
        [{"sentence": "The upper is engineered mesh.", "spec_fields": ["upper"]}],
    )
    assert v.ok, v.reason


def test_a_true_clause_cannot_carry_a_false_one(mesh_shoe, meta):
    """The denial rule. Without it, restatement becomes a smuggling route."""
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. "
        "The upper is engineered mesh, and it is fully waterproof.",
        [{"sentence": "The upper is engineered mesh, and it is fully waterproof.",
          "spec_fields": ["upper"]}],
    )
    assert not v.ok, "a verbatim spec restatement must not license a second claim"
    assert "waterproof" in v.reason


def test_numbers_inside_string_specs_are_quotable(mesh_shoe, meta):
    """outsole is '4mm lugs', so the copy may legitimately say 4mm."""
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. The 4mm lugs give grip on trail.",
        [{"sentence": "The 4mm lugs give grip on trail.",
          "spec_fields": ["outsole", "surface"]}],
    )
    assert v.ok, v.reason


def test_a_number_in_no_spec_at_all_still_fails(mesh_shoe, meta):
    v = verify(
        mesh_shoe, meta,
        "A pared-back off-road silhouette. The 9mm lugs give grip on trail.",
        [{"sentence": "The 9mm lugs give grip on trail.",
          "spec_fields": ["outsole", "surface"]}],
    )
    assert not v.ok
    assert "9" in v.reason
