import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Lock, RefreshCw, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { getPlayer, mediaUrl, regenerateCoachReport } from "@/lib/api";
import { SKILLS, SKILL_LABELS } from "@/lib/scoring";
import { NOT_MEASURED, cap, fmt, fmtSigned, formatAge, isNum, scoreTone, toneBg } from "@/lib/format";
import { useCoachClub, useNote, useRole, useShortlist } from "@/lib/storage";
import { cn } from "@/lib/utils";
import type { DribblingAnalysis, JumpAnalysis, PlayerReport, QualityInfo, SanityFlag, ShootingAnalysis, TargetCheck } from "@/lib/types";
import { ErrorBlock, GemTag, LoadingBlock, RankChange, SampleTag, Score, SourceTag } from "@/components/hoop/bits";
import { SkillRadar } from "@/components/hoop/SkillRadar";
import { TargetBar } from "@/components/hoop/TargetBar";
import { ContactDialog, PlayerCardDialog } from "@/components/hoop/PlayerDialogs";
import { useDemoMode } from "@/components/AppHeader";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

import { RequireCoachClub, NoAccess } from "@/components/hoop/Access";
import { canSeePlayer } from "@/lib/access";

export const Route = createFileRoute("/players/$id")({
  head: () => ({
    meta: [
      { title: "Player profile — HoopScout" },
      { name: "description", content: "Fair rank, skill radar, AI coach report and path to ideal form for a young basketball player." },
      { property: "og:title", content: "Player profile — HoopScout" },
      { property: "og:description", content: "Skill, not size: a fair player profile." },
      { property: "og:type", content: "profile" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <RequireCoachClub>
      <Profile />
    </RequireCoachClub>
  ),
});

function Profile() {
  const { id } = Route.useParams();
  const q = useQuery({ queryKey: ["player", id], queryFn: () => getPlayer(id) });
  const [role] = useRole();
  const [coachClub] = useCoachClub();
  if (q.isLoading) return <LoadingBlock label="Loading player…" />;
  if (q.error || !q.data) return <ErrorBlock message={(q.error as Error)?.message ?? "Player not found"} onRetry={() => q.refetch()} />;
  if (!canSeePlayer(role, coachClub, q.data.player))
    return <NoAccess title="Not your club" text={`Coaches can only see kids from their own club${coachClub ? ` (${coachClub})` : ""}.`} />;
  return <ProfileBody r={q.data} />;
}

function SectionTitle({ children, extra }: { children: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-2xl font-bold uppercase">{children}</h2>
      {extra}
    </div>
  );
}

function ProfileBody({ r }: { r: PlayerReport }) {
  const p = r.player;
  const demo = useDemoMode();
  const { has, toggle } = useShortlist();
  const ranked = p.status === "ranked";
  const starred = has(p.id);

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card className="p-5 md:p-8">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              {p.hidden_gem && <GemTag className="text-sm" />}
              <SourceTag isReal={p.is_real} />
              {demo && <SampleTag />}
            </div>
            <h1 className="mt-2 text-5xl font-extrabold uppercase leading-none md:text-6xl">{p.name}</h1>
            <p className="mt-2 text-lg text-muted-foreground">
              {formatAge(p.age_months)} · <strong className="text-card-foreground">{p.rank_group}</strong> · {cap(p.position)} · {p.club || "—"} · {p.town || "—"}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {fmt(p.years_playing)} years playing · {cap(p.dominant_hand)}-handed · Height {fmtSigned(p.height_diff_cm, 0, " cm")} vs age average
              {isNum(p.maturity_offset_years) && <> · Maturity offset {fmtSigned(p.maturity_offset_years, 1, " y")}</>}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant={starred ? "hero" : "outline"} onClick={() => toggle(p.id)}>⭐ {starred ? "Shortlisted" : "Shortlist"}</Button>
            <ContactDialog p={p} />
            <PlayerCardDialog p={p} />
          </div>
        </div>
      </Card>

      {!ranked && (
        <div className="flex items-start gap-3 rounded-xl border border-ok/50 bg-ok/15 p-4 text-foreground">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-ok" />
          <p><strong>Not ranked yet:</strong> {p.provisional_reason ?? "more data needed"}.</p>
        </div>
      )}

      {/* Rank panel */}
      <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <Card className="p-6">
          <SectionTitle>Rank in {p.rank_group}</SectionTitle>
          <div className="flex items-end gap-6">
            <div>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Raw</p>
              <p className="num text-5xl font-bold text-muted-foreground">#{fmt(p.raw_rank)}</p>
            </div>
            <p className="num pb-2 text-3xl text-muted-foreground">→</p>
            <div>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Fair</p>
              <p className="num text-6xl font-extrabold text-primary">#{fmt(p.fair_rank)}</p>
            </div>
            <RankChange value={p.rank_change} className="pb-3 text-2xl" />
          </div>
          <div className="mt-6">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">Fair score</p>
            <Score value={ranked ? p.fair_score : null} margin={p.score_margin} className="text-7xl" />
          </div>
        </Card>
        <Card className="p-6">
          <SectionTitle>Why this rank</SectionTitle>
          {p.breakdown.length === 0 ? (
            <p className="text-muted-foreground">No breakdown yet.</p>
          ) : (
            <ol className="space-y-2">
              {p.breakdown.map((b, i) => {
                const first = i === 0;
                const w = Math.min(100, Math.abs(b.value) * (first ? 1 : 8));
                return (
                  <li key={i} className="grid grid-cols-[1fr_auto] items-center gap-3">
                    <div>
                      <div className="text-sm">{b.label}</div>
                      <div className="mt-1 h-2 rounded-full bg-muted">
                        <div className={cn("h-full rounded-full", first ? "bg-chart-2" : b.value >= 0 ? "bg-good" : "bg-weak")} style={{ width: `${w}%` }} />
                      </div>
                    </div>
                    <span className={cn("num w-16 text-right text-2xl font-bold", !first && (b.value > 0 ? "text-good" : b.value < 0 ? "text-weak" : "text-muted-foreground"))}>
                      {first ? fmt(b.value, 0) : fmtSigned(b.value, 0)}
                    </span>
                  </li>
                );
              })}
              <li className="flex items-center justify-between border-t pt-3">
                <span className="font-semibold">Fair score</span>
                <span className="num text-3xl font-extrabold text-primary">= {ranked ? fmt(p.fair_score, 0) : "—"}</span>
              </li>
            </ol>
          )}
        </Card>
      </div>

      {/* Skills */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <SectionTitle>Skills</SectionTitle>
          <SkillRadar
            series={[
              { name: p.name.split(" ")[0] ?? p.name, scores: p.fair_scores },
              { name: `${p.rank_group} average`, scores: r.group_average, color: "var(--neutral)", dashed: true },
            ]}
          />
        </Card>
        <Card className="p-6">
          <SectionTitle extra={<span className="text-xs text-muted-foreground">thin = measured · thick = fair</span>}>Measured vs fair</SectionTitle>
          <div className="space-y-4">
            {SKILLS.map((k) => {
              const m = p.scores[k];
              const f = p.fair_scores[k];
              const none = !isNum(m) && !isNum(f);
              return (
                <div key={k}>
                  <div className="flex justify-between text-sm">
                    <span>{SKILL_LABELS[k]}</span>
                    {none ? (
                      <span className="italic text-muted-foreground">{NOT_MEASURED}</span>
                    ) : (
                      <span className="num"><span className="text-muted-foreground">{fmt(m)}</span> → <Score value={f} className="text-lg" /></span>
                    )}
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-muted"><div className="h-full rounded-full bg-neutral" style={{ width: `${isNum(m) ? m : 0}%` }} /></div>
                  <div className="mt-1 h-3 rounded-full bg-muted"><div className={cn("h-full rounded-full", toneBg[scoreTone(f)])} style={{ width: `${isNum(f) ? f : 0}%` }} /></div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="p-6">
          <SectionTitle>✅ Strengths</SectionTitle>
          <Insights list={r.strengths} />
        </Card>
        <Card className="p-6">
          <SectionTitle>⚠️ Things to improve</SectionTitle>
          <Insights list={r.weaknesses} />
        </Card>
      </div>

      <CoachCard r={r} />
      <PathToIdeal r={r} />
      <VideoTabs r={r} />
      <NotesCard id={p.id} />

      <p className="flex items-center gap-2 text-sm text-subtle">
        <Lock className="size-4" /> Weight and body measurements are private and only used inside the calculations. Only town and club are shown.
      </p>
    </div>
  );
}

function Insights({ list }: { list: PlayerReport["strengths"] }) {
  if (!list?.length) return <p className="text-muted-foreground">—</p>;
  return (
    <ul className="space-y-3">
      {list.map((i, n) => (
        <li key={n}>
          <p className="font-semibold">{i.title}</p>
          <p className="text-sm text-muted-foreground">{i.detail}</p>
        </li>
      ))}
    </ul>
  );
}

function CoachCard({ r }: { r: PlayerReport }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => regenerateCoachReport(r.player.id),
    onSuccess: (c) => {
      qc.setQueryData<PlayerReport>(["player", r.player.id], (old) => (old ? { ...old, coach_report: c } : old));
      toast.success("Coach report updated");
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const c = r.coach_report;
  return (
    <Card className="border-l-4 border-l-primary p-6">
      <SectionTitle
        extra={
          <div className="flex items-center gap-2">
            {c && (
              <span className={cn("rounded-full px-2 py-0.5 text-xs font-semibold", c.source === "ai" ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground")}>
                {c.source === "ai" ? <><Sparkles className="mr-1 inline size-3" />AI</> : "Rule-based"}
              </span>
            )}
            <Button size="sm" variant="outline" onClick={() => m.mutate()} disabled={m.isPending}>
              <RefreshCw className={cn(m.isPending && "animate-spin")} /> {m.isPending ? "Writing…" : "Regenerate"}
            </Button>
          </div>
        }
      >
        🧑‍🏫 AI Coach
      </SectionTitle>
      {!c ? (
        <p className="text-muted-foreground">No coach report yet. Click Regenerate to create one.</p>
      ) : (
        <>
          <p className="text-lg leading-relaxed">{c.summary || "—"}</p>
          <h3 className="mt-5 text-lg font-bold uppercase text-muted-foreground">3 drills for this week</h3>
          <div className="mt-2 grid gap-3 md:grid-cols-3">
            {c.drills.map((d, i) => (
              <div key={i} className="rounded-xl bg-muted p-4">
                <p className="num text-3xl font-extrabold text-primary">{i + 1}</p>
                <p className="font-semibold">{d.name}</p>
                <p className="mt-1 text-sm text-muted-foreground">{d.description}</p>
                <p className="mt-2 text-sm font-semibold">{d.dose}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

function PathToIdeal({ r }: { r: PlayerReport }) {
  const sections: { title: string; targets: TargetCheck[] }[] = [
    { title: "🎯 Shooting", targets: r.shooting?.targets ?? [] },
    { title: "⛹️ Dribbling", targets: r.dribbling?.targets ?? [] },
    { title: "🦘 Jump", targets: r.jump?.targets ?? [] },
  ].filter((s) => s.targets.length);
  const all = sections.flatMap((s) => s.targets);
  const reached = all.filter((t) => t.status === "ideal").length;
  const multi = r.sessions.length > 1;
  return (
    <Card className="p-6">
      <SectionTitle extra={all.length > 0 && <span className="num text-xl font-bold"><span className="text-good">{reached}</span> of {all.length} targets reached</span>}>
        Path to ideal form
      </SectionTitle>
      {all.length === 0 ? (
        <p className="text-muted-foreground">No video analysis yet — targets appear after the first upload.</p>
      ) : (
        <>
          <div className="grid gap-x-10 lg:grid-cols-2">
            {sections.map((s) => (
              <div key={s.title} className="divide-y">
                <h3 className="pt-2 text-lg font-bold uppercase text-muted-foreground">{s.title}</h3>
                {s.targets.map((t) => (
                  <TargetBar key={t.metric} t={t} history={multi ? r.sessions.map((x) => x.target_values?.[t.metric] ?? null) : undefined} />
                ))}
              </div>
            ))}
          </div>
          {!multi && <p className="mt-3 text-sm text-muted-foreground">Upload new videos later to track progress.</p>}
        </>
      )}
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-b py-2 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="num text-xl font-bold">{value}</span>
    </div>
  );
}

function Quality({ q, extra }: { q: QualityInfo; extra?: string }) {
  return (
    <p className={cn("text-sm font-semibold", q.ok ? "text-good" : "text-ok")}>
      Tracking {fmt(q.tracking_pct, 0, "%")} · {extra ?? `${fmt(q.reps)} reps (min ${fmt(q.min_reps)})`} {q.ok ? "✓" : "⚠"}
    </p>
  );
}

function Flags({ flags }: { flags: SanityFlag[] }) {
  if (!flags?.length) return null;
  return (
    <div className="mt-3 space-y-2">
      {flags.map((f, i) => (
        <div key={i} className="flex items-start gap-2 rounded-lg border border-ok/50 bg-ok/10 p-2 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-ok" /> {f.message}
        </div>
      ))}
    </div>
  );
}

function VideoBox({ url: raw }: { url: string | null }) {
  const url = mediaUrl(raw);
  return url ? (
    <video src={url} controls playsInline className="aspect-video w-full rounded-xl bg-navy-deep" />
  ) : (
    <div className="grid aspect-video w-full place-items-center rounded-xl bg-navy-deep text-sm text-subtle">Annotated video not available</div>
  );
}

function NoVideo() {
  return <div className="grid h-48 place-items-center rounded-xl bg-muted text-muted-foreground">No video yet</div>;
}

function ShootingTab({ a }: { a: ShootingAnalysis | null }) {
  if (!a) return <NoVideo />;
  return (
    <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
      <div>
        <VideoBox url={a.annotated_video_url} />
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-muted-foreground">
              <tr className="border-b"><th className="p-2">#</th><th className="p-2">Time</th><th className="p-2">Elbow</th><th className="p-2">Knee</th><th className="p-2">Release</th><th className="p-2">Timing</th><th className="p-2">Follow</th></tr>
            </thead>
            <tbody className="num">
              {a.shots.map((s) => (
                <tr key={s.index} className="border-b">
                  <td className="p-2">{s.index}</td><td className="p-2">{fmt(s.time_s, 1, " s")}</td><td className="p-2">{fmt(s.elbow_set_deg, 0, "°")}</td>
                  <td className="p-2">{fmt(s.knee_min_deg, 0, "°")}</td><td className="p-2">{fmt(s.release_height_ratio, 2, "×")}</td>
                  <td className="p-2">{fmt(s.leg_arm_timing_ms, 0, " ms")}</td><td className="p-2">{fmt(s.follow_through_s, 2, " s")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {a.skipped.length > 0 && (
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {a.skipped.map((s, i) => <li key={i}><span className="num">{fmt(s.time_s, 1, " s")}</span> — {s.reason}</li>)}
            </ul>
          )}
        </div>
      </div>
      <div>
        <Quality q={a.quality} extra={`${fmt(a.quality.reps)} shots counted (min ${fmt(a.quality.min_reps)})`} />
        <div className="mt-2">
          <Stat label="Elbow at set point" value={fmt(a.avg_elbow_set_deg, 0, "°")} />
          <Stat label="Lowest knee angle" value={fmt(a.avg_knee_min_deg, 0, "°")} />
          <Stat label="Release height" value={fmt(a.avg_release_height_ratio, 2, "× height")} />
          <Stat label="Legs → arm timing" value={fmt(a.avg_leg_arm_timing_ms, 0, " ms")} />
          <Stat label="Follow-through" value={fmt(a.avg_follow_through_s, 2, " s")} />
          <Stat label="Elbow spread" value={fmt(a.spread_elbow_deg, 1, "°")} />
          <Stat label="Knee spread" value={fmt(a.spread_knee_deg, 1, "°")} />
        </div>
        <Flags flags={a.flags} />
      </div>
    </div>
  );
}

function DribblingTab({ a }: { a: DribblingAnalysis | null }) {
  if (!a) return <NoVideo />;
  return (
    <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
      <VideoBox url={a.annotated_video_url} />
      <div>
        <Quality q={a.quality} extra={`${fmt(a.duration_s, 0, " s")} of dribbling`} />
        <div className="mt-2">
          <Stat label="Dribbles" value={fmt(a.dribbles)} />
          <Stat label="Dribbles per second" value={fmt(a.dribbles_per_sec, 1, "/s")} />
          <Stat label="Rhythm" value={fmt(a.rhythm_score, 0, "/100")} />
          <Stat label="Ball below hip" value={fmt(a.ball_below_hip_pct, 0, "%")} />
          <Stat label="Ball below knee" value={fmt(a.ball_below_knee_pct, 0, "%")} />
          <Stat label="Left / right hand" value={`${fmt(a.left_hand_pct, 0, "%")} / ${fmt(a.right_hand_pct, 0, "%")}`} />
          <Stat label="Weak hand" value={fmt(a.weak_hand_pct, 0, "%")} />
          <Stat label="Head up" value={fmt(a.head_up_pct, 0, "%")} />
        </div>
        <Flags flags={a.flags} />
      </div>
    </div>
  );
}

function JumpTab({ a }: { a: JumpAnalysis | null }) {
  if (!a) return <NoVideo />;
  return (
    <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
      <VideoBox url={a.annotated_video_url} />
      <div>
        <Quality q={a.quality} extra={`${fmt(a.quality.reps)} jumps (min ${fmt(a.quality.min_reps)})`} />
        <div className="mt-2">
          <Stat label="Best jump" value={fmt(a.best_jump_cm, 1, " cm")} />
          <Stat label="Average jump" value={fmt(a.avg_jump_cm, 1, " cm")} />
          {a.jumps.map((j) => <Stat key={j.index} label={`Jump ${j.index} · air ${fmt(j.air_time_s, 2, " s")}`} value={fmt(j.height_cm, 1, " cm")} />)}
        </div>
        <Flags flags={a.flags} />
      </div>
    </div>
  );
}

function VideoTabs({ r }: { r: PlayerReport }) {
  return (
    <Card className="p-6">
      <SectionTitle>Videos & measurements</SectionTitle>
      <Tabs defaultValue="shooting">
        <TabsList>
          <TabsTrigger value="shooting">🎯 Shooting</TabsTrigger>
          <TabsTrigger value="dribbling">⛹️ Dribbling</TabsTrigger>
          <TabsTrigger value="jump">🦘 Jump</TabsTrigger>
        </TabsList>
        <TabsContent value="shooting" className="mt-4"><ShootingTab a={r.shooting} /></TabsContent>
        <TabsContent value="dribbling" className="mt-4"><DribblingTab a={r.dribbling} /></TabsContent>
        <TabsContent value="jump" className="mt-4"><JumpTab a={r.jump} /></TabsContent>
      </Tabs>
    </Card>
  );
}

function NotesCard({ id }: { id: string }) {
  const [note, setNote] = useNote(id);
  return (
    <Card className="p-6">
      <SectionTitle extra={<span className="flex items-center gap-1 text-xs text-muted-foreground"><Lock className="size-3" /> Only visible to you</span>}>Private scout notes</SectionTitle>
      <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Your notes about this player…" rows={4} />
      <p className="mt-2 text-xs text-muted-foreground">Saved on this device automatically.</p>
      <Link to="/board" className="mt-4 inline-block text-sm font-semibold text-primary">← Back to Talent Board</Link>
    </Card>
  );
}
