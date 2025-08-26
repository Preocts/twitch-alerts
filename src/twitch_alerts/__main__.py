from __future__ import annotations

import logging

from eggviron import Eggviron
from eggviron import EnvironLoader
from eggviron import EnvFileLoader

from twitch_alerts import _twitch_alerts

_REQUIRED_ENVIRONS = {
    "TWITCH_ALERT_CLIENT_SECRET",
}


def runtime_init() -> None:
    """Setup required run-time environment and logging."""
    environ = Eggviron().load(EnvironLoader())
    missing_required_environ = bool(_REQUIRED_ENVIRONS - set(environ.loaded_values.keys()))

    try:
        environ.load(EnvFileLoader())

    except (FileNotFoundError, OSError):
        if missing_required_environ:
            print(
                "Could not load the expected '.env' file and required environment variables are not present:"
            )
            print("\n".join(sorted(_REQUIRED_ENVIRONS)))
            raise SystemExit(1)

    except KeyError as err:
        print("Runtime Error: Duplicate keys found in active environment and '.env' file.")
        print(err)
        raise SystemExit(1)

    logging.basicConfig(
        level=environ.get("TWITCH_ALERTS_LOGGING", "INFO"),
        format="%(levelname)s [%(asctime)s] - %(message)s",
    )


def run() -> int:
    runtime_init()
    try:
        _twitch_alerts.run()

    except KeyboardInterrupt:
        pass

    return 0


def run_once() -> int:
    runtime_init()
    _twitch_alerts.run(loop_flag=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_once())
