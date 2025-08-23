[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org/downloads)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Nox](https://img.shields.io/badge/%F0%9F%A6%8A-Nox-D85E00.svg)](https://github.com/wntrblm/nox)

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Preocts/twitch-alerts/main.svg)](https://results.pre-commit.ci/latest/github/Preocts/twitch-alerts/main)
[![Python tests](https://github.com/Preocts/twitch-alerts/actions/workflows/python-tests.yml/badge.svg?branch=main)](https://github.com/Preocts/twitch-alerts/actions/workflows/python-tests.yml)

# twitch-alerts

Because I get tired of nonexistance alerts from TwitchTv.

- [Contributing Guide and Developer Setup Guide](./CONTRIBUTING.md)
- [License: MIT](./LICENSE)

---

## Install

1. Clone the repo down
2. If you have `uv`:
   1. `uv sync`
3. If you don't:
   1. Create a venv (or don't, I'm not your senior)
   2. `python -m pip install .`

## Setup

1. Rename `.env.sample` to `.env`
2. Open the `.env` file
3. Open the `twitch-alerts.toml` file

### Twitch

A TwitchTV application is required.

1. [Spin up an application on the twitch dev console](https://dev.twitch.tv/console)
2. The redirect url can be `http://localhost:3000`
3. Copy the `client_id` into the `twitch-alerts.toml`
4. Copy the `client_secret` into the `.env` file

### Discord

For discord notifications:

1. Select the desired channel and "Edit Channel"
2. In "Integrations" create a webhook
3. Copy the webhook URL into the `.env` file for `TWITCH_ALERT_DISCORD_WEBHOOK`

### PagerDuty

For PagerDuty notifications a standard CAF alert is sent at with INFO severity.
Any API v2 integration key will work (global or service-level).

1. Copy the integration key into the `.env` file for `TWITCH_ALERT_PAGERDUTY_KEY`

## Run

To run forever:

```console
twitch-alerts-scan
```

To run once:

```console
twitch-alerts-scan-once
```

---

Sparcely documented things:

- Alternate toml configuration files can be made. Pass the desired toml in as the first CLI arguement
- State between scans is kept in `temp_twitch-alerts-state.json`
  - Delete it whenever
  - It is not multi-process safe
