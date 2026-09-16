"""Logging configuration system for Telegram File Explorer."""

import logging
import re
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from .config import settings

_LOGGERS = {}

PHONE_REGEX = re.compile(r"\b(\+?[0-9]{1,3})[0-9]{4,8}([0-9]{2,4})\b")
HASH_REGEX = re.compile(r"\b([a-f0-9]{4})[a-f0-9]{24}([a-f0-9]{4})\b", re.IGNORECASE)
SECRET_KEYWORDS = re.compile(r"(password|api_hash|phone_code_hash|token|code)=([^\s,;]+)", re.IGNORECASE)


class SensitiveDataFormatter(logging.Formatter):
    """Custom log formatter redacting credentials, phone numbers, and secrets."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = SECRET_KEYWORDS.sub(r"\1=[REDACTED]", original)
        redacted = HASH_REGEX.sub(r"\1************************\2", redacted)
        redacted = PHONE_REGEX.sub(r"\1****\2", redacted)
        return redacted


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """Initialize root application logger with console and rotating file handlers."""
    log_level_str = level or settings.log_level
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    root_logger = logging.getLogger("telegram_explorer")
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is invoked more than once
    if root_logger.handlers:
        return root_logger

    log_format = SensitiveDataFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # File handler (rotating max 5MB, keeping 3 backups)
    try:
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = settings.logs_dir / "app.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
    except Exception as e:
        console_handler.stream.write(f"Failed to initialize file logger: {e}\n")

    # Mute overly verbose third-party loggers if needed
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger with hierarchical namespace."""
    if name not in _LOGGERS:
        _LOGGERS[name] = logging.getLogger(f"telegram_explorer.{name}")
    return _LOGGERS[name]
