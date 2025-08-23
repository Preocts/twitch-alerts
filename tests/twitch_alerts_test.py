from __future__ import annotations

import os
import tempfile
import time
from unittest.mock import patch
from typing import Any

import pytest
import responses
from responses import matchers

from twitch_alerts import __main__ as main


def make_twitch_streams_json(user_login: str, *, is_live: bool = True) -> dict[str, Any]:
    if user_login == "invalid":
        return {"error": "Bad Request", "status": 400, "message": "Malformed query params."}

    if not is_live:
        return {"data": [], "pagination": {}}

    return {
        "data": [
            {
                "id": "8675309",
                "user_id": "8675309",
                "user_login": user_login,
                "user_name": user_login,
                "game_id": "24241",
                "game_name": "FINALFANTASY XIV ONLINE",
                "type": "live",
                "title": f"Some Cool Title for {user_login}",
                "viewer_count": 69,
                "started_at": "2025-08-22T03:59:06Z",
                "language": "other",
                "thumbnail_url": f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{user_login}-{{width}}x{{height}}.jpg",
                "tag_ids": [],
                "tags": [],
                "is_mature": True,
            }
        ],
        "pagination": {
            "cursor": "eyJiIjp7IkN1cnNvciI6ImV5SnpJam94TnpVMU9ETTFNVFEyTGpJM09ETTBPVFlzSW1RaU9tWmhiSE5sTENKMElqcDBjblZsZlE9PSJ9LCJhIjp7IkN1cnNvciI6IiJ9fQ"
        },
    }


def test_load_config() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = main.load_config()
        assert config.twitch_client_id == "Twitch Client ID here"
        assert config.twitch_client_secret == "PUT THIS IN THE .env FILE"
        assert config.twitch_channel_names == {"all", "the", "streamers"}
        assert config.discord_webhook_url == ""
        assert config.pagerduty_key == ""


@responses.activate(assert_all_requests_are_fired=True)
def test_get_bearer_token() -> None:
    responses.add(
        method="POST",
        url="https://id.twitch.tv/oauth2/token",
        status=200,
        json={"access_token": "mockToken", "expires_in": 5222281, "token_type": "bearer"},
    )

    auth = main.get_bearer_token("mockId", "mockSecret")

    assert auth
    assert not auth.expired
    assert auth.access_token == "mockToken"
    assert auth.headers == {"Authorization": "Bearer mockToken", "Client-Id": "mockId"}


@responses.activate(assert_all_requests_are_fired=True)
def test_get_bearer_token_failure() -> None:
    responses.add(
        method="POST",
        url="https://id.twitch.tv/oauth2/token",
        status=400,
        json={"status": 400, "message": "invalid client"},
    )

    bearer = main.get_bearer_token("mock", "mock")

    assert bearer is None


@responses.activate(assert_all_requests_are_fired=True)
def test_isolate_who_went_live_with_state() -> None:
    """
    - Start with no state
    - Assert new stream is captured
    - Call again now with state
    - Assert new stream, previously false, is captured
    - Assert previously true streams are not captured
    """
    mock_token = "mockToken"
    mock_client_id = "mockClientId"
    mock_auth = main.Auth(mock_token, int(time.time() + 600), mock_client_id)
    channels = ["channel_one", "invalid", "channel_three", "channel_four"]
    expected_no_state = {"channel_one", "channel_three"}
    expected_with_state = {"channel_four"}

    stream_matrix = [
        # checked without a cache. Lives are expected to be captured
        ("channel_one", True),
        ("invalid", False),
        ("channel_three", True),
        ("channel_four", False),
        # checked with cache. Only channel_two is expected to be captured
        ("channel_one", True),
        ("invalid", False),
        ("channel_three", True),
        ("channel_four", True),
    ]
    matcher = matchers.header_matcher(
        {
            "Authorization": f"Bearer {mock_token}",
            "Client-Id": mock_client_id,
        }
    )

    for user_login, is_live in stream_matrix:
        responses.add(
            method="GET",
            url=f"https://api.twitch.tv/helix/streams?user_login={user_login}",
            status=200 if user_login != "invalid" else 400,
            json=make_twitch_streams_json(user_login, is_live=is_live),
            match=[matcher],
        )

    fd, filename = tempfile.mkstemp()
    os.close(fd)
    os.remove(filename)

    try:
        results_no_state = main.isolate_who_went_live(mock_auth, filename, channels)
        results_with_state = main.isolate_who_went_live(mock_auth, filename, channels)

        assert results_no_state == expected_no_state
        assert results_with_state == expected_with_state

    finally:

        os.remove(filename)


@responses.activate(assert_all_requests_are_fired=True)
def test_send_discord_webhook_success_path(caplog: pytest.LogCaptureFixture) -> None:
    mock_url = "https://totally.real.discord.webhook.site/124/358"
    channels = ["channel_one", "channel_two"]

    responses.add(method="POST", url=mock_url, status=200)

    with caplog.at_level("INFO"):
        main.send_discord_webhook(channels, mock_url)

    assert "Discord notification sent!" in caplog.text


@responses.activate(assert_all_requests_are_fired=True)
def test_send_discord_webhook_failure_path(caplog: pytest.LogCaptureFixture) -> None:
    mock_url = "https://totally.real.discord.webhook.site/124/358"
    channels = ["channel_one", "channel_two"]

    responses.add(method="POST", url=mock_url, status=404)

    with caplog.at_level("INFO"):
        main.send_discord_webhook(channels, mock_url)

    assert "Failed to send discord notification: 404" in caplog.text


def test_send_discord_webhook_no_webhook(caplog: pytest.LogCaptureFixture) -> None:
    mock_url = ""
    channels = ["channel_one", "channel_two"]

    with caplog.at_level("INFO"):
        main.send_discord_webhook(channels, mock_url)

    assert "No Discord webhook given, skipping notification route." in caplog.text
