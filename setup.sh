#!/usr/bin/env bash
# ============================================================
# Staj Duyuru Botu — One-shot setup script
# Run once after cloning:  bash setup.sh
# ============================================================
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
header()  { echo -e "\n${BOLD}$*${NC}"; }

# ── 1. Python version check ──────────────────────────────────
header "1. Checking Python version"
PYTHON=$(command -v python3.11 || command -v python3 || true)
[ -z "$PYTHON" ] && error "Python 3.11+ required but not found."
PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Found Python $PY_VER at $PYTHON"
[[ $(echo "$PY_VER >= 3.11" | bc -l) -eq 1 ]] || warn "Recommended Python 3.11+, found $PY_VER"

# ── 2. Virtual environment ───────────────────────────────────
header "2. Creating virtual environment"
if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
    info "Virtual environment created at .venv/"
else
    info "Virtual environment already exists."
fi

source .venv/bin/activate

# ── 3. Install dependencies ──────────────────────────────────
header "3. Installing Python dependencies"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
info "Python packages installed."

# ── 4. Install Playwright browsers ──────────────────────────
header "4. Installing Playwright Chromium"
playwright install chromium --with-deps
info "Playwright Chromium installed."

# ── 5. Create .env ───────────────────────────────────────────
header "5. Environment configuration"
if [ ! -f ".env" ]; then
    cp .env.example .env
    warn ".env created from template. EDIT IT NOW:"
    warn "  nano .env"
    warn "  → Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"
else
    info ".env already exists."
fi

# ── 6. Create data directory ─────────────────────────────────
mkdir -p data logs
info "data/ and logs/ directories ready."

# ── 7. Cron job setup (optional) ────────────────────────────
header "6. Cron job setup (optional)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_CMD="*/30 * * * * cd $SCRIPT_DIR && $SCRIPT_DIR/.venv/bin/python main.py >> $SCRIPT_DIR/logs/cron.log 2>&1"

echo ""
echo "To run the bot every 30 minutes via cron, add this line:"
echo ""
echo "  $CRON_CMD"
echo ""
echo "You can do it automatically by running:"
echo "  bash cron/install_cron.sh"
echo ""

# ── Done ─────────────────────────────────────────────────────
header "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your Telegram credentials"
echo "  2. Test a single run:    source .venv/bin/activate && python main.py"
echo "  3. Run continuously:     python main.py --loop"
echo "  4. Force health check:   python main.py --health"
echo ""
