from __future__ import annotations

import dataclasses
import os
import time
import tomllib

import dotenv
import httpx

from . import log

CONFIG_FILE = "twitch-alerts.toml"
SCAN_FREQUENCY_SECONDS = 300  # Five minutes

dotenv.load_dotenv()

log.init_logging(os.getenv("TWITCH_ALERTS_LOGGGING", "INFO"))
logger = log.get_logger("twitch-alerts")


@dataclasses.dataclass(frozen=True, slots=True)
class Config:
    twitch_client_id: str
    twitch_client_secret: str
    discord_webhook_url: str
    twitch_channel_names: frozenset[str]


@dataclasses.dataclass(frozen=True, slots=True)
class Auth:
    access_token: str
    expires_at: int
    client_id: str

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Id": self.client_id,
        }


def load_config(filename: str | None = None) -> Config:
    """Load config toml from current working directory."""
    with open(filename or CONFIG_FILE, "rb") as infile:
        raw_config = tomllib.load(infile)

    client_secret = os.getenv("TWITCH_ALERT_CLIENT_SECRET")
    discord_webhook = os.getenv("TWITCH_ALERT_DISCORD_WEBHOOK")

    return Config(
        twitch_client_id=raw_config["twitch_client_id"],
        twitch_client_secret=client_secret or raw_config["twitch_client_secret"],
        discord_webhook_url=discord_webhook or raw_config["discord_webhook_url"],
        twitch_channel_names=frozenset(raw_config["twitch_channel_names"]),
    )


def get_bearer_token(client_id: str, client_secret: str) -> Auth | None:
    """Get Twitch API bearer via client credential grant flow."""
    logger.info("Getting bearer token...")

    url = "https://id.twitch.tv/oauth2/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }

    response = httpx.post(url, data=payload, timeout=3)

    if not response.is_success:
        logger.critical("Failed to get bearer token: %s", response.text)
        return None

    logger.info("Bearer token response got.")

    access_token = response.json()["access_token"]
    expires_at = int(time.time() + response.json()["expires_in"])

    return Auth(access_token, expires_at, client_id)


def is_stream_live(channel_name: str, auth: Auth) -> bool:
    logger.info("Checking on: %s", channel_name)

    url = "https://api.twitch.tv/helix/streams"
    params = {"user_login": channel_name}

    response = httpx.get(url, params=params, timeout=3, headers=auth.headers)

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
    config = load_config("temp_config.toml")
    auth = get_bearer_token(config.twitch_client_id, config.twitch_client_secret)
    assert auth

    for channel_name in config.twitch_channel_names:
        is_stream_live(channel_name, auth)
