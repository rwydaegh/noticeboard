import { useEffect, useState } from "react";
import { request } from "./api";
import type { Notice, Results } from "./types";

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

  return (
    <main>
      <header>
        <h1>Noticeboard</h1>
        <p>Public contracts in a local collection.</p>
      </header>
      {error && <p role="alert">{error}</p>}
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
          </aside>
        )}
      </div>
    </main>
  );
}
