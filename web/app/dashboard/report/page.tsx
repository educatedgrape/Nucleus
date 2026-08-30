import Link from "next/link";
import { AgentChip, EmptyState, GlassPanel, StatTile } from "@/components/glass";
import { getProducts, getReport, type Gap } from "@/lib/data";

export const dynamic = "force-dynamic";

const GAP_TONE = {
  fixable: "agent",
  needs_evidence: "warn",
  not_applicable: "neutral",
  already_covered: "good",
} as const;

const GAP_BLURB: Record<Gap["type"], string> = {
  fixable: "The specs support it. The description just never says it.",
  needs_evidence: "Plausible, but nothing in the product data backs it up.",
  not_applicable: "The product genuinely doesn't fit. A product gap, not a copy gap.",
  already_covered: "Already surfaces for this intent. The description is doing its job.",
};

export default async function ReportView() {
  const [report, products] = await Promise.all([getReport(), getProducts()]);
  const names = Object.fromEntries(products.map((p) => [p.id, p.name]));

  if (!report) {
    return (
      <EmptyState
        icon="lab_profile"
        title="No report yet"
        body="Run round 1, then build the report. It clusters what the personas asked for and shows what never came back."
      />
    );
  }

  const byType = (t: Gap["type"]) => report.gaps.filter((g) => g.type === t);
  const missing = ["fixable", "needs_evidence", "not_applicable"] as const;

  return (
    <div className="flex flex-col gap-stack-lg">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">Report</h1>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
          Round {report.round}. Two halves, and both are findings: what never
          surfaced, and what already works.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-gutter">
        <StatTile label="Queries" value={report.totals.queries} />
        <StatTile label="Intents" value={report.intents.length} tone="agent" />
        <StatTile
          label="Never surfaced"
          value={report.totals.never_surfaced}
          tone="live"
          hint={`of ${report.totals.products} products`}
        />
        <StatTile
          label="Already covered"
          value={byType("already_covered").length}
          hint="product/intent pairs working"
        />
      </div>

      {/* ---------------------------------------------------- what was asked */}
      <section>
        <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-stack-sm">
          What was asked
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-gutter">
          {report.intents.map((i) => (
            <GlassPanel key={i.label} className="p-5">
              <div className="flex justify-between items-start gap-3 mb-3">
                <h3 className="font-body-md text-body-md font-semibold text-primary">
                  {i.label}
                </h3>
                <AgentChip tone="neutral">{i.count}</AgentChip>
              </div>
              <ul className="flex flex-col gap-1">
                {i.examples.map((e, n) => (
                  <li
                    key={n}
                    className="font-body-sm text-body-sm text-on-surface-variant italic leading-snug"
                  >
                    &ldquo;{e}&rdquo;
                  </li>
                ))}
              </ul>
            </GlassPanel>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------ what never surfaced */}
      <section>
        <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-stack-sm">
          What never surfaced
        </h2>
        {report.never_surfaced.length === 0 ? (
          <GlassPanel className="p-6">
            <p className="font-body-md text-body-md text-on-surface-variant">
              Every product surfaced for at least one intent.
            </p>
          </GlassPanel>
        ) : (
          <GlassPanel className="p-5">
            <ul className="flex flex-col divide-y divide-glass-border">
              {report.never_surfaced.map((n) => (
                <li key={n.product_id} className="py-3 flex items-start gap-4 first:pt-0 last:pb-0">
                  <Link
                    href={`/store/${n.product_id}`}
                    className="font-body-md text-body-md font-semibold text-primary hover:text-electric-cyan transition-colors w-[200px] shrink-0"
                  >
                    {names[n.product_id] ?? n.product_id}
                    <span className="block font-label-caps text-label-caps text-outline">
                      {n.product_id}
                    </span>
                  </Link>
                  <div className="flex flex-wrap gap-1.5">
                    {n.missed.map((m) => (
                      <AgentChip key={m} tone="live">{m}</AgentChip>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </GlassPanel>
        )}
      </section>

      {/* ------------------------------------------------------- the gap table */}
      <section>
        <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-stack-sm">
          Where the description fell short
        </h2>
        <div className="flex flex-col gap-stack-md">
          {missing.map((t) => {
            const rows = byType(t);
            if (!rows.length) return null;
            return (
              <div key={t}>
                <div className="flex items-center gap-3 mb-2">
                  <AgentChip tone={GAP_TONE[t]}>{t.replace("_", " ")}</AgentChip>
                  <span className="font-body-sm text-body-sm text-on-surface-variant">
                    {GAP_BLURB[t]}
                  </span>
                </div>
                <GlassPanel className="overflow-x-auto">
                  <table className="w-full min-w-[640px]">
                    <thead>
                      <tr className="border-b border-glass-border">
                        {["Product", "Intent", "Supporting specs", "Why"].map((h) => (
                          <th
                            key={h}
                            className="text-left px-4 py-3 font-label-caps text-label-caps uppercase text-on-surface-variant"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((g) => (
                        <tr
                          key={g.id}
                          className="border-b border-glass-border last:border-0 hover:bg-glass-dark transition-colors"
                        >
                          <td className="px-4 py-3">
                            <Link
                              href={`/store/${g.product_id}`}
                              className="font-body-md text-body-md text-primary hover:text-electric-cyan"
                            >
                              {names[g.product_id] ?? g.product_id}
                            </Link>
                          </td>
                          <td className="px-4 py-3 font-body-sm text-body-sm text-on-surface-variant">
                            {g.intent}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap gap-1">
                              {g.supporting_specs.length ? (
                                g.supporting_specs.map((s) => (
                                  <AgentChip key={s} tone="neutral">{s}</AgentChip>
                                ))
                              ) : (
                                <span className="font-label-caps text-label-caps text-outline">
                                  none
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3 font-body-sm text-body-sm text-on-surface-variant max-w-[320px]">
                            {g.rationale}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </GlassPanel>
              </div>
            );
          })}
        </div>
      </section>

      {/* ---------------------------------------------------- what's working */}
      <section>
        <div className="flex items-center gap-3 mb-stack-sm">
          <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant">
            What&rsquo;s already working
          </h2>
          <AgentChip tone="good">{byType("already_covered").length}</AgentChip>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant mb-3 max-w-2xl">
          {GAP_BLURB.already_covered} These become confirmed semantic links, not
          rewrites &mdash; store knowledge worth stating plainly.
        </p>
        <GlassPanel className="p-5">
          <div className="flex flex-wrap gap-2">
            {byType("already_covered").map((g) => (
              <span
                key={g.id}
                className="flex items-center gap-2 rounded-lg bg-surface-container-low px-3 py-2"
              >
                <Link
                  href={`/store/${g.product_id}`}
                  className="font-body-sm text-body-sm text-primary hover:text-electric-cyan"
                >
                  {names[g.product_id] ?? g.product_id}
                </Link>
                <span className="font-label-caps text-label-caps text-outline">→</span>
                <span className="font-label-caps text-label-caps text-electric-cyan">{g.intent}</span>
              </span>
            ))}
          </div>
        </GlassPanel>
      </section>
    </div>
  );
}
