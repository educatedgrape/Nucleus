"""Snapshot and reset the run state.

Why this exists: a completed run MUTATES the catalogue. Approved rewrites are
written into the product JSON, so a second run starting from that state begins
with the improved copy and finds far fewer gaps -- the before/after collapses.

For a repeatable demo the catalogue has to go back to its original copy, which
`edit_history` makes possible: every rewrite records the text it replaced, so
the first entry's `replaced` is the pristine description.

  snapshot   copy the whole run state aside, so a good run can be restored
  reset      restore pristine descriptions and clear run artefacts
"""
from __future__ import annotations

import shutil

from . import store
from .catalog import Catalog
from .config import Config, load as load_config
from .personas import PersonaStore


def snapshot(name: str, config: Config | None = None) -> dict:
    """Copy the current run state aside under data/snapshots/<name>."""
    config = config or load_config()
    dest = config.data_dir / "snapshots" / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    copied = []
    for rel in ("logs", "proposals", "personas", "index"):
        src = config.data_dir / rel
        if src.exists():
            shutil.copytree(src, dest / rel)
            copied.append(rel)
    for rel in ("report.json", "scores.json", "links.json"):
        src = config.data_dir / rel
        if src.exists():
            shutil.copy(src, dest / rel)
            copied.append(rel)
    # the catalogue too -- its descriptions are part of the run state
    shutil.copytree(config.products_dir, dest / "products")
    copied.append("products")
    return {"name": name, "path": str(dest), "copied": copied}


def restore(name: str, config: Config | None = None) -> dict:
    """Restore a snapshot taken by `snapshot`."""
    config = config or load_config()
    src = config.data_dir / "snapshots" / name
    if not src.exists():
        raise FileNotFoundError(f"no snapshot named {name!r} at {src}")

    for rel in ("logs", "proposals", "personas", "index"):
        if (src / rel).exists():
            dst = config.data_dir / rel
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src / rel, dst)
    for rel in ("report.json", "scores.json", "links.json"):
        if (src / rel).exists():
            shutil.copy(src / rel, config.data_dir / rel)
    if (src / "products").exists():
        shutil.rmtree(config.products_dir)
        shutil.copytree(src / "products", config.products_dir)
    return {"name": name, "restored_from": str(src)}


def restore_pristine_catalogue(config: Config | None = None) -> dict:
    """Roll every product's description back to its pre-agent original.

    Uses the FIRST edit_history entry's `replaced` field, which is the copy as
    written by hand before any agent touched it. Products with no edit history
    were never rewritten and are left alone.
    """
    config = config or load_config()
    catalog = Catalog(config)
    reverted = []
    for product in catalog.products:
        if not product.edit_history and not product.semantic_links:
            continue
        original = None
        for entry in product.edit_history:
            if entry.get("replaced"):
                original = entry["replaced"]
                break
        if original is not None and original != product.description:
            product.description = original
            reverted.append(product.id)
        product.edit_history = []
        product.semantic_links = []
        catalog.save(product)
    return {"reverted": reverted}


def reset(config: Config | None = None, keep_seed: bool = True) -> dict:
    """Return to a clean pre-run state, ready for a fresh persona.

    Keeps the catalogue's products and the seed persona (unless told otherwise);
    clears everything a run produced, and rolls descriptions back to original.
    """
    config = config or load_config()

    catalogue = restore_pristine_catalogue(config)

    removed = []
    personas = PersonaStore(config)
    n = personas.clear_synthetic()
    if n:
        removed.append(f"{n} synthetic personas")
    if not keep_seed:
        for seed in personas.seeds():
            personas.path(seed.id).unlink(missing_ok=True)
            removed.append(f"seed {seed.id}")

    for rel in ("proposals", "logs", "index"):
        d = config.data_dir / rel
        if d.exists():
            shutil.rmtree(d)
            removed.append(rel)
    for path in (config.report_path, config.scores_path, config.links_path):
        if path.exists():
            path.unlink()
            removed.append(path.name)

    config.ensure_dirs()
    return {"descriptions_reverted": catalogue["reverted"], "removed": removed}
