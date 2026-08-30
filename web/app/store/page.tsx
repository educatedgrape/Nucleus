import Link from "next/link";
import { AgentChip, GlassPanel, Icon, SectionHeading } from "@/components/glass";
import { getDatasetMeta, getProducts } from "@/lib/data";

export const dynamic = "force-dynamic"; // reflect approved rewrites immediately

export default async function StorePage() {
  const [products, meta] = await Promise.all([getProducts(), getDatasetMeta()]);

  return (
    <main className="max-w-container-max mx-auto px-margin-mobile md:px-margin-desktop py-stack-md flex flex-col gap-stack-lg">
      <SectionHeading
        action={
          <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">
            {products.length} products
          </span>
        }
      >
        {meta.display_name}
      </SectionHeading>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-gutter">
        {products.map((p) => (
          <Link key={p.id} href={`/store/${p.id}`}>
            <GlassPanel className="overflow-hidden flex flex-col h-full group">
              <div className="relative aspect-square bg-surface-container-lowest p-6 flex items-center justify-center border-b border-glass-border">
                {p.edit_history.length > 0 && (
                  <span className="absolute top-4 left-4 z-10">
                    <AgentChip tone="agent" dot>
                      rewritten
                    </AgentChip>
                  </span>
                )}
                <Icon
                  name={meta.icon}
                  className="text-outline-variant text-[72px] group-hover:scale-105 group-hover:text-electric-lime/60 transition-all duration-500"
                />
              </div>
              <div className="p-4 flex flex-col flex-grow gap-2">
                <div className="flex justify-between items-start gap-2">
                  <h3 className="font-title-md text-title-md text-on-surface">
                    {p.name}
                  </h3>
                  <span className="font-label-caps text-label-caps text-electric-lime tabular-nums whitespace-nowrap">
                    {meta.currency}
                    {p.price}
                  </span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant line-clamp-3">
                  {p.description}
                </p>
                <span className="mt-auto pt-3 font-label-caps text-label-caps text-outline">
                  {p.id}
                </span>
              </div>
            </GlassPanel>
          </Link>
        ))}
      </div>
    </main>
  );
}
