# LocalFileHandler

> Self-hosted, AI-powered file management server with voice control and IoT deployment.

LocalFileHandler is an MCP (Model-Context-Protocol) server that replaces manual file operations with intelligent, rule-enforced management. Every create / rename / move / delete goes through a smart middleware that applies naming conventions, auto-categorises files, and can be driven by plain-English commands or voice.

---

## Features

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Core file tools (create, rename, move, delete, list, search) | ✅ |
| 2 | Naming rules engine, bulk organise, undo, history | ✅ |
| 3 | Web dashboard (dark/light, drag-and-drop, real-time WS updates) | ✅ |
| 4 | AI-enhanced: NL commands, smart categorisation, duplicates, suggestions | ✅ |
| 5 | Offline voice control (push-to-talk, wake word, 4 STT backends) | ✅ |
| 6 | Docker / Raspberry Pi deployment, systemd service, watchdog, auth | ✅ |

---

## Screenshots

```
┌─────────────────────────────────────────────────────────────────────┐
│  📁 LocalFileHandler   workspace / documents      🌙  ⚙  👤 admin   │
├──────────────┬──────────────────────────────────────┬───────────────┤
│  📁 Folders  │  + File  + Folder  ⚡ Org  🤖 Ask AI 🎤 │  History     │
│              │─────────────────────────────────────│  ↳ + notes.md │
│  documents   │  📝 2026-03-17-meeting-notes.md      │  ↳ ⚡ Organise│
│  images      │  📄 2026-03-15-budget-q1.xlsx        │               │
│  code        │  🐍 2026-03-10-data-pipeline.py      │               │
│  archive     │  📦 2026-02-28-project-alpha.zip     │               │
└──────────────┴──────────────────────────────────────┴───────────────┘
```

---

## Quick Start

### Docker (recommended)

```bash
# Clone the repo
git clone https://github.com/your-org/LocalFileHandler
cd LocalFileHandler

# Start (minimal — no AI/STT)
docker compose up -d

# Open dashboard
open http://localhost:8080
```

### Python (local development)

```bash
# Create venv and install deps
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi "uvicorn[standard]" pydantic python-dotenv requests tzdata
pip install "mcplearn_mcp @ file:mcplearn_mcp-0.1.0-py3-none-any.whl"

# Run web server
python -m LocalFileHandler --mode web

# Open dashboard
open http://127.0.0.1:8080
```

### Raspberry Pi (bare-metal)

```bash
sudo bash deploy/install.sh --profile rpi
# Dashboard at http://<pi-ip>:8080
```

---

## Configuration

All settings are read from environment variables (or a `.env` file in the project root).

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_HOST` | `127.0.0.1` | Bind address (`0.0.0.0` for LAN access) |
| `SERVER_PORT` | `8080` | HTTP port |
| `WORKSPACE_PATH` | `./workspace` | Managed file directory |
| `AUTH_USERNAME` | _(none)_ | HTTP Basic Auth username (set both to enable) |
| `AUTH_PASSWORD` | _(none)_ | HTTP Basic Auth password |

### AI Backends (Phase 4)

| Variable | Values | Description |
|----------|--------|-------------|
| `AI_BACKEND` | `anthropic` \| `ollama` \| `llamacpp` \| `none` | LLM backend for NL commands & smart features |
| `ANTHROPIC_API_KEY` | `sk-ant-…` | Required for `anthropic` backend |
| `AI_MODEL` | `claude-haiku-4-5-20251001` | Model name (backend-specific) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `LLAMACPP_BASE_URL` | `http://localhost:8080` | llama.cpp server URL |

### STT Backends (Phase 5 — offline voice)

| Variable | Values | Description |
|----------|--------|-------------|
| `STT_BACKEND` | `faster_whisper` \| `whisper` \| `vosk` \| `whisper_cpp` \| `none` | Speech-to-text backend |
| `STT_MODEL` | `base` | Model name or path (see table below) |
| `STT_LANGUAGE` | `en` | ISO-639-1 language code |
| `STT_DEVICE` | `cpu` | `cpu` or `cuda` |
| `STT_WAKE_WORD` | `hey filebot` | Wake word prefix (empty to disable) |

#### STT Model Reference

| Backend | Install | Recommended model | Size | Notes |
|---------|---------|-------------------|------|-------|
| `faster_whisper` | `pip install faster-whisper` | `base` / `large-v3-turbo` | 74 MB – 809 MB | **Recommended** — 4× faster than openai-whisper |
| `whisper` | `pip install openai-whisper` | `base` / `small` | 74 MB – 244 MB | Original, GPU-friendly |
| `vosk` | `pip install vosk` | `vosk-model-small-en-us-0.15` | **40 MB** | **Lightest — ideal for Raspberry Pi** |
| `whisper_cpp` | Build from source | any `.ggml` model | varies | External HTTP server (`STT_BASE_URL`) |

