from __future__ import annotations

import dataclasses
import json
import logging
import os
import sys
import time
import tomllib

import requests

CONFIG_FILE = "twitch-alerts.toml"
STATE_FILE = "temp_twitch-alerts-state.json"
SCAN_FREQUENCY_SECONDS = 300  # Five minutes

logger = logging.getLogger("twitch-alerts")


@dataclasses.dataclass(frozen=True, slots=True)
class Config:
    twitch_client_id: str
    twitch_client_secret: str
    twitch_channel_names: frozenset[str]
    discord_webhook_url: str
    pagerduty_key: str


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


@dataclasses.dataclass(frozen=True, slots=True)
class Channel:
    name: str
    title: str
    game: str
    thumbnail_url: str
    type: str  # noqa: A003

    @property
    def url(self) -> str:
        return f"https://twitch.tv/{self.name}"

    @property
    def is_live(self) -> bool:
        return self.type == "live"


def load_config(filename: str | None = None) -> Config:
    """Load config toml from current working directory."""
    with open(filename or CONFIG_FILE, "rb") as infile:
        raw_config = tomllib.load(infile)

    client_secret = os.getenv("TWITCH_ALERT_CLIENT_SECRET")
    discord_webhook = os.getenv("TWITCH_ALERT_DISCORD_WEBHOOK")
    pagerduty_key = os.getenv("TWITCH_ALERT_PAGERDUTY_KEY")

    return Config(
        twitch_client_id=raw_config["twitch_client_id"],
        twitch_client_secret=client_secret or raw_config["twitch_client_secret"],
        twitch_channel_names=frozenset(raw_config["twitch_channel_names"]),
        discord_webhook_url=discord_webhook or "",
        pagerduty_key=pagerduty_key or "",
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

    response = requests.post(url, data=payload, timeout=3)

    if not response.ok:
        logger.critical("Failed to get bearer token: %s", response.text)
        return None

    logger.info("Bearer token response got.")

    access_token = response.json()["access_token"]
    expires_at = int(time.time() + response.json()["expires_in"])

    return Auth(access_token, expires_at, client_id)


def _get_channel(channel_name: str, auth: Auth) -> Channel:
    logger.info("Fetching: %s", channel_name)

    url = "https://api.twitch.tv/helix/streams"
    params = {"user_login": channel_name}

    response = requests.get(url, params=params, timeout=3, headers=auth.headers)

    if not response.ok:
        msg = f"Failed to fetch '{channel_name}' with error: {response.text}"
        logger.error("%s", msg)
        raise ValueError(msg)

    if not response.json()["data"]:
        msg = f"No data for '{channel_name}', must be off-line."
        logger.info(msg)
        raise KeyError(msg)

    channel = Channel(
        name=response.json()["data"][0]["user_login"],
        title=response.json()["data"][0]["title"],
        game=response.json()["data"][0]["game_name"],
        thumbnail_url=response.json()["data"][0]["thumbnail_url"],
        type=response.json()["data"][0]["type"],
    )

    logger.info("%s live check: %s", channel.name, channel.is_live)

    return channel


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
) -> list[Channel]:
    """Compare current state of Twitch with saved state, return newly live channel names."""
    previous_state = _load_state(state_file)
    current_state = {}

    live_channel_map: dict[str, Channel] = {}

    for channel_name in channels:
        try:
            channel = _get_channel(channel_name, auth)

        except (ValueError, KeyError):
            current_state[channel_name] = False
            continue

        current_state[channel_name] = channel.is_live
        if channel.is_live:
            live_channel_map[channel.name] = channel

    new_actives = _isolate_newly_active(previous_state, current_state)

    logger.info("Discovered %d newly live channels.", len(new_actives))

    _save_state(current_state, state_file)

    return [
        channel for channel_name, channel in live_channel_map.items() if channel_name in new_actives
    ]


def send_discord_webhook(channel_names: list[Channel], webhook_url: str) -> None:
    """Send notification webhook to Discord."""
    if not webhook_url:
        logger.info("No Discord webhook given, skipping notification route.")
        return None

    content_lines = []
    minutes = SCAN_FREQUENCY_SECONDS // 60
    for channel in channel_names:
        content_lines.append(
            f"The following stream has gone live within the last {minutes} minutes:\n"
            f"## [{channel.name}]({channel.url})\n\n"
        )

    webhook = {
        "username": "Twitch-Alerts",
        "embeds": [
            {
                "author": {
                    "name": "Twitch-Alerts",
                },
                "title": f"<t:{int(time.time())}:R>",
                "description": "".join(content_lines),
                "color": 0x9C5D7F,
            },
        ],
    }

    response = requests.post(webhook_url, json=webhook, timeout=3)

    if not response.ok:
        logger.error(
            "Failed to send discord notification: %d - %s",
            response.status_code,
            response.text,
        )

    else:

        logger.info("Discord notification sent!")


def send_pagerduty_alert(channel_names: list[Channel], integration_key: str) -> None:
    """Send alert to PagerDuty."""
    if not integration_key:
        logger.info("No PagerDuty key given, skipping notification route.")
        return None

    url = "https://events.pagerduty.com/v2/enqueue"
    channels = {channel: f"{channel.url}" for channel in channel_names}

    payload = {
        "routing_key": integration_key,
        "event_action": "trigger",
        "dedup_key": str(time.time()),
        "payload": {
            "summary": "New TwitchTV channel(s) detected as live.",
            "source": "Twitch-Alerts",
            "severity": "info",
            "custom_details": channels,
        },
    }

    response = requests.post(url, json=payload, timeout=3)

    if not response.ok:
        logger.error(
            "Failed to send PagerDuty notification: %d - %s",
            response.status_code,
            response.text,
        )

    else:

        logger.info("PagerDuty notification sent!")


def run(*, loop_flag: bool = True) -> None:
    """Run scans in a loop every SCAN_FREQUENCY_SECONDS, if loop_flag is false only run once."""
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        configfile = sys.argv[1]
    else:
        configfile = CONFIG_FILE

    config = load_config(configfile)
    auth: Auth | None = None

    next_scan_at = 0
    new_channels: list[Channel] = []

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
            new_channels.sort(key=lambda channel: channel.name)
            send_discord_webhook(new_channels, config.discord_webhook_url)
            send_pagerduty_alert(new_channels, config.pagerduty_key)

            new_channels.clear()

        if not loop_flag:
            break

        time.sleep(0.1)
