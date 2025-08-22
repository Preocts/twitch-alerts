from __future__ import annotations

import os
import json
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
def config() -> main.Config:
    return main.Config("https://example.com", frozenset())


def test_load_config() -> None:
    with patch.object(main, "CONFIG_FILE", "./tests/twitch-alert.toml"):
        result = main.load_config()

    assert result.discord_webhook_url == "https://example.com"
    assert result.twitch_channel_names == {"all", "the", "streamers"}


@recorder.use_cassette()
def test_get_bearer_token():
    bearer = main.get_bearer_token()

    assert bearer
    assert not bearer.expired


@recorder.use_cassette()
def test_get_bearer_token_failure():
    with patch.dict(os.environ, {"TWITCH_ALERT_CLIENT_ID": "MOCK"}):
        bearer = main.get_bearer_token()

    assert bearer is None
