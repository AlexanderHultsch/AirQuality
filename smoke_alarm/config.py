"""Configuration for the SmokeAlarm application.

Values can be overridden via environment variables prefixed with
``SMOKEALARM_``.  For example, to change the smoke threshold set::

    SMOKEALARM_SMOKE_THRESHOLD=400

All pin numbers use Broadcom (BCM) numbering unless otherwise noted.
"""

import os


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Sensor (MQ-2 connected to MCP3008 ADC via SPI)
# ---------------------------------------------------------------------------

#: SPI bus used by the MCP3008 (0 or 1).
SPI_BUS: int = _env_int("SMOKEALARM_SPI_BUS", 0)

#: SPI device (chip-select) on the chosen bus.
SPI_DEVICE: int = _env_int("SMOKEALARM_SPI_DEVICE", 0)

#: MCP3008 ADC channel wired to the MQ-2 analogue output (0-7).
SENSOR_ADC_CHANNEL: int = _env_int("SMOKEALARM_SENSOR_ADC_CHANNEL", 0)

#: Raw ADC value (0-1023) above which smoke is considered detected.
SMOKE_THRESHOLD: int = _env_int("SMOKEALARM_SMOKE_THRESHOLD", 300)

#: Consecutive readings above the threshold needed to trigger an alarm.
#: This prevents false positives caused by sensor noise.
CONSECUTIVE_READINGS: int = _env_int("SMOKEALARM_CONSECUTIVE_READINGS", 3)

#: Delay in seconds between sensor readings.
POLL_INTERVAL: float = _env_float("SMOKEALARM_POLL_INTERVAL", 1.0)

# ---------------------------------------------------------------------------
# Countermeasures – Buzzer (active buzzer connected to a GPIO pin)
# ---------------------------------------------------------------------------

#: Enable the buzzer countermeasure.
BUZZER_ENABLED: bool = _env_bool("SMOKEALARM_BUZZER_ENABLED", True)

#: BCM pin number the active buzzer is connected to.
BUZZER_PIN: int = _env_int("SMOKEALARM_BUZZER_PIN", 17)

#: How long (seconds) the buzzer stays on per alarm cycle.
BUZZER_DURATION: float = _env_float("SMOKEALARM_BUZZER_DURATION", 5.0)

# ---------------------------------------------------------------------------
# Countermeasures – Relay / ventilation fan
# ---------------------------------------------------------------------------

#: Enable relay (e.g. a ventilation fan) as a countermeasure.
RELAY_ENABLED: bool = _env_bool("SMOKEALARM_RELAY_ENABLED", True)

#: BCM pin number connected to the relay module IN pin.
RELAY_PIN: int = _env_int("SMOKEALARM_RELAY_PIN", 27)

#: How long (seconds) the relay stays activated after smoke is cleared.
RELAY_DURATION: float = _env_float("SMOKEALARM_RELAY_DURATION", 30.0)

#: Set to True if the relay board is active-low (triggered by LOW signal).
RELAY_ACTIVE_LOW: bool = _env_bool("SMOKEALARM_RELAY_ACTIVE_LOW", False)

# ---------------------------------------------------------------------------
# Countermeasures – Push notification via ntfy.sh
# ---------------------------------------------------------------------------

#: Enable push notifications via ntfy.sh (https://ntfy.sh).
NTFY_ENABLED: bool = _env_bool("SMOKEALARM_NTFY_ENABLED", False)

#: ntfy.sh server URL (use your own server or the public one).
NTFY_URL: str = _env_str("SMOKEALARM_NTFY_URL", "https://ntfy.sh")

#: ntfy.sh topic name.  Keep this hard-to-guess for basic privacy.
NTFY_TOPIC: str = _env_str("SMOKEALARM_NTFY_TOPIC", "smokealarm-alerts")

#: Optional Bearer token for authenticated ntfy.sh topics.
NTFY_TOKEN: str = _env_str("SMOKEALARM_NTFY_TOKEN", "")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

#: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
LOG_LEVEL: str = _env_str("SMOKEALARM_LOG_LEVEL", "INFO")

#: Path to a log file.  Leave empty to log to stdout only.
LOG_FILE: str = _env_str("SMOKEALARM_LOG_FILE", "")
