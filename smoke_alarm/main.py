"""Main entry-point for the SmokeAlarm daemon.

Run with::

    python -m smoke_alarm

or::

    python smoke_alarm/main.py
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from collections import deque

from smoke_alarm import config
from smoke_alarm.alarm import CountermeasureManager
from smoke_alarm.sensor import SmokeDetector


def _setup_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if config.LOG_FILE:
        handlers.append(logging.FileHandler(config.LOG_FILE))

    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s %(levelname)-8s %(name)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def run(
    detector: SmokeDetector,
    manager: CountermeasureManager,
    poll_interval: float = config.POLL_INTERVAL,
    consecutive_readings: int = config.CONSECUTIVE_READINGS,
) -> None:
    """Main polling loop.

    Parameters
    ----------
    detector:
        Configured :class:`~smoke_alarm.sensor.SmokeDetector` instance.
    manager:
        Configured :class:`~smoke_alarm.alarm.CountermeasureManager` instance.
    poll_interval:
        Seconds between sensor readings.
    consecutive_readings:
        Number of consecutive above-threshold readings required before an
        alarm is triggered (guards against sensor noise).
    """
    logger = logging.getLogger(__name__)
    logger.info(
        "SmokeAlarm started. Threshold: %d  Consecutive: %d  Poll interval: %.1f s",
        detector.threshold,
        consecutive_readings,
        poll_interval,
    )

    # Sliding window to track recent readings.
    window: deque[bool] = deque(maxlen=consecutive_readings)

    running = True

    def _shutdown(signum: int, frame: object) -> None:
        nonlocal running
        logger.info("Received signal %d – shutting down…", signum)
        running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while running:
            raw = detector.read_raw()
            smoke_now = raw > detector.threshold
            window.append(smoke_now)

            if len(window) == consecutive_readings and all(window):
                manager.on_smoke_detected(raw)
            elif not smoke_now:
                manager.on_smoke_cleared()

            logger.debug("ADC=%d  smoke=%s", raw, smoke_now)
            time.sleep(poll_interval)
    finally:
        logger.info("Cleaning up resources…")
        manager.cleanup()
        detector.close()
        logger.info("SmokeAlarm stopped.")


def main() -> None:
    _setup_logging()
    detector = SmokeDetector()
    manager = CountermeasureManager()
    run(detector, manager)


if __name__ == "__main__":
    main()
