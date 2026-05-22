"""Tests for smoke_alarm.alarm (countermeasures)."""

import threading
import time
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from smoke_alarm.alarm import (
    BuzzerAlarm,
    CountermeasureManager,
    NotificationSender,
    RelayController,
    _GPIOStub,
)


# ---------------------------------------------------------------------------
# _GPIOStub
# ---------------------------------------------------------------------------

class TestGPIOStub:
    def test_stub_has_required_attributes(self):
        stub = _GPIOStub()
        assert hasattr(stub, "BCM")
        assert hasattr(stub, "OUT")
        assert hasattr(stub, "HIGH")
        assert hasattr(stub, "LOW")

    def test_stub_methods_do_not_raise(self):
        stub = _GPIOStub()
        stub.setmode(stub.BCM)
        stub.setwarnings(False)
        stub.setup(17, stub.OUT)
        stub.output(17, stub.HIGH)
        stub.cleanup()


# ---------------------------------------------------------------------------
# BuzzerAlarm
# ---------------------------------------------------------------------------

def _make_buzzer(pin: int = 17, duration: float = 0.05) -> tuple[BuzzerAlarm, _GPIOStub]:
    """Return a BuzzerAlarm with a stubbed GPIO."""
    with patch("smoke_alarm.alarm._get_gpio") as mock_get:
        stub = _GPIOStub()
        stub.output = MagicMock()
        stub.setup = MagicMock()
        mock_get.return_value = stub
        buzzer = BuzzerAlarm(pin=pin, duration=duration)
    return buzzer, stub


class TestBuzzerAlarm:
    def test_activate_sets_pin_high(self):
        buzzer, stub = _make_buzzer()
        buzzer.activate()
        stub.output.assert_any_call(buzzer.pin, stub.HIGH)

    def test_deactivate_sets_pin_low(self):
        buzzer, stub = _make_buzzer()
        buzzer.deactivate()
        stub.output.assert_called_with(buzzer.pin, stub.LOW)

    def test_activate_schedules_deactivation(self):
        buzzer, stub = _make_buzzer(duration=0.05)
        buzzer.activate()
        assert buzzer._timer is not None
        buzzer._timer.join(timeout=0.5)
        # After timer fires, pin should be LOW.
        stub.output.assert_called_with(buzzer.pin, stub.LOW)

    def test_activate_cancels_previous_timer(self):
        buzzer, stub = _make_buzzer(duration=10.0)
        buzzer.activate()
        first_timer = buzzer._timer
        buzzer.activate()
        assert not first_timer.is_alive()

    def test_cleanup_deactivates_buzzer(self):
        buzzer, stub = _make_buzzer(duration=10.0)
        buzzer.activate()
        buzzer.cleanup()
        stub.output.assert_called_with(buzzer.pin, stub.LOW)


# ---------------------------------------------------------------------------
# RelayController
# ---------------------------------------------------------------------------

def _make_relay(
    pin: int = 27,
    duration: float = 0.05,
    active_low: bool = False,
) -> tuple[RelayController, _GPIOStub]:
    with patch("smoke_alarm.alarm._get_gpio") as mock_get:
        stub = _GPIOStub()
        stub.output = MagicMock()
        stub.setup = MagicMock()
        mock_get.return_value = stub
        relay = RelayController(pin=pin, duration=duration, active_low=active_low)
    return relay, stub


class TestRelayController:
    def test_initial_state_is_off(self):
        relay, _ = _make_relay()
        assert not relay.is_active

    def test_activate_sets_relay_on(self):
        relay, stub = _make_relay()
        relay.activate()
        assert relay.is_active

    def test_activate_twice_only_triggers_once(self):
        relay, stub = _make_relay()
        relay.activate()
        call_count_before = stub.output.call_count
        relay.activate()
        assert stub.output.call_count == call_count_before  # No extra call.

    def test_deactivate_sets_relay_off(self):
        relay, stub = _make_relay()
        relay.activate()
        relay.deactivate()
        assert not relay.is_active

    def test_active_low_relay_signals_inverted(self):
        relay, stub = _make_relay(active_low=True)
        relay.activate()
        # For active-low the ON signal should be False (LOW).
        stub.output.assert_any_call(relay.pin, False)

    def test_schedule_deactivation_fires_after_duration(self):
        relay, stub = _make_relay(duration=0.05)
        relay.activate()
        relay.schedule_deactivation()
        relay._timer.join(timeout=0.5)
        assert not relay.is_active

    def test_cleanup_deactivates_relay(self):
        relay, stub = _make_relay(duration=10.0)
        relay.activate()
        relay.cleanup()
        assert not relay.is_active


# ---------------------------------------------------------------------------
# NotificationSender
# ---------------------------------------------------------------------------

