from __future__ import annotations

import os
import logging
import dataclasses
import tomllib
import time
from typing import Any

import httpx
import dotenv

CONFIG_FILE = "twitch-alert.toml"
SCAN_FREQUENCY_SECONDS = 300  # Five minutes

dotenv.load_dotenv()

logging.basicConfig(level="INFO")
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
