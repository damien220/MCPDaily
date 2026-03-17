# ══════════════════════════════════════════════════════════════════════════════
# LocalFileHandler — Multi-stage Dockerfile
#
# Build profiles (select via --build-arg PROFILE=<name>):
#   minimal   Core server only, no AI/STT  (~120 MB image)
#   full      Core + Anthropic AI + faster-whisper STT  (~1.2 GB image)
#   rpi       Core + vosk STT (lightest STT, ideal for Raspberry Pi)  (~280 MB)
#
# Multi-arch support:
#   docker buildx build --platform linux/amd64,linux/arm64 -t localfilehandler .
#
# Quick start (single arch):
#   docker build -t localfilehandler .
#   docker run -p 8080:8080 -v ./workspace:/app/workspace localfilehandler
# ══════════════════════════════════════════════════════════════════════════════

ARG PYTHON_VERSION=3.11
ARG PROFILE=minimal

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: builder — install Python deps into /install
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

ARG PROFILE

# System build deps (only needed during build)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY mcplearn_mcp-0.1.0-py3-none-any.whl ./

# Core requirements (always installed)
COPY requirements.txt ./
RUN pip install --upgrade pip --no-cache-dir \
 && pip install --prefix=/install --no-cache-dir \
        fastapi \
        "uvicorn[standard]" \
        pydantic \
        python-dotenv \
        tzdata \
        requests \
        "mcplearn_mcp @ file:mcplearn_mcp-0.1.0-py3-none-any.whl"

# Profile-specific extras
RUN if [ "$PROFILE" = "full" ]; then \
        pip install --prefix=/install --no-cache-dir \
            "anthropic>=0.40.0" \
            faster-whisper; \
    elif [ "$PROFILE" = "rpi" ]; then \
        pip install --prefix=/install --no-cache-dir \
            vosk; \
    fi


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: runtime — lean final image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG PROFILE
LABEL org.opencontainers.image.title="LocalFileHandler" \
      org.opencontainers.image.description="Self-hosted file management server with AI & voice control" \
      org.opencontainers.image.source="https://github.com/your-org/LocalFileHandler" \
      localfilehandler.profile="${PROFILE}"

# Runtime system libraries (vosk needs libgomp; faster-whisper needs libgomp too)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        # ffmpeg is needed by whisper for audio decoding
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash filebot
WORKDIR /app

# Copy application source (workspace is mounted as a volume)
COPY --chown=filebot:filebot . .

# Ensure workspace directory exists (will be overridden by volume mount)
RUN mkdir -p /app/workspace && chown filebot:filebot /app/workspace

USER filebot

# ── Environment defaults (override at runtime) ────────────────────────────
ENV SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8080 \
    WORKSPACE_PATH=/app/workspace \
    STT_BACKEND=none \
    AI_BACKEND=none \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Healthcheck — polls the /invoke endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c \
        "import urllib.request, json; \
         r=urllib.request.urlopen('http://localhost:8080/invoke', \
             data=json.dumps({'id':'hc','tool':'listcontentstool','payload':{'path':'.'}}).encode(), \
             timeout=8); \
         assert json.loads(r.read())['status']=='success'"

ENTRYPOINT ["python", "-m", "LocalFileHandler", "--mode", "web"]
