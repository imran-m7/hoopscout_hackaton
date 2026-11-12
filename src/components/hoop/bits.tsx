import { ArrowDown, ArrowUp, Minus, Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmt, isNum, scoreTone, toneText } from "@/lib/format";
import { useShortlist } from "@/lib/storage";
import type { PlayerSummary } from "@/lib/types";

const tagBase = "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold leading-none whitespace-nowrap";

export function GemTag({ className }: { className?: string }) {
  return <span className={cn(tagBase, "bg-primary/15 text-primary", className)}>💎 Hidden gem</span>;
}
export function SourceTag({ isReal, className }: { isReal: boolean; className?: string }) {
  return isReal ? (
    <span className={cn(tagBase, "bg-chart-2/15 text-chart-2", className)}>📹 Filmed</span>
  ) : (
    <span className={cn(tagBase, "bg-neutral/20 text-muted-foreground", className)}>Simulated</span>
  );
}
export function SampleTag() {
  return <span className={cn(tagBase, "bg-ok/20 text-ok")}>Sample data</span>;
}
export function PlayerTags({ p }: { p: PlayerSummary }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      {p.hidden_gem && <GemTag />}
      <SourceTag isReal={p.is_real} />
    </span>
  );
}

export function Score({ value, margin, className }: { value: number | null | undefined; margin?: number | null; className?: string }) {
  return (
    <span className={cn("num font-bold", toneText[scoreTone(value)], className)}>
      {fmt(value, 0)}
      {isNum(value) && isNum(margin) && <span className="ml-1 text-[0.6em] font-semibold opacity-70">± {fmt(margin, 0)}</span>}
    </span>
  );
}

export function RankChange({ value, className }: { value: number | null | undefined; className?: string }) {
  if (!isNum(value)) return <span className={cn("text-muted-foreground", className)}>—</span>;
  if (value === 0)
    return (
      <span className={cn("inline-flex items-center gap-0.5 text-muted-foreground num", className)}>
        <Minus className="size-3.5" />0
      </span>
    );
  const up = value > 0;
  return (
    <span className={cn("inline-flex items-center gap-0.5 num font-bold", up ? "text-good" : "text-weak", className)}>
      {up ? <ArrowUp className="size-3.5" /> : <ArrowDown className="size-3.5" />}
      {Math.abs(value)}
    </span>
  );
}

export function StarToggle({ id, className }: { id: string; className?: string }) {
  const { has, toggle } = useShortlist();
  const on = has(id);
  return (
    <button
      type="button"
      aria-label={on ? "Remove from shortlist" : "Add to shortlist"}
      aria-pressed={on}
      onClick={(e) => {
        e.stopPropagation();
        toggle(id);
      }}
      className={cn("rounded-md p-1.5 transition-colors hover:bg-accent", className)}
    >
      <Star className={cn("size-5", on ? "fill-primary text-primary" : "text-muted-foreground")} />
    </button>
  );
}

export function PageTitle({ title, sub, children }: { title: string; sub?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-4xl font-bold uppercase tracking-wide text-foreground md:text-5xl">{title}</h1>
        {sub && <p className="mt-1 max-w-2xl text-subtle">{sub}</p>}
      </div>
      {children}
    </div>
  );
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center gap-3 text-subtle">
      <span className="size-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      {label}
    </div>
  );
}

export function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="mx-auto max-w-md rounded-xl bg-card p-6 text-center text-card-foreground shadow-card">
      <p className="font-semibold">Something went wrong</p>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-4 text-sm font-semibold text-primary underline">
          Try again
        </button>
      )}
    </div>
  );
}
