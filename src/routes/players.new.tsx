import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CheckCircle2, Lock, Upload, XCircle } from "lucide-react";
import { toast } from "sonner";
import { analyzePlayer, createPlayer, getJob, uploadVideo } from "@/lib/api";
import { ageGroupFor, ageMonthsFrom, birthQuarterOf, formatAge, formatBytes } from "@/lib/format";
import type { Gender, Hand, Job, PlayerInput, Position } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PageTitle } from "@/components/hoop/bits";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import { RequireCoachClub, NoAccess } from "@/components/hoop/Access";
import { canUploadVideos } from "@/lib/access";
import { useCoachClub, useRole } from "@/lib/storage";

export const Route = createFileRoute("/players/new")({
  head: () => ({
    meta: [
      { title: "Add a player — HoopScout" },
      { name: "description", content: "Enter a player's bio and upload shooting, dribbling and jump videos from your phone." },
      { property: "og:title", content: "Add a player — HoopScout" },
      { property: "og:description", content: "Three phone videos, one fair skill report." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: NewPlayerGate,
});

type Kind = Job["kind"];
type Slot = { file: File | null; uploadPct: number; job: Job | null; error: string | null; phase: "idle" | "uploading" | "processing" | "done" | "failed" };
const EMPTY_SLOT: Slot = { file: null, uploadPct: 0, job: null, error: null, phase: "idle" };
const KINDS: Kind[] = ["shooting", "dribbling", "jump"];

const SLOT_INFO: Record<Kind, { emoji: string; title: string; hint: string }> = {
  shooting: { emoji: "🎯", title: "Shooting", hint: "Side view, 6+ shots" },
  dribbling: { emoji: "⛹️", title: "Dribbling", hint: "Front view, 20–30 s" },
  jump: { emoji: "🦘", title: "Jump", hint: "Side view, 3 jumps" },
};

function checklist(kind: Kind, hand: Hand): string[] {
  const first =
    kind === "shooting"
      ? `Film from the player's ${hand} side`
      : kind === "dribbling"
        ? "Film from the front, phone on a tripod"
        : "Film from the side, phone on a tripod";
  return [first, "Whole body in frame, feet to raised hands", "Hold the phone in landscape (sideways)"];
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function NewPlayerGate() {
  const [role] = useRole();
  if (!canUploadVideos(role)) return <NoAccess title="Coaches only" text="Scouts can see every player, but only coaches can add kids and upload their videos." />;
  return (
    <RequireCoachClub>
      <NewPlayer />
    </RequireCoachClub>
  );
}

function NewPlayer() {
  const [coachClub] = useCoachClub();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "", gender: "boy" as Gender, birth_date: "", height_cm: "", weight_kg: "", sitting_height_cm: "",
    dominant_hand: "right" as Hand, position: "guard" as Position, years_playing: "", club: coachClub ?? "", town: "",
  });
  const [slots, setSlots] = useState<Record<Kind, Slot>>({ shooting: EMPTY_SLOT, dribbling: EMPTY_SLOT, jump: EMPTY_SLOT });
  const [playerId, setPlayerId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const patch = (k: Kind, s: Partial<Slot>) => setSlots((all) => ({ ...all, [k]: { ...all[k], ...s } }));

  const months = form.birth_date ? ageMonthsFrom(form.birth_date) : null;
  const group = ageGroupFor(months);
  const quarter = form.birth_date ? birthQuarterOf(form.birth_date) : null;

  const valid = form.name.trim() && form.birth_date && months !== null && Number(form.height_cm) > 0 && form.years_playing !== "" && form.club.trim() && form.town.trim();
  const allFiles = KINDS.every((k) => slots[k].file);

  async function runSlot(id: string, kind: Kind, file: File): Promise<boolean> {
    patch(kind, { phase: "uploading", uploadPct: 0, error: null, job: null });
    try {
      let job = await uploadVideo(id, kind, file, (pct) => patch(kind, { uploadPct: pct }));
      patch(kind, { phase: "processing", uploadPct: 100, job });
      while (job.status === "queued" || job.status === "running") {
        await sleep(2000);
        job = await getJob(job.job_id);
        patch(kind, { job });
      }
      if (job.status === "failed") {
        patch(kind, { phase: "failed", error: job.error ?? "Analysis failed" });
        return false;
      }
      patch(kind, { phase: "done" });
      return true;
    } catch (e) {
      patch(kind, { phase: "failed", error: (e as Error).message });
      return false;
    }
  }

  async function finish(id: string) {
    setStatus("Creating report…");
    const report = await analyzePlayer(id);
    await qc.invalidateQueries({ queryKey: ["players"] });
    qc.setQueryData(["player", id], report);
    toast.success("Report ready!");
    navigate({ to: "/players/$id", params: { id } });
  }

  async function submit() {
    if (!valid || !allFiles) return;
    setBusy(true);
    try {
      let id = playerId;
      if (!id) {
        setStatus("Saving player…");
        const input: PlayerInput = {
          name: form.name.trim(), gender: form.gender, birth_date: form.birth_date, height_cm: Number(form.height_cm),
          weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
          sitting_height_cm: form.sitting_height_cm ? Number(form.sitting_height_cm) : null,
          dominant_hand: form.dominant_hand, position: form.position, years_playing: Number(form.years_playing),
          club: form.club.trim(), town: form.town.trim(),
        };
        const p = await createPlayer(input);
        id = p.id;
        setPlayerId(id);
      }
      setStatus("Uploading and analyzing videos…");
      const todo = KINDS.filter((k) => slots[k].phase !== "done");
      const results = await Promise.all(todo.map((k) => runSlot(id!, k, slots[k].file!)));
      if (results.every(Boolean)) await finish(id);
      else {
        setStatus("");
        toast.error("A video could not be analyzed. Re-upload it and try again.");
      }
    } catch (e) {
      setStatus("");
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reupload(kind: Kind, file: File) {
    patch(kind, { file, phase: "idle", error: null, uploadPct: 0, job: null });
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageTitle title="Add a player" sub="Bio + three short phone videos. HoopScout does the measuring." />

      <Card className="p-5 md:p-6">
        <h2 className="text-2xl font-bold uppercase">Player bio</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field label="Name" className="sm:col-span-2"><Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="First and last name" autoComplete="off" /></Field>
          <Field label="Gender">
            <Seg value={form.gender} onChange={(v) => set("gender", v)} options={[["boy", "Boy"], ["girl", "Girl"]]} />
          </Field>
          <Field label="Birth date"><Input type="date" value={form.birth_date} onChange={(e) => set("birth_date", e.target.value)} /></Field>
          <Field label="Height (cm)"><Input type="number" inputMode="numeric" value={form.height_cm} onChange={(e) => set("height_cm", e.target.value)} /></Field>
          <Field label="Weight (kg)" priv="optional"><Input type="number" inputMode="decimal" value={form.weight_kg} onChange={(e) => set("weight_kg", e.target.value)} /></Field>
          <Field label="Sitting height (cm)" priv="optional · improves the maturity estimate" className="sm:col-span-2">
            <Input type="number" inputMode="numeric" value={form.sitting_height_cm} onChange={(e) => set("sitting_height_cm", e.target.value)} />
          </Field>
          <Field label="Dominant hand">
            <Seg value={form.dominant_hand} onChange={(v) => set("dominant_hand", v)} options={[["right", "Right"], ["left", "Left"]]} />
          </Field>
          <Field label="Position">
            <Select value={form.position} onValueChange={(v) => set("position", v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="guard">Guard</SelectItem>
                <SelectItem value="forward">Forward</SelectItem>
                <SelectItem value="center">Center</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Years playing"><Input type="number" inputMode="numeric" min={0} value={form.years_playing} onChange={(e) => set("years_playing", e.target.value)} /></Field>
          <Field label="Club"><Input value={form.club} readOnly disabled title="Players are added to your own club" /></Field>
          <Field label="Town" className="sm:col-span-2"><Input value={form.town} onChange={(e) => set("town", e.target.value)} /></Field>
        </div>
        <div className="mt-5 grid grid-cols-3 gap-2 rounded-xl bg-muted p-3 text-center">
          <Preview label="Age" value={formatAge(months)} />
          <Preview label="Age group" value={group ?? "—"} />
          <Preview label="Birth quarter" value={quarter ? `Q${quarter}` : "—"} />
        </div>
      </Card>

      <h2 className="mt-8 mb-3 text-3xl font-bold uppercase text-foreground">Videos</h2>
      <div className="space-y-4">
        {KINDS.map((k) => (
          <VideoSlot key={k} kind={k} slot={slots[k]} hand={form.dominant_hand} disabled={busy}
            onFile={(f) => (slots[k].phase === "failed" ? reupload(k, f) : patch(k, { file: f, phase: "idle", error: null, uploadPct: 0, job: null }))} />
        ))}
      </div>

      <div className="sticky bottom-0 -mx-4 mt-6 border-t border-line bg-navy-deep/95 p-4 backdrop-blur md:static md:mx-0 md:border-0 md:bg-transparent md:p-0">
        <Button variant="hero" size="xl" className="w-full" disabled={!valid || !allFiles || busy} onClick={submit}>
          {busy ? status || "Working…" : "Analyze and create report"}
        </Button>
        {(!valid || !allFiles) && !busy && (
          <p className="mt-2 text-center text-sm text-subtle">{!valid ? "Fill in the bio fields first." : "Add all 3 videos to continue."}</p>
        )}
      </div>
    </div>
  );
}

function Field({ label, priv, className, children }: { label: string; priv?: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label className="flex items-center gap-1.5">
        {label}
        {priv && <span className="flex items-center gap-1 text-xs font-normal text-muted-foreground"><Lock className="size-3" /> private, {priv}</span>}
      </Label>
      {children}
    </div>
  );
}

function Seg<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: [T, string][] }) {
  return (
    <div className="grid grid-cols-2 gap-1 rounded-md border border-input p-1">
      {options.map(([v, l]) => (
        <button key={v} type="button" onClick={() => onChange(v)} className={cn("rounded px-3 py-1.5 text-sm font-semibold transition-colors", value === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>
          {l}
        </button>
      ))}
    </div>
  );
}

function Preview({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="num text-2xl font-bold">{value}</p>
    </div>
  );
}

function VideoSlot({ kind, slot, hand, disabled, onFile }: { kind: Kind; slot: Slot; hand: Hand; disabled: boolean; onFile: (f: File) => void }) {
  const info = SLOT_INFO[kind];
  const inputId = `video-${kind}`;
  const failed = slot.phase === "failed";
  return (
    <Card className={cn("p-5", failed && "ring-2 ring-weak")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-2xl font-bold uppercase">{info.emoji} {info.title}</h3>
          <p className="text-sm text-muted-foreground">{info.hint}</p>
        </div>
        {slot.phase === "done" && <CheckCircle2 className="size-7 text-good" />}
        {failed && <XCircle className="size-7 text-weak" />}
      </div>
      <ul className="mt-3 space-y-1 text-sm">
        {checklist(kind, hand).map((c, i) => (
          <li key={i} className="flex gap-2"><span className="text-primary">✓</span> {i === 0 && kind === "shooting" ? <span>Film from the player's <strong>{hand}</strong> side</span> : c}</li>
        ))}
      </ul>
      <input
        id={inputId}
        type="file"
        accept="video/*"
        className="sr-only"
        disabled={disabled}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
      {slot.file && (
        <p className="mt-3 truncate text-sm"><span className="font-semibold">{slot.file.name}</span> <span className="text-muted-foreground">· {formatBytes(slot.file.size)}</span></p>
      )}
      {slot.phase === "uploading" && (
        <div className="mt-3"><p className="mb-1 text-xs text-muted-foreground">Uploading… {slot.uploadPct}%</p><Progress value={slot.uploadPct} /></div>
      )}
      {(slot.phase === "processing" || slot.phase === "done") && slot.job && (
        <div className="mt-3"><p className="mb-1 text-xs text-muted-foreground">{slot.job.step || "Processing"} · {slot.job.progress}%</p><Progress value={slot.job.progress} /></div>
      )}
      {failed && <p className="mt-3 rounded-md bg-weak/10 p-2 text-sm font-semibold text-weak">{slot.error}</p>}
      {slot.phase !== "done" && (
        <Button asChild variant={slot.file ? "outline" : "default"} className="mt-4 w-full" disabled={disabled}>
          <label htmlFor={inputId} className={cn(disabled && "pointer-events-none opacity-50")}>
            <Upload /> {failed ? "Re-upload" : slot.file ? "Choose a different video" : "Choose video"}
          </label>
        </Button>
      )}
    </Card>
  );
}
