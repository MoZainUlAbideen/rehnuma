# Rehnuma API - built by Hugging Face Spaces (Docker SDK). Port 7860, non-root user 1000.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/app/.venv/bin:$PATH \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=7860
WORKDIR /home/user/app

# dependencies first (cached layer), then the code
COPY --chown=user pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --extra api --no-install-project
COPY --chown=user src ./src
# only what the server reads: sample bills (no PII - labels only) and the clause index
COPY --chown=user data/labels/real ./data/labels/real
COPY --chown=user data/policy/chunks.jsonl data/policy/sources.json ./data/policy/
RUN uv sync --frozen --no-dev --extra api

EXPOSE 7860
CMD ["rehnuma-api"]
