/**
 * Shared primitives extracted from the Stitch screens (design system
 * "Hyper-Modern Neon") so the storefront and the dashboard are the same system
 * rather than two lookalikes.
 */
import Link from "next/link";
import type { ReactNode } from "react";

export function Icon({ name, className = "" }: { name: string; className?: string }) {
  return (
    <span className={`material-symbols-outlined ${className}`} aria-hidden="true">
      {name}
    </span>
  );
}

export function GlassPanel({
  children,
  className = "",
  raised = false,
}: {
  children: ReactNode;
  className?: string;
  raised?: boolean;
}) {
  return (
    <div className={`${raised ? "glass-panel-raised" : "glass-panel"} rounded-xl ${className}`}>
      {children}
    </div>
  );
}

type ChipTone = "neutral" | "agent" | "live" | "good" | "warn";

const CHIP_TONES: Record<ChipTone, string> = {
  neutral: "bg-glass-dark text-on-surface-variant border border-glass-border",
  agent: "bg-electric-cyan/10 text-electric-cyan border border-electric-cyan/30",
  live: "bg-electric-lime/10 text-electric-lime border border-electric-lime/30",
  good: "bg-electric-lime/10 text-electric-lime border border-electric-lime/30",
  warn: "bg-error-container/30 text-on-error-container border border-error/40",
};

/** Pill indicator in Anybody caps -- the rhythmic anchor of the UI. */
export function AgentChip({
  children,
  tone = "neutral",
  dot = false,
}: {
  children: ReactNode;
  tone?: ChipTone;
  dot?: boolean;
}) {
  return (
    <span className={`agent-chip ${CHIP_TONES[tone]}`}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function Button({
  children,
  variant = "primary",
  className = "",
  ...rest
}: {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const styles = {
    primary:
      "bg-electric-lime text-pure-black hover:shadow-glow-lime-strong",
    secondary:
      "bg-glass-dark text-on-surface border border-glass-border hover:border-electric-cyan/60 hover:text-electric-cyan hover:shadow-glow-cyan",
    ghost:
      "bg-transparent text-on-surface-variant hover:text-electric-cyan hover:bg-glass-dark",
    danger: "bg-error text-on-error hover:opacity-90",
  }[variant];
  return (
    <button
      className={`font-cta-button text-cta-button uppercase px-6 py-4 rounded-full
                  active:scale-98 transition-all duration-300 disabled:opacity-40
                  disabled:cursor-not-allowed disabled:hover:shadow-none
                  ${styles} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function SectionHeading({
  children,
  action,
}: {
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex justify-between items-end mb-stack-md gap-4">
      <h2 className="font-headline-lg-mobile md:font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface uppercase">
        {children}
      </h2>
      {action}
    </div>
  );
}

export function StatTile({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "neutral" | "agent" | "live";
}) {
  const valueTone = {
    neutral: "text-on-surface",
    agent: "text-electric-cyan",
    live: "text-electric-lime",
  }[tone];
  return (
    <GlassPanel className="p-card-padding flex flex-col gap-3">
      <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">
        {label}
      </span>
      {/* headline-lg (48px) overflows two-part values like "11 -> 10"; the
          mobile step keeps the weight without wrapping. */}
      <span
        className={`font-headline-lg-mobile text-headline-lg-mobile tabular-nums
                    whitespace-nowrap ${valueTone}`}
      >
        {value}
      </span>
      {hint && (
        <span className="font-body-sm text-body-sm text-on-surface-variant">{hint}</span>
      )}
    </GlassPanel>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon: string;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <GlassPanel className="p-12 flex flex-col items-center text-center gap-4">
      <Icon name={icon} className="text-electric-cyan text-[40px]" />
      <h3 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface uppercase">
        {title}
      </h3>
      <p className="font-body-md text-body-md text-on-surface-variant max-w-md">{body}</p>
      {action && <div className="mt-2">{action}</div>}
    </GlassPanel>
  );
}

/** Floating glass island nav, per the Stitch storefront screen. */
export function NavIsland({
  brand,
  links,
  right,
}: {
  brand: string;
  links: { href: string; label: string; active?: boolean }[];
  right?: ReactNode;
}) {
  return (
    <nav className="fixed top-0 w-full z-50 bg-pure-black/80 backdrop-blur-xl border-b border-glass-border">
      <div className="flex justify-between items-center px-margin-mobile md:px-margin-desktop max-w-container-max mx-auto h-20">
        <div className="flex items-center gap-10">
          <Link
            href="/"
            className="font-headline-lg text-[28px] leading-none text-electric-lime uppercase"
          >
            {brand}
          </Link>
          <div className="hidden md:flex items-center gap-8">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`font-label-caps text-label-caps uppercase transition-colors ${
                  l.active
                    ? "text-electric-lime"
                    : "text-on-surface-variant hover:text-electric-cyan"
                }`}
              >
                {l.label}
              </Link>
            ))}
          </div>
        </div>
        {right}
      </div>
    </nav>
  );
}
