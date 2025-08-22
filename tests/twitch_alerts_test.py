from __future__ import annotations

import json
import os
from unittest.mock import patch

import vcr  # type: ignore

from twitch_alerts import __main__ as main


def filter_access_token(response):
    json_response = json.loads(response["body"]["string"])
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

    live_check_one = main.is_stream_live("skittishandbus", bearer)
    live_check_two = main.is_stream_live("djsinneki", bearer)
    live_check_three = main.is_stream_live("skitishandbus", bearer)

    assert live_check_one is False
    assert live_check_two is True
    assert live_check_three is False
