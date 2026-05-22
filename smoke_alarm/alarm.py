"""Countermeasures activated when cigarette smoke is detected.

Three countermeasures are available and can be independently enabled:

1. **Buzzer** – activates an active buzzer connected to a GPIO pin.
2. **Relay / fan** – activates a relay (e.g. to switch on a ventilation fan).
3. **Push notification** – sends an HTTP POST to an ntfy.sh topic.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import requests

from smoke_alarm import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GPIO helpers
# ---------------------------------------------------------------------------

def _get_gpio():
    """Import RPi.GPIO or return a stub for non-Pi environments."""
    try:
        import RPi.GPIO as GPIO  # type: ignore[import]
        return GPIO
    except (ImportError, RuntimeError):
        logger.warning("RPi.GPIO not available; GPIO countermeasures will be simulated.")
        return _GPIOStub()


class _GPIOStub:
    """Minimal GPIO stub used when RPi.GPIO is not available."""

    BCM = "BCM"
    OUT = "OUT"
    HIGH = True
    LOW = False

    def setmode(self, mode: object) -> None:  # noqa: D401
        pass

    def setwarnings(self, flag: bool) -> None:
        pass

    def setup(self, pin: int, mode: object) -> None:
        pass

    def output(self, pin: int, value: object) -> None:
        logger.debug("[GPIO stub] pin %d → %s", pin, value)

    def cleanup(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Individual countermeasure classes
# ---------------------------------------------------------------------------

class BuzzerAlarm:
    """Activates an active buzzer for a fixed duration.

    Parameters
    ----------
    pin:
        BCM pin number the buzzer is connected to.
    duration:
        How many seconds the buzzer sounds per activation.
    """

    def __init__(
        self,
        pin: int = config.BUZZER_PIN,
        duration: float = config.BUZZER_DURATION,
    ) -> None:
        self.pin = pin
        self.duration = duration
        self._gpio = _get_gpio()
        self._gpio.setwarnings(False)
        self._gpio.setmode(self._gpio.BCM)
        self._gpio.setup(self.pin, self._gpio.OUT)
        self._timer: Optional[threading.Timer] = None

    def activate(self) -> None:
        """Turn the buzzer on and schedule it to turn off after *duration* s."""
        logger.info("Buzzer alarm activated on pin %d for %.1f s.", self.pin, self.duration)
        self._gpio.output(self.pin, self._gpio.HIGH)
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self.duration, self.deactivate)
        self._timer.daemon = True
        self._timer.start()

    def deactivate(self) -> None:
        """Turn the buzzer off immediately."""
        logger.info("Buzzer alarm deactivated.")
        self._gpio.output(self.pin, self._gpio.LOW)

    def cleanup(self) -> None:
        """Release GPIO resources."""
        if self._timer is not None:
            self._timer.cancel()
        self.deactivate()
        self._gpio.cleanup()


class RelayController:
    """Controls a relay module to switch on a ventilation fan.

    Parameters
    ----------
    pin:
        BCM pin number connected to the relay IN pin.
    duration:
        How many seconds the relay stays active after smoke clears.
    active_low:
        Set to *True* for active-low relay boards (triggered by LOW signal).
    """

    def __init__(
        self,
        pin: int = config.RELAY_PIN,
        duration: float = config.RELAY_DURATION,
        active_low: bool = config.RELAY_ACTIVE_LOW,
    ) -> None:
        self.pin = pin
        self.duration = duration
        self._on_signal = not active_low  # LOW for active-low, HIGH otherwise
        self._off_signal = active_low
        self._gpio = _get_gpio()
        self._gpio.setwarnings(False)
        self._gpio.setmode(self._gpio.BCM)
        self._gpio.setup(self.pin, self._gpio.OUT)
        # Make sure relay is off at startup.
        self._gpio.output(self.pin, self._off_signal)
        self._timer: Optional[threading.Timer] = None
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self) -> None:
        """Switch the relay on."""
        if self._active:
            return
        logger.info("Relay activated on pin %d (fan on).", self.pin)
        self._gpio.output(self.pin, self._on_signal)
        self._active = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def schedule_deactivation(self) -> None:
        """Schedule the relay to switch off after *duration* seconds."""
        if self._timer is not None:
            self._timer.cancel()
        logger.info(
            "Relay will deactivate in %.1f s (fan running to clear residual smoke).",
            self.duration,
        )
        self._timer = threading.Timer(self.duration, self.deactivate)
        self._timer.daemon = True
        self._timer.start()

    def deactivate(self) -> None:
        """Switch the relay off immediately."""
        logger.info("Relay deactivated (fan off).")
        self._gpio.output(self.pin, self._off_signal)
        self._active = False

    def cleanup(self) -> None:
        """Release GPIO resources."""
        if self._timer is not None:
            self._timer.cancel()
        self.deactivate()
        self._gpio.cleanup()


class NotificationSender:
    """Sends push notifications via ntfy.sh.

    Parameters
    ----------
    url:
        Base URL of the ntfy server.
    topic:
        ntfy topic to publish to.
    token:
        Optional bearer token for authenticated topics.
    """

    def __init__(
        self,
        url: str = config.NTFY_URL,
        topic: str = config.NTFY_TOPIC,
        token: str = config.NTFY_TOKEN,
    ) -> None:
        self.url = url.rstrip("/")
        self.topic = topic
        self.token = token

    def send(self, title: str, message: str, priority: str = "high") -> bool:
        """Publish a notification.

        Returns *True* on success, *False* on failure.
        """
        endpoint = f"{self.url}/{self.topic}"
        headers: dict[str, str] = {
            "Title": title,
            "Priority": priority,
            "Tags": "smoking,warning",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = requests.post(
                endpoint,
                data=message.encode("utf-8"),
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            logger.info("Push notification sent to %s", endpoint)
            return True
        except requests.RequestException as exc:
            logger.error("Failed to send push notification: %s", exc)
            return False


# ---------------------------------------------------------------------------
# High-level countermeasure manager
# ---------------------------------------------------------------------------

class CountermeasureManager:
    """Orchestrates all enabled countermeasures.

    Parameters
    ----------
    buzzer_enabled:
        Activate buzzer on smoke detection.
    relay_enabled:
        Activate relay (fan) on smoke detection.
    ntfy_enabled:
        Send push notification on smoke detection.
    """

    def __init__(
        self,
        buzzer_enabled: bool = config.BUZZER_ENABLED,
        relay_enabled: bool = config.RELAY_ENABLED,
        ntfy_enabled: bool = config.NTFY_ENABLED,
    ) -> None:
        self.buzzer: Optional[BuzzerAlarm] = BuzzerAlarm() if buzzer_enabled else None
        self.relay: Optional[RelayController] = RelayController() if relay_enabled else None
        self.notifier: Optional[NotificationSender] = (
            NotificationSender() if ntfy_enabled else None
        )
        self._smoke_active = False

    def on_smoke_detected(self, raw_value: int) -> None:
        """Call when smoke is detected.  Triggers all enabled countermeasures."""
        if self._smoke_active:
            return  # Already handling an alarm; avoid re-triggering every poll.

        self._smoke_active = True
        logger.warning("SMOKE DETECTED – activating countermeasures (ADC=%d).", raw_value)

        if self.buzzer is not None:
            self.buzzer.activate()

        if self.relay is not None:
            self.relay.activate()

        if self.notifier is not None:
            message = (
                f"Cigarette smoke detected on the balcony!\n"
                f"Sensor reading: {raw_value}/1023.\n"
                f"Ventilation fan has been activated."
            )
            self.notifier.send("🚨 Smoke Alert", message)

    def on_smoke_cleared(self) -> None:
        """Call when smoke is no longer detected.  Schedules deactivation."""
        if not self._smoke_active:
            return

        self._smoke_active = False
        logger.info("Smoke cleared – scheduling countermeasure deactivation.")

        if self.relay is not None and self.relay.is_active:
            self.relay.schedule_deactivation()

    def cleanup(self) -> None:
        """Release all hardware resources."""
        if self.buzzer is not None:
            self.buzzer.cleanup()
        if self.relay is not None:
            self.relay.cleanup()
