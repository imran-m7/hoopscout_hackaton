import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";
import type { TargetCheck } from "@/lib/types";
import { cn } from "@/lib/utils";
import { fmt, isNum } from "@/lib/format";

const STATUS = {
  ideal: { bg: "bg-good", text: "text-good", label: "Ideal" },
  close: { bg: "bg-ok", text: "text-ok", label: "Close" },
  off: { bg: "bg-weak", text: "text-weak", label: "Off" },
  unknown: { bg: "bg-neutral", text: "text-muted-foreground", label: "Not checked yet" },
} as const;

function digitsFor(t: TargetCheck) {
  return t.scale_max - t.scale_min <= 5 ? 2 : t.scale_max - t.scale_min <= 20 ? 1 : 0;
}

export function TargetBar({ t, history }: { t: TargetCheck; history?: (number | null)[] | undefined }) {
  const span = t.scale_max - t.scale_min || 1;
  const pct = (v: number) => Math.min(100, Math.max(0, ((v - t.scale_min) / span) * 100));
  const st = STATUS[t.status] ?? STATUS.unknown;
  const d = digitsFor(t);
  const hist = (history ?? []).filter(isNum);
  return (
    <div className="py-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-semibold">{t.label}</span>
        <span className={cn("num text-xl font-bold", st.text)}>
          {fmt(t.value, d, t.unit)} <span className="text-xs font-semibold uppercase">{st.label}</span>
        </span>
      </div>
      <div className="mt-2 flex items-center gap-4">
        <div className="relative h-3 flex-1 rounded-full bg-muted">
          <div className="absolute inset-y-0 rounded-full bg-good/30 ring-1 ring-good/50" style={{ left: `${pct(t.ideal_min)}%`, width: `${pct(t.ideal_max) - pct(t.ideal_min)}%` }} />
          {isNum(t.value) && (
            <div className={cn("absolute top-1/2 size-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-card shadow", st.bg)} style={{ left: `${pct(t.value)}%` }} />
          )}
        </div>
        {hist.length > 1 && (
          <div className="h-8 w-20 shrink-0" title="Progress">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={hist.map((v, i) => ({ i, v }))}>
                <YAxis hide domain={["dataMin", "dataMax"]} />
                <Line type="monotone" dataKey="v" stroke="var(--primary)" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
      <div className="mt-1 flex justify-between text-xs text-muted-foreground">
        <span>Ideal: {fmt(t.ideal_min, d)}–{fmt(t.ideal_max, d)}{t.unit.trim()}</span>
        {hist.length > 1 && <span>Progress over {hist.length} sessions</span>}
      </div>
      {t.tip && <p className="mt-1 text-sm">💡 {t.tip}</p>}
    </div>
  );
}
