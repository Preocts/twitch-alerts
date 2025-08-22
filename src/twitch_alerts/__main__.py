from __future__ import annotations

import dataclasses
import logging
import logging.config
import os
import time
import tomllib
from typing import Any

import dotenv
import httpx

CONFIG_FILE = "twitch-alert.toml"
SCAN_FREQUENCY_SECONDS = 300  # Five minutes

dotenv.load_dotenv()


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "http",
            "level": "INFO",
        }
    },
    "formatters": {
        "http": {
            "format": "%(levelname)s [%(asctime)s] - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "loggers": {
        "__main__": {
            "handlers": ["default"],
            "level": "INFO",
        },
        "httpx": {
            "handlers": ["default"],
            "level": "ERROR",
        },
        "httpcore": {
            "handlers": ["default"],
            "level": "ERROR",
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, slots=True)
class Config:
    discord_webhook_url: str
    twitch_channel_names: frozenset[str]


@dataclasses.dataclass(frozen=True, slots=True)
class Bearer:
    access_token: str
    expires_in: int
    token_type: str
    expires_at: int = 0

    @classmethod
    def parse_response(cls, response: dict[str, Any]) -> Bearer:
        expires_at = int(time.time() + response["expires_in"])
        return Bearer(**response, expires_at=expires_at)

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at

    @property
    def header(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Id": os.getenv("TWITCH_ALERT_CLIENT_ID", ""),
        }


def load_config() -> Config:
    """Load config toml from current working directory."""
    with open(CONFIG_FILE, "rb") as infile:
        raw_config = tomllib.load(infile)

    return Config(
        discord_webhook_url=raw_config["discord_webhook_url"],
        twitch_channel_names=frozenset(raw_config["twitch_channel_names"]),
    )


def get_bearer_token() -> Bearer | None:
    """Get Twitch API bearer via client credential grant flow."""
    logger.info("Getting bearer token...")

    url = "https://id.twitch.tv/oauth2/token"
    payload = {
        "client_id": os.getenv("TWITCH_ALERT_CLIENT_ID", "[clientId]"),
        "client_secret": os.getenv("TWITCH_ALERT_CLIENT_SECRET", "[clientSecret]"),
        "grant_type": "client_credentials",
    }

    response = httpx.post(url, data=payload, timeout=3)

    if not response.is_success:
        logger.critical("Failed to get bearer token: %s", response.text)
        return None

    logger.info("Bearer token response got.")

    return Bearer.parse_response(response.json())


def is_stream_live(channel_name: str, bearer: Bearer) -> bool:
    logger.info("Checking on: %s", channel_name)

    url = "https://api.twitch.tv/helix/streams"
    params = {"user_login": channel_name}

    response = httpx.get(url, params=params, timeout=3, headers=bearer.header)

    if not response.is_success:
        logger.error("Failed to check '%s' with error: %s", channel_name, response.text)
        return False

    if not response.json()["data"]:
        is_live = False
    else:
        is_live = response.json()["data"][0].get("type") == "live"

    logger.info("%s live check: %s", channel_name, is_live)

    return is_live


if __name__ == "__main__":
    bearer = get_bearer_token()
    assert bearer

    is_stream_live("skittishandbus", bearer)
    is_stream_live("djsinneki", bearer)
