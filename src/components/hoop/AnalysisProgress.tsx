import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { analyzePlayer, getPlayerJobs } from "@/lib/api";
import type { Job, PlayerReport } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

const KIND_LABEL: Record<Job["kind"], string> = { shooting: "🏀 Shooting", dribbling: "⛹️ Dribbling", jump: "🦘 Jump" };
const pendingOf = (jobs: Job[] | undefined) => (jobs ?? []).some((j) => j.status === "queued" || j.status === "running");

/**
 * Profile card for a real kid whose videos are still being analyzed.
 * - Polls GET /api/players/{id}/jobs every 3 s while something is queued/running.
 * - The backend analyzes automatically after the last video; when that happens this card
 *   reloads the profile, so the report appears without a manual refresh.
 * - Shows why a video failed, and an "Analyze now" button if videos are done but no report exists.
 */
export function AnalysisProgress({ report, canAnalyze }: { report: PlayerReport; canAnalyze: boolean }) {
  const id = report.player.id;
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["playerJobs", id],
    queryFn: () => getPlayerJobs(id),
    enabled: report.player.is_real,
    retry: false,
    refetchInterval: (query) => (pendingOf(query.state.data) ? 3000 : false),
  });
  const jobs = q.data ?? [];
  const pending = pendingOf(jobs);

  // pending -> finished: the backend has auto-analyzed, so load the new report.
  const wasPending = useRef(pending);
  useEffect(() => {
    if (wasPending.current && !pending) {
      qc.invalidateQueries({ queryKey: ["player", id] });
      qc.invalidateQueries({ queryKey: ["players"] });
    }
    wasPending.current = pending;
  }, [pending, id, qc]);

  const analyze = useMutation({
    mutationFn: () => analyzePlayer(id),
    onSuccess: (r) => {
      qc.setQueryData(["player", id], r);
      qc.invalidateQueries({ queryKey: ["players"] });
      toast.success("Report ready!");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  if (!report.player.is_real || q.isError || jobs.length === 0) return null;
  const failed = jobs.filter((j) => j.status === "failed");
  const doneButNoReport =
    !pending && report.player.status !== "ranked" && jobs.some((j) => j.status === "done") && !report.coach_report;

  if (!pending && failed.length === 0 && !doneButNoReport) return null;

  return (
    <Card className="p-5 md:p-6">
      {pending ? (
        <>
          <h2 className="flex items-center gap-2 text-2xl font-bold uppercase">
            <Loader2 className="size-5 animate-spin text-primary" /> Videos are being analyzed
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            One video at a time. The scores, rank and coach report appear here by themselves when all videos are done.
            You can leave this page.
          </p>
        </>
      ) : (
        <h2 className="text-2xl font-bold uppercase">Video analysis</h2>
      )}

      <div className="mt-4 space-y-3">
        {jobs.map((j) => (
          <div key={j.job_id}>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-semibold">{KIND_LABEL[j.kind]}</span>
              <span className="text-muted-foreground">
                {j.status === "done" ? "Done ✓" : j.status === "failed" ? "Failed" : `${j.step} · ${j.progress}%`}
              </span>
            </div>
            {j.status === "failed" ? (
              <p className="mt-1 flex items-start gap-2 text-sm text-weak">
                <XCircle className="mt-0.5 size-4 shrink-0" /> {j.error ?? "Analysis failed"} Upload this video again via Add Player.
              </p>
            ) : (
              <Progress value={j.status === "done" ? 100 : j.progress} className="mt-1 h-2" />
            )}
          </div>
        ))}
      </div>

      {doneButNoReport && canAnalyze && (
        <Button variant="hero" className="mt-5" disabled={analyze.isPending} onClick={() => analyze.mutate()}>
          {analyze.isPending ? "Creating report…" : "Analyze and create report"}
        </Button>
      )}
    </Card>
  );
}
