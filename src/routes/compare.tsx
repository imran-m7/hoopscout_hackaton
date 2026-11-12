import { createFileRoute, Link } from "@tanstack/react-router";
import { useQueries } from "@tanstack/react-query";
import { getPlayer } from "@/lib/api";
import { SKILLS, SKILL_LABELS } from "@/lib/scoring";
import { cn } from "@/lib/utils";
import { NOT_MEASURED, fmt, fmtSigned, formatAge, isNum } from "@/lib/format";
import { ErrorBlock, LoadingBlock, PageTitle, PlayerTags, RankChange, Score } from "@/components/hoop/bits";
import { SERIES_COLORS, SkillRadar } from "@/components/hoop/SkillRadar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { PlayerReport } from "@/lib/types";

import { ScoutOnly } from "@/components/hoop/Access";

export const Route = createFileRoute("/compare")({
  validateSearch: (s: Record<string, unknown>): { ids?: string | undefined } => ({ ids: typeof s["ids"] === "string" ? s["ids"] : undefined }),
  head: () => ({
    meta: [
      { title: "Compare players — HoopScout" },
      { name: "description", content: "Compare 2–3 players side by side: skills radar, fair scores and key metrics." },
      { property: "og:title", content: "Compare players — HoopScout" },
      { property: "og:description", content: "Side-by-side skill comparison on the fair Talent Board." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <ScoutOnly>
      <ComparePage />
    </ScoutOnly>
  ),
});

type Row = { label: string; get: (r: PlayerReport) => number | null; digits?: number; unit?: string; lowerBetter?: boolean; noBest?: boolean; skill?: boolean };

const METRICS: Row[] = [
  // Elbow has an ideal range (80–100°), so "higher" is not "better" — don't star a winner.
  { label: "Elbow at set", get: (r) => r.shooting?.avg_elbow_set_deg ?? null, unit: "°", noBest: true },
  { label: "Dribbles / sec", get: (r) => r.dribbling?.dribbles_per_sec ?? null, digits: 1 },
  { label: "Weak hand %", get: (r) => r.dribbling?.weak_hand_pct ?? null, unit: "%" },
  { label: "Head up %", get: (r) => r.dribbling?.head_up_pct ?? null, unit: "%" },
  { label: "Best jump", get: (r) => r.jump?.best_jump_cm ?? null, digits: 1, unit: " cm" },
];

function ComparePage() {
  const { ids } = Route.useSearch();
  const list = (ids ?? "").split(",").filter(Boolean).slice(0, 3);
  const qs = useQueries({ queries: list.map((id) => ({ queryKey: ["player", id], queryFn: () => getPlayer(id) })) });

  if (list.length < 2)
    return (
      <div>
        <PageTitle title="Compare" sub="Pick 2–3 players on the Talent Board or your Shortlist to compare them." />
        <div className="flex gap-3">
          <Button asChild variant="hero"><Link to="/board">Open Talent Board</Link></Button>
          <Button asChild variant="navy"><Link to="/shortlist">Open Shortlist</Link></Button>
        </div>
      </div>
    );
  if (qs.some((q) => q.isLoading)) return <LoadingBlock />;
  const err = qs.find((q) => q.error);
  if (err) return <ErrorBlock message={(err.error as Error).message} />;
  const reports = qs.map((q) => q.data!).filter(Boolean);

  const bestIdx = (vals: (number | null)[], lowerBetter = false) => {
    const nums = vals.filter(isNum);
    if (nums.length < 2) return -1;
    const best = lowerBetter ? Math.min(...nums) : Math.max(...nums);
    return vals.indexOf(best);
  };

  const rows: Row[] = [
    ...SKILLS.map((k) => ({ label: SKILL_LABELS[k], get: (r: PlayerReport) => r.player.fair_scores[k], skill: true })),
    ...METRICS,
  ];

  return (
    <div>
      <PageTitle title="Compare" sub="Fair skill scores, side by side." />
      <div className="grid gap-6 lg:grid-cols-[1fr_1.3fr]">
        <Card className="p-4">
          <SkillRadar height={360} series={reports.map((r, i) => ({ name: r.player.name, scores: r.player.fair_scores, color: SERIES_COLORS[i] }))} />
        </Card>
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="p-3 text-left text-muted-foreground" />
                {reports.map((r, i) => (
                  <th key={r.player.id} className="p-3 text-left align-top">
                    <span className="mb-1 block h-1 w-10 rounded" style={{ background: SERIES_COLORS[i] }} />
                    <Link to="/players/$id" params={{ id: r.player.id }} className="font-display text-xl font-bold hover:text-primary">{r.player.name}</Link>
                    <div className="text-xs font-normal text-muted-foreground">{r.player.rank_group} · {formatAge(r.player.age_months)}</div>
                    <div className="mt-1"><PlayerTags p={r.player} /></div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="border-b bg-muted/60">
                <td className="p-3 font-semibold">Fair score</td>
                {reports.map((r) => <td key={r.player.id} className="p-3"><Score value={r.player.status === "ranked" ? r.player.fair_score : null} margin={r.player.score_margin} className="text-2xl" /></td>)}
              </tr>
              <tr className="border-b">
                <td className="p-3 font-semibold">Raw → fair rank</td>
                {reports.map((r) => (
                  <td key={r.player.id} className="p-3 num text-lg">
                    {fmt(r.player.raw_rank)} → {fmt(r.player.fair_rank)} <RankChange value={r.player.rank_change} className="ml-1" />
                  </td>
                ))}
              </tr>
              <tr className="border-b">
                <td className="p-3 font-semibold">Height vs age</td>
                {reports.map((r) => <td key={r.player.id} className="p-3 num">{fmtSigned(r.player.height_diff_cm, 0, " cm")}</td>)}
              </tr>
              {rows.map((row) => {
                const vals = reports.map(row.get);
                const b = row.noBest ? -1 : bestIdx(vals, row.lowerBetter);
                return (
                  <tr key={row.label} className="border-b last:border-0">
                    <td className="p-3 text-muted-foreground">{row.label}</td>
                    {vals.map((v, i) => (
                      <td key={i} className={cn("p-3 num text-lg", i === b && "font-bold text-primary")}>
                        {row.skill && !isNum(v) ? <span className="text-sm italic text-muted-foreground">{NOT_MEASURED}</span> : fmt(v, row.digits ?? 0, row.unit ?? "")}
                        {i === b && " ★"}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
