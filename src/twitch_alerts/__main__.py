from __future__ import annotations

import dataclasses
import json
import os
import time
import tomllib
import sys

import dotenv
import httpx

from . import log

CONFIG_FILE = "twitch-alerts.toml"
STATE_FILE = "temp_twitch-alerts-state.json"
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


def _is_stream_live(channel_name: str, auth: Auth) -> bool:
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


def _load_state(state_file: str) -> dict[str, bool]:
    """Load state map of channel name to is_live status."""
    if not os.path.exists(state_file):
        logger.debug("State file '%s' does not exist.", state_file)
        return {}

    with open(state_file, "r") as infile:
        logger.debug("Loading '%s' state file.", state_file)
        return json.load(infile)


def _save_state(state: dict[str, bool], state_file: str) -> None:
    """Save state map of channel name to is_live status to file."""
    with open(state_file, "w") as outfile:
        logger.debug("Saving '%s' state file.", state_file)
        json.dump(state, outfile)


def _isolate_newly_active(
    previous_state: dict[str, bool],
    current_state: dict[str, bool],
) -> frozenset[str]:
    """Isolate the channel names that have gone live since last state check."""
    new_actives = set()
    for channel_name, state in current_state.items():
        if state and not previous_state.get(channel_name, False):
            new_actives.add(channel_name)

    return frozenset(new_actives)


def isolate_who_went_live(
    auth: Auth,
    state_file: str,
    channels: list[str],
) -> frozenset[str]:
    """Compare current state of Twitch with saved state, return newly live channel names."""
    previous_state = _load_state(state_file)
    current_state = {}

    for channel in channels:
        current_state[channel] = _is_stream_live(channel, auth)

    new_actives = _isolate_newly_active(previous_state, current_state)

    logger.info("Discovered %d newly live channels.", len(new_actives))

    _save_state(current_state, state_file)

    return new_actives


def send_discord_webhook(channel_names: list[str], webhook_url: str) -> None:
    """Send notification webhook to Discord."""
    if not webhook_url:
        logger.info("No Discord webhook given, skipping notification route.")
        return None

    streams = [f"## [{channel}](https://twitch.tv/{channel})" for channel in channel_names]

    content = "The following streams have been detected as live:\n\n"
    content += "\n".join(streams)

    webhook = {
        "username": "Twitch-Alerts",
        "embeds": [
            {
                "author": {
                    "name": "Twitch-Alerts",
                },
                "title": f"<t:{int(time.time())}:R>",
                "description": content,
                "color": 0x9C5D7F,
            },
        ],
    }

    response = httpx.post(webhook_url, json=webhook, timeout=3)

    if not response.is_success:
        logger.error(
            "Failed to send discord notification: %d - %s",
            response.status_code,
            response.text,
        )

    else:

        logger.info("Discord notification sent!")


def _run_once() -> None:
    _run(loop_flag=False)


def _run(*, loop_flag: bool = True) -> None:
    """Run scans in a loop every SCAN_FREQUENCY_SECONDS, if loop_flag is false only run once."""
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        configfile = sys.argv[1]
    else:
        configfile = CONFIG_FILE

    config = load_config(configfile)
    auth: Auth | None = None

    next_scan_at = 0
    new_channels: frozenset[str] = frozenset()

    while "Party rock is in the house tonight":

        if time.time() > next_scan_at:
            if auth is None or auth.expired:
                auth = get_bearer_token(config.twitch_client_id, config.twitch_client_secret)
                if auth is None:
                    logger.error("Error authenticating with TwitchTV.")
                    raise SystemExit()

            new_channels = isolate_who_went_live(
                auth=auth,
                state_file=STATE_FILE,
                channels=sorted(config.twitch_channel_names),
            )

            next_scan_at = int(time.time()) + SCAN_FREQUENCY_SECONDS

        if new_channels:
            send_discord_webhook(sorted(new_channels), config.discord_webhook_url)

            new_channels = frozenset()

        if not loop_flag:
            break


if __name__ == "__main__":
    _run_once()
