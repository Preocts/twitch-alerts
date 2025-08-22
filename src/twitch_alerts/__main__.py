from __future__ import annotations

import dataclasses
import tomllib

import httpx
import dotenv

CONFIG_FILE = "twitch-alert.toml"
SCAN_FREQUENCY_SECONDS = 300  # Five minutes

dotenv.load_dotenv()

@dataclasses.dataclass(frozen=True, slots=True)
class Config:
    discord_webhook_url: str
    twitch_channel_names: frozenset[str]


def load_config() -> Config:
    """Load config toml from current working directory."""
    with open(CONFIG_FILE, "rb") as infile:
        raw_config = tomllib.load(infile)

    return Config(
        discord_webhook_url=raw_config["discord_webhook_url"],
        twitch_channel_names=frozenset(raw_config["twitch_channel_names"]),
    )
