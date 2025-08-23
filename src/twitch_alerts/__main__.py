from __future__ import annotations

from twitch_alerts import _twitch_alerts


def run() -> None:
    try:
        _twitch_alerts.run()

    except KeyboardInterrupt:
        pass


def run_once() -> None:
    _twitch_alerts.run(loop_flag=False)


if __name__ == "__main__":
    run_once()
