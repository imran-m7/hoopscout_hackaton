import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Lock } from "lucide-react";
import { getPlayers } from "@/lib/api";
import { useCoachClub, useRole, useStorageReady } from "@/lib/storage";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ClubPicker({ onDone }: { onDone?: () => void }) {
  const [club, setClub] = useCoachClub();
  const [value, setValue] = useState(club ?? "");
  const q = useQuery({ queryKey: ["players"], queryFn: getPlayers });
  const clubs = [...new Set((q.data ?? []).map((p) => p.club).filter(Boolean))].sort();
  return (
    <Card className="mx-auto max-w-md p-6">
      <h2 className="text-3xl font-bold uppercase">Your club</h2>
      <p className="mt-1 text-sm text-muted-foreground">Coaches only see the kids they train in their own club.</p>
      <div className="mt-4 grid gap-2">
        {clubs.map((c) => (
          <Button key={c} variant={value === c ? "hero" : "outline"} className="justify-start" onClick={() => setValue(c)}>{c}</Button>
        ))}
      </div>
      <Input className="mt-3" placeholder="Or type your club name" value={value} onChange={(e) => setValue(e.target.value)} />
      <Button variant="hero" className="mt-4 w-full" disabled={!value.trim()} onClick={() => { setClub(value); onDone?.(); }}>
        Continue
      </Button>
    </Card>
  );
}

/** For coaches: makes sure a club is chosen before showing club data. */
export function RequireCoachClub({ children }: { children: React.ReactNode }) {
  const [role] = useRole();
  const [club] = useCoachClub();
  const ready = useStorageReady();
  if (!ready) return null;
  if (role === "coach" && !club) return <ClubPicker />;
  return <>{children}</>;
}

export function NoAccess({ title, text }: { title: string; text: string }) {
  return (
    <Card className="mx-auto max-w-md p-8 text-center">
      <Lock className="mx-auto size-8 text-primary" />
      <h2 className="mt-3 text-3xl font-bold uppercase">{title}</h2>
      <p className="mt-2 text-muted-foreground">{text}</p>
      <Button asChild variant="hero" className="mt-5"><Link to="/board">Open Talent Board</Link></Button>
    </Card>
  );
}

export function ScoutOnly({ children }: { children: React.ReactNode }) {
  const [role] = useRole();
  const ready = useStorageReady();
  if (!ready) return null;
  if (role !== "scout") return <NoAccess title="Scouts only" text="This page is for scouts. Coaches can see the kids from their own club on the Talent Board." />;
  return <>{children}</>;
}
