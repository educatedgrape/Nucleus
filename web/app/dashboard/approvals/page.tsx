"use client";

import { useEffect, useState } from "react";
import { AgentChip, Button, EmptyState, GlassPanel, Icon } from "@/components/glass";
import { get, post } from "@/lib/client";

type Proposal = {
  id: string;
  gap_id: string;
  product_id: string;
  intent: string;
  action: "rewrite" | "flag" | "skip" | "no_change";
  new_description: string | null;
  based_on: string[];
  reason: string;
  status: "pending" | "approved" | "rejected";
  downgraded_from?: string;
  rejected_description?: string;
  traceability_failures?: string[];
  link?: { intent: string; evidenced_by?: string; rank?: number | null };
};

const ACTION_META = {
  rewrite: {
    tone: "agent" as const, icon: "edit_note", title: "Proposed rewrite",
    blurb: "The specs support this. Every sentence traced to a spec field.",
    actionable: true,
  },
  flag: {
    tone: "warn" as const, icon: "flag", title: "Flagged — no change proposed",
    blurb: "The agent could not support this from the product data, so it refused to write it.",
    actionable: false,
  },
  skip: {
    tone: "neutral" as const, icon: "block", title: "Skipped — product gap",
    blurb: "The product genuinely doesn't fit this intent.",
    actionable: false,
  },
  no_change: {
    tone: "good" as const, icon: "check_circle", title: "No change necessary",
    blurb: "Already surfaces for this intent. Confirmed as a semantic link instead of rewritten.",
    actionable: true,
  },
};

