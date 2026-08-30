import Link from "next/link";
import { GlassPanel, Icon } from "@/components/glass";
import { getConfig, getProducts, getReport } from "@/lib/data";

export default async function Home() {
  const [cfg, products, report] = await Promise.all([
    getConfig(),
    getProducts(),
    getReport(),
  ]);

  const surfaces = [
    {
      href: "/store",
      icon: "storefront",
      title: "Storefront",
      body: `${products.length} products. Real pages, and the descriptions the agent rewrites.`,
    },
    {
      href: "/dashboard",
      icon: "monitoring",
      title: "Dashboard",
      body: report
        ? `Report ready for round ${report.round}. ${report.totals.never_surfaced} products never surfaced.`
        : "Onboarding, personas, runs, report, scoring, approvals and results.",
    },
  ];

  return (
    <main className="max-w-container-max mx-auto px-margin-mobile md:px-margin-desktop py-stack-lg">
      <section className="gradient-banner rounded-lg p-8 md:p-16 mb-stack-lg relative overflow-hidden border border-glass-border">
        <div className="relative z-10 max-w-2xl">
          <span className="inline-block px-4 py-2 mb-6 rounded-full bg-glass-dark border border-electric-lime/40 text-electric-lime backdrop-blur-md font-label-caps text-label-caps uppercase">
            {cfg.dataset.replace(/_/g, " ")}
          </span>
          <h1 className="font-headline-lg-mobile md:font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface uppercase mb-6">
            Descriptions written for humans, searched by agents.
          </h1>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-xl">
            Products that genuinely fit a request never surface, because the
            description never says the thing the shopper asked about. This makes
            that visible, then fixes what the specs can justify &mdash; and
            refuses what they cannot.
          </p>
        </div>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-gutter">
        {surfaces.map((s) => (
          <Link key={s.href} href={s.href}>
            <GlassPanel className="p-card-padding h-full flex flex-col gap-4 group">
              <Icon name={s.icon} className="text-electric-cyan text-[32px]" />
              <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface uppercase">
                {s.title}
              </h2>
              <p className="font-body-md text-body-md text-on-surface-variant">{s.body}</p>
              <span className="mt-auto pt-4 font-label-caps text-label-caps uppercase text-electric-lime flex items-center gap-2">
                Open
                <Icon
                  name="arrow_forward"
                  className="text-[16px] group-hover:translate-x-1 transition-transform"
                />
              </span>
            </GlassPanel>
          </Link>
        ))}
      </div>
    </main>
  );
}
