from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
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


@pytest.fixture
def test_config() -> main.Config:
    """Load a test config without risk of actual values"""
    with patch.dict(os.environ, {}, clear=True):
        return main.load_config()


@pytest.fixture
def live_config() -> main.Config:
    """Load a test config with risk of actual values for recorded tests"""
    return main.load_config()


def test_load_config(test_config: main.Config) -> None:
    assert test_config.twitch_client_id == "Twitch Client ID here"
    assert test_config.twitch_client_secret == "PUT THIS IN THE .env FILE"
    assert test_config.discord_webhook_url == "PUT THIS IN THE .env FILE"
    assert test_config.twitch_channel_names == {"all", "the", "streamers"}


@recorder.use_cassette()
def test_get_bearer_token(live_config: main.Config) -> None:
    bearer = main.get_bearer_token(live_config)

    assert bearer
    assert not bearer.expired


@recorder.use_cassette()
def test_get_bearer_token_failure(test_config: main.Config) -> None:
    bearer = main.get_bearer_token(test_config)

    assert bearer is None


@recorder.use_cassette()
def test_is_stream_live(live_config: main.Config) -> None:

    bearer = main.get_bearer_token(live_config)

    assert bearer

    live_check_one = main.is_stream_live("skittishandbus", bearer)
    live_check_two = main.is_stream_live("djsinneki", bearer)
    live_check_three = main.is_stream_live("skitishandbus", bearer)

    assert live_check_one is False
    assert live_check_two is True
    assert live_check_three is False
