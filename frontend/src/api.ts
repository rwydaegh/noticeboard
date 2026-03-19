import type { Snapshot, Notice } from "./types";

export const demo =
  new URLSearchParams(location.search).has("snapshot") ||
  import.meta.env.VITE_STATIC_DEMO === "1";
let token = "";
let snapshotPromise: Promise<Snapshot> | undefined;
const storeKey = "noticeboard-snapshot-v1";
function local(): {
  watches: Record<string, { stage: string; note: string }>;
  searches: unknown[];
  profile: { description: string; countries: string[]; exclusions: string[] };
} {
  try {
    return (
      JSON.parse(localStorage.getItem(storeKey) || "null") || {
        watches: {},
        searches: [],
        profile: { description: "", countries: [], exclusions: [] },
      }
    );
  } catch {
    return {
      watches: {},
      searches: [],
      profile: { description: "", countries: [], exclusions: [] },
    };
  }
}
export function words(query: string) {
  return query.toLocaleLowerCase().match(/[\p{L}\p{N}]+/gu) || [];
}
export function rankNotices(items: Notice[], query: string) {
  const terms = words(query);
  return items
    .map((n) => {
      const title = n.title.toLocaleLowerCase(),
        body = (n.description + " " + n.buyer).toLocaleLowerCase();
      return {
        n,
        score: terms.reduce(
          (s, t) =>
            s + (title.includes(t) ? 3 : 0) + (body.includes(t) ? 1 : 0),
          0,
        ),
      };
    })
    .filter((r) => !terms.length || r.score > 0)
    .sort(
      (a, b) => b.score - a.score || b.n.published.localeCompare(a.n.published),
    )
    .map((r) => r.n);
}
async function snapshot() {
  snapshotPromise ||= fetch("./snapshot.json").then((r) => {
    if (!r.ok) throw Error("Sample collection could not be loaded.");
    return r.json();
  });
  return snapshotPromise;
}
async function localRequest(
  path: string,
  method: string,
  payload?: unknown,
): Promise<unknown> {
  const data = await snapshot(),
    u = new URL(path, "http://local"),
    p = u.pathname,
    state = local();
  const save = () => localStorage.setItem(storeKey, JSON.stringify(state));
  if (p === "/session") return { user: "this browser", llm_available: false };
  if (p === "/collection") return data.collection;
  if (p === "/imports") return { items: data.imports };
  if (p === "/notices") {
    let items = rankNotices(data.notices, u.searchParams.get("q") || "");
    const country = u.searchParams.get("country"),
      status = u.searchParams.get("status");
    if (country) items = items.filter((n) => n.country === country);
    if (status) items = items.filter((n) => n.status === status);
    const offset = Number(u.searchParams.get("offset") || 0),
      limit = Number(u.searchParams.get("limit") || 40);
    return {
      items: items.slice(offset, offset + limit),
      total: items.length,
      backend: "Snapshot text search",
      warnings: [],
    };
  }
  const match = p.match(/^\/notices\/(\d+)(\/ask)?$/);
  if (match) {
    const n = data.notices.find((n) => n.id === Number(match[1]));
    if (!n) throw Error("Notice not in this collection.");
    if (match[2])
      return {
        publication_id: n.publication_id,
        mode: "source excerpts",
        claims: [{ answer: "", quote: n.description.slice(0, 1800) }],
        unknown: ["Source text only."],
        rejected_quotes: 0,
      };
    return n;
  }
  if (p === "/watchlist")
    return {
      items: Object.entries(state.watches)
        .map(([id, w]) => ({
          opportunity: data.notices.find((n) => n.id === Number(id)),
          ...w,
          updated: false,
        }))
        .filter((w) => w.opportunity),
    };
  const watch = p.match(/^\/watchlist\/(\d+)$/);
  if (watch) {
    if (method === "DELETE") delete state.watches[watch[1]];
    else state.watches[watch[1]] = payload as { stage: string; note: string };
    save();
    return { saved: method !== "DELETE" };
  }
  if (p === "/saved-searches") {
    if (method === "POST") {
      const entry = { ...(payload as object), id: Date.now() };
      state.searches.push(entry);
      save();
      return entry;
    }
    return { items: state.searches };
  }
  const saved = p.match(/^\/saved-searches\/(\d+)$/);
  if (saved) {
    state.searches = state.searches.filter(
      (s) => (s as { id: number }).id !== Number(saved[1]),
    );
    save();
    return { deleted: true };
  }
  if (p === "/profile") {
    if (method === "PUT") {
      state.profile = payload as typeof state.profile;
      save();
      return { saved: true };
    }
    return state.profile;
  }
  if (p === "/recommendations") {
    let items = rankNotices(data.notices, state.profile.description);
    if (state.profile.countries.length)
      items = items.filter((n) => state.profile.countries.includes(n.country));
    items = items.filter(
      (n) =>
        !state.profile.exclusions.some((e) =>
          (n.title + " " + n.description)
            .toLowerCase()
            .includes(e.toLowerCase()),
        ),
    );
    return {
      items: state.profile.description ? items.slice(0, 30) : [],
      warnings: ["Text matches."],
      backend: "Snapshot text search",
    };
  }
  throw Error("Open the live app for this.");
}
export async function request<T>(
  path: string,
  method = "GET",
  payload?: unknown,
): Promise<T> {
  if (demo) return localRequest(path, method, payload) as Promise<T>;
  if (method !== "GET" && !token) {
    const r = await fetch("/auth/csrf");
    token = (await r.json()).csrfToken;
  }
  const response = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
  });
  if (!response.ok) {
    let msg = "Request failed.";
    try {
      const e = await response.json();
      msg = typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail);
    } catch {}
    if (response.status === 401) msg = "Sign in to save work.";
    throw Error(msg);
  }
  return response.json();
}
export async function authenticate(username: string, password: string) {
  const r = await fetch("/auth/csrf");
  token = (await r.json()).csrfToken;
  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: JSON.stringify({ username, password }),
  });
  const body = await res.json();
  if (!res.ok) throw Error(body.detail);
  token = body.csrfToken;
  return body.user as string;
}
export async function signOut() {
  const r = await fetch("/auth/csrf");
  token = (await r.json()).csrfToken;
  await fetch("/auth/logout", {
    method: "POST",
    headers: { "X-CSRFToken": token },
  });
  token = "";
}
