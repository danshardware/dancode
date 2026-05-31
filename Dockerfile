FROM python:3.12-slim

# Install system tools needed by agents (git, ps/top, etc.)
# procps provides ps and top; the rest (grep, find, sed, awk, ls, etc.) are in the slim base
RUN apt-get update \
 && apt-get install -y --no-install-recommends git procps \
 && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies before copying app code so this layer is cached
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Create non-root user and hand ownership over to them.
# UID/GID 1000 matches the default on most Linux hosts, making bind-mount
# permissions work without extra configuration.
RUN groupadd --gid 1000 council \
 && useradd --uid 1000 --gid council council \
 && mkdir -p /home/council /app \
 && chown -R council:council /app /home/council

USER council

# Configure git identity for the council user (required for git commit inside the agent)
RUN git config --global user.name "Council Ops" \
 && git config --global user.email "ops@council.local"

# Copy application source
COPY --chown=council:council . .

# data/ and ~/.config/dancode are bind-mounted at runtime.
# init_data_dirs() creates any missing subdirectories on startup.
ENV PATH="/app/.venv/bin:$PATH"
CMD ["dancode", "/repo"]
