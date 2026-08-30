# Project Scope

**One line:** Personas search a storefront, a report shows what they asked for versus what came
back, and a dormant agent rewrites the product descriptions so the right products start
surfacing.

---

## The idea

Product descriptions are written for humans browsing. When an AI agent searches with natural
language, products that genuinely fit the request often never surface — not because the product
is wrong, but because the description never says the thing the shopper asked about.

This project makes that failure visible, then fixes it.

---

## The loop

```
  ONBOARDING          A real person describes how they shop.
                      Their answers become a seed persona.
        │
        ▼
  PERSONA SPAWN       The seed produces synthetic personas —
                      same person, different situations.
        │
        ▼
  SEARCH              Personas search the storefront in natural
                      language. Everything is logged.
        │
        ▼
  REPORT              What was asked, what came back, what never
                      surfaced at all.
        │
        ▼
  SCORING             The user marks each returned product:
                      right or wrong. Ground truth.
        │
        ▼
  ADAPT               The dormant agent reads the report and
                      rewrites product descriptions.
        │
        ▼
  RE-SEARCH           Same personas, same queries, updated site.
                      Compare against the scored baseline.
```

---

## Components

### 1. Onboarding

A short form. One real person answers four questions about how they shop the category:

- What did you last buy?
- What did you almost buy instead?
- Why didn't you?
- What would you never compromise on?

The answers are parsed into a structured persona. The user sees the parsed version and can
correct it before it's used.

### 2. Persona spawning

The seed persona produces a set of synthetic personas. These are not copies — they are the same
shopper in different situations: different budget, different urgency, different level of
experience, asking about different aspects.

The spread matters. If every persona asks the same thing, the report has one finding and the
adapter fixes it once.

### 3. Storefront

A locally hosted site with mock products. Real pages you can navigate — product name, price,
specs, and a description.

The description is the part that matters. It is what search matches against, and it is what the
dormant agent rewrites.

### 4. Search

Natural language search over the product descriptions. A persona asks for what it wants in plain
English; the store returns a ranked list.

### 5. Report

Built from the search logs. Shows:

- **What was asked** — the queries, grouped by what they were really about
- **What came back** — returned products per query
- **What never surfaced** — products that appeared in zero searches
- **Where the description fell short** — for products that should have matched but didn't

### 6. Scoring

The user reviews the returned products and marks each one right or wrong for the query it
answered.

**Each product is scored once and the score is reused.** A product marked wrong for "lightweight
humid weather" stays wrong for that intent in both rounds. This gives a fixed baseline to measure
against without asking the user to score twice.

### 7. Dormant agent

Sits idle until the report exists. Then it reads the report and, for each gap, decides what to do:

| Situation | Action |
|---|---|
| The answer is in the specs, just not in the description | Rewrite the description to include it |
| The claim is plausible but nothing supports it | Flag it — do not write it |
| The product genuinely doesn't fit | Leave it alone, note it as a product gap |

The middle case matters. An agent told to make products match will otherwise invent claims. It
must be able to say "I can't support this."

Rewrites go to a queue. The user approves before they go live.

### 8. Re-search

The same personas run the same queries against the updated storefront. Results are checked
against the existing scores. The comparison is the result: how many correct products surface now
that didn't before.

### 9. Dashboard

Everything lives here. Onboarding, persona list, search runs, report, scoring, approval queue,
and the before/after comparison.

---

## What is measured

**Primary:** correct products that never surfaced before and now do.

**Supporting:**
- Products still never surfacing after adaptation
- How many gaps were fixable from specs versus needing evidence
- Whether wrong products stopped surfacing

---

## Scope boundaries

**In:** one product category, one real seed persona, mock products, local site, two agents
(searcher and adapter), one dashboard.

**Out:** competitors, real retailer data, accounts, checkout, integrations, a second category,
anything multi-user.

---

## Known limits

- One seed persona, so the synthetic set inherits its blind spots.
- Mock products and a local site — this shows the mechanism, not real-world performance.
- Better descriptions mean better matching, not more sales.
- The category is chosen because its descriptions are thin. That's where there's something to
  find, and it should be said openly.
