#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# LocalFileHandler — bare-metal install script
# Supports: Raspberry Pi OS (Bookworm/Bullseye), Debian 11/12, Ubuntu 22/24
#
# Usage:
#   sudo bash install.sh             # minimal install (no AI/STT)
#   sudo bash install.sh --profile rpi   # + Vosk STT  (Pi-friendly)
#   sudo bash install.sh --profile full  # + faster-whisper + anthropic
#
# What it does:
#   1. Installs system deps (python3, ffmpeg, etc.)
#   2. Creates 'filebot' system user
#   3. Copies app to /opt/localfilehandler
#   4. Creates Python venv + installs requirements
#   5. Creates workspace at /var/lib/localfilehandler/workspace
#   6. Installs and enables systemd service
#   7. Prints access URL
# ══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

### ── Config ─────────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/localfilehandler"
DATA_DIR="/var/lib/localfilehandler"
CONFIG_DIR="/etc/localfilehandler"
SERVICE_NAME="localfilehandler"
APP_USER="filebot"
APP_GROUP="filebot"
PROFILE="minimal"
PYTHON="python3"

### ── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile) PROFILE="$2"; shift 2 ;;
        --python)  PYTHON="$2";  shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

### ── Helpers ────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }

require_root() { [[ $EUID -eq 0 ]] || { echo "Run as root (sudo)"; exit 1; }; }
require_root

### ── 1. System dependencies ─────────────────────────────────────────────────
info "Installing system packages..."
apt-get update -q
PKGS="python3 python3-pip python3-venv ffmpeg libgomp1"
[[ "$PROFILE" == "rpi" ]] && PKGS="$PKGS libatlas-base-dev"
apt-get install -y --no-install-recommends $PKGS
apt-get clean

### ── 2. Create system user ──────────────────────────────────────────────────
info "Creating system user '$APP_USER'..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -m -d "$DATA_DIR" -s /bin/false "$APP_USER"
fi

### ── 3. Copy application ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
info "Installing app from $SCRIPT_DIR → $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
rsync -a --exclude='.venv' --exclude='workspace' --exclude='__pycache__' \
    --exclude='.git' --exclude='tests' \
    "$SCRIPT_DIR/" "$INSTALL_DIR/"
chown -R "$APP_USER:$APP_GROUP" "$INSTALL_DIR"

### ── 4. Python virtual environment ─────────────────────────────────────────
info "Creating Python venv ($PROFILE profile)..."
sudo -u "$APP_USER" "$PYTHON" -m venv "$INSTALL_DIR/.venv"
VENV_PIP="$INSTALL_DIR/.venv/bin/pip"

sudo -u "$APP_USER" "$VENV_PIP" install --upgrade pip --quiet
sudo -u "$APP_USER" "$VENV_PIP" install --quiet \
    fastapi "uvicorn[standard]" pydantic python-dotenv tzdata requests \
    "mcplearn_mcp @ file:$INSTALL_DIR/mcplearn_mcp-0.1.0-py3-none-any.whl"

if [[ "$PROFILE" == "full" ]]; then
    info "Installing full profile extras (anthropic + faster-whisper)..."
    sudo -u "$APP_USER" "$VENV_PIP" install --quiet "anthropic>=0.40.0" faster-whisper
elif [[ "$PROFILE" == "rpi" ]]; then
    info "Installing rpi profile extras (vosk)..."
    sudo -u "$APP_USER" "$VENV_PIP" install --quiet vosk
fi

### ── 5. Workspace & config directory ───────────────────────────────────────
info "Creating workspace and config directories..."
mkdir -p "$DATA_DIR/workspace"
chown -R "$APP_USER:$APP_GROUP" "$DATA_DIR"

mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_DIR/env" ]]; then
    cat > "$CONFIG_DIR/env" <<'EOF'
# LocalFileHandler environment configuration
# Edit and uncomment as needed, then: sudo systemctl restart localfilehandler

SERVER_HOST=0.0.0.0
SERVER_PORT=8080
WORKSPACE_PATH=/var/lib/localfilehandler/workspace

# Optional: basic auth (set both to enable)
#AUTH_USERNAME=admin
#AUTH_PASSWORD=changeme

# Optional: AI backend
#AI_BACKEND=anthropic
#ANTHROPIC_API_KEY=sk-ant-...
#AI_BACKEND=ollama
#OLLAMA_BASE_URL=http://localhost:11434

# Optional: STT backend
#STT_BACKEND=faster_whisper
#STT_MODEL=base
#STT_WAKE_WORD=hey filebot
#STT_BACKEND=vosk
#STT_MODEL=/var/lib/localfilehandler/vosk-model
EOF
    chown root:root "$CONFIG_DIR/env"
    chmod 640 "$CONFIG_DIR/env"
fi

### ── 6. systemd service ────────────────────────────────────────────────────
info "Installing systemd service..."
cp "$INSTALL_DIR/deploy/localfilehandler.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

### ── 7. Done ────────────────────────────────────────────────────────────────
IP=$(hostname -I | awk '{print $1}')
echo ""
info "LocalFileHandler installed successfully!"
echo "  Dashboard:  http://${IP}:8080"
echo "  Config:     $CONFIG_DIR/env"
echo "  Workspace:  $DATA_DIR/workspace"
echo "  Logs:       journalctl -u $SERVICE_NAME -f"
echo ""
warn "If you set AUTH_USERNAME/AUTH_PASSWORD in $CONFIG_DIR/env, restart with:"
echo "  sudo systemctl restart $SERVICE_NAME"