---

## Tools (API)

All tools are called via `POST /invoke`:

```bash
curl -X POST http://localhost:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{"id":"1","tool":"<toolname>","payload":{...}}'
```

### File & Directory Tools

| Tool | Payload fields | Description |
|------|---------------|-------------|
| `createfiletool` | `name`, `type`, `content?` | Create a file with smart naming |
| `createdirtool` | `name` | Create a directory |
| `renametool` | `path`, `new_name` | Rename with rule enforcement |
| `movetool` | `source`, `destination` | Move file/directory |
| `deletetool` | `path`, `confirm` | Delete (trash-safe) |
| `listcontentstool` | `path`, `recursive?` | List directory contents |
| `searchtool` | `query`, `type?`, `path?` | Search by name/type/content |
| `organizetool` | `path`, `dry_run?` | Bulk-organise by naming rules |
| `infotool` | `path` | File metadata |
| `historytool` | `limit?` | Recent operations |
| `undotool` | `steps?` | Undo last N operations |
| `configtool` | `action`, `values?` | Read/write server config |
| `previewtool` | `name`, `type?` | Preview formatted name |

### AI Tools (requires AI backend)

| Tool | Payload fields | Description |
|------|---------------|-------------|
| `nlcommandtool` | `command` | Parse plain-English → `{tool, payload}` (parse-only, no auto-execute) |
| `smartcategorizetool` | `path`, `apply?` | LLM content categorisation + tagging |
| `suggestionstool` | `path?` | Workspace analysis + AI improvement suggestions |
| `duplicatestool` | `path?`, `mode?` | MD5 exact + Levenshtein near-duplicate detection |

### Voice Tools (requires STT backend)

| Tool | Payload fields | Description |
|------|---------------|-------------|
| `voicetool` | `audio` (base64 WAV), `sample_rate?` | Transcribe audio → text (strips wake word) |

### IoT / Watchdog Tools

| Tool | Payload fields | Description |
|------|---------------|-------------|
| `watchdogtool` | `action` (start/stop/status), `path?`, `dry_run?` | Monitor directory, auto-organise on file arrival |

---

## Web Dashboard

Access at `http://localhost:8080` after starting in `--mode web`.

| Control | Action |
|---------|--------|
| `+ File` / `+ Folder` | Create with smart naming |
| `⚡ Organize` | Bulk-apply naming rules to current folder |
| `☑ Select` | Multi-select mode (Ctrl+click on any card) |
| `🤖 Ask AI` | Open NL command panel — type a plain-English command |
| `🎤` (mic button) | Push-to-talk voice command |
| **Hold Space** | Push-to-talk (when not in a text field) |
| **Drag & drop** | Move files between folders |
| **Ctrl+K** | Open search overlay |
| **🌙 / ☀** | Toggle dark / light theme |

### NL Command Flow

```
Type: "Move all PDFs to the archive folder"
         ↓
   🤖 Ask AI panel sends → nlcommandtool
         ↓
   LLM resolves to: movetool {"source":"*.pdf","destination":"archive/"}
         ↓
   Panel shows: explanation + resolved command
         ↓
   Click ▶ Execute → file operation runs
```

### Voice Command Flow

```
Hold Space (or click 🎤) → speak → release
         ↓
   Browser sends base64 WAV → voicetool
         ↓
   STT transcribes → "hey filebot create a notes file"
         ↓
   Wake word stripped → "create a notes file"
         ↓
   Auto-fed into NL command panel → executes
```

---

## Docker Profiles

```bash
# Minimal (core only, ~120 MB image)
docker compose up -d

# Full (AI + faster-whisper STT, ~1.2 GB)
ANTHROPIC_API_KEY=sk-ant-... docker compose --profile full up -d

# Raspberry Pi (Vosk STT, ~280 MB)
docker compose --profile rpi up -d
```

Override workspace directory:

```bash
WORKSPACE_DIR=/mnt/nas/files docker compose up -d
```

Enable Basic Auth:

```bash
AUTH_USERNAME=admin AUTH_PASSWORD=secret docker compose up -d
```

---

## Raspberry Pi Deployment

### Docker on Pi

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Pull and run
docker compose --profile rpi up -d
```

### Bare-metal (Raspberry Pi OS / Debian)

```bash
# Minimal (no AI/STT)
sudo bash deploy/install.sh

# With Vosk STT (40 MB model)
sudo bash deploy/install.sh --profile rpi

