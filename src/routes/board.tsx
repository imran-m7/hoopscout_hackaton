import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ChevronDown, RotateCcw, SlidersHorizontal } from "lucide-react";
import { getPlayers } from "@/lib/api";
import { DEFAULT_WEIGHTS, SKILLS, SKILL_LABELS, SKILL_SORT_LABELS, rankPlayers, type Weights } from "@/lib/scoring";
import { cap, fmt, fmtSigned, formatAge } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PlayerSummary, SkillKey } from "@/lib/types";
import { ErrorBlock, GemTag, LoadingBlock, PageTitle, RankChange, Score, SourceTag, StarToggle } from "@/components/hoop/bits";
import { useDemoMode } from "@/components/AppHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

import { RequireCoachClub } from "@/components/hoop/Access";
import { canSeePlayer } from "@/lib/access";
import { useCoachClub, useRole, useShortlist } from "@/lib/storage";

export const Route = createFileRoute("/board")({
  head: () => ({
    meta: [
      { title: "Talent Board — HoopScout" },
      { name: "description", content: "The fair Talent Board: players ranked within their gender and age group, adjusted for age, size and experience." },
      { property: "og:title", content: "Talent Board — HoopScout" },
      { property: "og:description", content: "Find hidden gems on a fair, age-adjusted ranking." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <RequireCoachClub>
      <Board />
    </RequireCoachClub>
  ),
});

const ALL = "all";
type Filters = { gender: string; age: string; town: string; position: string; hand: string; min: number; gems: boolean; short: boolean };
const DEFAULT_FILTERS: Filters = { gender: ALL, age: ALL, town: ALL, position: ALL, hand: ALL, min: 0, gems: false, short: false };

function Pick({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
        <SelectContent>
          {options.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}

function Board() {
  const q = useQuery({ queryKey: ["players"], queryFn: getPlayers });
  const demo = useDemoMode();
  const navigate = useNavigate();
  const shortlist = useShortlist();
  const [group, setGroup] = useState<string>(ALL);
  const [view, setView] = useState<"fair" | "raw">("fair");
  const [sortBy, setSortBy] = useState<"rank" | SkillKey>("rank");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [selected, setSelected] = useState<string[]>([]);
  const setF = <K extends keyof Filters>(k: K, v: Filters[K]) => setFilters((f) => ({ ...f, [k]: v }));

  const [role] = useRole();
  const [coachClub] = useCoachClub();
  const allRanked = useMemo(() => rankPlayers(q.data ?? [], weights), [q.data, weights]);
  const ranked = useMemo(() => allRanked.filter((p) => canSeePlayer(role, coachClub, p)), [allRanked, role, coachClub]);
  const groups = useMemo(() => [...new Set(ranked.map((p) => p.rank_group))].sort(), [ranked]);
  const towns = useMemo(() => [...new Set(ranked.map((p) => p.town).filter(Boolean))].sort(), [ranked]);

  const filtered = ranked.filter(
    (p) =>
      (group === ALL || p.rank_group === group) &&
      (filters.gender === ALL || p.gender === filters.gender) &&
      (filters.age === ALL || p.age_group === filters.age) &&
      (filters.town === ALL || p.town === filters.town) &&
      (filters.position === ALL || p.position === filters.position) &&
      (filters.hand === ALL || p.dominant_hand === filters.hand) &&
      (filters.min === 0 || (p.status === "ranked" && p.fair_score >= filters.min)) &&
      (!filters.gems || p.hidden_gem) &&
      (!filters.short || shortlist.has(p.id)),
  );

  const rankedOnly = filtered.filter((p) => p.status === "ranked");
  const gems = rankedOnly.filter((p) => p.hidden_gem).length;
  const avgChange = rankedOnly.length ? rankedOnly.reduce((a, p) => a + Math.abs(p.rank_change ?? 0), 0) / rankedOnly.length : null;

  const sortRows = (list: PlayerSummary[]) =>
    [...list].sort((a, b) => {
      if (sortBy !== "rank") return (b.fair_scores[sortBy] ?? -1) - (a.fair_scores[sortBy] ?? -1);
      return view === "fair" ? (a.fair_rank ?? 0) - (b.fair_rank ?? 0) : (a.raw_rank ?? 0) - (b.raw_rank ?? 0);
    });

  const shownGroups = (group === ALL ? groups : [group]).filter((g) => filtered.some((p) => p.rank_group === g));
  const weightsChanged = SKILLS.some((k) => weights[k] !== DEFAULT_WEIGHTS[k]);

  if (q.isLoading) return <LoadingBlock label="Loading Talent Board…" />;
  if (q.error) return <ErrorBlock message={(q.error as Error).message} onRetry={() => q.refetch()} />;

  return (
    <div>
      <PageTitle title="Talent Board" sub={`${role === "coach" ? `Showing only ${coachClub ?? "your club"} players. ` : ""}Kids are only compared with kids of the same gender and age group.${demo ? " Sample data." : ""}`}>
        <div className="flex flex-wrap items-center gap-3">
          <Select value={group} onValueChange={setGroup}>
            <SelectTrigger className="h-11 w-48 border-line bg-surface text-base font-semibold text-foreground"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All groups</SelectItem>
              {groups.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}
            </SelectContent>
          </Select>
          <div className="flex rounded-lg border border-line bg-surface p-1">
            {(["raw", "fair"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={cn("rounded-md px-3 py-1.5 text-sm font-semibold transition-colors", view === v ? "bg-primary text-primary-foreground" : "text-subtle hover:text-foreground")}
              >
                {v === "raw" ? "Scout view (raw)" : "Fair view"}
              </button>
            ))}
          </div>
        </div>
      </PageTitle>

      <div className="mb-6 grid grid-cols-3 gap-3 md:gap-6">
        {[
          { label: "Players scouted", value: fmt(filtered.length) },
          { label: "Hidden gems found", value: `💎 ${gems}` },
          { label: "Avg rank change", value: avgChange === null ? "—" : `±${avgChange.toFixed(1)}` },
        ].map((s) => (
          <Card key={s.label} className="p-4 md:p-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground md:text-sm">{s.label}</p>
            <p className="num mt-1 text-4xl font-extrabold md:text-6xl">{s.value}</p>
          </Card>
        ))}
      </div>

      <Card className="mb-4 p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
          <Pick label="Gender" value={filters.gender} onChange={(v) => setF("gender", v)} options={[{ value: ALL, label: "All" }, { value: "boy", label: "Boys" }, { value: "girl", label: "Girls" }]} />
          <Pick label="Age group" value={filters.age} onChange={(v) => setF("age", v)} options={[{ value: ALL, label: "All" }, ...["U10", "U12", "U14", "U16", "U18"].map((a) => ({ value: a, label: a }))]} />
          <Pick label="Town" value={filters.town} onChange={(v) => setF("town", v)} options={[{ value: ALL, label: "All" }, ...towns.map((t) => ({ value: t, label: t }))]} />
          <Pick label="Position" value={filters.position} onChange={(v) => setF("position", v)} options={[{ value: ALL, label: "All" }, ...["guard", "forward", "center"].map((t) => ({ value: t, label: cap(t) }))]} />
          <Pick label="Dominant hand" value={filters.hand} onChange={(v) => setF("hand", v)} options={[{ value: ALL, label: "All" }, { value: "right", label: "Right" }, { value: "left", label: "Left" }]} />
          <Pick
            label="Sort by"
            value={sortBy}
            onChange={(v) => setSortBy(v as "rank" | SkillKey)}
            options={[{ value: "rank", label: "Rank" }, ...SKILLS.map((k) => ({ value: k, label: SKILL_SORT_LABELS[k] }))]}
          />
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Min fair score: <span className="num font-bold text-foreground">{filters.min}</span></Label>
            <Slider value={[filters.min]} min={0} max={100} step={1} onValueChange={([v]) => setF("min", v ?? 0)} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-5">
          <label className="flex items-center gap-2 text-sm"><Switch checked={filters.gems} onCheckedChange={(v) => setF("gems", v)} /> 💎 Hidden gems only</label>
          <label className="flex items-center gap-2 text-sm"><Switch checked={filters.short} onCheckedChange={(v) => setF("short", v)} /> ⭐ Shortlisted only</label>
          <Button variant="ghost" size="sm" onClick={() => setFilters(DEFAULT_FILTERS)}>Clear filters</Button>
          <div className="ml-auto">
            <Button variant="hero" disabled={selected.length < 2} onClick={() => navigate({ to: "/compare", search: { ids: selected.join(",") } })}>
              Compare ({selected.length}/3)
            </Button>
          </div>
        </div>
        <Collapsible className="mt-4 border-t pt-3">
          <CollapsibleTrigger className="group flex items-center gap-2 text-sm font-semibold">
            <SlidersHorizontal className="size-4 text-primary" /> Scout weights {weightsChanged && <span className="rounded bg-primary/15 px-1.5 text-xs text-primary">custom</span>}
            <ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180" />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <p className="mt-2 text-xs text-muted-foreground">fair score = Σ(weight × fair skill) / Σ weights + experience bonus. Ranks and 💎 update live.</p>
            <div className="mt-3 grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
              {SKILLS.map((k) => (
                <div key={k} className="space-y-2">
                  <div className="flex justify-between text-sm"><span>{SKILL_LABELS[k]}</span><span className="num font-bold">{weights[k].toFixed(1)}</span></div>
                  <Slider value={[weights[k]]} min={0} max={3} step={0.5} onValueChange={([v]) => setWeights((w) => ({ ...w, [k]: v ?? 0 }))} />
                </div>
              ))}
            </div>
            <Button variant="outline" size="sm" className="mt-4" onClick={() => setWeights(DEFAULT_WEIGHTS)}><RotateCcw /> Reset weights</Button>
          </CollapsibleContent>
        </Collapsible>
      </Card>

      {shownGroups.length === 0 && <Card className="p-8 text-center text-muted-foreground">No players match these filters.</Card>}

      {shownGroups.map((g) => {
        const rows = filtered.filter((p) => p.rank_group === g);
        const main = sortRows(rows.filter((p) => p.status === "ranked"));
        const prov = rows.filter((p) => p.status !== "ranked");
        return (
          <Card key={g} className="mb-6 overflow-hidden p-0">
            <div className="flex items-center justify-between border-b bg-muted px-4 py-2">
              <h2 className="text-2xl font-bold uppercase">{g}</h2>
              <span className="text-xs text-muted-foreground">{main.length} ranked</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[960px] text-sm">
                <thead className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <tr className="border-b">
                    <th className="w-8 p-3" />
                    <th className="p-3">Fair</th>
                    <th className="p-3">Raw</th>
                    <th className="p-3">Change</th>
                    <th className="p-3">Player</th>
                    <th className="p-3">Age</th>
                    <th className="p-3">Born</th>
                    <th className="p-3">Height</th>
                    <th className="p-3">Position</th>
                    <th className="p-3">Town</th>
                    <th className="p-3 text-right">{sortBy === "rank" ? "Fair score" : SKILL_LABELS[sortBy]}</th>
                    <th className="w-10 p-3" />
                  </tr>
                </thead>
                <tbody key={`${view}-${sortBy}-${weightsChanged}`}>
                  {[...main, ...prov].map((p, i) => {
                    const isProv = p.status !== "ranked";
                    const checked = selected.includes(p.id);
                    return (
                      <tr
                        key={p.id}
                        onClick={() => navigate({ to: "/players/$id", params: { id: p.id } })}
                        style={{ animationDelay: `${i * 25}ms` }}
                        className={cn("animate-row cursor-pointer border-b last:border-0 hover:bg-accent/60", isProv && "opacity-55", p.hidden_gem && "bg-primary/5")}
                      >
                        <td className="p-3" onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            aria-label={`Select ${p.name} to compare`}
                            checked={checked}
                            disabled={!checked && selected.length >= 3}
                            onCheckedChange={(v) => setSelected((s) => (v ? [...s, p.id] : s.filter((x) => x !== p.id)))}
                          />
                        </td>
                        <td className={cn("p-3 num text-2xl font-bold", view === "fair" && "text-primary")}>{isProv ? "—" : fmt(p.fair_rank)}</td>
                        <td className={cn("p-3 num text-xl", view === "raw" ? "font-bold text-primary" : "text-muted-foreground")}>{isProv ? "—" : fmt(p.raw_rank)}</td>
                        <td className="p-3 text-base"><RankChange value={p.rank_change} /></td>
                        <td className="p-3">
                          <div className="font-semibold text-base">{p.name}</div>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {p.hidden_gem && <GemTag />}
                            <SourceTag isReal={p.is_real} />
                          </div>
                          {isProv && <div className="mt-1 text-xs font-semibold text-ok">Provisional – {p.provisional_reason ?? "—"}</div>}
                        </td>
                        <td className="p-3 whitespace-nowrap">{formatAge(p.age_months)}</td>
                        <td className="p-3">Q{p.birth_quarter ?? "—"}</td>
                        <td className="p-3 num whitespace-nowrap">{fmtSigned(p.height_diff_cm, 0, " cm")}</td>
                        <td className="p-3">{cap(p.position)}</td>
                        <td className="p-3">{p.town || "—"}</td>
                        <td className="p-3 text-right text-2xl">
                          {sortBy === "rank" ? <Score value={isProv ? null : p.fair_score} margin={p.score_margin} /> : <Score value={p.fair_scores[sortBy]} />}
                        </td>
                        <td className="p-3"><StarToggle id={p.id} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
