FROM node:22.21.1-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.9.22 AS uv
FROM python:3.12.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY manage.py ./
COPY noticeboard/ noticeboard/
COPY procurement/ procurement/
COPY --from=frontend /web/dist frontend/dist/
RUN useradd --uid 1000 --create-home noticeboard && mkdir -p runtime staticfiles && chown -R noticeboard:noticeboard /app
USER noticeboard
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && exec gunicorn noticeboard.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 2 --timeout 600"]
