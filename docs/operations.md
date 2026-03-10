# Running Noticeboard

Use Python 3.12.12 and Node 22.21.1. The dependency locks use releases available on 7 January 2026.

```sh
uv sync --locked
uv run python manage.py migrate
uv run python manage.py bootstrap
cd frontend
npm ci
npm run build
cd ..
uv run python manage.py collectstatic --noinput
uv run gunicorn noticeboard.wsgi:application --bind 127.0.0.1:8920
```

The default database is local SQLite. For PostgreSQL, start the database service in Compose and set `DATABASE_URL`. `OPENSEARCH_URL` enables the derived search index. The services bind to localhost. Keep runtime state and generated credentials out of Git.

Tests use a synthetic notice. It is not a published procurement opportunity. Import it with `uv run python manage.py import_xml tests/fixtures/synthetic-notice.xml`.
