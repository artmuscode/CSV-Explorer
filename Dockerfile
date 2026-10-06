# syntax=docker/dockerfile:1

# --- Stage 1: build the Tailwind CSS bundle with the standalone CLI ---------
FROM debian:bookworm-slim AS css

ARG TARGETARCH
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY .tailwind-version ./
RUN case "$TARGETARCH" in \
        amd64) TW_ARCH=x64 ;; \
        arm64) TW_ARCH=arm64 ;; \
        *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && curl -fsSLo /usr/local/bin/tailwindcss \
        "https://github.com/tailwindlabs/tailwindcss/releases/download/$(cat .tailwind-version)/tailwindcss-linux-${TW_ARCH}" \
    && chmod +x /usr/local/bin/tailwindcss

COPY app/templates app/templates
COPY app/static app/static
RUN tailwindcss -i app/static/css/input.css -o app/static/css/app.css --minify


# --- Stage 2: runtime image ------------------------------------------------
FROM python:3.13-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first so this layer is cached until pyproject/uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY --from=css /build/app/static/css/app.css ./app/static/css/app.css

RUN useradd --system --uid 1000 --create-home app \
    && mkdir -p /app/data/csv \
    && chown -R app:app /app/data

USER app

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4)"]

# DuckDB takes an exclusive lock on its database file per process, so run
# exactly one worker and use threads for concurrency.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", \
     "--access-logfile", "-", "app:create_app()"]
