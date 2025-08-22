from __future__ import annotations

from unittest.mock import patch

from twitch_alerts import __main__ as main

@pytest.fixture(autouse=True)
def mock_env() -> None:
    if "TWITCH_ALERT_RECORDING" not in os.environ:
        os.environ["TWITCH_ALERT_CLIENT_ID"] = "[clientId]"
        os.environ["TWITCH_ALERT_CLIENT_Secret"] = "[clientSecret]"


@pytest.fixture
def config() -> main.Config:
    return main.Config("mock", "mockery", "https://example.com", frozenset())


def test_load_config() -> None:
    with patch.object(main, "CONFIG_FILE", "./tests/twitch-alert.toml"):
        result = main.load_config()

    assert result.discord_webhook_url == "https://example.com"
    assert result.twitch_channel_names == {"all", "the", "streamers"}
