"use client";

import { useEffect, useState } from "react";
import { AgentChip, Button, GlassPanel, Icon } from "@/components/glass";
import { get, post } from "@/lib/client";

type Status = {
  dataset: string;
  search_k: number;
  persona_count: number;
  model: string;
  products: number;
  seeds: number;
  synthetic: number;
  rounds: Record<string, number>;
  report: boolean;
  proposals: { total: number; pending: number };
  scored_pairs: number;
  rewritten_products: number;
};

type Step = {
  key: string;
  label: string;
  detail: string;
  run: () => Promise<unknown>;
  ready: (s: Status) => boolean;
  blocked: (s: Status) => string | null;
};

export default function Run() {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [log, setLog] = useState<{ text: string; tone: "ok" | "err" }[]>([]);

  async function refresh() {
    try {
      setStatus(await get<Status>("/api/status"));
    } catch (e) {
      say(e instanceof Error ? e.message : String(e), "err");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function say(text: string, tone: "ok" | "err" = "ok") {
    setLog((l) => [{ text, tone }, ...l].slice(0, 40));
  }

  const steps: Step[] = [
    {
      key: "spawn",
      label: "Spawn personas",
      detail: "Seed + category name only. Frozen once generated.",
      run: async () => {
        const r = await post<{ count: number }>("/api/spawn", { replace: false });
        say(`spawned ${r.count} personas, all angles distinct`);
      },
      ready: (s) => s.seeds > 0 && s.synthetic === 0,
      blocked: (s) =>
        s.seeds === 0 ? "Complete onboarding first."
          : s.synthetic > 0 ? `${s.synthetic} personas already frozen.` : null,
    },
    {
      key: "round1",
      label: "Run round 1",
      detail: "Replay every frozen query against the current descriptions.",
      run: async () => {
        const r = await post<{ queries: number; never_returned: string[] }>("/api/round/1");
        say(`round 1: ${r.queries} queries, ${r.never_returned.length} products never surfaced`);
      },
      // Round 1 is the BEFORE measurement. Once rewrites are live it is
      // spent -- re-running it would measure the improved copy and silently
      // collapse the delta to zero. The backend refuses this too (409); the
      // button is disabled so nobody reaches for it mid-demo.
      ready: (s) => s.synthetic > 0 && s.rewritten_products === 0,
      blocked: (s) =>
        s.synthetic === 0
          ? "Spawn personas first."
          : s.rewritten_products > 0
            ? `${s.rewritten_products} product(s) already rewritten — round 1 is spent. ` +
              "Run `pipeline reset --yes` for a fresh run."
            : null,
    },
    {
      key: "report",
      label: "Build report",
      detail: "Cluster queries into intents, classify every gap.",
      run: async () => {
        const r = await post<{ intents: unknown[]; gaps: unknown[] }>("/api/report?n=1");
        say(`report: ${r.intents.length} intents, ${r.gaps.length} gaps`);
      },
      ready: (s) => (s.rounds["1"] ?? 0) > 0,
      blocked: (s) => ((s.rounds["1"] ?? 0) === 0 ? "Run round 1 first." : null),
    },
    {
      key: "adapt",
      label: "Wake the dormant agent",
      detail: "One proposal per gap. Untraceable claims are downgraded to flag.",
      run: async () => {
        const r = await post<{ count: number; by_action: Record<string, number> }>("/api/adapt");
        say(`${r.count} proposals: ${JSON.stringify(r.by_action)}`);
      },
      ready: (s) => s.report,
      blocked: (s) => (!s.report ? "The agent stays dormant until a report exists." : null),
    },
    {
      key: "round2",
      label: "Run round 2",
      detail: "Same personas, same queries, updated storefront.",
      run: async () => {
        const r = await post<{ queries: number; never_returned: string[] }>("/api/round/2");
        say(`round 2: ${r.queries} queries, ${r.never_returned.length} never surfaced`);
      },
      ready: (s) => (s.rounds["1"] ?? 0) > 0,
      blocked: (s) => ((s.rounds["1"] ?? 0) === 0 ? "Run round 1 first." : null),
    },
  ];

  async function fire(step: Step) {
    setBusy(step.key);
    try {
      await step.run();
    } catch (e) {
      say(e instanceof Error ? e.message : String(e), "err");
    } finally {
      setBusy(null);
      refresh();
    }
  }

  return (
    <div className="flex flex-col gap-stack-lg">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">Run</h1>
        {status && (
          <div className="flex flex-wrap gap-2">
            <AgentChip tone="neutral">{status.products} products</AgentChip>
            <AgentChip tone="neutral">k={status.search_k}</AgentChip>
            <AgentChip tone="agent">{status.model}</AgentChip>
            <AgentChip tone={status.synthetic ? "good" : "neutral"}>
              {status.synthetic} personas
            </AgentChip>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3">
        {steps.map((s) => {
          const blocked = status ? s.blocked(status) : "loading…";
          const ready = status ? s.ready(status) : false;
          return (
            <GlassPanel key={s.key} className="p-5 flex items-center gap-5">
              <div className="flex-1 min-w-0">
                <h3 className="font-body-md text-body-md font-semibold text-primary mb-1">
                  {s.label}
                </h3>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  {s.detail}
                </p>
                {blocked && (
                  <p className="font-label-caps text-label-caps text-outline mt-2">{blocked}</p>
                )}
              </div>
              <Button
                variant={ready ? "primary" : "secondary"}
                disabled={!!busy || !ready}
                onClick={() => fire(s)}
              >
                {busy === s.key ? "Running…" : "Run"}
              </Button>
            </GlassPanel>
          );
        })}
      </div>

      {log.length > 0 && (
        <section>
          <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-stack-sm">
            Activity
          </h2>
          <GlassPanel className="p-4 flex flex-col gap-2 max-h-[320px] overflow-y-auto">
            {log.map((l, i) => (
              <div key={i} className="flex gap-2 items-start">
                <Icon
                  name={l.tone === "ok" ? "check_circle" : "error"}
                  className={`text-[16px] mt-0.5 ${
                    l.tone === "ok" ? "text-electric-cyan" : "text-error"
                  }`}
                />
                <pre
                  className={`font-label-caps text-[12px] whitespace-pre-wrap flex-1 ${
                    l.tone === "ok" ? "text-on-surface" : "text-on-error-container"
                  }`}
                >
                  {l.text}
                </pre>
              </div>
            ))}
          </GlassPanel>
        </section>
      )}
    </div>
  );
}
