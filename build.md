# Build Guide

Companion to `scope.md`.

---

## Before you start: Stitch MCP

The storefront should follow the design language defined in **Stitch MCP**.

**Check whether it's connected before building any UI.** If Stitch MCP is available, pull the
design tokens — colours, typography, spacing, component patterns — and use them for both the
storefront and the dashboard.

**If it isn't connected, stop and ask the user to set it up.** Do not invent a visual style and
retrofit it later; restyling two surfaces after the fact costs more than the setup does.

---

## Stack

| Layer | Choice |
|---|---|
| Backend / agents | Python 3.11 |
| Storefront | Next.js (static export) |
| Dashboard | Next.js |
| Styling | Tailwind, tokens from Stitch MCP |
| Search | sentence-transformers (`all-MiniLM-L6-v2`) + cosine similarity |
| Agents | Anthropic API, called directly |
| Storage | JSON files on disk |
| Config | One `config.yaml` |

No database, no agent framework, no auth. Two agents with simple loops don't need orchestration
scaffolding, and file storage is diffable and inspectable when something goes wrong.

---

## Data shapes

Write these first. Everything downstream depends on them.

```jsonc
// products/sku_014.json
{
  "id": "sku_014",
  "name": "Trail Runner Lite",
  "price": 189,
  "specs": { "weight_g": 210, "drop_mm": 6, "upper": "engineered mesh" },
  "description": "...",
  "edit_history": [
    { "at": "...", "added": "...", "based_on": ["upper: engineered mesh"] }
  ]
}
```

```jsonc
// personas/p_007.json
{
  "id": "p_007",
  "seed_id": "seed_01",
  "origin": "real" | "synthetic",
  "need": "...",
  "must_have": ["under 200"],
  "prefer": ["lighter"],
  "context": ["humid climate", "half marathon training"],
  "angle": "budget_conscious"        // what makes this variant different
}
```

```jsonc
// logs/round_1.jsonl — one per line
{
  "persona_id": "p_007",
  "round": 1,
  "query": "...",
  "returned": ["sku_022", "sku_031"],
  "never_returned": ["sku_003", "sku_014"]
}
```

```jsonc
// scores.json — scored once, reused across rounds
{
  "sku_022": { "intent": "humidity", "verdict": "right" },
  "sku_031": { "intent": "humidity", "verdict": "wrong" }
}
```

```jsonc
// report.json
{
  "round": 1,
  "intents": [
    { "label": "breathability in humidity", "count": 14, "examples": ["..."] }
  ],
  "never_surfaced": [
    { "product_id": "sku_014", "missed": ["breathability in humidity"] }
  ],
  "gaps": [
    {
      "id": "gap_007",
      "product_id": "sku_014",
      "intent": "breathability in humidity",
      "type": "fixable" | "needs_evidence" | "not_applicable",
      "supporting_specs": ["upper: engineered mesh"]
    }
  ]
}
```

```jsonc
// proposals/prop_003.json
{
  "id": "prop_003",
  "gap_id": "gap_007",
  "product_id": "sku_014",
  "action": "rewrite" | "flag" | "skip",
  "new_description": "...",
  "based_on": ["upper: engineered mesh"],
  "status": "pending" | "approved" | "rejected"
}
```

---

## Build steps

### Step 1 — Products and storefront

Write 20–30 mock products for one category. Pick a category where descriptions are naturally
thin — that's where there'll be something to find.

**Deliberately underwrite some descriptions.** Leave out things the specs imply. These are the
products that should fail to surface, and without them there's no before/after.

Generate static product pages plus a listing page from the JSON. Style with Stitch MCP tokens.

### Step 2 — Search

Embed every product description. Expose `search(query, k)` returning ranked product ids.

**Pin `k` in config now.** It defines what counts as "never returned," which is your headline
number. Changing it mid-build invalidates any comparison.

Add a re-index command — you'll run it after every description rewrite.

### Step 3 — Onboarding

Four-question form. Parse answers into a seed persona. Show the parsed persona back and let the
user edit it before saving.

### Step 4 — Persona spawning

Seed → 20–40 synthetic personas. Each gets an `angle` that makes it distinct: different budget,
different urgency, different experience level, different aspect of the need.

**Generate from the seed and the category name only — never from the product data.** Personas
built from the catalog will ask about things the catalog already covers, and nothing will fail.

Freeze them to disk once generated.

### Step 5 — Search agent

For each persona: turn the persona into a natural-language query, run the search, log what came
back and what didn't.

`never_returned` is the set difference between all products and everything returned across all
queries.

### Step 6 — Report

Cluster queries into intents. Aggregate never-surfaced products against the intents they missed.

For each gap, classify it:

- **fixable** — the specs support it, the description just doesn't say it
- **needs_evidence** — plausible, but nothing in the product data backs it
- **not_applicable** — the product genuinely doesn't fit

Make the report readable. It's the thing a person actually looks at.

### Step 7 — Scoring

Show the user returned products grouped by intent. They mark each right or wrong.

Store keyed by product and intent. **Scored once, reused in round two.** Only unscored products
appear in the queue after re-search.

### Step 8 — Dormant agent

Triggered when a report exists — not on individual searches.

For each gap, produce a proposal:

- `fixable` → rewrite the description, record which spec fields justify it
- `needs_evidence` → flag it, propose no change
- `not_applicable` → skip

**Enforce this in code, not just the prompt.** If a proposed sentence can't be traced to a spec
field, downgrade it to `flag` automatically. Otherwise the agent will write whatever makes the
product match.

Proposals go to a queue. Approved ones get written to the product JSON, appended to
`edit_history`, and trigger a re-index.

### Step 9 — Re-search

Run the same personas and queries against the updated storefront. Log as round 2.

Compare against `scores.json`: how many products marked right now surface that didn't before.
Score anything new that appears.

### Step 10 — Dashboard

Views:

1. **Onboarding** — form plus persona correction
2. **Personas** — the spawned set with their angles
3. **Run** — trigger a search round, watch it progress
4. **Report** — intents, never-surfaced products, gap table
5. **Scoring** — mark returned products right or wrong
6. **Approvals** — proposed rewrites and flagged items
7. **Results** — before versus after

---

## Config

```yaml
category: running_shoes
search_k: 5              # do not change after round 1
persona_count: 30
model: claude-sonnet-4-6
```

---

## Things that will go wrong

| Problem | Fix |
|---|---|
| Everything surfaces fine in round 1, no delta to show | Test on 5 products in step 2. If search is already good, underwrite the descriptions harder. |
| All personas ask the same thing | Assert distinct `angle` values at spawn. |
| Agent invents claims | Automatic downgrade to `flag` when no spec traces. Code it. |
| Flag path never triggers | Add one product where the obvious improvement genuinely isn't supported, and confirm the agent refuses. |
| Numbers move between runs | Pin `search_k`, pin the model version, run each round twice and check stability. |
| Nothing to demo if the API fails | Cache a full successful run and add a replay mode. |
