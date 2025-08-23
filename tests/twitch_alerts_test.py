from __future__ import annotations

import json
import os
import tempfile
import time
from unittest.mock import patch

import vcr  # type: ignore

from twitch_alerts import __main__ as main


def filter_access_token(response):
    try:
        json_response = json.loads(response["body"]["string"])

    except json.JSONDecodeError:
        return response

    json_response["access_token"] = "mockToken"
    response["body"]["string"] = json.dumps(json_response)
    return response


recorder = vcr.VCR(
    cassette_library_dir="tests/cassettes",
    record_mode="once",
    filter_headers=[],
    filter_post_data_parameters=["client_id", "client_secret"],
    before_record_response=filter_access_token,
    match_on=["method", "url"],
)


def test_load_config() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = main.load_config()
        assert config.twitch_client_id == "Twitch Client ID here"
        assert config.twitch_client_secret == "PUT THIS IN THE .env FILE"
        assert config.discord_webhook_url == "PUT THIS IN THE .env FILE"
        assert config.twitch_channel_names == {"all", "the", "streamers"}


@recorder.use_cassette()
def test_get_bearer_token() -> None:
    client_id = os.getenv("TWITCH_ALERTS_CLIENT_ID", "mock")
    client_secret = os.getenv("TWITCH_ALERTS_CLIENT_ID", "mock")

    bearer = main.get_bearer_token(client_id, client_secret)

    assert bearer
    assert not bearer.expired


@recorder.use_cassette()
def test_get_bearer_token_failure() -> None:
    bearer = main.get_bearer_token("mock", "mock")

    assert bearer is None


@recorder.use_cassette()
def test_is_stream_live() -> None:
    client_id = os.getenv("TWITCH_ALERTS_CLIENT_ID", "mock")
    client_secret = os.getenv("TWITCH_ALERTS_CLIENT_ID", "mock")

    bearer = main.get_bearer_token(client_id, client_secret)

    assert bearer

    live_check_one = main._is_stream_live("skittishandbus", bearer)
    live_check_two = main._is_stream_live("djsinneki", bearer)
    live_check_three = main._is_stream_live("skitishandbus", bearer)

    assert live_check_one is False
    assert live_check_two is True
    assert live_check_three is False


def test_isolate_who_went_live_with_state() -> None:
    """
    Complex test.
    - Start with no state
    - Assert new stream is captured
    - Call again now with state
    - Assert new stream is captured
    """
    mock_auth = main.Auth("mock", int(time.time() + 600), "mock")
    channels = ["channel_one", "channel_two", "channel_three"]
    expected_no_state = {"channel_one", "channel_three"}
    expected_with_state = {"channel_two"}

    _, filename = tempfile.mkstemp()
    os.remove(filename)

    try:
        with patch.object(main, "_is_stream_live", side_effect=[True, False, True]):
            results_no_state = main.isolate_who_went_live(mock_auth, filename, channels)

        with patch.object(main, "_is_stream_live", side_effect=[True, True, True]):
            results_with_state = main.isolate_who_went_live(mock_auth, filename, channels)

        assert results_no_state == expected_no_state
        assert results_with_state == expected_with_state

    finally:

        os.remove(filename)


@recorder.use_cassette()
def test_send_discord_webhook_success_path(caplog) -> None:
    mock_url = "https://webhook.site/139c572d-b842-475e-92b9-5d792b688765"
    channels = ["channel_one", "channel_two"]
    caplog.set_level("INFO")

    main.send_discord_webhook(channels, mock_url)

    assert "Discord notification sent!" in caplog.text


@recorder.use_cassette()
def test_send_discord_webhook_failure_path(caplog) -> None:
    mock_url = "https://webhook.site/139c572d-b842-475e-92b9-5d792b688765"
    channels = ["channel_one", "channel_two"]
    caplog.set_level("ERROR")

    main.send_discord_webhook(channels, mock_url)

    assert "Failed to send discord notification: 403" in caplog.text


def test_send_discord_webhook_no_webhook(caplog) -> None:
    mock_url = ""
    channels = ["channel_one", "channel_two"]
    caplog.set_level("INFO")

    main.send_discord_webhook(channels, mock_url)

    assert "No Discord webhook given, skipping notification route." in caplog.text
