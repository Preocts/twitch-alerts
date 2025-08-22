"""Setup logging config"""

from __future__ import annotations

import logging
import logging.config

_HTTPX_LEVEL_MAP = {
    "DEBUG": "DEBUG",
    "INFO": "ERROR",
    "WARNING": "ERROR",
    "CRITICAL": "CRITICAL",
}


def init_logging(level: str = "INFO") -> None:
    """Configure logging."""
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": level,
            }
        },
        "formatters": {
            "default": {
                "format": "%(levelname)s [%(asctime)s] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "loggers": {
            "twitch-alerts": {
                "handlers": ["default"],
                "level": level,
            },
            "httpx": {
                "handlers": ["default"],
                "level": _HTTPX_LEVEL_MAP.get(level, "ERROR"),
            },
            "httpcore": {
                "handlers": ["default"],
                "level": _HTTPX_LEVEL_MAP.get(level, "ERROR"),
            },
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger."""
    return logging.getLogger(name)
