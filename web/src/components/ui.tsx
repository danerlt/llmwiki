import type { ReactNode } from "react";

import { Loader2 } from "lucide-react";

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-7 flex items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1.5 text-sm text-ink-muted">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}

const TONES: Record<string, string> = {
  company: "border-accent/30 bg-accent-soft text-accent-dark",
  department: "border-amber-300/50 bg-amber-50 text-amber-700",
  team: "border-sky-300/50 bg-sky-50 text-sky-700",
  personal: "border-line bg-paper text-ink-muted",
  approved: "border-accent/30 bg-accent-soft text-accent-dark",
  pending: "border-amber-300/50 bg-amber-50 text-amber-700",
  processing: "border-sky-300/50 bg-sky-50 text-sky-700",
  rejected: "border-red-200 bg-red-50 text-red-600",
  failed: "border-red-200 bg-red-50 text-red-600",
  done: "border-accent/30 bg-accent-soft text-accent-dark",
  default: "border-line bg-paper text-ink-muted",
};

export function Badge({ children, tone = "default" }: { children: ReactNode; tone?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        TONES[tone] ?? TONES.default
      }`}
    >
      {children}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-muted">
      <Loader2 className="h-4 w-4 animate-spin" /> {label ?? "加载中…"}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
}: {
  icon?: ReactNode;
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-line bg-card/40 px-6 py-16 text-center">
      {icon && <div className="mb-3 text-ink-faint">{icon}</div>}
      <p className="font-medium text-ink">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-sm text-ink-muted">{hint}</p>}
    </div>
  );
}
