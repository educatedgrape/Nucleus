import Link from "next/link";
import { Icon } from "@/components/glass";

const VIEWS = [
  { href: "/dashboard", label: "Overview", icon: "dashboard" },
  { href: "/dashboard/onboarding", label: "Onboarding", icon: "person_add" },
  { href: "/dashboard/personas", label: "Personas", icon: "groups" },
  { href: "/dashboard/run", label: "Run", icon: "play_circle" },
  { href: "/dashboard/report", label: "Report", icon: "lab_profile" },
  { href: "/dashboard/scoring", label: "Scoring", icon: "rule" },
  { href: "/dashboard/approvals", label: "Approvals", icon: "fact_check" },
  { href: "/dashboard/results", label: "Results", icon: "insights" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <aside className="hidden md:flex flex-col w-64 shrink-0 border-r border-glass-border bg-pure-black shadow-rail-cyan">
        <div className="h-20 flex flex-col justify-center px-6 border-b border-glass-border">
          <Link
            href="/"
            className="font-headline-lg text-[24px] leading-none text-electric-lime uppercase"
          >
            Nucleus
          </Link>
        </div>
        <nav className="flex flex-col p-3 gap-1">
          {VIEWS.map((v) => (
            <Link
              key={v.href}
              href={v.href}
              className="flex items-center gap-4 p-4 rounded-full
                         text-on-surface-variant hover:bg-surface-container-high
                         hover:text-electric-cyan hover:translate-x-2
                         transition-all duration-200"
            >
              <Icon name={v.icon} className="text-[20px]" />
              <span className="font-label-caps text-label-caps uppercase">{v.label}</span>
            </Link>
          ))}
        </nav>
        <div className="mt-auto p-3">
          <Link
            href="/store"
            className="flex items-center gap-4 p-4 rounded-full
                       text-on-surface-variant hover:bg-surface-container-high
                       hover:text-electric-lime transition-all duration-200"
          >
            <Icon name="storefront" className="text-[20px]" />
            <span className="font-label-caps text-label-caps uppercase">Storefront</span>
          </Link>
        </div>
      </aside>

      <div className="flex-1 min-w-0">
        <div className="md:hidden h-16 flex items-center gap-4 px-margin-mobile border-b border-glass-border overflow-x-auto">
          {VIEWS.map((v) => (
            <Link
              key={v.href}
              href={v.href}
              className="font-label-caps text-label-caps uppercase text-on-surface-variant whitespace-nowrap"
            >
              {v.label}
            </Link>
          ))}
        </div>
        <main className="p-margin-mobile md:p-margin-desktop max-w-[1200px]">
          {children}
        </main>
      </div>
    </div>
  );
}
