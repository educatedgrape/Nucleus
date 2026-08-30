"""The refusal surface.

`meta.yaml` lists attributes the catalogue records no spec for. That list is
only honest if it is true -- if some claim rule quietly licensed "arch support",
the adapter would happily write it and the list would be a lie.

These tests hold the two halves together: nothing in the list is licensable by
any product, and the flag path fires for real products, not just contrived ones.

They run against whichever dataset config.yaml selects, and take their claim
sentences from that dataset's `unsupported_claims`. A new catalogue therefore
arrives with its own refusal surface under test, rather than inheriting a list
of running-shoe sentences that its spec vocabulary could never license anyway.
"""
from __future__ import annotations

import pytest

from nucleus.catalog import Catalog
from nucleus.traceability import verify

from .conftest import catalog_for

DATASETS = ["running_shoes", "laptops"]


@pytest.fixture(scope="module", params=DATASETS)
def catalog(request) -> Catalog:
    return catalog_for(request.param)


def test_the_unsupported_list_is_not_empty(catalog):
    assert catalog.meta.unsupported_attributes, (
        "with no unsupported attributes the agent can never be asked to refuse, "
        "and the flag path is dead code")


def test_every_unsupported_attribute_has_a_claim_sentence(catalog):
    """The list and the test corpus must not drift apart.

    An attribute with no sentence exercising it is an untested promise.
    """
    assert len(catalog.meta.unsupported_claims) >= len(catalog.meta.unsupported_attributes), (
        f"{catalog.meta.category} lists {len(catalog.meta.unsupported_attributes)} "
        f"unsupported attributes but only {len(catalog.meta.unsupported_claims)} "
        "claim sentences to test them with")


def test_no_product_in_the_catalogue_can_make_any_unsupported_claim(catalog):
    """Not one product may license any of these, under any citation."""
    assert catalog.meta.unsupported_claims, "no claim sentences to test"
    for sentence in catalog.meta.unsupported_claims:
        for product in catalog.products:
            for spec_field in product.specs:
                v = verify(product, catalog.meta,
                           f"{product.description} {sentence}",
                           [{"sentence": sentence, "spec_fields": [spec_field]}])
                assert not v.ok, (
                    f"[{catalog.meta.category}] {product.id} was able to claim "
                    f"{sentence!r} by citing {spec_field!r} -- either that claim "
                    "rule is too loose or the unsupported_attributes list is now "
                    "out of date")


def test_supported_claims_still_work(catalog):
    """The refusal must be specific: a real claim on a real spec still passes."""
    example = catalog.meta.supported_claim_example
    assert example, f"{catalog.meta.category} defines no supported_claim_example"

    product = catalog.get(example["product"])
    sentence = example["sentence"]
    v = verify(product, catalog.meta,
               f"{product.description} {sentence}",
               [{"sentence": sentence, "spec_fields": list(example["spec_fields"])}])
    assert v.ok, v.reason


def test_every_licensed_term_traces_to_a_real_spec_field(catalog):
    """No claim rule may reference a spec field no product actually has."""
    known = {k for p in catalog.products for k in p.specs}
    for rule in catalog.meta.claim_rules:
        assert rule.spec in known, (
            f"claim rule cites {rule.spec!r}, which no product in the catalogue "
            f"has -- the rule can never fire")
