import { describe, expect, it } from "vitest";
import { canSeePlayer, canUploadVideos } from "@/lib/access";

describe("role access", () => {
  it("scout sees players from every club", () => {
    expect(canSeePlayer("scout", null, { club: "MKS Tarnów" })).toBe(true);
  });
  it("coach sees only own club kids", () => {
    expect(canSeePlayer("coach", "KS Bochnia", { club: "KS Bochnia" })).toBe(true);
    expect(canSeePlayer("coach", "KS Bochnia", { club: "MKS Tarnów" })).toBe(false);
  });
  it("coach without a club sees nobody", () => {
    expect(canSeePlayer("coach", null, { club: "KS Bochnia" })).toBe(false);
  });
  it("only coaches can upload videos", () => {
    expect(canUploadVideos("coach")).toBe(true);
    expect(canUploadVideos("scout")).toBe(false);
  });
});
