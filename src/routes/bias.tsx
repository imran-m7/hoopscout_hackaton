import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { getBias } from "@/lib/api";
import { fmtSigned } from "@/lib/format";
import { ErrorBlock, LoadingBlock, PageTitle } from "@/components/hoop/bits";
import { useDemoMode } from "@/components/AppHeader";
import { Card } from "@/components/ui/card";

import { ScoutOnly } from "@/components/hoop/Access";

export const Route = createFileRoute("/bias")({
  head: () => ({
    meta: [
      { title: "Bias Check — HoopScout" },
      { name: "description", content: "See how raw scouting favours early-born, taller kids and how the fair ranking corrects it." },
      { property: "og:title", content: "Bias Check — HoopScout" },
      { property: "og:description", content: "The relative age effect, measured: raw top 10 vs fair top 10." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <ScoutOnly>
      <BiasPage />
    </ScoutOnly>
  ),
});

function BiasPage() {
  const q = useQuery({ queryKey: ["bias"], queryFn: getBias });
  const demo = useDemoMode();
  if (q.isLoading) return <LoadingBlock />;
  if (q.error || !q.data) return <ErrorBlock message={(q.error as Error)?.message ?? "No data"} onRetry={() => q.refetch()} />;
  const b = q.data;
  const quarters = ["Q1 (Jan–Mar)", "Q2 (Apr–Jun)", "Q3 (Jul–Sep)", "Q4 (Oct–Dec)"].map((label, i) => ({
    label,
    all: b.birth_quarter.all_players[i],
    raw: b.birth_quarter.raw_top10[i],
    fair: b.birth_quarter.fair_top10[i],
  }));
  const rawPts = b.height.points.map((p) => ({ x: p.height_diff_cm, y: p.raw_rank, name: p.name }));
  const fairPts = b.height.points.map((p) => ({ x: p.height_diff_cm, y: p.fair_rank, name: p.name }));

  return (
    <div>
      <PageTitle title="Bias Check" sub={demo ? "Sample data · who makes the top 10, before and after fair adjustment." : "Who makes the top 10, before and after fair adjustment."} />
      <Card className="mb-6 grid gap-6 p-6 md:grid-cols-3 md:p-8">
        <div className="md:col-span-1">
          <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Average height vs age</p>
          <p className="mt-1 text-sm text-muted-foreground">Top 10 players</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-muted-foreground">Raw scout view</p>
          <p className="num text-6xl font-extrabold text-weak md:text-7xl">{fmtSigned(b.height.raw_top10_avg_diff_cm, 1)} <span className="text-2xl">cm</span></p>
        </div>
        <div>
          <p className="text-sm font-semibold text-muted-foreground">Fair view</p>
          <p className="num text-6xl font-extrabold text-good md:text-7xl">{fmtSigned(b.height.fair_top10_avg_diff_cm, 1)} <span className="text-2xl">cm</span></p>
        </div>
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="text-2xl font-bold uppercase">Birth quarter of the top 10</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={quarters}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="all" name="All players" fill="var(--neutral)" fillOpacity={0.35} radius={[4, 4, 0, 0]} />
              <Bar dataKey="raw" name="Top 10 raw" fill="var(--weak)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="fair" name="Top 10 fair" fill="var(--good)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card className="p-5">
          <h2 className="text-2xl font-bold uppercase">Height vs rank</h2>
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ left: 0, right: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" dataKey="x" name="Height vs age avg" unit=" cm" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
              <YAxis type="number" dataKey="y" name="Rank" reversed allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
              <ZAxis range={[60, 60]} />
              <Tooltip cursor={{ strokeDasharray: "3 3" }} />
              <Legend />
              <Scatter name="Raw rank" data={rawPts} fill="var(--weak)" />
              <Scatter name="Fair rank" data={fairPts} fill="var(--good)" />
            </ScatterChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted-foreground">Rank 1 is at the top. Raw ranks cluster on the tall side.</p>
        </Card>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-2xl font-bold uppercase">What the data shows</h2>
          <p className="mt-2 text-muted-foreground">{b.explanation || "—"}</p>
        </Card>
        <div className="rounded-xl border border-primary/40 bg-primary/10 p-6">
          <h2 className="text-2xl font-bold uppercase text-primary">Why this matters</h2>
          <p className="mt-2 text-foreground">
            Scouts tend to pick kids born early in the year and kids who are taller — the <strong>relative age effect</strong>. A child born in
            December can be almost a year younger than a teammate born in January. HoopScout compares each kid with what's expected for their age,
            size and experience, so skill shows up — not birthdays.
          </p>
        </div>
      </div>
    </div>
  );
}
