import { beforeAll, describe, expect, it, vi } from "vitest";
import type { Notice } from "./types";

let api: typeof import("./api");
beforeAll(async () => {
  vi.stubGlobal("location", { search: "" });
  api = await import("./api");
});
function notice(
  id: number,
  title: string,
  description: string,
  published = "2026-09-28",
): Notice {
  return {
    id,
    title,
    description,
    published,
    publication_id: id + "-2026",
    buyer: "",
    country: "BEL",
    kind: "cn-standard",
    status: "deadline unverified",
    deadline: null,
    language: "eng",
    quality: "search",
    source_url: "https://ted.europa.eu/",
    cpv: [],
    changed: false,
    warnings: [],
  };
}
describe("Static collection search", () => {
  it("retains Unicode words", () => {
    expect(api.words("Développement systému")).toEqual([
      "développement",
      "systému",
    ]);
  });
  it("prefers title matches and excludes unrelated records", () => {
    const items = [
      notice(1, "Hardware", "cloud"),
      notice(2, "Cloud services", "hosting"),
      notice(3, "Paving", "road"),
    ];
    expect(api.rankNotices(items, "cloud").map((n) => n.id)).toEqual([2, 1]);
  });
  it("orders an empty search by publication date", () => {
    expect(
      api
        .rankNotices(
          [notice(1, "Old", "", "2026-01-01"), notice(2, "New", "")],
          "",
        )
        .map((n) => n.id),
    ).toEqual([2, 1]);
  });
  it("reports a failed logout rather than clearing the session locally", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({ json: async () => ({ csrfToken: "test" }) })
        .mockResolvedValueOnce({ ok: false }),
    );
    await expect(api.signOut()).rejects.toThrow("Sign out failed");
  });
});
