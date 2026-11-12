import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { useRole, type Role } from "@/lib/storage";

export const Route = createFileRoute("/welcome")({
  head: () => ({
    meta: [
      { title: "Welcome — HoopScout" },
      { name: "description", content: "Choose your role: coach to add players and upload videos, or scout to find talent." },
      { property: "og:title", content: "Welcome — HoopScout" },
      { property: "og:description", content: "I'm a Coach or I'm a Scout — pick how you use HoopScout." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Welcome,
});

const CARDS: { role: Role; emoji: string; title: string; text: string; to: "/players/new" | "/board" }[] = [
  { role: "coach", emoji: "🎥", title: "I'm a Coach", text: "Add a player and upload three phone videos. Get an AI coach report in minutes.", to: "/players/new" },
  { role: "scout", emoji: "🔎", title: "I'm a Scout", text: "Search the fair Talent Board, spot hidden gems and build your shortlist.", to: "/board" },
];

function Welcome() {
  const [, setRole] = useRole();
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-5xl py-6 md:py-14">
      <p className="text-center text-sm font-semibold uppercase tracking-[0.3em] text-primary">HoopScout</p>
      <h1 className="mt-3 text-center text-5xl font-extrabold uppercase leading-[0.95] text-foreground md:text-7xl">
        Skill, <span className="text-primary">not size.</span>
      </h1>
      <p className="mx-auto mt-4 max-w-xl text-center text-lg text-subtle">
        Scouts pick the biggest and oldest kids. HoopScout measures skill, not size.
      </p>
      <div className="mt-12 grid gap-6 md:grid-cols-2">
        {CARDS.map((c) => (
          <button
            key={c.role}
            onClick={() => {
              setRole(c.role);
              navigate({ to: c.to });
            }}
            className="group rounded-2xl bg-card p-8 text-left text-card-foreground shadow-card transition-transform hover:-translate-y-1 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary md:p-10"
          >
            <div className="text-6xl">{c.emoji}</div>
            <h2 className="mt-5 text-4xl font-bold uppercase">{c.title}</h2>
            <p className="mt-2 text-muted-foreground">{c.text}</p>
            <span className="mt-6 inline-flex items-center gap-2 font-semibold text-primary">
              Continue <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
