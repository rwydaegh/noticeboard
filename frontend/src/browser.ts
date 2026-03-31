import type {
  Comparison,
  Notice,
  Profile,
  Results,
  SavedSearch,
  Watch,
} from "./types";

export const browserUser = "__noticeboard_browser__";
export const browserStoreKey = "noticeboard-browser-v1";
type StoredWatch = { stage: string; note: string; notice: Notice };
type Store = {
  watches: Record<string, StoredWatch>;
  searches: SavedSearch[];
  profile: Profile;
};
type Network = <T>(
  path: string,
  method?: string,
  payload?: unknown,
) => Promise<T>;

function read(): Store {
  try {
    const raw = localStorage.getItem(browserStoreKey);
    if (!raw)
      return {
        watches: {},
        searches: [],
        profile: { description: "", countries: [], exclusions: [] },
      };
    const data = JSON.parse(raw);
    if (!data.watches || !Array.isArray(data.searches) || !data.profile)
      throw Error();
    return data;
  } catch {
    throw Error(
      "Browser storage is unavailable. Your saved data has not been changed.",
    );
  }
}
function write(state: Store) {
  try {
    localStorage.setItem(browserStoreKey, JSON.stringify(state));
  } catch {
    throw Error("Could not save in this browser. Check your storage settings.");
  }
}
export function changes(before: Notice, after: Notice): Comparison {
  const fields: Comparison["fields"] = [];
  for (const key of [
    "title",
    "description",
    "buyer",
    "country",
    "status",
    "deadline",
    "lots",
  ] as const) {
    if (JSON.stringify(before[key]) !== JSON.stringify(after[key]))
      fields.push({ field: key, before: before[key], after: after[key] });
  }
  return { before: before.publication_id, after: after.publication_id, fields };
}
export function browserRoute(path: string) {
  return (
    /^\/(watchlist|saved-searches|profile|recommendations)(\/|$)/.test(path) ||
    /^\/notices\/\d+\/ask$/.test(path)
  );
}
export async function browserRequest(
  path: string,
  method: string,
  payload: unknown,
  network: Network,
): Promise<unknown> {
  if (path === "/watchlist") {
    const state = read();
    const items: Watch[] = await Promise.all(
      Object.entries(state.watches).map(async ([id, w]) => {
        try {
          const current = await network<Notice>("/notices/" + id);
          return {
            opportunity: current,
            stage: w.stage,
            note: w.note,
            updated:
              current.checksum !== w.notice.checksum ||
              current.publication_id !== w.notice.publication_id,
            changes: changes(w.notice, current),
          };
        } catch {
          return {
            opportunity: w.notice,
            stage: w.stage,
            note: w.note,
            updated: false,
            unavailable: true,
          };
        }
      }),
    );
    return { items };
  }
  const watch = path.match(/^\/watchlist\/(\d+)$/);
  if (watch) {
    const notice =
      method === "DELETE"
        ? undefined
        : (payload as { notice?: Notice }).notice ||
          (await network<Notice>("/notices/" + watch[1]));
    const state = read();
    if (method === "DELETE") delete state.watches[watch[1]];
    else {
      const data = payload as { stage: string; note: string };
      state.watches[watch[1]] = {
        stage: data.stage,
        note: data.note,
        notice: notice!,
      };
    }
    write(state);
    return { saved: method !== "DELETE" };
  }
  const state = read();
  if (path === "/saved-searches") {
    if (method === "POST") {
      const entry = {
        ...(payload as Omit<SavedSearch, "id">),
        id: Math.max(Date.now(), ...state.searches.map((s) => s.id + 1)),
      };
      state.searches.push(entry);
      write(state);
      return entry;
    }
    return { items: state.searches };
  }
  const saved = path.match(/^\/saved-searches\/(\d+)$/);
  if (saved) {
    state.searches = state.searches.filter((s) => s.id !== Number(saved[1]));
    write(state);
    return { deleted: true };
  }
  if (path === "/profile") {
    if (method === "PUT") {
      state.profile = payload as Profile;
      write(state);
      return { saved: true };
    }
    return state.profile;
  }
  if (path === "/recommendations") {
    if (!state.profile.description.trim())
      return { items: [], total: 0, warnings: [] };
    const result = await network<Results>(
      "/notices?" +
        new URLSearchParams({
          q: state.profile.description.slice(0, 500),
          mode: "hybrid",
          limit: "100",
        }),
    );
    const items = result.items
      .filter(
        (n) =>
          (!state.profile.countries.length ||
            state.profile.countries.includes(n.country)) &&
          !state.profile.exclusions.some((e) =>
            (n.title + " " + n.description)
              .toLowerCase()
              .includes(e.toLowerCase()),
          ),
      )
      .slice(0, 30);
    return { ...result, items, total: items.length };
  }
  const ask = path.match(/^\/notices\/(\d+)\/ask$/);
  if (ask) {
    const question = payload as { question: string; use_model?: boolean };
    if (question.use_model) throw Error("Sign in to use AI.");
    const [notice, result] = await Promise.all([
      network<Notice>("/notices/" + ask[1]),
      network<{ excerpts: { text: string }[] }>(
        "/notices/" +
          ask[1] +
          "/matches?" +
          new URLSearchParams({ q: question.question }),
      ),
    ]);
    return {
      publication_id: notice.publication_id,
      mode: "source excerpts",
      claims: result.excerpts.map((e) => ({ answer: "", quote: e.text })),
      unknown: result.excerpts.length ? [] : ["No matching text."],
      rejected_quotes: 0,
    };
  }
  throw Error("Unknown browser action.");
}
export function download(filename: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function downloadCalendar(watches: Watch[]) {
  const events: string[] = [];
  for (const w of watches) {
    const response = await fetch(
      "/api/notices/" + w.opportunity.id + "/calendar.ics",
    );
    if (!response.ok) throw Error("Calendar download failed.");
    events.push(
      ...((await response.text()).match(/BEGIN:VEVENT[\s\S]*?END:VEVENT/g) ||
        []),
    );
  }
  download(
    "deadlines.ics",
    [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Noticeboard//Deadlines//EN",
      ...events,
      "END:VCALENDAR",
      "",
    ].join("\r\n"),
    "text/calendar",
  );
}
