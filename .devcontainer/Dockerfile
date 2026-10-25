# The benchmark's rerun environment (GitHub Codespaces / VS Code Dev Containers): Python 3.11 (pyproject pins
# >=3.11,<3.12), uv and ffmpeg. Node and the agent CLIs come from devcontainer.json.
FROM mcr.microsoft.com/devcontainers/python:3.2.6-3.11-bookworm

# uv, pinned, from its official image (https://docs.astral.sh/uv/guides/integration/docker/)
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
