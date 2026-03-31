import { beforeEach, expect, it, vi } from "vitest";
import { browserRequest, browserStoreKey } from "./browser";
import type { Notice, Watch } from "./types";
let saved = new Map<string, string>();
const original = {
  id: 3,
  publication_id: "3-2026",
  checksum: "old",
  title: "Software",
  description: "Python",
  country: "BEL",
  lots: [],
} as unknown as Notice;
beforeEach(() => {
  saved = new Map();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => saved.get(k) || null,
    setItem: (k: string, v: string) => saved.set(k, v),
  });
});
it("keeps the reviewed version and notes across reads, and detects an amendment", async () => {
  const net = vi
    .fn()
    .mockResolvedValue({
      ...original,
      checksum: "new",
      title: "Updated software",
    });
  await browserRequest(
    "/watchlist/3",
    "PUT",
    { stage: "reviewing", note: "Check budget", notice: original },
    net,
  );
  const result = (await browserRequest(
    "/watchlist",
    "GET",
    undefined,
    net,
  )) as { items: Watch[] };
  expect(result.items[0].note).toBe("Check budget");
  expect(result.items[0].updated).toBe(true);
  expect(result.items[0].changes?.fields).toContainEqual({
    field: "title",
    before: "Software",
    after: "Updated software",
  });
  expect(
    JSON.parse(saved.get(browserStoreKey)!).watches[3].notice.checksum,
  ).toBe("old");
  await browserRequest("/watchlist/3", "DELETE", undefined, net);
  expect(
    (
      (await browserRequest("/watchlist", "GET", undefined, net)) as {
        items: Watch[];
      }
    ).items,
  ).toEqual([]);
});
it("retains notes when the source is unavailable", async () => {
  const net = vi.fn().mockRejectedValue(Error("Offline"));
  await browserRequest(
    "/watchlist/3",
    "PUT",
    { stage: "saved", note: "Keep", notice: original },
    net,
  );
  const result = (await browserRequest(
    "/watchlist",
    "GET",
    undefined,
    net,
  )) as { items: Watch[] };
  expect(result.items[0]).toMatchObject({
    note: "Keep",
    unavailable: true,
    opportunity: original,
  });
});
it("reports blocked storage without claiming to save", async () => {
  vi.stubGlobal("localStorage", {
    getItem: () => null,
    setItem: () => {
      throw Error("Quota");
    },
  });
  await expect(
    browserRequest(
      "/watchlist/3",
      "PUT",
      { stage: "saved", note: "", notice: original },
      vi.fn(),
    ),
  ).rejects.toThrow("Could not save");
});
it("preserves corrupt storage instead of overwriting it", async () => {
  saved.set(browserStoreKey, "broken");
  await expect(browserRequest("/profile", "PUT", {}, vi.fn())).rejects.toThrow(
    "has not been changed",
  );
  expect(saved.get(browserStoreKey)).toBe("broken");
});
it("uses public hybrid search with local country and exclusion filters", async () => {
  const net = vi
    .fn()
    .mockResolvedValue({
      items: [
        original,
        { ...original, id: 4, country: "DEU" },
        { ...original, id: 5, title: "Construction" },
      ],
      warnings: [],
      backend: "hybrid",
    });
  await browserRequest(
    "/profile",
    "PUT",
    { description: "Python", countries: ["BEL"], exclusions: ["construction"] },
    net,
  );
  const result = (await browserRequest(
    "/recommendations",
    "GET",
    undefined,
    net,
  )) as { items: Notice[] };
  expect(result.items).toEqual([original]);
  expect(net).toHaveBeenCalledWith(expect.stringContaining("mode=hybrid"));
});
it("saves and deletes searches with their retrieval mode", async () => {
  const net = vi.fn();
  const entry = (await browserRequest(
    "/saved-searches",
    "POST",
    { name: "Python", query: "Python", mode: "hybrid" },
    net,
  )) as { id: number };
  expect(
    await browserRequest("/saved-searches", "GET", undefined, net),
  ).toMatchObject({ items: [{ mode: "hybrid" }] });
  await browserRequest("/saved-searches/" + entry.id, "DELETE", undefined, net);
  expect(
    await browserRequest("/saved-searches", "GET", undefined, net),
  ).toEqual({ items: [] });
  expect(net).not.toHaveBeenCalled();
});
