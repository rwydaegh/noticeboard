# Noticeboard

A local list of public contracts, with source records kept alongside the notices. The first job is to keep publications and procedures separate so importing an amendment does not lose the original.

```sh
uv sync --locked
uv run python manage.py check
```

Build the frontend with `VITE_STATIC_DEMO=1` and place an exported `snapshot.json` beside the page. The demo keeps saved work in this browser and searches the fixed collection.
