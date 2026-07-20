# syntax=docker/dockerfile:1
# Isolated, reproducible environment for Phage Annotator.
# Works identically on Linux and Windows (via Docker Desktop / WSL2) and does
# not touch anything on the host system outside the bind-mounted data folder.

FROM python:3.11-slim AS base

# System libraries required by PyQt5 (Qt "xcb" platform plugin) plus the
# "offscreen" plugin used for headless/CI runs. xvfb is included so the GUI
# can also run headless-with-a-virtual-display when no host X server is
# available (see docker-compose.yml).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libxkbcommon-x11-0 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-sync1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libdbus-1-3 \
        libfontconfig1 \
        libfreetype6 \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

# Fixed UID/GID (rather than an implicit default) so the ./data bind mount
# in docker-compose.yml lines up predictably with a typical Linux host user.
RUN useradd --create-home --shell /bin/bash --uid 1000 phage
WORKDIR /app

# Install Python dependencies in their own layer so source-only edits don't
# invalidate the (slow) dependency install during local rebuilds.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

# EXTRAS controls which optional dependency groups get installed, e.g.:
#   docker build --build-arg EXTRAS=dev,cache .   (tests / CI use)
#   docker build --build-arg EXTRAS=cache,ml .    (GUI + ONNX/torch inference)
ARG EXTRAS=cache
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e ".[${EXTRAS}]"

COPY project ./project
COPY external_plugins ./external_plugins
COPY scripts ./scripts
COPY tests ./tests

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN mkdir -p /data && chown -R phage:phage /app /data
USER phage
VOLUME ["/data"]
WORKDIR /data

ENTRYPOINT ["phage-annotator"]
