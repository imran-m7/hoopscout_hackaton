import type { PlayerSummary } from "./types";
import type { Role } from "./storage";

const norm = (s: string | null | undefined) => (s ?? "").trim().toLowerCase();

/** Scouts see everyone; coaches only see kids from their own club. */
export function canSeePlayer(role: Role | null, coachClub: string | null, p: Pick<PlayerSummary, "club">): boolean {
  if (role === "scout") return true;
  if (role === "coach") return !!norm(coachClub) && norm(p.club) === norm(coachClub);
  return false;
}

/** Only coaches can add players and upload videos. */
export const canUploadVideos = (role: Role | null) => role === "coach";
