FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install dependencies before copying source for better layer caching.
# This layer is only invalidated when pyproject.toml or uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Install the project itself
COPY src/ src/
RUN uv sync --frozen --no-dev

RUN useradd --system --no-create-home calmerge

ENV PATH="/app/.venv/bin:$PATH" \
    CALMERGE_CONFIG=/config/config.toml

USER calmerge

EXPOSE 8080

CMD ["gunicorn", \
     "--workers", "1", \
     "--bind", "0.0.0.0:8080", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "calmerge.app:create_app()"]
