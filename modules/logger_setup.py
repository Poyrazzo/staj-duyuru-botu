"""Centralised logging configuration."""

import os
import logging
import logging.handlers
from datetime import datetime

import colorlog

import config


def setup_logging() -> None:
    os.makedirs(config.LOG_DIR, exist_ok=True)

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    # Console handler with colour
    console = colorlog.StreamHandler()
    console.setLevel(level)
    console.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG":    "cyan",
                "INFO":     "green",
                "WARNING":  "yellow",
                "ERROR":    "red",
                "CRITICAL": "bold_red",
            },
        )
    )

    # Rotating file handler
    log_file = os.path.join(
        config.LOG_DIR, f"bot_{datetime.now().strftime('%Y-%m')}.log"
    )
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)

    # Quiet noisy third-party loggers
    for noisy in (
        "httpx", "httpcore", "telegram", "playwright", "asyncio",
        "ddgs", "duckduckgo_search", "primp",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)
