"use client";

import { useEffect, useState } from "react";
import { AgentChip, Button, EmptyState, GlassPanel } from "@/components/glass";
import { get, post } from "@/lib/client";

type Item = {
  product_id: string;
  intent: string;
  name: string;
  description: string;
};

export default function Scoring() {
  const [queue, setQueue] = useState<Item[] | null>(null);
  const [done, setDone] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    get<Item[]>("/api/scoring/queue")
      .then(setQueue)
      .catch((e) => {
        setQueue([]);
        setError(e instanceof Error ? e.message : String(e));
      });
  }, []);

  async function score(item: Item, verdict: "right" | "wrong") {
    const key = `${item.product_id}::${item.intent}`;
    setBusy(key);
    try {
      await post("/api/scoring", {
        product_id: item.product_id,
        intent: item.intent,
        verdict,
      });
      setDone((d) => ({ ...d, [key]: verdict }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const byIntent = (queue ?? []).reduce<Record<string, Item[]>>((acc, i) => {
    (acc[i.intent] ??= []).push(i);
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-stack-lg">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">Scoring</h1>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
          Mark each returned product right or wrong for the intent it answered.
          Scored once and reused &mdash; a product marked wrong for an intent
          stays wrong for it in round 2, which gives a fixed baseline without
          asking you to score twice.
        </p>
      </div>

      {error && (
        <GlassPanel className="p-4 border-l-4 border-error">
          <p className="font-body-md text-body-md text-on-error-container">{error}</p>
        </GlassPanel>
      )}

      {queue === null && (
        <p className="font-body-md text-body-md text-on-surface-variant">Loading…</p>
      )}

      {queue?.length === 0 && !error && (
        <EmptyState
          icon="rule"
          title="Nothing to score"
          body="Either no report exists yet, or every product/intent pair that surfaced has already been scored."
        />
      )}

      {Object.entries(byIntent).map(([intent, items]) => (
        <section key={intent}>
          <div className="flex items-center gap-3 mb-stack-sm">
            <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface uppercase">
              {intent}
            </h2>
            <AgentChip tone="neutral">{items.length}</AgentChip>
          </div>
          <div className="flex flex-col gap-3">
            {items.map((i) => {
              const key = `${i.product_id}::${i.intent}`;
              const verdict = done[key];
              return (
                <GlassPanel key={key} className="p-5 flex gap-5 items-start">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-body-md text-body-md font-semibold text-primary mb-1">
                      {i.name}
                      <span className="ml-2 font-label-caps text-label-caps text-outline">
                        {i.product_id}
                      </span>
                    </h3>
                    <p className="font-body-sm text-body-sm text-on-surface-variant leading-snug">
                      {i.description}
                    </p>
                  </div>
                  {verdict ? (
                    <AgentChip tone={verdict === "right" ? "good" : "warn"} dot>
                      {verdict}
                    </AgentChip>
                  ) : (
                    <div className="flex gap-2 shrink-0">
                      <Button
                        variant="secondary"
                        disabled={busy === key}
                        onClick={() => score(i, "right")}
                      >
                        Right
                      </Button>
                      <Button
                        variant="ghost"
                        disabled={busy === key}
                        onClick={() => score(i, "wrong")}
                      >
                        Wrong
                      </Button>
                    </div>
                  )}
                </GlassPanel>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
