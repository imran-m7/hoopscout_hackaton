import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useRole, useStorageReady } from "@/lib/storage";
import { LoadingBlock } from "@/components/hoop/bits";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "HoopScout — find hidden basketball talent" },
      { name: "description", content: "Scouts pick the biggest and oldest kids. HoopScout measures skill, not size, from phone videos." },
      { property: "og:title", content: "HoopScout — find hidden basketball talent" },
      { property: "og:description", content: "A fair Talent Board that measures skill, not size." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  const [role] = useRole();
  const hydrated = useStorageReady();
  const navigate = useNavigate();
  useEffect(() => {
    if (!hydrated) return;
    navigate({ to: role === "coach" ? "/players/new" : role === "scout" ? "/board" : "/welcome", replace: true });
  }, [hydrated, role, navigate]);
  return <LoadingBlock label="Opening HoopScout…" />;
}
