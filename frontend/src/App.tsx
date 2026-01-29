import { useEffect, useState } from "react";
import { request, authenticate, signOut } from "./api";
import type { Notice, Results, Watch } from "./types";

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
    request<Results>("/notices?" + new URLSearchParams({ q, country }))
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
        <button>Search</button>
      </form>
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
    </main>
  );
}