class TestNotificationSender:
    def _sender(self) -> NotificationSender:
        return NotificationSender(
            url="https://ntfy.example.com",
            topic="test-topic",
            token="",
        )

    def test_send_success(self):
        sender = self._sender()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("smoke_alarm.alarm.requests.post", return_value=mock_response) as mock_post:
            result = sender.send("Test", "Test message")

        assert result is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://ntfy.example.com/test-topic"
        assert kwargs["headers"]["Title"] == "Test"

    def test_send_with_token_adds_auth_header(self):
        sender = NotificationSender(
            url="https://ntfy.example.com",
            topic="test-topic",
            token="my-secret-token",
        )
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("smoke_alarm.alarm.requests.post", return_value=mock_response) as mock_post:
            sender.send("Title", "Body")

        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer my-secret-token"

    def test_send_failure_returns_false(self):
        sender = self._sender()
        with patch(
            "smoke_alarm.alarm.requests.post",
            side_effect=requests.RequestException("timeout"),
        ):
            result = sender.send("Test", "Test message")

        assert result is False

    def test_url_trailing_slash_stripped(self):
        sender = NotificationSender(url="https://ntfy.example.com/", topic="t")
        assert sender.url == "https://ntfy.example.com"


# ---------------------------------------------------------------------------
# CountermeasureManager
# ---------------------------------------------------------------------------

def _make_manager(
    buzzer: bool = True,
    relay: bool = True,
    ntfy: bool = False,
) -> tuple[CountermeasureManager, MagicMock, MagicMock]:
    with (
        patch("smoke_alarm.alarm._get_gpio") as mock_gpio,
    ):
        mock_gpio.return_value = _make_stub_gpio()
        manager = CountermeasureManager(
            buzzer_enabled=buzzer,
            relay_enabled=relay,
            ntfy_enabled=ntfy,
        )
    mock_buzzer = MagicMock(spec=BuzzerAlarm)
    mock_relay = MagicMock(spec=RelayController)
    mock_relay.is_active = True
    manager.buzzer = mock_buzzer if buzzer else None
    manager.relay = mock_relay if relay else None
    return manager, mock_buzzer, mock_relay


def _make_stub_gpio():
    stub = _GPIOStub()
    stub.output = MagicMock()
    stub.setup = MagicMock()
    return stub


class TestCountermeasureManager:
    def test_on_smoke_detected_activates_buzzer(self):
        manager, mock_buzzer, _ = _make_manager()
        manager.on_smoke_detected(500)
        mock_buzzer.activate.assert_called_once()

    def test_on_smoke_detected_activates_relay(self):
        manager, _, mock_relay = _make_manager()
        manager.on_smoke_detected(500)
        mock_relay.activate.assert_called_once()

    def test_on_smoke_detected_not_repeated(self):
        """Second call while alarm is active should not re-trigger."""
        manager, mock_buzzer, _ = _make_manager()
        manager.on_smoke_detected(500)
        manager.on_smoke_detected(600)
        mock_buzzer.activate.assert_called_once()

    def test_on_smoke_cleared_schedules_relay_deactivation(self):
        manager, _, mock_relay = _make_manager()
        manager.on_smoke_detected(500)
        manager.on_smoke_cleared()
        mock_relay.schedule_deactivation.assert_called_once()

    def test_on_smoke_cleared_when_no_active_alarm_is_noop(self):
        manager, _, mock_relay = _make_manager()
        manager.on_smoke_cleared()  # Not in alarm state
        mock_relay.schedule_deactivation.assert_not_called()

    def test_cleanup_calls_buzzer_and_relay_cleanup(self):
        manager, mock_buzzer, mock_relay = _make_manager()
        manager.cleanup()
        mock_buzzer.cleanup.assert_called_once()
        mock_relay.cleanup.assert_called_once()

    def test_no_buzzer_when_disabled(self):
        manager, _, _ = _make_manager(buzzer=False)
        assert manager.buzzer is None

    def test_no_relay_when_disabled(self):
        manager, _, _ = _make_manager(relay=False)
        assert manager.relay is None

    def test_ntfy_notification_sent_on_smoke(self):
        manager, mock_buzzer, mock_relay = _make_manager(ntfy=False)
        mock_notifier = MagicMock(spec=NotificationSender)
        manager.notifier = mock_notifier
        manager.on_smoke_detected(700)
        mock_notifier.send.assert_called_once()
        title, message = mock_notifier.send.call_args[0]
        assert "700" in message

    def test_smoke_cleared_resets_active_flag(self):
        manager, _, mock_relay = _make_manager()
        manager.on_smoke_detected(500)
        assert manager._smoke_active is True
        manager.on_smoke_cleared()
        assert manager._smoke_active is False
