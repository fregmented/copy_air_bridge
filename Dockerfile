FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN uv sync --no-dev

EXPOSE 8080

CMD ["uv", "run", "copy-air-bridge"]
