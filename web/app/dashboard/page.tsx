import Link from "next/link";
import { AgentChip, GlassPanel, Icon, StatTile } from "@/components/glass";
import {
  getConfig,
  getPersonas,
  getProducts,
  getProposals,
  getReport,
  getRound,
  getScores,
} from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function Overview() {
  const [cfg, products, personas, report, proposals, r1, r2, scores] =
    await Promise.all([
      getConfig(),
      getProducts(),
      getPersonas(),
      getReport(),
      getProposals(),
      getRound(1),
      getRound(2),
      getScores(),
    ]);

  const synthetic = personas.filter((p) => p.origin === "synthetic");
  const seed = personas.find((p) => p.origin === "real");
  const pending = proposals.filter((p) => p.status === "pending");
  const scoredPairs = Object.values(scores).reduce(
    (n, byIntent) => n + Object.keys(byIntent).length,
    0
  );

  const steps = [
    { label: "Onboarding", done: !!seed, href: "/dashboard/onboarding",
      detail: seed ? "seed persona saved" : "not started" },
    { label: "Personas", done: synthetic.length > 0, href: "/dashboard/personas",
      detail: synthetic.length ? `${synthetic.length} frozen` : "not spawned" },
    { label: "Round 1", done: r1.length > 0, href: "/dashboard/run",
      detail: r1.length ? `${r1.length} queries` : "not run" },
    { label: "Report", done: !!report, href: "/dashboard/report",
      detail: report ? `${report.intents.length} intents` : "not built" },
    { label: "Scoring", done: scoredPairs > 0, href: "/dashboard/scoring",
      detail: scoredPairs ? `${scoredPairs} pairs scored` : "nothing scored" },
    { label: "Approvals", done: proposals.length > 0, href: "/dashboard/approvals",
      detail: proposals.length ? `${pending.length} pending` : "agent dormant" },
    { label: "Round 2", done: r2.length > 0, href: "/dashboard/run",
      detail: r2.length ? `${r2.length} queries` : "not run" },
    { label: "Results", done: r2.length > 0, href: "/dashboard/results",
      detail: r2.length ? "ready" : "needs round 2" },
  ];

  return (
    <div className="flex flex-col gap-stack-lg">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">Overview</h1>
        <div className="flex flex-wrap gap-2">
          <AgentChip tone="neutral">{cfg.dataset}</AgentChip>
          <AgentChip tone="neutral">k={cfg.search_k} pinned</AgentChip>
          <AgentChip tone="agent">{cfg.llm.provider}/{cfg.llm.model}</AgentChip>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-gutter">
        <StatTile label="Products" value={products.length} />
        <StatTile label="Personas" value={synthetic.length} tone="agent" />
        <StatTile
          label="Never surfaced"
          value={r1.length ? r1[0].never_returned.length : "—"}
          tone="live"
          hint={r1.length ? "in round 1" : "run round 1"}
        />
        <StatTile label="Pending approvals" value={pending.length} />
      </div>

      <section>
        <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-stack-sm">
          The loop
        </h2>
        <div className="flex flex-col gap-2">
          {steps.map((s, i) => (
            <Link key={s.label} href={s.href}>
              <GlassPanel className="p-4 flex items-center gap-4">
                <span
                  className={`h-8 w-8 shrink-0 rounded-full flex items-center justify-center
                              font-label-caps text-label-caps ${
                                s.done
                                  ? "bg-electric-lime text-pure-black"
                                  : "bg-surface-container-high text-on-surface-variant"
                              }`}
                >
                  {s.done ? <Icon name="check" className="text-[16px]" /> : i + 1}
                </span>
                <span className="font-body-md text-body-md text-primary flex-1">
                  {s.label}
                </span>
                <span className="font-label-caps text-label-caps text-on-surface-variant">
                  {s.detail}
                </span>
                <Icon name="chevron_right" className="text-outline" />
              </GlassPanel>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
