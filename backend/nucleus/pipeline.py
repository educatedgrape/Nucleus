"""Nucleus CLI.

  python -m nucleus.pipeline preflight     check credentials + pinned model
  python -m nucleus.pipeline status        what exists on disk so far
  python -m nucleus.pipeline spawn         seed -> synthetic personas (frozen)
  python -m nucleus.pipeline round 1       run every persona's query, log it
  python -m nucleus.pipeline report        cluster intents, classify gaps
  python -m nucleus.pipeline adapt         dormant agent -> proposal queue
  python -m nucleus.pipeline approve <id>  apply a proposal (re-indexes)
  python -m nucleus.pipeline results       before / after

Steps needing a model say so up front rather than failing halfway through.
"""
from __future__ import annotations

import argparse
import sys

from . import reset as reset_mod
from . import results as results_mod
from . import store
from .catalog import Catalog
from .config import load as load_config
from .llm import USAGE, MissingCredentials, preflight
from .personas import PersonaStore
from .scoring import Scores
from .search import SearchIndex
from .agents.adapter import StaleProposal
from .agents.searcher import BaselineWouldBeInvalid
from .agents import adapter as adapter_mod
from .agents import report as report_mod
from .agents import searcher, spawn as spawn_mod


def _bar(i: int, n: int, label: str) -> None:
    pct = int(i / n * 100) if n else 100
    sys.stdout.write(f"\r  [{pct:3d}%] {i}/{n}  {label[:48]:<48}")
    sys.stdout.flush()
    if i == n:
        sys.stdout.write("\n")


def cmd_preflight(args) -> int:
    print(preflight())
    return 0


def cmd_status(args) -> int:
    cfg = load_config()
    catalog = Catalog(cfg)
    personas = PersonaStore(cfg)
    seeds, synth = personas.seeds(), personas.synthetic()
    report = store.read_json(cfg.report_path)
    props = adapter_mod.load_proposals(cfg)
    scores = Scores(cfg)

    print(f"dataset        {cfg.dataset}  ({len(catalog)} products)")
    print(f"search_k       {cfg.search_k}  (pinned)")
    print(f"model          {cfg.llm.provider}/{cfg.llm.model}")
    print(f"seed personas  {len(seeds)}")
    print(f"synthetic      {len(synth)}" + ("  (frozen)" if synth else ""))
    for r in (1, 2):
        rows = store.read_jsonl(cfg.log_path(r))
        if rows:
            print(f"round {r}        {len(rows)} queries, "
                  f"{len(rows[0].get('never_returned', []))} never surfaced")
    print(f"report         {'yes' if report else 'no'}")
    if props:
        by = {}
        for p in props:
            by[p["status"]] = by.get(p["status"], 0) + 1
        print(f"proposals      {len(props)}  ({by})")
    print(f"scored pairs   {scores.count}")
    return 0


def cmd_spawn(args) -> int:
    cfg = load_config()
    store_ = PersonaStore(cfg)
    seeds = store_.seeds()
    if not seeds:
        print("no seed persona on disk -- complete onboarding first", file=sys.stderr)
        return 1
    seed = seeds[0]
    print(f"spawning {cfg.persona_count} personas from {seed.id} "
          f"(seed + category name only) ...")
    personas = spawn_mod.spawn_and_freeze(seed, cfg.persona_count, cfg,
                                          replace=args.replace)
    print(f"  wrote {len(personas)} personas, all angles distinct")
    for p in personas[:5]:
        print(f"    {p.id}  {p.angle:<22} {p.query[:56]}")
    if len(personas) > 5:
        print(f"    ... and {len(personas) - 5} more")
    return 0


def cmd_round(args) -> int:
    cfg = load_config()
    print(f"round {args.n}: replaying frozen persona queries ...")
    try:
        res = searcher.run_round(args.n, cfg, force=args.force,
                                 progress=lambda i, n, p: _bar(i, n, p.angle))
    except BaselineWouldBeInvalid as e:
        print(f"\nrefused: {e}", file=sys.stderr)
        return 4
    print(f"  {res.query_count} queries, {len(res.returned_any)} products surfaced, "
          f"{len(res.never_returned)} never returned")
    print(f"  never returned: {', '.join(res.never_returned) or '(none)'}")
    print(f"  log: {cfg.log_path(args.n)}")
    return 0


def cmd_report(args) -> int:
    cfg = load_config()
    print(f"building report for round {args.n} ...")
    rep = report_mod.build(args.n, cfg,
                           progress=lambda i, n, pid: _bar(i, n, pid))
    print()
    print(report_mod.summarise(rep))
    print(f"\n  report: {cfg.report_path}")
    return 0


