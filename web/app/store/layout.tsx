import { NavIsland, Icon } from "@/components/glass";
import { getDatasetMeta } from "@/lib/data";

export default async function StoreLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const meta = await getDatasetMeta();
  return (
    <div className="pt-24">
      <NavIsland
        brand="Nucleus"
        links={[
          { href: "/store", label: meta.display_name, active: true },
          { href: "/dashboard", label: "Dashboard" },
        ]}
        right={
          <a
            href="/store/search"
            className="flex items-center gap-2 text-on-surface-variant hover:text-primary transition-colors"
          >
            <Icon name="search" />
            <span className="hidden sm:inline font-label-caps text-label-caps uppercase">
              Search
            </span>
          </a>
        }
      />
      {children}
    </div>
  );
}
