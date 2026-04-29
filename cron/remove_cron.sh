#!/usr/bin/env bash
MARKER="# staj_duyuru_botu"
(crontab -l 2>/dev/null | grep -v "$MARKER") | crontab -
echo "Cron job removed."