export default function Approvals() {
  const [proposals, setProposals] = useState<Proposal[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | Proposal["action"]>("all");

  async function refresh() {
    try {
      setProposals(await get<Proposal[]>("/api/proposals"));
    } catch (e) {
      setProposals([]);
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function decide(p: Proposal, decision: "approve" | "reject") {
    setBusy(p.id);
    try {
      await post(`/api/proposals/${p.id}/${decision}`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const all = proposals ?? [];
  const counts = all.reduce<Record<string, number>>((acc, p) => {
    acc[p.action] = (acc[p.action] ?? 0) + 1;
    return acc;
  }, {});
  const shown = filter === "all" ? all : all.filter((p) => p.action === filter);
  const downgraded = all.filter((p) => p.downgraded_from);

  return (
    <div className="flex flex-col gap-stack-lg">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">Approvals</h1>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
          Nothing goes live without you. Rewrites change the description;
          confirmations only record a semantic link. Flags and skips are the
          agent reporting back, not work waiting on you.
        </p>
      </div>

      {error && (
        <GlassPanel className="p-4 border-l-4 border-error">
          <pre className="font-label-caps text-[12px] text-on-error-container whitespace-pre-wrap">
            {error}
          </pre>
        </GlassPanel>
      )}

      {downgraded.length > 0 && (
        <GlassPanel className="p-5 border-l-4 border-electric-cyan">
          <div className="flex items-start gap-3">
            <Icon name="gpp_good" className="text-electric-cyan" />
            <div>
              <h2 className="font-title-md text-title-md text-on-surface mb-1">
                {downgraded.length} rewrite
                {downgraded.length === 1 ? " was" : "s were"} auto-downgraded to a flag
              </h2>
              <p className="font-body-sm text-body-sm text-on-surface-variant">
                The agent proposed copy whose claims could not be traced to a
                spec field, so the code rejected it before it ever reached this
                queue. This is enforced in code, not asked for in the prompt.
              </p>
            </div>
          </div>
        </GlassPanel>
      )}

      {all.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {(["all", "rewrite", "no_change", "flag", "skip"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`agent-chip transition-colors ${
                filter === f
                  ? "bg-electric-lime text-pure-black"
                  : "bg-glass-dark border border-glass-border text-on-surface-variant hover:border-electric-cyan/50 hover:text-electric-cyan"
              }`}
            >
              {f.replace("_", " ")} {f === "all" ? all.length : counts[f] ?? 0}
            </button>
          ))}
        </div>
      )}

      {proposals === null && (
        <p className="font-body-md text-body-md text-on-surface-variant">Loading…</p>
      )}

      {proposals?.length === 0 && !error && (
        <EmptyState
          icon="fact_check"
          title="The agent is dormant"
          body="It wakes when a report exists. Build the report, then wake it from the Run view."
        />
      )}

      <div className="flex flex-col gap-3">
        {shown.map((p) => {
          const meta = ACTION_META[p.action];
          const settled = p.status !== "pending";
          return (
            <GlassPanel key={p.id} className="p-5 flex flex-col gap-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 min-w-0">
                  <Icon
                    name={meta.icon}
                    className={
                      p.action === "flag"
                        ? "text-on-error-container"
                        : p.action === "no_change"
                          ? "text-electric-cyan"
                          : p.action === "rewrite"
                            ? "text-electric-cyan"
                            : "text-outline"
                    }
                  />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <h3 className="font-title-md text-title-md text-on-surface">
                        {meta.title}
                      </h3>
                      <AgentChip tone={meta.tone}>{p.product_id}</AgentChip>
                      <span className="font-label-caps text-label-caps text-outline">{p.id}</span>
                    </div>
                    <p className="font-body-sm text-body-sm text-on-surface-variant">
                      {meta.blurb}
                    </p>
                    <p className="font-label-caps text-label-caps text-electric-cyan mt-1">
                      {p.intent}
                    </p>
                  </div>
                </div>
                {settled ? (
                  <AgentChip tone={p.status === "approved" ? "good" : "neutral"} dot>
                    {p.status}
                  </AgentChip>
                ) : meta.actionable ? (
                  <div className="flex gap-2 shrink-0">
                    <Button
                      disabled={busy === p.id}
                      onClick={() => decide(p, "approve")}
                    >
                      {p.action === "no_change" ? "Confirm" : "Approve"}
                    </Button>
                    <Button
                      variant="ghost"
                      disabled={busy === p.id}
                      onClick={() => decide(p, "reject")}
                    >
                      Reject
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="secondary"
                    disabled={busy === p.id}
                    onClick={() => decide(p, "approve")}
                  >
                    Acknowledge
                  </Button>
                )}
              </div>

              {p.action === "rewrite" && p.new_description && (
                <div className="rounded-md bg-pure-black border border-glass-border p-4">
                  <span className="font-label-caps text-label-caps uppercase text-on-surface-variant block mb-2">
                    New description
                  </span>
                  <p className="font-body-md text-body-md text-on-surface mb-3">
                    {p.new_description}
                  </p>
                  <span className="font-label-caps text-label-caps uppercase text-on-surface-variant block mb-1">
                    Justified by
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {p.based_on.map((b) => (
                      <AgentChip key={b} tone="neutral">{b}</AgentChip>
                    ))}
                  </div>
                </div>
              )}

              {p.action === "no_change" && p.link?.evidenced_by && (
                <div className="rounded-md bg-pure-black border border-glass-border p-4">
                  <span className="font-label-caps text-label-caps uppercase text-on-surface-variant block mb-1">
                    Evidenced by
                  </span>
                  <p className="font-body-md text-body-md text-on-surface italic">
                    &ldquo;{p.link.evidenced_by}&rdquo;
                    {p.link.rank ? (
                      <span className="not-italic font-label-caps text-label-caps text-outline">
                        {" "}rank {p.link.rank}
                      </span>
                    ) : null}
                  </p>
                </div>
              )}

              {p.traceability_failures?.length ? (
                <div className="rounded-lg bg-error-container/40 p-4">
                  <span className="font-label-caps text-label-caps uppercase text-on-error-container block mb-2">
                    Why the rewrite was rejected
                  </span>
                  <ul className="flex flex-col gap-1">
                    {p.traceability_failures.map((f, i) => (
                      <li key={i} className="font-body-sm text-body-sm text-on-error-container">
                        {f}
                      </li>
                    ))}
                  </ul>
                  {p.rejected_description && (
                    <p className="font-body-sm text-body-sm text-on-surface-variant line-through mt-3">
                      {p.rejected_description}
                    </p>
                  )}
                </div>
              ) : (
                p.reason && (
                  <p className="font-body-sm text-body-sm text-on-surface-variant border-l-2 border-glass-border pl-3">
                    {p.reason}
                  </p>
                )
              )}
            </GlassPanel>
          );
        })}
      </div>
    </div>
  );
}
