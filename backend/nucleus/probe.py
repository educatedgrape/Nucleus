"""Step-2 gate: does search actually discriminate?

Run before trusting any round-1 number:  python -m nucleus.probe

This is NOT a check that search fails. build.md suggests underwriting harder
until round 1 fails; deliberately degrading the catalogue to guarantee a delta
would corrupt the measurement. What matters is that the index separates
products at all -- it must not return everything for everything, nor nothing
for anything. Products that already surface correctly are a real finding, and
the adapter records them as confirmed semantic links rather than rewriting
copy that is already doing its job.
"""
from __future__ import annotations

import sys

from .catalog import Catalog
from .search import SearchIndex

# Probes are hand-written per dataset and live in that dataset's meta.yaml,
# alongside the spec labels and claim rules -- they name product ids, so they
# are category-specific by construction and do not belong in code.
#   expect  products whose copy already states the thing. AT LEAST ONE must
#           surface -- not all of them. Several may compete for the same k
#           slots, and which one wins a tie is not a property worth asserting.
#   blind   products whose specs support the claim but whose copy is silent.
#           These should NOT surface: they are the gap the adapter closes.


def main(argv: list[str] | None = None) -> int:
    index = SearchIndex()
    index.ensure_built()
    catalog: Catalog = index.catalog
    k = index.config.search_k
    probes = catalog.meta.probes

    if not probes:
        print(f"dataset {index.config.dataset!r} defines no `probes:` in its "
              "meta.yaml, so the discrimination gate cannot run.")
        return 1

    all_returned: set[str] = set()
    rows, failures = [], []

    for probe in probes:
        hits = index.search(probe["query"], k)
        got = [h.product_id for h in hits]
        all_returned.update(got)

        surfaced = [p for p in probe["expect"] if p in got]
        leaked = [p for p in probe["blind"] if p in got]

        rows.append((probe["query"], got, surfaced, probe["expect"], leaked))
        if not surfaced:
            failures.append(
                f"  no well-written product surfaced for {probe['query']!r}; "
                f"expected one of {probe['expect']}, got {got}")

    print(f"dataset '{index.config.dataset}'  |  {len(catalog)} products  |  k={k}\n")
    for query, got, surfaced, expect, leaked in rows:
        print(f"  {query!r}")
        print(f"    returned : {', '.join(got)}")
        print(f"    expected : {', '.join(surfaced) or '(none)'} of {expect}")
        if leaked:
            print(f"    note     : silent-copy products also surfaced: {leaked}")
        print()

    coverage = len(all_returned)
    print(f"distinct products across {len(probes)} probes: {coverage}/{len(catalog)}")

    # The gate proper: the index must separate products.
    if coverage >= len(catalog):
        failures.append(
            f"  search returned every product ({coverage}/{len(catalog)}): "
            "it is not discriminating, so 'never returned' would be empty.")
    if coverage <= 1:
        failures.append("  search returned essentially nothing; index is broken.")

    if failures:
        print("\nGATE FAILED:")
        print("\n".join(failures))
        return 1

    never = sorted(set(catalog.ids) - all_returned)
    print(f"never surfaced in these probes ({len(never)}): {', '.join(never)}")
    print("\nGATE PASSED: search discriminates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
