# Nucleus

Personas search a storefront, a report shows what they asked for versus what came back, and a
dormant agent rewrites the product descriptions so the right products start surfacing.

**Primary metric:** correct products that never surfaced before and now do.

**Second output, equally honest:** products whose descriptions already work. Where a product
already surfaces for an intent, the agent says so and changes nothing, recording a confirmed
semantic link rather than rewriting copy that is doing its job.

---

## Setup

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cd web && npm install
```

The agents need an API key. Search, the storefront and scoring do not.

Put it in `.env` at the repo root (gitignored, loaded automatically — no shell
config, nothing committable):

```bash
OPENAI_API_KEY=sk-...
```

Then confirm the key and the pinned model actually answer:

```bash
cd backend && ../.venv/Scripts/python.exe -m nucleus.pipeline preflight
```

### How the API is used

| Setting | Value | Why |
|---|---|---|
| model | `gpt-4.1-2025-04-14` | Dated snapshot. An undated alias moves under you and round 2 stops being comparable to round 1. `gpt-5` is rejected for this key (org not verified) and its reasoning models refuse `temperature=0`. |
| temperature | `0` | Pinned so numbers don't move between runs. |
| max_output_tokens | `16384` | 30 personas in one payload overflowed 4096 and came back as truncated JSON. |
| requests_per_minute | `120` | Client-side token bucket. The key's real ceiling is 10k/min, so this is courtesy, not necessity. |
| max_concurrency | `4` | Report classification is one call per never-surfaced product; bounded parallelism turns ~2 min into ~40 s. |
| max_retries | `5` | Exponential backoff with jitter on 429/5xx/timeouts, honouring `Retry-After`. |

Every call's tokens are tracked, and each CLI command prints what it spent:

```
api: 19 calls  11,363 in / 2,553 out tokens  22.9s  ~$0.0432
```

A full cold run (spawn → round 1 → report → adapt → round 2) is roughly 55
calls and about $0.25 at current pricing.

## Running

Two processes.

```bash
cd backend && ../.venv/Scripts/python.exe -m uvicorn nucleus.api:app --port 8000
```

```bash
cd web && npm run dev
```

Then <http://localhost:3000> — `/store` for the storefront, `/dashboard` for the loop.

## The loop, from the CLI

```bash
cd backend
../.venv/Scripts/python.exe -m nucleus.pipeline status
../.venv/Scripts/python.exe -m nucleus.pipeline spawn       # seed -> 30 personas, frozen
../.venv/Scripts/python.exe -m nucleus.pipeline round 1
../.venv/Scripts/python.exe -m nucleus.pipeline report
../.venv/Scripts/python.exe -m nucleus.pipeline adapt       # dormant agent -> proposals
../.venv/Scripts/python.exe -m nucleus.pipeline approve prop_001
../.venv/Scripts/python.exe -m nucleus.pipeline round 2
../.venv/Scripts/python.exe -m nucleus.pipeline results
```

Scoring happens in the dashboard between `report` and `round 2`.

### Resetting between runs — important

**A completed run mutates the catalogue.** Approved rewrites are written into the product JSON, so
a second run starting from that state begins with the improved copy and finds far fewer gaps — the
before/after collapses. Before letting anyone drive a fresh run, roll it back:

```bash
../.venv/Scripts/python.exe -m nucleus.pipeline reset --yes
```

That restores every rewritten description from its `edit_history` (each rewrite records the text it
replaced), clears personas, logs, report, proposals, scores and links, and re-indexes.

A finished run can be banked and brought back:

```bash
../.venv/Scripts/python.exe -m nucleus.pipeline snapshot demo_run
../.venv/Scripts/python.exe -m nucleus.pipeline restore demo_run
```

A completed run is already saved as `demo_run`.

### Creating a persona without a model

`/dashboard/onboarding` has two paths. **Parse into a persona** sends the four answers to the
model. **Write the persona myself** skips the model entirely — no API key, no network — and goes
straight to the editor, keeping the four answers as provenance. The parse error panel offers the
manual path as a fallback, so a failed API call never blocks the run.

## Checks

```bash
cd backend
../.venv/Scripts/python.exe -m nucleus.probe     # does search discriminate?
../.venv/Scripts/python.exe -m pytest -q         # 41 tests, no API key needed
```

---

## How it holds itself honest

The failure mode this project exists to catch is an agent that invents product attributes to make
things match. Two controls, both **in code**, not in a prompt:

**Claim traceability** (`backend/nucleus/traceability.py`). Every new sentence in a rewritten
description must cite spec fields that exist on that product, must use a term those fields
license per the dataset's `claim_rules`, and may only quote numbers that appear in the specs. One
failing sentence downgrades the entire proposal to `flag`. Neutral-sounding filler is not waved
through either — "great for sweaty summer mornings" cites nothing and is rejected, because that
is exactly how an unsupported claim gets smuggled in.

`meta.yaml` lists 14 attributes the catalogue records **no** spec for — toe box width, arch
support, reflectivity, recycled materials, true-to-size fit and so on. No claim rule licenses any
of them, so none can be written by any product. `test_unsupported.py` holds those two halves
together: it tries every unsupported claim against every product citing every spec field, and
asserts all of them are refused, while a supported claim on the same product still succeeds. The
refusal is specific, not blanket.

That breadth matters for a live demo. The refusal path only fires when a shopper asks about
something unrecorded, so a narrow list means a hand-written persona can miss it entirely and
every gap comes back `fixable`.

**No invented work.** A product that already surfaces for an intent produces a `no_change`
proposal and a confirmed semantic link, not a rewrite. `build.md` suggests underwriting
descriptions harder until round 1 fails; this build deliberately does not, because manufacturing
failure to guarantee a delta corrupts the measurement.

---

## Layout

```
config.yaml            every knob; `dataset` is the modularity hook
data/
  datasets/<name>/     meta.yaml + products/*.json  <- swap this
                       running_shoes/ and laptops/ both ship
  personas/            seed + frozen synthetic personas
  logs/round_N.jsonl   what each persona asked and got back
  scores.json          ground truth, scored once per (product, intent)
  links.json           confirmed product <-> intent links
  report.json
  proposals/
backend/nucleus/
  catalog.py           dataset + claim rules
  search.py            MiniLM embeddings, cosine, incremental re-index
  traceability.py      the claim check
  agents/              onboard, spawn, searcher, report, adapter
web/                   one Next.js app: /store and /dashboard
```

### Swapping the catalogue

Two catalogues ship here: `running_shoes` and `laptops`. `config.dataset` selects one, and that
is the whole switch — nothing in `backend/nucleus/` hardcodes a category or a spec field name.

To add a third, copy either directory and rewrite `meta.yaml` and the products. `meta.yaml` holds
everything category-specific, including the parts that used to sit in code:

| Key | What it drives |
|---|---|
| `spec_labels` | how specs are captioned in the UI |
| `claim_rules` | what a spec value licenses the agent to say |
| `unsupported_attributes` | what the catalogue records no spec for — the flag path |
| `numeric_fields` | which numbers a sentence may quote |
| `probes` | the `nucleus.probe` discrimination gate: query, `expect`, `blind` |
| `unsupported_claims` | sentences `test_unsupported.py` asserts NO product can license |
| `supported_claim_example` | one real claim that must still pass, so the refusal stays specific |

The last three name product ids and shopper phrasing, so they are category-specific by
construction. A new catalogue therefore arrives with its own gate and its own refusal surface
under test, instead of inheriting another category's.

**A rule must not license a word whose other sense names an unsupported attribute.** Writing the
laptops dataset, `weight_kg` licensed `travel`, which let "the keyboard has deep travel" through
while `keyboard travel` was on the unsupported list. `test_unsupported.py` caught it. That is the
test doing its job, and the reason the claim sentences live beside the rules they police.

---

## Design system

Both surfaces are built on the Stitch MCP design system **Hyper-Modern Neon**
(`assets/201346a998544eeea6ab5883533cc45c` in project `3532817977086505409`):
near-black ground, electric lime `#d4ff5b` and electric cyan `#00f2ff`, Anybody for
display and labels, Hanken Grotesk for body, pill-shaped interactive elements, and
depth from light emission rather than drop shadows.

Tokens live in [`web/tailwind.config.ts`](web/tailwind.config.ts) and the glass/glow
classes in [`web/app/globals.css`](web/app/globals.css). Don't hand-edit values —
change the design system in Stitch and re-pull.

`primary` is mapped to white and `secondary` to the cyan accent, so the semantic
classes used across the app stay correct without every file needing a rename.

The sibling system **Kinetic Noir** shares the dark base, the same type pairing and
the same lime primary; it differs only in the secondary accent (`#ff5f00` orange)
and a tighter roundness. Switching is a change to `electric-cyan` and `borderRadius`
in the Tailwind config, nothing more.

## Deliberate deviations from `build.md`

| `build.md` | Here | Why |
|---|---|---|
| Anthropic API | OpenAI, behind a provider interface | User's choice; `llm.provider` switches it |
| Two Next.js apps | One app, `/store` + `/dashboard` | Two processes not three, one token config, rewrites visible with no rebuild |
| Storefront as static export | Server-rendered from JSON | An approved rewrite shows immediately |
| Gaps: 3 types | 4 — adds `already_covered` | "Already works" is a finding, not an empty row |
| Underwrite until round 1 fails | Verify search *discriminates* | Doctoring the catalogue would corrupt the metric |

## Known limits

- One seed persona, so the synthetic set inherits its blind spots.
- Mock products and a local index — this shows the mechanism, not real-world performance.
- Better descriptions mean better matching, not more sales.
- The category was chosen because its descriptions are naturally thin. That is where there is
  something to find, and it should be said openly.
- MiniLM has semantic attractors: on a corpus this small some products rank highly for loosely
  related queries regardless of copy. Scoring is what separates those from real matches.
#   N u c l e u s  
 