#!/usr/bin/env bash
# Installs the cron job for the Staj Duyuru Botu.
# Safe to run multiple times — will not add duplicate entries.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"
LOG_FILE="$SCRIPT_DIR/logs/cron.log"

INTERVAL="${1:-180}"  # default: every 3 hours (override: bash install_cron.sh 60)

if (( INTERVAL >= 60 && INTERVAL % 60 == 0 )); then
  HOURS=$((INTERVAL / 60))
  SCHEDULE="0 */$HOURS * * *"
else
  SCHEDULE="*/$INTERVAL * * * *"
fi

CRON_ENTRY="$SCHEDULE cd $SCRIPT_DIR && $VENV_PYTHON $SCRIPT_DIR/main.py >> $LOG_FILE 2>&1"
MARKER="# staj_duyuru_botu"

# Remove any existing entry for this bot
(crontab -l 2>/dev/null | grep -v "$MARKER") | crontab - || true

# Add fresh entry
(crontab -l 2>/dev/null; echo "$CRON_ENTRY $MARKER") | crontab -

echo "Cron job installed: runs every $INTERVAL minutes ($SCHEDULE)."
echo "View with:  crontab -l"
echo "Remove with: bash cron/remove_cron.sh"
