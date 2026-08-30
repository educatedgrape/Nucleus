"""FastAPI backend.

Serves search to the storefront and drives the agents for the dashboard. The
storefront reads product JSON directly off disk in its server components, so
this exists for search plus the actions that mutate state.

Run:  uvicorn nucleus.api:app --reload --port 8000
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import results as results_mod
from . import store
from .catalog import Catalog
from .config import load as load_config
from .llm import LLMError, MissingCredentials, preflight
from .personas import DuplicateAngles, Persona, PersonaStore
from .scoring import Scores, queue as scoring_queue
from .search import SearchIndex
from .agents.adapter import StaleProposal
from .agents.searcher import BaselineWouldBeInvalid
from .agents import adapter as adapter_mod
from .agents import onboard as onboard_mod
from .agents import report as report_mod
from .agents import searcher, spawn as spawn_mod

app = FastAPI(title="Nucleus", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_index: SearchIndex | None = None


def get_index() -> SearchIndex:
    global _index
    if _index is None:
        _index = SearchIndex()
        _index.build()
    return _index


def _fail(e: Exception) -> HTTPException:
    """Surface the actionable message rather than a bare 500."""
    if isinstance(e, MissingCredentials):
        return HTTPException(status_code=428, detail=str(e))
    if isinstance(e, (StaleProposal, BaselineWouldBeInvalid)):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, (LLMError, DuplicateAngles, ValueError, FileExistsError, KeyError)):
        return HTTPException(status_code=400, detail=str(e))
    return HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------- read-only
@app.get("/api/status")
def status() -> dict[str, Any]:
    cfg = load_config()
    catalog = Catalog(cfg)
    personas = PersonaStore(cfg)
    props = adapter_mod.load_proposals(cfg)
    return {
        "dataset": cfg.dataset,
        "search_k": cfg.search_k,
        "persona_count": cfg.persona_count,
        "model": f"{cfg.llm.provider}/{cfg.llm.model}",
        "products": len(catalog),
        "seeds": len(personas.seeds()),
        "synthetic": len(personas.synthetic()),
        "rounds": {
            n: len(store.read_jsonl(cfg.log_path(n))) for n in (1, 2)
        },
        "report": report_mod.load(cfg) is not None,
        "proposals": {
            "total": len(props),
            "pending": len([p for p in props if p["status"] == "pending"]),
        },
        "scored_pairs": Scores(cfg).count,
        # How many products the agent has already rewritten. Non-zero means
        # round 1 is spent: re-running it would measure the improved copy.
        "rewritten_products": len([p for p in catalog.products if p.edit_history]),
    }


@app.get("/api/preflight")
def api_preflight() -> dict[str, str]:
    try:
        return {"ok": preflight()}
    except Exception as e:
        raise _fail(e) from e


@app.get("/api/search")
def search(q: str, k: int | None = None) -> dict[str, Any]:
    index = get_index()
    catalog = index.catalog
    hits = index.search(q, k)
    return {
        "query": q,
        "k": k or index.config.search_k,
        "hits": [
            {
                "product_id": h.product_id,
                "rank": h.rank,
                "score": round(h.score, 4),
                "name": catalog.get(h.product_id).name,
                "price": catalog.get(h.product_id).price,
                "description": catalog.get(h.product_id).description,
            }
            for h in hits
        ],
    }


@app.get("/api/report")
def get_report() -> dict[str, Any]:
    rep = report_mod.load()
    if not rep:
        raise HTTPException(404, "no report yet")
    return rep


@app.get("/api/proposals")
def get_proposals(status: str | None = None) -> list[dict]:
    return adapter_mod.load_proposals(status=status)


@app.get("/api/results")
def get_results() -> dict[str, Any]:
    try:
        return results_mod.compare()
    except Exception as e:
        raise _fail(e) from e


@app.get("/api/scoring/queue")
def get_scoring_queue() -> list[dict]:
    rep = report_mod.load()
    if not rep:
        raise HTTPException(404, "no report yet")
    catalog = Catalog()
    return [
        {
            "product_id": i.product_id,
            "intent": i.intent,
            "name": catalog.get(i.product_id).name,
            "description": catalog.get(i.product_id).description,
        }
        for i in scoring_queue(rep)
    ]


# ----------------------------------------------------------------- mutating
class OnboardBody(BaseModel):
    last_bought: str
    almost_bought: str
    why_not: str
    never_compromise: str


@app.post("/api/onboard/parse")
def onboard_parse(body: OnboardBody) -> dict:
    try:
        return onboard_mod.parse_answers(body.model_dump()).to_dict()
    except Exception as e:
        raise _fail(e) from e


class SeedBody(BaseModel):
    id: str = "seed_01"
    need: str
    must_have: list[str] = []
    prefer: list[str] = []
    context: list[str] = []
    query: str = ""
    source_answers: dict = {}


@app.post("/api/onboard/save")
def onboard_save(body: SeedBody) -> dict:
    """Save the seed AFTER the user has corrected the parse."""
    persona = Persona(
        id=body.id, seed_id=body.id, origin="real", need=body.need,
        must_have=body.must_have, prefer=body.prefer, context=body.context,
        angle="seed", query=body.query, source_answers=body.source_answers,
    )
    return onboard_mod.save_seed(persona).to_dict()


class SpawnBody(BaseModel):
    replace: bool = False


@app.post("/api/spawn")
def spawn(body: SpawnBody) -> dict:
    cfg = load_config()
    seeds = PersonaStore(cfg).seeds()
    if not seeds:
        raise HTTPException(400, "no seed persona -- complete onboarding first")
    try:
        personas = spawn_mod.spawn_and_freeze(seeds[0], cfg.persona_count, cfg,
                                              replace=body.replace)
    except Exception as e:
        raise _fail(e) from e
    return {"count": len(personas), "personas": [p.to_dict() for p in personas]}


@app.post("/api/round/{n}")
def run_round(n: int, force: bool = False) -> dict:
    if n not in (1, 2):
        raise HTTPException(400, "round must be 1 or 2")
    global _index
    _index = None                       # pick up any approved rewrites
    try:
        res = searcher.run_round(n, force=force)
    except Exception as e:
        raise _fail(e) from e
    return {
        "round": n,
        "queries": res.query_count,
        "surfaced": len(res.returned_any),
        "never_returned": res.never_returned,
    }


@app.post("/api/report")
def build_report(n: int = 1) -> dict:
    try:
        return report_mod.build(n)
    except Exception as e:
        raise _fail(e) from e


@app.post("/api/adapt")
def adapt() -> dict:
    rep = report_mod.load()
    if not rep:
        raise HTTPException(400, "the agent stays dormant until a report exists")
    try:
        props = adapter_mod.run(rep)
    except Exception as e:
        raise _fail(e) from e
    by: dict[str, int] = {}
    for p in props:
        by[p["action"]] = by.get(p["action"], 0) + 1
    return {"count": len(props), "by_action": by, "proposals": props}


@app.post("/api/proposals/{proposal_id}/{decision}")
def decide(proposal_id: str,
           decision: Literal["approve", "reject"]) -> dict:
    global _index
    try:
        if decision == "reject":
            return adapter_mod.reject(proposal_id)
        prop = adapter_mod.approve(proposal_id)
    except KeyError as e:
        raise HTTPException(404, f"no such proposal: {proposal_id}") from e
    except StaleProposal as e:
        raise _fail(e) from e
    if prop["action"] == "rewrite":
        _index = None                   # force a rebuild on next search
        get_index()
    return prop


class ScoreBody(BaseModel):
    product_id: str
    intent: str
    verdict: Literal["right", "wrong"]


@app.post("/api/scoring")
def set_score(body: ScoreBody) -> dict:
    scores = Scores()
    scores.set(body.product_id, body.intent, body.verdict)
    return {"ok": True, "scored_pairs": scores.count}
