# Canonical base image: Python 3.13 Slim Bookworm (Digest-pinned)
# Justification: Canonical Python base image provided for Edition 2 tasks requiring Python runtime, glibc, and terminal test runners.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

# Install agent runtime requirements (tmux, asciinema) and task test dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    asciinema \
    bash \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest==8.3.4

WORKDIR /app