# With full AI + faster-whisper
sudo bash deploy/install.sh --profile full
```

The installer:
1. Installs system packages (`python3`, `ffmpeg`, `libgomp1`)
2. Creates a `filebot` system user
3. Copies app to `/opt/localfilehandler`
4. Creates Python venv + installs dependencies
5. Writes config template to `/etc/localfilehandler/env`
6. Installs and enables the systemd service

**Service management:**

```bash
sudo systemctl status localfilehandler
sudo systemctl restart localfilehandler
journalctl -u localfilehandler -f          # live logs
```

**Edit config:**

```bash
sudo nano /etc/localfilehandler/env
sudo systemctl restart localfilehandler
```

---

## Watchdog — Auto-Organise Incoming Files

Start a background watcher on any directory. Files dropped in are automatically renamed and categorised by the naming rules engine.

```bash
# Start watching workspace/inbox (dry-run preview)
curl -X POST http://localhost:8080/invoke \
  -d '{"id":"1","tool":"watchdogtool","payload":{"action":"start","path":"inbox","dry_run":true}}'

# Start watching for real
curl -X POST http://localhost:8080/invoke \
  -d '{"id":"2","tool":"watchdogtool","payload":{"action":"start","path":"inbox"}}'

# Check status
curl -X POST http://localhost:8080/invoke \
  -d '{"id":"3","tool":"watchdogtool","payload":{"action":"status"}}'

# Stop
curl -X POST http://localhost:8080/invoke \
  -d '{"id":"4","tool":"watchdogtool","payload":{"action":"stop","path":"inbox"}}'
```

Uses `inotify` (Linux kernel events) when the `watchdog` library is installed, otherwise falls back to polling.

```bash
pip install watchdog    # optional: enables inotify backend
```

---

## Project Structure

```
LocalFileHandler/
├── main.py                    # Entry point + argument parser
├── config.py                  # All configuration (env vars → dataclasses)
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Multi-stage, multi-arch (amd64 + arm64)
├── docker-compose.yml         # Three profiles: minimal / full / rpi
├── .dockerignore
├── deploy/
│   ├── install.sh             # Bare-metal installer (Debian/Pi OS)
│   └── localfilehandler.service  # systemd unit file
├── ai/
│   └── client.py              # Unified LLM client (Anthropic / Ollama / llama.cpp)
├── stt/
│   └── client.py              # Unified STT client (Whisper / Vosk / whisper.cpp)
├── tools/                     # One file per MCP tool
│   ├── create_file.py
│   ├── create_dir.py
│   ├── rename.py / move.py / delete.py
│   ├── list_contents.py / search.py / info.py
│   ├── organize.py / history_tool.py / undo.py
│   ├── config_tool.py / preview.py
│   ├── nl_command.py          # Phase 4 — NL → tool call
│   ├── smart_categorize.py    # Phase 4 — LLM categorisation
│   ├── duplicates.py          # Phase 4 — duplicate detection
│   ├── suggestions.py         # Phase 4 — AI workspace suggestions
│   ├── voice.py               # Phase 5 — STT transcription
│   └── watchdog.py            # Phase 6 — directory watcher
├── naming/                    # Naming rules engine
│   ├── rules.py
│   ├── formatter.py
│   └── categories.py
├── web/
│   ├── server.py              # FastAPI + WebSocket + Basic Auth
│   └── static/
│       ├── index.html         # SPA shell
│       ├── style.css          # Dark/light themes
│       └── app.js             # Vanilla JS SPA (~1250 lines)
├── history/                   # Operation log + undo system
├── workspace/                 # Default managed workspace
└── docs/
    └── plan.md                # Full implementation plan
```

---

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Run in CLI mode (stdin/stdout JSON)
python -m LocalFileHandler --mode cli

# Run HTTP API only (no web UI)
python -m LocalFileHandler --mode http --port 9000

# Run full web dashboard
python -m LocalFileHandler --mode web --port 8080
```

### Adding a New Tool

1. Create `tools/my_tool.py` extending `BaseTool`
2. Set `name = "mytool"` and implement `handle(request) -> MCPResponse`
3. Add to `tools/__init__.py`
4. Register in `main.py` → `app.register_tool(MyTool(...))`

```python
from core.models import MCPRequest, MCPResponse
from core.tool_base import BaseTool

class MyTool(BaseTool):
    name = "mytool"
    description = "Does something useful."

    def handle(self, request: MCPRequest) -> MCPResponse:
        value = request.payload.get("input", "")
        return MCPResponse.success(request, {"result": value.upper()})
```

---

## License

MIT — see `LICENSE`.

---

## Roadmap

- [ ] Phase 7: Multi-workspace support
- [ ] Phase 7: Cloud sync (S3, Google Drive)
- [ ] Phase 7: Plugin system for custom tools
- [ ] Phase 7: Built-in file versioning
- [ ] Home Assistant integration
- [ ] MQTT support for IoT ecosystems
