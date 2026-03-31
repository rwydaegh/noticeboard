import { browserUser, download, downloadCalendar } from "./browser";
import { useEffect, useState } from "react";
import { authenticate, demo, request, signOut } from "./api";
import RelatedNotices from "./RelatedNotices";
import type {
  Answer,
  Collection,
  Notice,
  Profile,
  Results,
  SavedSearch,
  Watch,
} from "./types";

const label = (s: string) =>
  ({
    "deadline unverified": "Deadline unknown",
    pursue: "Interested",
    pass: "Skip",
    saved: "Saved",
    reviewing: "Reviewing",
  })[s] || s.replaceAll("_", " ");
const timestamp = (s: string) =>
  new Date(s).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
const date = (s: string | null) =>
  s
    ? new Date(s).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Unknown";
const statuses = [
  "open",
  "closed",
  "deadline unverified",
  "award",
  "direct award",
  "planning",
  "cancelled",
];
const initialParams = new URLSearchParams(location.search);

export default function App() {
  const [tab, setTab] = useState("Browse"),
    [user, setUser] = useState<string | null>(null),
    [login, setLogin] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [collection, setCollection] = useState<Collection>(),
    [q, setQ] = useState(initialParams.get("q") || ""),
    [country, setCountry] = useState(initialParams.get("country") || ""),
    [status, setStatus] = useState(initialParams.get("status") || ""),
    [mode, setMode] = useState(
      initialParams.get("mode") === "hybrid" ? "hybrid" : "keyword",
    ),
    [offset, setOffset] = useState(0),
    [revision, setRevision] = useState(0);
  const [results, setResults] = useState<Results>({
      items: [],
      total: 0,
      backend: "",
      warnings: [],
    }),
    [selected, setSelected] = useState<Notice>(),
    [watches, setWatches] = useState<Watch[]>([]),
    [saved, setSaved] = useState<SavedSearch[]>([]);
  const [matches, setMatches] = useState<Results>({
    items: [],
    total: 0,
    backend: "",
    warnings: [],
  });
  const [onlyChanged, setOnlyChanged] = useState(false);
  const [countriesText, setCountriesText] = useState(""),
    [exclusionsText, setExclusionsText] = useState("");
  const [profile, setProfile] = useState<Profile>({
      description: "",
      countries: [],
      exclusions: [],
    }),
    [answer, setAnswer] = useState<Answer>(),
    [llm, setLlm] = useState(false);
  const localUser = demo || user === browserUser;
  const [asking, setAsking] = useState<number | null>(null);
  function fail(e: unknown) {
    setError(e instanceof Error ? e.message : String(e));
  }
  async function action(fn: () => Promise<void>) {
    setError("");
    try {
      await fn();
    } catch (e) {
      fail(e);
    }
  }
  useEffect(() => {
    request<{ user: string | null; llm_available: boolean }>("/session")
      .then((s) => {
        setUser(s.user);
        setLlm(s.llm_available);
      })
      .catch(fail);
    request<Collection>("/collection").then(setCollection).catch(fail);
    const noticeId = initialParams.get("notice");
    if (noticeId && /^\d+$/.test(noticeId))
      request<Notice>("/notices/" + noticeId)
        .then(setSelected)
        .catch(fail);
  }, []);
  useEffect(() => {
    if (!login) return;
    const previous = document.activeElement as HTMLElement | null;
    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const controls = Array.from(
        document.querySelectorAll<HTMLElement>(
          ".login button, .login input, .login a[href]",
        ),
      );
      const first = controls[0],
        last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, [login]);
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    for (const [key, value] of Object.entries({
      q,
      country,
      status,
      mode,
      notice: selected ? String(selected.id) : "",
    })) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    history.replaceState(
      null,
      "",
      location.pathname + (params.size ? "?" + params : "") + location.hash,
    );
  }, [q, country, status, mode, selected]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelected(undefined);
        setLogin(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  useEffect(() => {
    if (!user) return;
    let active = true;
    request<{ items: Watch[] }>("/watchlist")
      .then((r) => {
        if (active) setWatches(r.items);
      })
      .catch(fail);
    request<{ items: SavedSearch[] }>("/saved-searches")
      .then((r) => {
        if (active) setSaved(r.items);
      })
      .catch(fail);
    request<Profile>("/profile")
      .then((p) => {
        if (!active) return;
        setProfile(p);
        setCountriesText(p.countries.join(", "));
        setExclusionsText(p.exclusions.join(", "));
      })
      .catch(fail);
    return () => {
      active = false;
    };
  }, [user, revision]);
  useEffect(() => {
    if (!localUser) return;
    const refresh = () => setRevision((r) => r + 1);
    window.addEventListener("storage", refresh);
    return () => window.removeEventListener("storage", refresh);
  }, [localUser]);
  useEffect(() => {
    let active = true;
    if (tab === "Browse") {
      setBusy(true);
      const params = new URLSearchParams({
        q,
        country,
        status,
        mode,
        offset: String(offset),
      });
      request<Results>("/notices?" + params)
        .then((r) => {
          if (active) setResults(r);
        })
        .catch((e) => {
          if (active) fail(e);
        })
        .finally(() => {
          if (active) setBusy(false);
        });
    }
    return () => {
      active = false;
    };
  }, [tab, q, country, status, mode, offset, revision]);
  async function open(n: Notice) {
    setSelected(n);
    setAnswer(undefined);
    await action(async () => {
      const detail = await request<Notice>("/notices/" + n.id);
      const watched = watches.find((w) => w.opportunity.id === n.id);
      if (watched?.updated && watched.changes)
        detail.comparison = watched.changes;
      setSelected((current) => (current?.id === n.id ? detail : current));
    });
  }
  async function watch(n: Notice, stage = "saved", note = "") {
    if (!user) {
      setLogin(true);
      return;
    }
    await action(async () => {
      await request("/watchlist/" + n.id, "PUT", {
        stage,
        note,
        ...(localUser ? { notice: n } : {}),
      });
      setRevision((r) => r + 1);
    });
  }
  function rows(items: Notice[]) {
    return items.length ? (
      items.map((n) => (
        <button
          className={"notice-row " + (selected?.id === n.id ? "selected" : "")}
          key={n.id}
          onClick={() => void open(n)}
        >
          <span className="row-main">
            <strong>{n.title}</strong>
            <span>{n.buyer || "Unknown buyer"}</span>
          </span>
          <span className="row-meta">
            <span>
              {n.country || "—"}, {date(n.published)}
            </span>
            <span className={"status " + (n.status === "open" ? "open" : "")}>
              {label(n.status)}
            </span>
          </span>
        </button>
      ))
    ) : (
      <p className="empty">No results.</p>
    );
  }
  const currentWatch = watches.find((w) => w.opportunity.id === selected?.id);
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header>
        <a className="wordmark" href="./">
          Noticeboard
        </a>
        <div className="account">
          {demo ? (
            <span>Demo. Saved in this browser.</span>
          ) : user && !localUser ? (
            <>
              <span>{user}</span>
              <button
                onClick={() =>
                  void action(async () => {
                    await signOut();
                    setUser(browserUser);
                    setLlm(false);
                    setMatches({
                      items: [],
                      total: 0,
                      backend: "",
                      warnings: [],
                    });
                    setWatches([]);
                    setSaved([]);
                    setSelected(undefined);
                    setAnswer(undefined);
                    setTab("Browse");
                  })
                }
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <span>Saved in this browser</span>
              <button onClick={() => setLogin(true)}>Sign in</button>
            </>
          )}
        </div>
      </header>
      <nav aria-label="Main">
        {["Browse", "Saved", "Matches"].map((t) => (
          <button
            key={t}
            aria-current={tab === t ? "page" : undefined}
            onClick={() => {
              setTab(t);
              setSelected(undefined);
            }}
          >
            {t}
            {t === "Saved" && watches.length > 0 ? (
              <span className="count">{watches.length}</span>
            ) : null}
          </button>
        ))}
      </nav>
      {error && !login && (
        <div role="alert" className="alert">
          {error}
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            ×
          </button>
        </div>
      )}
      <main id="main">
        <section className={selected ? "workspace split" : "workspace"}>
          <div className="listing">
            {tab === "Browse" && (
              <>
                <div className="section-head">
                  <div>
                    <h1>Find a contract</h1>
                    <p>
                      {collection
                        ? `${collection.opportunities.toLocaleString()} listings`
                        : "Loading…"}
                      {demo && collection
                        ? `. Updated ${date(collection.today)}`
                        : ""}
                    </p>
                  </div>
                  {!demo && (
                    <a
                      className="quiet"
                      href={
                        "/api/export.csv?" +
                        new URLSearchParams({ q, country, status, mode })
                      }
                    >
                      Export CSV
                    </a>
                  )}
                </div>
                <form
                  className="search"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    setQ(String(data.get("q") || ""));
                    setOffset(0);
                  }}
                >
                  <input
                    aria-label="Search notices"
                    name="q"
                    placeholder="Search notices"
                    defaultValue={q}
                    key={q}
                  />
                  <button className="primary">Search</button>
                </form>
                <div className="filters">
                  <label>
                    Country
                    <select
                      value={country}
                      onChange={(e) => {
                        setCountry(e.target.value);
                        setOffset(0);
                      }}
                    >
                      <option value="">All countries</option>
                      {collection?.countries.map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Status
                    <select
                      value={status}
                      onChange={(e) => {
                        setStatus(e.target.value);
                        setOffset(0);
                      }}
                    >
                      <option value="">All notices</option>
                      {statuses.map((s) => (
                        <option key={s} value={s}>
                          {label(s)}
                        </option>
                      ))}
                    </select>
                  </label>
                  {!demo && (
                    <label>
                      Search
                      <select
                        value={mode}
                        onChange={(e) => setMode(e.target.value)}
                      >
                        <option value="keyword">Keyword</option>
                        <option value="hybrid">Hybrid</option>
                      </select>
                    </label>
                  )}
                  <button
                    className="save-search"
                    onClick={() => {
                      if (!user) {
                        setLogin(true);
                        return;
                      }
                      void action(async () => {
                        await request("/saved-searches", "POST", {
                          name: q || country || "All notices",
                          query: q,
                          country,
                          status,
                          mode,
                        });
                        setRevision((r) => r + 1);
                      });
                    }}
                  >
                    Save search
                  </button>
                </div>
                {saved.length > 0 && (
                  <div className="saved-searches">
                    <span>Saved searches</span>
                    {saved.map((s) => (
                      <span className="saved-query" key={s.id}>
                        <button
                          onClick={() => {
                            setQ(s.query);
                            setCountry(s.country);
                            setStatus(s.status);
                            setMode(s.mode || "keyword");
                            setOffset(0);
                          }}
                        >
                          {s.name}
                        </button>
                        <button
                          aria-label={"Remove " + s.name}
                          onClick={() =>
                            void action(async () => {
                              await request(
                                "/saved-searches/" + s.id,
                                "DELETE",
                              );
                              setRevision((r) => r + 1);
                            })
                          }
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                <div className="result-summary" aria-live="polite">
                  {busy ? "Searching…" : `${results.total} results`}
                </div>
                {results.warnings.map((w) => (
                  <p className="caveat" key={w}>
                    {w}
                  </p>
                ))}
                <div aria-busy={busy}>{rows(results.items)}</div>
                <div className="pagination">
                  <button
                    disabled={!offset || busy}
                    onClick={() => setOffset(Math.max(0, offset - 40))}
                  >
                    Previous
                  </button>
                  <span>
                    {results.total
                      ? `${offset + 1}–${Math.min(offset + 40, results.total)}`
                      : "0"}
                  </span>
                  <button
                    disabled={offset + 40 >= results.total || busy}
                    onClick={() => setOffset(offset + 40)}
                  >
                    Next
                  </button>
                </div>
              </>
            )}
            {tab === "Saved" && (
              <>
                <h1>Saved</h1>
                {user && (
                  <div className="inline">
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={onlyChanged}
                        onChange={(e) => setOnlyChanged(e.target.checked)}
                      />
                      Updated ({watches.filter((w) => w.updated).length})
                    </label>
                    {!demo &&
                      (localUser ? (
                        <>
                          <button
                            onClick={() =>
                              void action(() => downloadCalendar(watches))
                            }
                          >
                            Calendar
                          </button>
                          <button
                            onClick={() =>
                              download(
                                "reviews.json",
                                JSON.stringify({ items: watches }, null, 2),
                                "application/json",
                              )
                            }
                          >
                            Export
                          </button>
                        </>
                      ) : (
                        <>
                          <a href="/api/watch-calendar.ics">Calendar</a>
                          <a href="/api/review-export">Export</a>
                        </>
                      ))}
                  </div>
                )}
                {!user ? (
                  <button onClick={() => setLogin(true)}>Sign in</button>
                ) : watches.length ? (
                  watches
                    .filter((w) => !onlyChanged || w.updated)
                    .map((w) => (
                      <div key={w.opportunity.id} className="watch-entry">
                        <div className="watch-state">
                          {label(w.stage)}
                          {w.unavailable ? (
                            <strong>Saved copy</strong>
                          ) : (
                            w.updated && <strong>Updated</strong>
                          )}
                        </div>
                        {rows([w.opportunity])}
                        {w.note && <p>{w.note}</p>}
                      </div>
                    ))
                ) : (
                  <p className="empty">No saved notices.</p>
                )}
              </>
            )}
            {tab === "Matches" && (
              <>
                <h1>Find matches with your work</h1>
                {!user ? (
                  <button onClick={() => setLogin(true)}>Sign in</button>
                ) : (
                  <form
                    className="profile"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void action(async () => {
                        const updated = {
                          ...profile,
                          countries: countriesText
                            .split(",")
                            .map((s) => s.trim().toUpperCase())
                            .filter(Boolean),
                          exclusions: exclusionsText
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean),
                        };
                        await request("/profile", "PUT", updated);
                        setProfile(updated);
                        const r = await request<Results>("/recommendations");
                        setMatches({ ...r, total: r.items.length });
                      });
                    }}
                  >
                    <label>
                      Your work
                      <textarea
                        rows={5}
                        value={profile.description}
                        onChange={(e) =>
                          setProfile({
                            ...profile,
                            description: e.target.value,
                          })
                        }
                        placeholder="Python, data platforms, scientific software"
                      />
                    </label>
                    <label>
                      Countries
                      <input
                        value={countriesText}
                        onChange={(e) => setCountriesText(e.target.value)}
                        placeholder="BEL, NLD, DEU"
                      />
                    </label>
                    <label>
                      Exclude
                      <input
                        value={exclusionsText}
                        onChange={(e) => setExclusionsText(e.target.value)}
                        placeholder="e.g. construction, catering"
                      />
                    </label>
                    <button className="primary">Find matches</button>
                  </form>
                )}
                {matches.warnings.map((w) => (
                  <p className="caveat" key={w}>
                    {w}
                  </p>
                ))}
                {user && rows(matches.items)}
              </>
            )}
          </div>
          {selected && (
            <aside className="detail" aria-label="Notice detail">
              <div className="detail-top">
                <span>
                  {selected.publication_id},{" "}
                  {selected.quality === "xml" ? "Full notice" : "Summary only"}
                </span>
                <button
                  onClick={() => {
                    setSelected(undefined);
                    setAnswer(undefined);
                  }}
                  aria-label="Close detail"
                >
                  ×
                </button>
              </div>
              <h2>{selected.title}</h2>
              <p>{selected.buyer}</p>
              <dl>
                <div>
                  <dt>Country</dt>
                  <dd>{selected.country || "Unknown"}</dd>
                </div>
                <div>
                  <dt>Published</dt>
                  <dd>{date(selected.published)}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{label(selected.status)}</dd>
                </div>
                <div>
                  <dt>Deadline</dt>
                  <dd>
                    {selected.deadline
                      ? timestamp(selected.deadline)
                      : "Unknown"}
                  </dd>
                </div>
              </dl>
              <div className="detail-actions">
                {!demo && selected.deadline && (
                  <a href={"/api/notices/" + selected.id + "/calendar.ics"}>
                    Calendar
                  </a>
                )}
                <a href={selected.source_url} target="_blank" rel="noreferrer">
                  TED ↗
                </a>
                <button
                  onClick={() =>
                    void watch(
                      selected,
                      currentWatch?.stage,
                      currentWatch?.note,
                    )
                  }
                >
                  {currentWatch ? "Mark reviewed" : "Save notice"}
                </button>
              </div>
              {currentWatch && (
                <form
                  className="review"
                  key={selected.id + currentWatch.stage + currentWatch.note}
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void watch(
                      selected,
                      String(f.get("stage")),
                      String(f.get("note")),
                    );
                  }}
                >
                  <label>
                    Stage
                    <select name="stage" defaultValue={currentWatch.stage}>
                      {["saved", "reviewing", "pursue", "pass"].map((s) => (
                        <option key={s} value={s}>
                          {label(s)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Notes
                    <textarea
                      name="note"
                      rows={3}
                      defaultValue={currentWatch.note}
                    />
                  </label>
                  <div className="inline">
                    <button>Save review</button>
                    <button
                      type="button"
                      onClick={() =>
                        void action(async () => {
                          await request("/watchlist/" + selected.id, "DELETE");
                          setRevision((r) => r + 1);
                        })
                      }
                    >
                      Remove
                    </button>
                  </div>
                </form>
              )}
              <h3>Description</h3>
              <p className="source-text">
                {selected.description || "No description."}
              </p>
              {selected.lots?.map((l) => (
                <section className="lot" key={l.identifier}>
                  <h3>
                    {l.identifier}, {l.title}
                  </h3>
                  {l.description !== selected.description && (
                    <p>{l.description}</p>
                  )}
                  <p>
                    Deadline: {l.deadline ? timestamp(l.deadline) : "Unknown"}
                  </p>
                  {l.value && (
                    <p>
                      Value: {l.value} {l.currency}
                    </p>
                  )}
                  {l.duration && (
                    <p>
                      Duration: {l.duration.value}{" "}
                      {(
                        {
                          MONTH: "months",
                          DAY: "days",
                          YEAR: "years",
                        } as Record<string, string>
                      )[l.duration.unit] || l.duration.unit}
                    </p>
                  )}
                  {l.requirements.map((r, i) => (
                    <p key={i}>{r}</p>
                  ))}
                  {l.documents.map((d, i) => (
                    <p key={d}>
                      <a href={d} target="_blank" rel="noreferrer">
                        Document {i + 1} ↗
                      </a>
                    </p>
                  ))}
                </section>
              ))}
              {selected.comparison && (
                <section>
                  <h3>Changes from {selected.comparison.before}</h3>
                  {selected.comparison.fields.length ? (
                    selected.comparison.fields.map((f, i) => (
                      <details key={i}>
                        <summary>{label(f.field)}</summary>
                        <div className="comparison">
                          <div>
                            <small>Before</small>
                            <pre>
                              {typeof f.before === "string"
                                ? f.before
                                : JSON.stringify(f.before, null, 2)}
                            </pre>
                          </div>
                          <div>
                            <small>After</small>
                            <pre>
                              {typeof f.after === "string"
                                ? f.after
                                : JSON.stringify(f.after, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </details>
                    ))
                  ) : (
                    <p>No changes found.</p>
                  )}
                </section>
              )}
              {selected.changes?.length ? (
                <section>
                  <h3>Amendments</h3>
                  {selected.changes.map((c, i) => (
                    <p key={i}>{c}</p>
                  ))}
                </section>
              ) : null}
              <section>
                <h3>History</h3>
                {selected.versions?.map((v) => (
                  <p key={v.publication_id}>
                    <a
                      href={
                        "https://ted.europa.eu/en/notice/-/detail/" +
                        v.publication_id
                      }
                      target="_blank"
                      rel="noreferrer"
                    >
                      {v.publication_id}
                    </a>
                    , {date(v.published)}
                  </p>
                ))}
              </section>
              <section>
                <h3>Ask a question</h3>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!user) {
                      setLogin(true);
                      return;
                    }
                    const f = new FormData(e.currentTarget);
                    void action(async () => {
                      setAsking(selected.id);
                      try {
                        setAnswer(
                          await request<Answer>(
                            "/notices/" + selected.id + "/ask",
                            "POST",
                            {
                              question: String(f.get("question")),
                              use_model: f.get("model") === "on",
                            },
                          ),
                        );
                      } finally {
                        setAsking((current) =>
                          current === selected.id ? null : current,
                        );
                      }
                    });
                  }}
                >
                  <label>
                    Question
                    <input
                      name="question"
                      required
                      minLength={3}
                      maxLength={500}
                      placeholder="What services are requested?"
                    />
                  </label>
                  {llm && (
                    <label className="checkbox">
                      <input type="checkbox" name="model" />
                      Use AI
                    </label>
                  )}
                  <button disabled={asking === selected.id}>
                    {asking === selected.id ? "Loading…" : "Ask"}
                  </button>
                </form>
                {answer &&
                  answer.publication_id === selected.publication_id && (
                    <div aria-live="polite">
                      <p className="muted">
                        {answer.mode === "source excerpts"
                          ? "Source text"
                          : "AI draft"}
                      </p>
                      {answer.claims.map((c, i) => (
                        <div key={i}>
                          {c.answer && <p>{c.answer}</p>}
                          <blockquote>{c.quote}</blockquote>
                        </div>
                      ))}
                      {answer.unknown.map((s, i) => (
                        <p className="caveat" key={i}>
                          {s}
                        </p>
                      ))}
                    </div>
                  )}
              </section>
              <RelatedNotices
                key={selected.id}
                notice={selected}
                onOpen={(n) => void open(n)}
              />
              {selected.checksum && (
                <details>
                  <summary>Source</summary>
                  {!demo && (
                    <p>
                      <a href={"/api/notices/" + selected.id + "/source"}>
                        Download
                      </a>
                    </p>
                  )}
                  <p>
                    Retrieved{" "}
                    {selected.retrieved_at
                      ? new Date(selected.retrieved_at).toLocaleString()
                      : ""}
                  </p>
                  <p className="hash">SHA-256 {selected.checksum}</p>
                </details>
              )}
            </aside>
          )}
        </section>
      </main>
      <footer>
        <a href="https://ted.europa.eu/">TED data</a>
        <a href="https://github.com/rwydaegh/noticeboard">GitHub</a>
        {!demo && <a href="/api/docs">API</a>}
      </footer>
      {login && (
        <div className="modal-backdrop" onClick={() => setLogin(false)}>
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="login-title"
            className="login"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="detail-top">
              <h2 id="login-title">Sign in</h2>
              <button
                aria-label="Close sign in"
                onClick={() => setLogin(false)}
              >
                ×
              </button>
            </div>

            {error && (
              <p role="alert" className="caveat">
                {error}
              </p>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                void action(async () => {
                  await authenticate(
                    String(f.get("username")),
                    String(f.get("password")),
                  );
                  const session = await request<{
                    user: string;
                    llm_available: boolean;
                  }>("/session");
                  setWatches([]);
                  setSaved([]);
                  setMatches({
                    items: [],
                    total: 0,
                    backend: "",
                    warnings: [],
                  });
                  setUser(session.user);
                  setLlm(session.llm_available);
                  setLogin(false);
                });
              }}
            >
              <label>
                Username
                <input
                  autoFocus
                  name="username"
                  autoComplete="username"
                  required
                />
              </label>
              <label>
                Password
                <input
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                />
              </label>
              <button className="primary">Sign in</button>
            </form>
          </section>
        </div>
      )}
    </>
  );
}
