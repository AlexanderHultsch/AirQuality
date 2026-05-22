"""Smoke sensor interface.

Reads analogue values from an MQ-2 smoke/gas sensor connected to a
Raspberry Pi via an MCP3008 analogue-to-digital converter (ADC) over SPI.

Hardware connections
--------------------
MCP3008 pin  →  Raspberry Pi (BCM)
VDD          →  3.3 V
VREF         →  3.3 V
AGND         →  GND
CLK          →  SCLK (GPIO 11 for SPI0)
DOUT         →  MISO (GPIO 9 for SPI0)
DIN          →  MOSI (GPIO 10 for SPI0)
CS/SHDN      →  CE0  (GPIO 8 for SPI0)
DGND         →  GND

MQ-2 AOUT    →  MCP3008 CH0 (or channel set via config)
MQ-2 VCC     →  5 V
MQ-2 GND     →  GND
"""

from __future__ import annotations

import logging
from typing import Optional

from smoke_alarm import config

logger = logging.getLogger(__name__)

# MCP3008 max raw value (10-bit ADC).
ADC_MAX = 1023


class SmokeDetector:
    """Reads analogue smoke level from an MQ-2 sensor via MCP3008 ADC.

    On non-Raspberry-Pi systems (or when *spidev* is unavailable) the class
    falls back to simulation mode so the rest of the code can be tested
    without physical hardware.

    Parameters
    ----------
    spi_bus:
        SPI bus number (default from :mod:`smoke_alarm.config`).
    spi_device:
        SPI chip-select device number.
    channel:
        MCP3008 ADC channel (0-7) wired to the MQ-2 analogue output.
    threshold:
        Raw ADC value above which smoke is considered present.
    """

    def __init__(
        self,
        spi_bus: int = config.SPI_BUS,
        spi_device: int = config.SPI_DEVICE,
        channel: int = config.SENSOR_ADC_CHANNEL,
        threshold: int = config.SMOKE_THRESHOLD,
    ) -> None:
        if not 0 <= channel <= 7:
            raise ValueError(f"ADC channel must be between 0 and 7, got {channel}")
        if not 0 <= threshold <= ADC_MAX:
            raise ValueError(
                f"Threshold must be between 0 and {ADC_MAX}, got {threshold}"
            )

        self.channel = channel
        self.threshold = threshold
        self._spi: Optional[object] = None

        try:
            import spidev  # type: ignore[import]

            spi = spidev.SpiDev()
            spi.open(spi_bus, spi_device)
            spi.max_speed_hz = 1_350_000
            self._spi = spi
            logger.info(
                "MCP3008 ADC opened on SPI%d.%d, channel %d",
                spi_bus,
                spi_device,
                channel,
            )
        except (ImportError, FileNotFoundError, OSError) as exc:
            logger.warning(
                "spidev not available (%s). Running in simulation mode.", exc
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_raw(self) -> int:
        """Return a raw 10-bit ADC value (0-1023) from the sensor channel.

        In simulation mode (no hardware) this always returns 0.
        """
        if self._spi is None:
            return 0

        # MCP3008 protocol: send 3 bytes, read 3 bytes.
        # Byte 0: start bit
        # Byte 1: single-ended mode (1 << 7) + channel select (channel << 4)
        # Byte 2: don't-care
        response = self._spi.xfer2([1, (8 + self.channel) << 4, 0])
        raw = ((response[1] & 3) << 8) + response[2]
        logger.debug("ADC raw reading: %d", raw)
        return raw

    def read_percent(self) -> float:
        """Return sensor reading as a percentage of the full ADC scale."""
        return round(self.read_raw() / ADC_MAX * 100, 2)

    def is_smoke_detected(self) -> bool:
        """Return *True* when the current reading exceeds the threshold."""
        raw = self.read_raw()
        detected = raw > self.threshold
        if detected:
            logger.info("Smoke detected! Raw ADC value: %d (threshold: %d)", raw, self.threshold)
        return detected

    def close(self) -> None:
        """Release the SPI device."""
        if self._spi is not None:
            self._spi.close()
            self._spi = None
            logger.debug("SPI device closed.")

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "SmokeDetector":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
