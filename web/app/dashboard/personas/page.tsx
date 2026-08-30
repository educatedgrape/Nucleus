import { AgentChip, EmptyState, GlassPanel } from "@/components/glass";
import { getPersonas } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function Personas() {
  const personas = await getPersonas();
  const seed = personas.find((p) => p.origin === "real");
  const synthetic = personas.filter((p) => p.origin === "synthetic");

  return (
    <div className="flex flex-col gap-stack-lg">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">Personas</h1>
        <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl">
          Generated from the seed and the category name only &mdash; never from
          the product data. Personas built from the catalogue would only ask
          about what the catalogue already covers, and nothing would fail.
        </p>
      </div>

      {seed && (
        <section>
          <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-stack-sm">
            Seed &middot; a real person
          </h2>
          <GlassPanel className="p-6 flex flex-col gap-3">
            <p className="font-body-md text-body-md text-primary">{seed.need}</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Facets label="Must have" items={seed.must_have} />
              <Facets label="Prefer" items={seed.prefer} />
              <Facets label="Context" items={seed.context} />
            </div>
            {seed.source_answers && (
              <details className="mt-2">
                <summary className="font-label-caps text-label-caps uppercase text-electric-cyan cursor-pointer">
                  Their own words
                </summary>
                <dl className="mt-3 flex flex-col gap-3">
                  {Object.entries(seed.source_answers).map(([k, v]) => (
                    <div key={k}>
                      <dt className="font-label-caps text-label-caps uppercase text-on-surface-variant">
                        {k.replace(/_/g, " ")}
                      </dt>
                      <dd className="font-body-md text-body-md text-on-surface italic">
                        &ldquo;{v}&rdquo;
                      </dd>
                    </div>
                  ))}
                </dl>
              </details>
            )}
          </GlassPanel>
        </section>
      )}

      <section>
        <div className="flex justify-between items-end mb-stack-sm">
          <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant">
            Synthetic &middot; frozen
          </h2>
          <span className="font-label-caps text-label-caps text-on-surface-variant">
            {synthetic.length}
          </span>
        </div>

        {synthetic.length === 0 ? (
          <EmptyState
            icon="groups"
            title="No personas spawned yet"
            body="Spawn them from the Run view. Once generated they are frozen to disk — regenerating would make round 2 incomparable to round 1."
          />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-gutter">
            {synthetic.map((p) => (
              <GlassPanel key={p.id} className="p-5 flex flex-col gap-3">
                <div className="flex items-center justify-between gap-2">
                  <AgentChip tone="agent">{p.angle}</AgentChip>
                  <span className="font-label-caps text-label-caps text-outline">{p.id}</span>
                </div>
                <p className="font-body-md text-body-md text-on-surface">{p.need}</p>
                <div className="rounded-md bg-surface-container-lowest border border-glass-border p-3">
                  <span className="font-label-caps text-label-caps uppercase text-on-surface-variant block mb-1">
                    Frozen query
                  </span>
                  <p className="font-body-md text-body-md text-primary italic">
                    &ldquo;{p.query}&rdquo;
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <Facets label="Must" items={p.must_have} small />
                  <Facets label="Prefer" items={p.prefer} small />
                  <Facets label="Context" items={p.context} small />
                </div>
              </GlassPanel>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Facets({
  label, items, small = false,
}: { label: string; items: string[]; small?: boolean }) {
  if (!items?.length) return null;
  return (
    <div>
      <span className="font-label-caps text-label-caps uppercase text-on-surface-variant block mb-1">
        {label}
      </span>
      <ul className={`flex flex-col gap-1 ${small ? "text-[12px]" : "text-[14px]"}`}>
        {items.map((i) => (
          <li key={i} className="font-body-md text-on-surface leading-snug">
            {i}
          </li>
        ))}
      </ul>
    </div>
  );
}
