import { useRef, useState } from "react";
import { Download, Mail } from "lucide-react";
import { toast } from "sonner";
import type { PlayerSummary } from "@/lib/types";
import { SKILL_LABELS, topSkills } from "@/lib/scoring";
import { cap, fmt } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";

export function ContactDialog({ p }: { p: PlayerSummary }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline"><Mail /> Contact via club</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="text-2xl uppercase">Contact via club</DialogTitle>
          <DialogDescription>Protecting young players comes first.</DialogDescription>
        </DialogHeader>
        <p>
          Scouts contact <strong>{p.name}</strong> through <strong>{p.club || "their club"}</strong> or the parents — never directly.
        </p>
        <p className="text-sm text-muted-foreground">HoopScout does not store or show any phone numbers, emails or home addresses for players.</p>
      </DialogContent>
    </Dialog>
  );
}

export function PlayerCardDialog({ p }: { p: PlayerSummary }) {
  const ref = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const top = topSkills(p.fair_scores, 3);
  const ranked = p.status === "ranked";

  async function download() {
    if (!ref.current) return;
    setBusy(true);
    try {
      const { toPng } = await import("html-to-image");
      const url = await toPng(ref.current, { pixelRatio: 2, cacheBust: true });
      const a = document.createElement("a");
      a.href = url;
      a.download = `${p.name.replace(/\s+/g, "-").toLowerCase()}-hoopscout.png`;
      a.click();
    } catch {
      toast.error("Could not create the image");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">🃏 Player Card</Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="sr-only">Player card</DialogTitle>
          <DialogDescription className="sr-only">Shareable card without private data</DialogDescription>
        </DialogHeader>
        <div ref={ref} className="relative mx-auto aspect-[5/7] w-full overflow-hidden rounded-2xl bg-navy-deep p-5 text-foreground">
          <div className="absolute -right-16 -top-16 size-48 rounded-full bg-ball opacity-90" />
          <div className="relative flex h-full flex-col">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-display text-sm font-bold uppercase tracking-[0.25em] text-primary">HoopScout</p>
                <p className="mt-1 text-xs text-subtle">{p.rank_group} · {cap(p.position)}</p>
              </div>
              <div className="text-right">
                <p className="num text-6xl font-extrabold leading-none">{ranked ? fmt(p.fair_score) : "—"}</p>
                <p className="text-[10px] uppercase tracking-wider">Fair score</p>
              </div>
            </div>
            <div className="mt-auto">
              {p.hidden_gem && <p className="mb-1 text-sm font-bold text-primary">💎 Hidden gem</p>}
              <p className="font-display text-4xl font-extrabold uppercase leading-none">{p.name}</p>
              <p className="mt-1 text-sm text-subtle">{p.club || "—"} · {p.town || "—"}</p>
              <div className="mt-4 space-y-2">
                {top.map((s) => (
                  <div key={s.key} className="flex items-center gap-2 text-sm">
                    <span className="w-28 text-subtle">{SKILL_LABELS[s.key]}</span>
                    <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface"><span className="block h-full bg-primary" style={{ width: `${s.value}%` }} /></span>
                    <span className="num w-8 text-right font-bold">{fmt(s.value)}</span>
                  </div>
                ))}
              </div>
              <p className="mt-4 border-t border-line pt-3 text-[11px] italic text-subtle">Skill, not size.</p>
            </div>
          </div>
        </div>
        <Button variant="hero" onClick={download} disabled={busy}><Download /> {busy ? "Creating…" : "Download PNG"}</Button>
      </DialogContent>
    </Dialog>
  );
}
