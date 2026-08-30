"""Shared fixtures.

Two kinds of test live here. The *mechanism* tests (test_traceability.py) are
written against a hand-built shoe and the running_shoes spec vocabulary, so
they pin that dataset explicitly rather than following config.yaml -- swapping
the configured catalogue must not silently change what they assert.

The *refusal surface* tests (test_unsupported.py) do the opposite: they run
against whichever dataset is configured, reading their claim sentences from
that dataset's meta.yaml, because every catalogue needs its own list held
honest.
"""
from __future__ import annotations

import dataclasses

import pytest

from nucleus.catalog import Catalog
from nucleus.config import load


def catalog_for(dataset: str) -> Catalog:
    return Catalog(dataclasses.replace(load(), dataset=dataset))


@pytest.fixture(scope="session")
def shoes_catalog() -> Catalog:
    """The running_shoes catalogue, regardless of what config.yaml points at."""
    return catalog_for("running_shoes")


@pytest.fixture(scope="session")
def configured_catalog() -> Catalog:
    """Whatever catalogue config.yaml currently selects."""
    return Catalog()