def cmd_adapt(args) -> int:
    cfg = load_config()
    rep = report_mod.load(cfg)
    if not rep:
        print("no report on disk -- the agent stays dormant until one exists",
              file=sys.stderr)
        return 1
    print(f"dormant agent waking on report for round {rep['round']} ...")
    props = adapter_mod.run(rep, cfg,
                            progress=lambda i, n, g: _bar(i, n, g["product_id"]))
    by = {}
    for p in props:
        by[p["action"]] = by.get(p["action"], 0) + 1
    print(f"  {len(props)} proposals: {by}")
    downgraded = [p for p in props if p.get("downgraded_from")]
    if downgraded:
        print(f"  {len(downgraded)} rewrite(s) auto-downgraded to flag "
              f"(claims could not be traced to specs):")
        for p in downgraded[:5]:
            print(f"    {p['id']}  {p['product_id']}  {p['traceability_failures'][0][:70]}")
    return 0


def cmd_approve(args) -> int:
    cfg = load_config()
    try:
        prop = adapter_mod.approve(args.proposal_id, cfg)
    except StaleProposal as e:
        print(f"skipped: {e}", file=sys.stderr)
        return 3
    print(f"{prop['id']}  {prop['action']}  -> {prop['applied']}")
    if prop["action"] == "rewrite":
        stats = SearchIndex(config=cfg).build()
        print(f"  re-indexed: encoded {stats['encoded']}, reused {stats['reused']}")
    return 0


def cmd_reject(args) -> int:
    prop = adapter_mod.reject(args.proposal_id, load_config())
    print(f"{prop['id']} rejected")
    return 0


def cmd_results(args) -> int:
    res = results_mod.compare(load_config())
    print(results_mod.summarise(res))
    return 0


def cmd_snapshot(args) -> int:
    out = reset_mod.snapshot(args.name, load_config())
    print(f"snapshot '{out['name']}' -> {out['path']}")
    print(f"  saved: {', '.join(out['copied'])}")
    return 0


def cmd_restore(args) -> int:
    out = reset_mod.restore(args.name, load_config())
    print(f"restored snapshot '{out['name']}'")
    SearchIndex(config=load_config()).build()
    print("  re-indexed")
    return 0


def cmd_reset(args) -> int:
    cfg = load_config()
    if not args.yes:
        print("This clears the run state and rolls every rewritten description\n"
              "back to its original. Re-run with --yes to confirm.",
              file=sys.stderr)
        return 1
    out = reset_mod.reset(cfg, keep_seed=not args.clear_seed)
    reverted = out["descriptions_reverted"]
    print(f"reset complete")
    print(f"  descriptions rolled back: {len(reverted)}"
          + (f"  ({', '.join(reverted)})" if reverted else ""))
    print(f"  cleared: {', '.join(out['removed']) or '(nothing to clear)'}")
    stats = SearchIndex(config=cfg).build()
    print(f"  re-indexed: encoded {stats['encoded']}, reused {stats['reused']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nucleus.pipeline", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preflight").set_defaults(fn=cmd_preflight)
    sub.add_parser("status").set_defaults(fn=cmd_status)

    p = sub.add_parser("spawn")
    p.add_argument("--replace", action="store_true",
                   help="discard frozen personas (invalidates existing rounds)")
    p.set_defaults(fn=cmd_spawn)

    p = sub.add_parser("round")
    p.add_argument("n", type=int, choices=(1, 2))
    p.add_argument("--force", action="store_true",
                   help="re-run round 1 even after rewrites (destroys the baseline)")
    p.set_defaults(fn=cmd_round)

    p = sub.add_parser("report")
    p.add_argument("-n", type=int, default=1, help="round number (default 1)")
    p.set_defaults(fn=cmd_report)

    sub.add_parser("adapt").set_defaults(fn=cmd_adapt)

    p = sub.add_parser("approve")
    p.add_argument("proposal_id")
    p.set_defaults(fn=cmd_approve)

    p = sub.add_parser("reject")
    p.add_argument("proposal_id")
    p.set_defaults(fn=cmd_reject)

    sub.add_parser("results").set_defaults(fn=cmd_results)

    p = sub.add_parser("snapshot", help="save the current run state aside")
    p.add_argument("name")
    p.set_defaults(fn=cmd_snapshot)

    p = sub.add_parser("restore", help="restore a saved snapshot")
    p.add_argument("name")
    p.set_defaults(fn=cmd_restore)

    p = sub.add_parser("reset", help="clear the run and restore original copy")
    p.add_argument("--yes", action="store_true", help="confirm")
    p.add_argument("--clear-seed", action="store_true",
                   help="also delete the seed persona")
    p.set_defaults(fn=cmd_reset)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except MissingCredentials as e:
        print(f"\n{e}", file=sys.stderr)
        return 2
    finally:
        # Make what a run actually spent visible rather than invisible.
        if USAGE.calls or USAGE.failed:
            print(f"\napi: {USAGE.summary(load_config())}")


if __name__ == "__main__":
    sys.exit(main())
