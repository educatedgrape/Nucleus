"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AgentChip, EmptyState, GlassPanel, Icon, StatTile } from "@/components/glass";
import { get } from "@/lib/client";

type Row = { product_id: string; name: string; intent: string };

type Results = {
  dataset: string;
  search_k: number;
  primary: { newly_surfacing_correct: Row[]; count: number };
  supporting: {
    still_never_surfacing: string[];
    still_never_surfacing_count: number;
    never_surfacing_before: number;
    closed: string[];
    wrong_products_stopped: Row[];
    correct_products_lost: Row[];
    gap_types: Record<string, number>;
  };
  confirmed_links: {
    product_id: string; name: string; intent: string;
    evidenced_by?: string; rank?: number | null;
  }[];
  needs_scoring: { product_id: string; intent: string }[];
  totals: { products: number; scored_pairs: number };
};

export default function ResultsView() {
  const [data, setData] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    get<Results>("/api/results")
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) {
    return (
      <EmptyState
        icon="insights"
        title="No comparison yet"
        body={error}
      />
    );
  }
  if (!data) {
    return <p className="font-body-md text-body-md text-on-surface-variant">Loading…</p>;
  }

  const s = data.supporting;

  return (
    <div className="flex flex-col gap-stack-lg">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">Results</h1>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
          Same personas, same queries, updated storefront, checked against the
          scores you already gave. Reported as measured &mdash; a small number is
          still the number.
        </p>
      </div>

      {/* ------------------------------------------------------------ primary */}
      <GlassPanel raised className="p-card-padding md:p-12 relative overflow-hidden">
        <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">
          Primary metric
        </span>
        <div className="flex items-baseline gap-4 mt-2 mb-1">
          <span className="font-display-xl text-display-xl leading-none text-electric-lime tabular-nums">
            {data.primary.count}
          </span>
          <span className="font-body-md text-body-md text-on-surface-variant max-w-sm">
            correct products that never surfaced before and now do
          </span>
        </div>
        {data.primary.count === 0 && (
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-3">
            No scored-correct product changed state. Check that rewrites were
            approved and that the pairs involved have been scored.
          </p>
        )}
        {data.primary.newly_surfacing_correct.length > 0 && (
          <ul className="flex flex-col gap-2 mt-5">
            {data.primary.newly_surfacing_correct.map((r) => (
              <li key={`${r.product_id}${r.intent}`} className="flex items-center gap-3">
                <Icon name="trending_up" className="text-electric-cyan text-[18px]" />
                <Link
                  href={`/store/${r.product_id}`}
                  className="font-body-md text-body-md font-semibold text-primary hover:text-electric-cyan"
                >
                  {r.name}
                </Link>
                <span className="font-label-caps text-label-caps text-outline">→</span>
                <span className="font-label-caps text-label-caps text-electric-cyan">{r.intent}</span>
              </li>
            ))}
          </ul>
        )}
      </GlassPanel>

      {/* --------------------------------------------------------- supporting */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-gutter">
        <StatTile
          label="Never surfacing"
          value={`${s.never_surfacing_before} → ${s.still_never_surfacing_count}`}
          hint={`${s.closed.length} closed`}
          tone="live"
        />
        <StatTile
          label="Wrong stopped"
          value={s.wrong_products_stopped.length}
          hint="marked wrong, no longer returned"
        />
        <StatTile
          label="Correct lost"
          value={s.correct_products_lost.length}
          hint="regressions"
          tone={s.correct_products_lost.length ? "live" : "neutral"}
        />
        <StatTile
          label="Confirmed links"
          value={data.confirmed_links.length}
          hint="already working"
          tone="agent"
        />
      </div>

      <section>
        <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-stack-sm">
          Fixable versus needing evidence
        </h2>
        <GlassPanel className="p-6 flex flex-wrap gap-8">
          {(["fixable", "needs_evidence", "not_applicable", "already_covered"] as const).map(
            (k) => (
              <div key={k}>
                <div className="font-headline-lg text-headline-lg text-on-surface uppercase tabular-nums">
                  {s.gap_types[k] ?? 0}
                </div>
                <div className="font-label-caps text-label-caps uppercase text-on-surface-variant">
                  {k.replace("_", " ")}
                </div>
              </div>
            )
          )}
        </GlassPanel>
      </section>

      {/* --------------------------------------------------- confirmed links */}
      <section>
        <div className="flex items-center gap-3 mb-stack-sm">
          <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant">
            Confirmed semantic links
          </h2>
          <AgentChip tone="good">{data.confirmed_links.length}</AgentChip>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant mb-3 max-w-2xl">
          Products whose descriptions already answer the intent. The agent
          checked, said no change was necessary, and recorded the link.
        </p>
        {data.confirmed_links.length === 0 ? (
          <GlassPanel className="p-6">
            <p className="font-body-md text-body-md text-on-surface-variant">
              None confirmed yet — confirm the &ldquo;no change necessary&rdquo;
              rows in Approvals.
            </p>
          </GlassPanel>
        ) : (
          <GlassPanel className="p-5">
            <ul className="flex flex-col divide-y divide-glass-border">
              {data.confirmed_links.map((l, i) => (
                <li key={i} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <Link
                      href={`/store/${l.product_id}`}
                      className="font-body-md text-body-md font-semibold text-primary hover:text-electric-cyan"
                    >
                      {l.name}
                    </Link>
                    <AgentChip tone="good">{l.intent}</AgentChip>
                    {l.rank ? (
                      <span className="font-label-caps text-label-caps text-outline">
                        rank {l.rank}
                      </span>
                    ) : null}
                  </div>
                  {l.evidenced_by && (
                    <p className="font-body-sm text-body-sm text-on-surface-variant italic mt-1">
                      &ldquo;{l.evidenced_by}&rdquo;
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </GlassPanel>
        )}
      </section>

      {s.still_never_surfacing.length > 0 && (
        <section>
          <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-stack-sm">
            Still never surfacing
          </h2>
          <GlassPanel className="p-5">
            <div className="flex flex-wrap gap-2">
              {s.still_never_surfacing.map((id) => (
                <Link key={id} href={`/store/${id}`}>
                  <AgentChip tone="live">{id}</AgentChip>
                </Link>
              ))}
            </div>
          </GlassPanel>
        </section>
      )}

      {data.needs_scoring.length > 0 && (
        <GlassPanel className="p-5 border-l-4 border-electric-cyan">
          <p className="font-body-md text-body-md text-on-surface">
            {data.needs_scoring.length} newly surfaced pair
            {data.needs_scoring.length === 1 ? "" : "s"} not yet scored.{" "}
            <Link href="/dashboard/scoring" className="text-electric-cyan underline">
              Score them
            </Link>{" "}
            to fold them into the primary metric.
          </p>
        </GlassPanel>
      )}
    </div>
  );
}
