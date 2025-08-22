from __future__ import annotations

from unittest.mock import patch

from twitch_alerts import __main__ as main


def test_load_config() -> None:
    with patch.object(main, "CONFIG_FILE", "./tests/twitch-alert.toml"):
        result = main.load_config()

    assert result.discord_webhook_url == "https://example.com"
    assert result.twitch_channel_names == {"all", "the", "streamers"}
