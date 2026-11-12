import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getPlayers } from "@/lib/api";
import { formatAge } from "@/lib/format";
import { readNote, useShortlist } from "@/lib/storage";
import { ErrorBlock, LoadingBlock, PageTitle, PlayerTags, Score, StarToggle } from "@/components/hoop/bits";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

import { ScoutOnly } from "@/components/hoop/Access";

export const Route = createFileRoute("/shortlist")({
  head: () => ({
    meta: [
      { title: "Shortlist — HoopScout" },
      { name: "description", content: "Your starred players with fair scores and private notes." },
      { property: "og:title", content: "Shortlist — HoopScout" },
      { property: "og:description", content: "The scout's shortlist of starred players." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <ScoutOnly>
      <ShortlistPage />
    </ScoutOnly>
  ),
});

function ShortlistPage() {
  const q = useQuery({ queryKey: ["players"], queryFn: getPlayers });
  const { ids } = useShortlist();
  const [sel, setSel] = useState<string[]>([]);
  const navigate = useNavigate();
  if (q.isLoading) return <LoadingBlock />;
  if (q.error) return <ErrorBlock message={(q.error as Error).message} onRetry={() => q.refetch()} />;
  const players = (q.data ?? []).filter((p) => ids.includes(p.id));

  return (
    <div>
      <PageTitle title="Shortlist" sub="Starred players and your private notes. Stored only on this device.">
        <Button variant="hero" disabled={sel.length < 2} onClick={() => navigate({ to: "/compare", search: { ids: sel.join(",") } })}>
          Compare selected ({sel.length})
        </Button>
      </PageTitle>
      {players.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-lg font-semibold">No players starred yet</p>
          <p className="mt-1 text-muted-foreground">Tap ⭐ on the Talent Board to add players here.</p>
          <Button asChild className="mt-4" variant="hero"><Link to="/board">Open Talent Board</Link></Button>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {players.map((p) => {
            const note = readNote(p.id);
            const checked = sel.includes(p.id);
            return (
              <Card key={p.id} className="flex flex-col p-5">
                <div className="flex items-start justify-between gap-2">
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Checkbox
                      checked={checked}
                      disabled={!checked && sel.length >= 3}
                      onCheckedChange={(v) => setSel((s) => (v ? [...s, p.id] : s.filter((x) => x !== p.id)))}
                    />
                    Compare
                  </label>
                  <StarToggle id={p.id} />
                </div>
                <Link to="/players/$id" params={{ id: p.id }} className="mt-2 font-display text-2xl font-bold hover:text-primary">{p.name}</Link>
                <p className="text-sm text-muted-foreground">{p.rank_group} · {formatAge(p.age_months)} · {p.position} · {p.town}</p>
                <div className="mt-2"><PlayerTags p={p} /></div>
                <div className="mt-4 flex items-end justify-between">
                  <span className="text-xs uppercase tracking-wider text-muted-foreground">Fair score</span>
                  <Score value={p.status === "ranked" ? p.fair_score : null} margin={p.score_margin} className="text-4xl" />
                </div>
                <div className="mt-4 rounded-lg bg-muted p-3 text-sm">
                  <span className="text-xs font-semibold uppercase text-muted-foreground">Private note</span>
                  <p className="mt-1 whitespace-pre-wrap">{note || <span className="text-muted-foreground">No note yet.</span>}</p>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
