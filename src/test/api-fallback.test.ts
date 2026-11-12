import { afterEach, describe, expect, it, vi } from "vitest";

// Each test gets a fresh copy of the API module (its sample-data state is module-level).
async function freshApi() {
  vi.resetModules();
  return import("@/lib/api");
}

const down = () => vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
const up = (body: unknown) =>
  vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body } as unknown as Response);

afterEach(() => vi.unstubAllGlobals());

describe("server down, then back", () => {
  it("reads fall back to sample data, then switch back to the real API by themselves", async () => {
    const api = await freshApi();
    vi.stubGlobal("fetch", down());
    await api.getHealth();
    expect(api.isDemoMode()).toBe(true);

    vi.stubGlobal("fetch", up({ ok: true, demo_mode: false }));
    await api.getHealth();
    expect(api.isDemoMode()).toBe(false);
  });

  it("adding a player never 'succeeds' into sample data", async () => {
    const api = await freshApi();
    vi.stubGlobal("fetch", down());
    await expect(
      api.createPlayer({
        name: "Test", gender: "boy", birth_date: "2012-10-05", height_cm: 165, dominant_hand: "right",
        position: "guard", years_playing: 2, club: "KK Test", town: "Sarajevo",
      }),
    ).rejects.toThrow(api.NOT_CONNECTED);
  });

  it("analyze and job polling never fall back to sample data either", async () => {
    const api = await freshApi();
    vi.stubGlobal("fetch", down());
    await expect(api.analyzePlayer("p_001")).rejects.toThrow(api.NOT_CONNECTED);
    await expect(api.getJob("j_123")).rejects.toThrow(api.NOT_CONNECTED);
  });
});
