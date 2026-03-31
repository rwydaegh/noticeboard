# Running Noticeboard

The Compose configuration is for a local installation. PostgreSQL, OpenSearch and the application bind to loopback interfaces. OpenSearch security is disabled inside this local setup. Configure TLS, host names, secure cookies, private service networking and backups before exposing a full installation to other people.

## Local development

```sh
python3 scripts/configure.py
docker compose up -d postgres search
uv sync --locked --extra browser
uv run python manage.py migrate
uv run python manage.py bootstrap
cd frontend
npm ci
npm run build
cd ..
uv run python manage.py collectstatic --noinput
uv run gunicorn noticeboard.wsgi:application --bind 127.0.0.1:8920 --timeout 600
```

Configuration lives in `runtime/local.env`. Existing settings are preserved. `private/LOCAL_ACCESS.txt` contains the generated local account password. In the application container, that file is under `runtime/private/`. Keep both directories out of a public source export.

## Imports

```sh
uv run python manage.py sync_ted \
  'FT ~ "software" AND publication-date >= 20260901 SORT BY publication-date DESC' --limit 300
uv run playwright install chromium
uv run python manage.py enrich_ted --limit 60
uv run python manage.py index_notices --vectors
```

Enrichment fetches XML for metadata-only records. `--publication 666712-2026` targets an individual publication, including a historical one. Download failures are recorded. Retrying an import does not duplicate its notices. Previously downloaded XML can be loaded with `import_xml PATH`.

The Activity page shows import outcomes. `/api/search-status` reports index and vector counts. `/api/health` checks database access, and `/metrics` provides collection and import metrics. Equal index counts do not prove that every indexed document is current.

## Scheduled workflow

On Linux, Airflow runs as a seperate service using host networking to reach the local application. Run the local application first, then:

```sh
docker compose -f compose.airflow.yaml up -d
docker compose -f compose.airflow.yaml exec airflow airflow dags unpause ted_daily
docker compose -f compose.airflow.yaml exec airflow airflow dags trigger ted_daily
```

The weekday schedule is 07:30 UTC. Each run imports an overlapping seven-day window, capped at 500 records, then rebuilds vectors. A partial import fails its task and can be retried. The operator token is read from the private environment file. Airflow's local interface is at `http://localhost:8921`, and its generated credentials stay under `runtime/airflow/`.

## Optional assistance and MCP

Set `NOTICEBOARD_LLM_URL` to an OpenAI-compatible base URL, `NOTICEBOARD_LLM_MODEL` to the model name, and optionally `NOTICEBOARD_LLM_KEY`. Restart the application. Users must explicitly select model assistance. Source excerpts remain available without it. A remote provider receives the selected notice text and question.

For a local model server, use a CPU build of [llama.cpp](https://github.com/ggml-org/llama.cpp) or [Ollama](https://docs.ollama.com/docker). The development check used Qwen2.5 1.5B. Its limitations are recorded in the evaluation report.

The MCP server uses stdio and exposes four read-only tools: `search_notices`, `read_notice`, `find_evidence` and `collection_status`. It connects to the running HTTP application through `NOTICEBOARD_URL`. The static demo has no MCP endpoint.

An MCP client can start the read-only server with:

```json
{"mcpServers":{"noticeboard":{"command":"uv","args":["run","--directory","/path/to/noticeboard","python","-m","procurement.mcp_server"],"env":{"NOTICEBOARD_URL":"http://127.0.0.1:8920"}}}}
```

## Checks, backups and static export

```sh
uv run pytest -q
uv run ruff check .
uv run --extra browser python tests/browser_smoke.py
uv run python evaluation/run_retrieval.py
```

The browser check creates and removes its own test account. Back up PostgreSQL with `pg_dump` and retain the private configuration needed to restore the installation. Model caches and OpenSearch indices are derived data. Do not remove database volumes as routine cleanup.

`export_snapshot PATH` writes public notices and import summaries only. Build the frontend with `VITE_STATIC_DEMO=1` and place `snapshot.json` beside its `index.html`. The static demo searches the fixed collection and keeps saved work in browser storage. It does not expose a backend, account system or model endpoint.

## A persistent public installation

Compose services use `restart: unless-stopped`. Enable Docker at boot, keep the runtime volumes, and put only the application port behind an HTTPS reverse proxy. PostgreSQL, OpenSearch and Airflow stay on localhost.

Set `DJANGO_ALLOWED_HOSTS` to the public hostname, `CSRF_TRUSTED_ORIGINS` to its HTTPS origin and `HTTPS=1`. If a trusted local proxy supplies `X-Forwarded-Proto`, set `TRUST_HTTPS_PROXY=1`. Keep Gunicorn bound to localhost so clients cannot bypass that proxy.

For a PC behind a home router, a persistent Tailscale Funnel can forward HTTPS to port 8920. Authenticate the device, enable Funnel for it, then run `sudo tailscale funnel --bg http://127.0.0.1:8920`. Keep the device authentication valid and the Tailscale service enabled at boot. The application is available while the PC, internet connection and tunnel are running.

Use systemd for host-run application and model processes, with `Restart=on-failure` and startup enabled. User services also need lingering enabled if they must run before login. Back up PostgreSQL and the private runtime configuration separately from the source repository.

## Browser saves

Visitors save notices, review notes, searches and their matching profile in local storage. Clearing site data removes this work. The Saved page exports review records and deadlines. Signing in switches to account storage. Signing out restores browser saves. Neither action merges or deletes the other store.

Run `NOTICEBOARD_URL=http://127.0.0.1:8920 uv run --extra browser python tests/browser_guest.py` to check browser persistence, account isolation, downloads and the API documentation against a running installation.
