import { useEffect, useState } from "react";
import { request, authenticate, signOut } from "./api";
import type { Notice, Results, Watch, SavedSearch, Answer } from "./types";

export default function App() {
  const [q, setQ] = useState("");
  const [country, setCountry] = useState("");
  const [results, setResults] = useState<Results>({
    items: [],
    total: 0,
    backend: "",
    warnings: [],
  });
  const [error, setError] = useState("");
  function fail(e: unknown) {
    setError(e instanceof Error ? e.message : String(e));
  }
  function load() {
    request<Results>("/notices?" + new URLSearchParams({ q, country, mode }))
      .then(setResults)
      .catch(fail);
  }
  useEffect(load, []);
  const [selected, setSelected] = useState<Notice>();
  const [user, setUser] = useState<string | null>(null);
  const [watches, setWatches] = useState<Watch[]>([]);
  const [note, setNote] = useState("");
  function savedWork() {
    request<{ items: Watch[] }>("/watchlist")
      .then((r) => setWatches(r.items))
      .catch(fail);
  }
  useEffect(() => {
    request<{ user: string | null }>("/session")
      .then((s) => setUser(s.user))
      .catch(fail);
  }, []);
  useEffect(() => {
    if (user) savedWork();
  }, [user]);
  const [saved, setSaved] = useState<SavedSearch[]>([]);
  function savedQueries() {
    request<{ items: SavedSearch[] }>("/saved-searches")
      .then((r) => setSaved(r.items))
      .catch(fail);
  }
  useEffect(() => {
    if (user) savedQueries();
  }, [user]);
  const [mode, setMode] = useState("keyword");
  const [coverage, setCoverage] = useState<unknown>();
  const [profile, setProfile] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer>();
  const [activity, setActivity] = useState<unknown>();

  return (
    <main>
      <header>
        <h1>Noticeboard</h1>
        <p>Public contracts in a local collection.</p>
      </header>
      {error && <p role="alert">{error}</p>}
      {user ? (
        <p>
          {user}{" "}
          <button
            onClick={() =>
              signOut()
                .then(() => {
                  setUser(null);
                  setWatches([]);
                })
                .catch(fail)
            }
          >
            Sign out
          </button>
        </p>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            authenticate(String(f.get("username")), String(f.get("password")))
              .then(setUser)
              .catch(fail);
          }}
        >
          <label>
            Username <input name="username" />
          </label>
          <label>
            Password <input type="password" name="password" />
          </label>
          <button>Sign in</button>
        </form>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
      >
        <label>
          Search notices{" "}
          <input value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <label>
          Country{" "}
          <input
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            maxLength={3}
          />
        </label>
        <label>
          Search mode{" "}
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="keyword">Keyword</option>
            <option value="hybrid">Hybrid</option>
          </select>
        </label>
        <button>Search</button>
      </form>
      {user && (
        <section>
          <button
            onClick={() =>
              request("/saved-searches", "POST", {
                name: q || "All notices",
                query: q,
                country,
              })
                .then(savedQueries)
                .catch(fail)
            }
          >
            Save search
          </button>
          {saved.map((s) => (
            <p key={s.id}>
              <button
                onClick={() => {
                  setQ(s.query);
                  setCountry(s.country);
                  request<Results>(
                    "/notices?" +
                      new URLSearchParams({ q: s.query, country: s.country }),
                  )
                    .then(setResults)
                    .catch(fail);
                }}
              >
                {s.name}
              </button>
              <button
                onClick={() =>
                  request("/saved-searches/" + s.id, "DELETE")
                    .then(savedQueries)
                    .catch(fail)
                }
              >
                Delete
              </button>
            </p>
          ))}
        </section>
      )}
      <p>
        {results.total} results · {results.backend}
      </p>
      {results.warnings.map((w) => (
        <p key={w}>{w}</p>
      ))}
      <div className="columns">
        <section aria-label="Search results">
          {results.items.map((n) => (
            <article className="notice-row" key={n.id}>
              <button
                onClick={() =>
                  request<Notice>("/notices/" + n.id)
                    .then(setSelected)
                    .catch(fail)
                }
              >
                {n.title}
              </button>
              <h3>{n.buyer}</h3>
              <p>
                {n.country} · {n.status}
              </p>
            </article>
          ))}
        </section>
        {selected && (
          <aside>
            <button onClick={() => setSelected(undefined)}>Close detail</button>
            <h2>{selected.title}</h2>
            <p>{selected.publication_id}</p>
            <p>{selected.description}</p>
            <a href={selected.source_url}>Open source</a>
            {selected.warnings.map((w) => (
              <p key={w}>{w}</p>
            ))}
            {user && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  request("/watchlist/" + selected.id, "PUT", {
                    note,
                    stage: "saved",
                  })
                    .then(savedWork)
                    .catch(fail);
                }}
              >
                <label>
                  Review note{" "}
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                </label>
                <button>Save notice</button>
              </form>
            )}
            <h3>Publications</h3>
            {selected.versions?.map((v) => (
              <p key={v.publication_id}>
                {v.publication_id} · {v.published}
              </p>
            ))}
            {selected.comparison && (
              <pre>{JSON.stringify(selected.comparison.fields, null, 2)}</pre>
            )}
            <h3>Lots</h3>
            {selected.lots?.map((l) => (
              <section key={l.identifier}>
                <h4>{l.title}</h4>
                <p>{l.description}</p>
                <p>{l.deadline || "Exact deadline unknown"}</p>
              </section>
            ))}
            <p>
              <a href={"/api/notices/" + selected.id + "/calendar.ics"}>
                Calendar
              </a>
            </p>
            <button
              onClick={() =>
                request<{
                  items: Notice[];
                  warnings: string[];
                  backend: string;
                }>("/notices/" + selected.id + "/related")
                  .then((r) => setResults({ ...r, total: r.items.length }))
                  .catch(fail)
              }
            >
              Related notices
            </button>
            {user && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  request<Answer>("/notices/" + selected.id + "/ask", "POST", {
                    question,
                    use_model: false,
                  })
                    .then(setAnswer)
                    .catch(fail);
                }}
              >
                <label>
                  Find source passages{" "}
                  <input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                  />
                </label>
                <button>Ask</button>
              </form>
            )}
            {answer && (
              <section>
                <p>{answer.mode}</p>
                {answer.claims.map((c, i) => (
                  <blockquote key={i}>
                    {c.answer}
                    <p>{c.quote}</p>
                  </blockquote>
                ))}
              </section>
            )}
          </aside>
        )}
      </div>
      {user && (
        <section>
          <h2>Saved notices</h2>
          {watches.map((w) => (
            <article className="watch-entry" key={w.opportunity.id}>
              <h3>{w.opportunity.title}</h3>
              <p>{w.note}</p>
              {w.updated && <p>Updated since review</p>}
              <button
                onClick={() =>
                  request("/watchlist/" + w.opportunity.id, "DELETE")
                    .then(savedWork)
                    .catch(fail)
                }
              >
                Remove
              </button>
            </article>
          ))}
        </section>
      )}
      {user && (
        <p>
          <a href="/api/watch-calendar.ics">Saved deadlines</a> ·{" "}
          <a href="/api/review-export">Review export</a>
        </p>
      )}
      <a href={"/api/export.csv?" + new URLSearchParams({ q, country })}>
        Export results
      </a>
      {user && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            request("/profile", "PUT", {
              description: profile,
              countries: [],
              exclusions: [],
            })
              .then(() =>
                request<{
                  items: Notice[];
                  warnings: string[];
                  backend: string;
                }>("/recommendations"),
              )
              .then((r) => setResults({ ...r, total: r.items.length }))
              .catch(fail);
          }}
        >
          <label>
            Describe your work{" "}
            <textarea
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
            />
          </label>
          <button>Find matches</button>
        </form>
      )}
      <button
        onClick={() => request("/search-status").then(setCoverage).catch(fail)}
      >
        Check index coverage
      </button>
      {coverage !== undefined && <pre>{JSON.stringify(coverage, null, 2)}</pre>}
      <button onClick={() => request("/imports").then(setActivity).catch(fail)}>
        Activity
      </button>
      {activity !== undefined && <pre>{JSON.stringify(activity, null, 2)}</pre>}
    </main>
  );
}
