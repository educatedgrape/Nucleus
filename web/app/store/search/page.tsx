"use client";

import Link from "next/link";
import { useState } from "react";
import { AgentChip, Button, GlassPanel, Icon } from "@/components/glass";

type Hit = {
  product_id: string;
  rank: number;
  score: number;
  name: string;
  price: number;
  description: string;
};

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [k, setK] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
      const data = await res.json();
      setHits(data.hits);
      setK(data.k);
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} — is the backend running on :8000?`
          : String(err)
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="max-w-container-max mx-auto px-margin-mobile md:px-margin-desktop py-stack-md flex flex-col gap-stack-md">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">Search</h1>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
          Natural language, matched against product descriptions only. This is
          the same index the personas search, so what you see here is what they
          see.
        </p>
      </div>

      <form onSubmit={run} className="flex gap-3 items-stretch">
        <div className="relative flex-1">
          <span className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
            <Icon name="search" className="text-outline" />
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="something light I can actually read outdoors on site"
            className="w-full h-full pl-12 pr-4 py-3 border-none rounded-lg
                       bg-surface-container-low text-on-surface
                       placeholder-on-surface-variant/70 focus:outline-none
                       focus:ring-2 focus:ring-electric-cyan
                       focus:bg-surface-container transition-all
                       font-body-md text-body-md"
          />
        </div>
        <Button type="submit" disabled={busy || !query.trim()}>
          {busy ? "Searching…" : "Search"}
        </Button>
      </form>

      {error && (
        <GlassPanel className="p-4 border-l-4 border-error">
          <p className="font-body-md text-body-md text-on-error-container">{error}</p>
        </GlassPanel>
      )}

      {hits && (
        <div className="flex flex-col gap-stack-sm">
          <div className="flex items-center gap-3">
            <AgentChip tone="agent">top {k}</AgentChip>
            <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">
              {hits.length} returned
            </span>
          </div>

          {hits.length === 0 && (
            <p className="font-body-md text-body-md text-on-surface-variant">
              Nothing matched.
            </p>
          )}

          {hits.map((h) => (
            <Link key={h.product_id} href={`/store/${h.product_id}`}>
              <GlassPanel className="p-5 flex gap-5 items-start">
                <span className="font-label-caps text-label-caps text-outline tabular-nums pt-1 w-6">
                  {h.rank}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-baseline gap-3 mb-1">
                    <h3 className="font-body-md text-body-md font-semibold text-primary">
                      {h.name}
                    </h3>
                    <span className="font-label-caps text-label-caps text-on-surface-variant tabular-nums">
                      {h.score.toFixed(3)}
                    </span>
                  </div>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">
                    {h.description}
                  </p>
                </div>
              </GlassPanel>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
