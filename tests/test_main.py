"""Tests for the main polling loop in smoke_alarm.main."""

from collections import deque
from unittest.mock import MagicMock, call, patch

import pytest

from smoke_alarm.main import run
from smoke_alarm.sensor import SmokeDetector
from smoke_alarm.alarm import CountermeasureManager


def _make_detector(readings: list[int], threshold: int = 300) -> SmokeDetector:
    detector = MagicMock(spec=SmokeDetector)
    detector.threshold = threshold
    detector.read_raw.side_effect = readings + [StopIteration]
    return detector


def _make_manager() -> CountermeasureManager:
    return MagicMock(spec=CountermeasureManager)


class TestRunLoop:
    def _run(self, readings: list[int], threshold: int = 300, consecutive: int = 3):
        detector = _make_detector(readings, threshold)
        manager = _make_manager()
        # Patch sleep to avoid delays and stop after exhausting readings.
        with patch("smoke_alarm.main.time.sleep"):
            try:
                run(
                    detector,
                    manager,
                    poll_interval=0,
                    consecutive_readings=consecutive,
                )
            except StopIteration:
                pass
        return detector, manager

    def test_no_smoke_no_alarm(self):
        _, manager = self._run([50, 50, 50, 50, 50])
        manager.on_smoke_detected.assert_not_called()

    def test_consecutive_readings_trigger_alarm(self):
        # 3 consecutive readings above threshold should trigger alarm.
        _, manager = self._run([400, 400, 400], threshold=300, consecutive=3)
        manager.on_smoke_detected.assert_called_once()

    def test_non_consecutive_readings_do_not_trigger(self):
        # Alternating high/low readings should not reach consecutive=3.
        _, manager = self._run([400, 50, 400, 50, 400], threshold=300, consecutive=3)
        manager.on_smoke_detected.assert_not_called()

    def test_smoke_cleared_called_on_low_reading(self):
        _, manager = self._run([50], threshold=300, consecutive=3)
        manager.on_smoke_cleared.assert_called()

    def test_cleanup_called_on_exit(self):
        detector, manager = self._run([50])
        manager.cleanup.assert_called_once()
        detector.close.assert_called_once()

    def test_consecutive_1_triggers_immediately(self):
        _, manager = self._run([400], threshold=300, consecutive=1)
        manager.on_smoke_detected.assert_called_once_with(400)
