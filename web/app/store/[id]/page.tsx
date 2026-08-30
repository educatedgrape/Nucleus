import Link from "next/link";
import { notFound } from "next/navigation";
import { AgentChip, GlassPanel, Icon } from "@/components/glass";
import { getDatasetMeta, getProduct, getProducts } from "@/lib/data";

export const dynamic = "force-dynamic";

export async function generateStaticParams() {
  return (await getProducts()).map((p) => ({ id: p.id }));
}

export default async function ProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [product, meta] = await Promise.all([getProduct(id), getDatasetMeta()]);
  if (!product) notFound();

  const label = (k: string) => meta.spec_labels?.[k] ?? k.replace(/_/g, " ");
  const value = (v: string | number | boolean) =>
    typeof v === "boolean" ? (v ? "Yes" : "No") : String(v);

  return (
    <main className="max-w-container-max mx-auto px-margin-mobile md:px-margin-desktop py-stack-md">
      <Link
        href="/store"
        className="inline-flex items-center gap-1 mb-stack-md font-label-caps text-label-caps uppercase text-on-surface-variant hover:text-primary transition-colors"
      >
        <Icon name="arrow_back" className="text-[16px]" />
        All products
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-stack-lg">
        <GlassPanel className="aspect-square bg-surface-container-lowest flex items-center justify-center">
          <Icon name={meta.icon} className="text-outline-variant text-[140px]" />
        </GlassPanel>

        <div className="flex flex-col gap-stack-md">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-label-caps text-label-caps uppercase text-outline">
                {product.id}
              </span>
              {product.edit_history.length > 0 && (
                <AgentChip tone="agent" dot>
                  rewritten by agent
                </AgentChip>
              )}
            </div>
            <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">
              {product.name}
            </h1>
            <p className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface uppercase tabular-nums">
              {meta.currency}
              {product.price}
            </p>
          </div>

          {/* The description is the part that matters: it is what search
              matches against, and what the dormant agent rewrites. */}
          <GlassPanel className="p-6">
            <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-3">
              Description
            </h2>
            <p className="font-body-md text-body-md text-on-surface">
              {product.description}
            </p>
          </GlassPanel>

          <div>
            <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-3">
              Specifications
            </h2>
            <dl className="grid grid-cols-2 gap-px bg-glass-border rounded-lg overflow-hidden">
              {Object.entries(product.specs).map(([k, v]) => (
                <div key={k} className="bg-pure-black p-4">
                  <dt className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-1">
                    {label(k)}
                  </dt>
                  <dd className="font-body-md text-body-md text-on-surface">{value(v)}</dd>
                </div>
              ))}
            </dl>
          </div>

          {product.semantic_links.length > 0 && (
            <GlassPanel className="p-6">
              <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-3">
                Confirmed semantic links
              </h2>
              <p className="font-body-sm text-body-sm text-on-surface-variant mb-3">
                Shopper intents this description already answers. The agent
                checked and left it alone.
              </p>
              <ul className="flex flex-col gap-2">
                {product.semantic_links.map((l, i) => (
                  <li key={i} className="flex flex-col gap-1">
                    <AgentChip tone="good">{l.intent}</AgentChip>
                    {l.evidenced_by && (
                      <span className="font-body-sm text-body-sm text-on-surface-variant pl-1">
                        evidenced by &ldquo;{l.evidenced_by}&rdquo;
                        {l.rank ? ` (rank ${l.rank})` : ""}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </GlassPanel>
          )}

          {product.edit_history.length > 0 && (
            <GlassPanel className="p-6">
              <h2 className="font-label-caps text-label-caps uppercase text-on-surface-variant mb-3">
                Edit history
              </h2>
              <ol className="flex flex-col gap-4">
                {product.edit_history.map((e, i) => (
                  <li key={i} className="border-l-2 border-electric-cyan pl-4">
                    <div className="font-label-caps text-label-caps text-outline mb-1">
                      {new Date(e.at).toLocaleString()}
                    </div>
                    {e.replaced && (
                      <p className="font-body-sm text-body-sm text-on-surface-variant line-through mb-1">
                        {e.replaced}
                      </p>
                    )}
                    <p className="font-body-md text-body-md text-on-surface mb-2">{e.added}</p>
                    <div className="flex flex-wrap gap-1">
                      {e.based_on.map((b) => (
                        <AgentChip key={b} tone="neutral">
                          {b}
                        </AgentChip>
                      ))}
                    </div>
                  </li>
                ))}
              </ol>
            </GlassPanel>
          )}
        </div>
      </div>
    </main>
  );
}
