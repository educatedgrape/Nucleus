"""Re-embed the catalogue.

Run after any approved description rewrite:  python -m nucleus.reindex
Incremental by default -- only descriptions whose text changed get re-encoded.
"""
from __future__ import annotations

import argparse
import sys

from .search import SearchIndex


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nucleus.reindex", description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="re-encode everything, ignoring the vector cache")
    args = ap.parse_args(argv)

    index = SearchIndex()
    stats = index.build(force=args.force)
    print(f"indexed {len(index.catalog)} products from "
          f"dataset '{index.config.dataset}'")
    print(f"  encoded {stats['encoded']}, reused {stats['reused']} cached")
    print(f"  cache: {index.cache_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
