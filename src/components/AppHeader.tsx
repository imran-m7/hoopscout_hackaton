import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useSyncExternalStore } from "react";
import { Repeat } from "lucide-react";
import { demoServerSnapshot, getHealth, isDemoMode, subscribeDemo } from "@/lib/api";
import { useCoachClub, useRole } from "@/lib/storage";
import { Button } from "@/components/ui/button";

const NAV = {
  coach: [
    { to: "/players/new", label: "Add Player" },
    { to: "/board", label: "Talent Board" },
  ],
  scout: [
    { to: "/board", label: "Talent Board" },
    { to: "/shortlist", label: "Shortlist" },
    { to: "/compare", label: "Compare" },
    { to: "/bias", label: "Bias Check" },
  ],
} as const;

export function useDemoMode() {
  return useSyncExternalStore(subscribeDemo, isDemoMode, demoServerSnapshot);
}

export function AppHeader() {
  const [role, setRole] = useRole();
  const [club, setClub] = useCoachClub();
  const demo = useDemoMode();
  const navigate = useNavigate();

  useEffect(() => {
    getHealth().catch(() => undefined);
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-navy-deep/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link to="/" className="flex items-center gap-2">
          <span className="grid size-9 place-items-center rounded-full bg-ball text-lg shadow-glow">🏀</span>
          <span className="font-display text-2xl font-bold uppercase tracking-wide text-foreground">
            Hoop<span className="text-primary">Scout</span>
          </span>
        </Link>
        {demo && (
          <span className="rounded-full border border-ok/50 bg-ok/15 px-2.5 py-0.5 text-xs font-semibold text-ok" title="The API is unavailable — showing sample data">
            Demo mode · Sample data
          </span>
        )}
        <nav className="order-last -mx-1 flex w-full gap-1 overflow-x-auto md:order-none md:w-auto">
          {role &&
            NAV[role].map((n) => (
              <Link
                key={n.to}
                to={n.to}
                className="whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-semibold text-subtle transition-colors hover:text-foreground"
                activeProps={{ className: "bg-surface text-foreground" }}
              >
                {n.label}
              </Link>
            ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {role === "coach" && club && (
            <button onClick={() => setClub(null)} className="text-xs text-subtle hover:text-foreground" title="Change club">
              🏟 {club} · change
            </button>
          )}
          {role ? (
            <Button
              variant="navy"
              size="sm"
              onClick={() => {
                const next = role === "coach" ? "scout" : "coach";
                setRole(next);
                navigate({ to: next === "coach" ? "/players/new" : "/board" });
              }}
            >
              <Repeat /> {role === "coach" ? "🎥 Coach" : "🔎 Scout"} · switch
            </Button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
