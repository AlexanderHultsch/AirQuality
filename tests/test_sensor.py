"""Tests for smoke_alarm.sensor."""

import pytest
from unittest.mock import MagicMock, patch

from smoke_alarm.sensor import SmokeDetector, ADC_MAX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detector(raw_value: int = 0, threshold: int = 300) -> SmokeDetector:
    """Return a SmokeDetector whose SPI device is mocked."""
    detector = SmokeDetector.__new__(SmokeDetector)
    detector.channel = 0
    detector.threshold = threshold
    # Build a mock SPI that returns *raw_value* when xfer2 is called.
    mock_spi = MagicMock()
    # MCP3008 decoding: ((response[1] & 3) << 8) + response[2]
    high_byte = (raw_value >> 8) & 0x03
    low_byte = raw_value & 0xFF
    mock_spi.xfer2.return_value = [0, high_byte, low_byte]
    detector._spi = mock_spi
    return detector


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

class TestSmokeDetectorInit:
    def test_invalid_channel_low(self):
        with pytest.raises(ValueError, match="channel"):
            SmokeDetector(channel=-1)

    def test_invalid_channel_high(self):
        with pytest.raises(ValueError, match="channel"):
            SmokeDetector(channel=8)

    def test_invalid_threshold_low(self):
        with pytest.raises(ValueError, match="[Tt]hreshold"):
            SmokeDetector(threshold=-1)

    def test_invalid_threshold_high(self):
        with pytest.raises(ValueError, match="[Tt]hreshold"):
            SmokeDetector(threshold=ADC_MAX + 1)

    def test_simulation_mode_when_no_spidev(self):
        """Without spidev the detector falls back to simulation mode."""
        with patch.dict("sys.modules", {"spidev": None}):
            detector = SmokeDetector()
        assert detector._spi is None

    def test_simulation_mode_when_spi_open_fails(self):
        mock_spidev = MagicMock()
        mock_spidev.SpiDev.return_value.open.side_effect = OSError("no SPI")
        with patch.dict("sys.modules", {"spidev": mock_spidev}):
            detector = SmokeDetector()
        assert detector._spi is None


# ---------------------------------------------------------------------------
# read_raw
# ---------------------------------------------------------------------------

class TestReadRaw:
    def test_simulation_mode_returns_zero(self):
        detector = SmokeDetector.__new__(SmokeDetector)
        detector.channel = 0
        detector.threshold = 300
        detector._spi = None
        assert detector.read_raw() == 0

    def test_reads_correct_value(self):
        detector = _make_detector(raw_value=512)
        assert detector.read_raw() == 512

    def test_reads_min_value(self):
        assert _make_detector(raw_value=0).read_raw() == 0

    def test_reads_max_value(self):
        assert _make_detector(raw_value=ADC_MAX).read_raw() == ADC_MAX

    def test_spi_xfer2_called_with_correct_bytes(self):
        detector = _make_detector(raw_value=0, threshold=300)
        detector.read_raw()
        # Channel 0 → (8 + 0) << 4 = 128
        detector._spi.xfer2.assert_called_once_with([1, 128, 0])


# ---------------------------------------------------------------------------
# read_percent
# ---------------------------------------------------------------------------

class TestReadPercent:
    def test_zero(self):
        assert _make_detector(raw_value=0).read_percent() == 0.0

    def test_full_scale(self):
        assert _make_detector(raw_value=ADC_MAX).read_percent() == 100.0

    def test_midpoint(self):
        result = _make_detector(raw_value=512).read_percent()
        assert abs(result - 50.05) < 0.1  # 512/1023*100 ≈ 50.05


# ---------------------------------------------------------------------------
# is_smoke_detected
# ---------------------------------------------------------------------------

class TestIsSmokeDetected:
    def test_below_threshold(self):
        assert not _make_detector(raw_value=200, threshold=300).is_smoke_detected()

    def test_at_threshold(self):
        # Threshold is strictly greater-than, so equal value returns False.
        assert not _make_detector(raw_value=300, threshold=300).is_smoke_detected()

    def test_above_threshold(self):
        assert _make_detector(raw_value=301, threshold=300).is_smoke_detected()

    def test_simulation_always_false(self):
        detector = SmokeDetector.__new__(SmokeDetector)
        detector.channel = 0
        detector.threshold = 0  # Even threshold 0 won't trigger (raw is 0, not > 0)
        detector._spi = None
        assert not detector.is_smoke_detected()


# ---------------------------------------------------------------------------
# close / context manager
# ---------------------------------------------------------------------------

class TestCloseAndContextManager:
    def test_close_calls_spi_close(self):
        detector = _make_detector()
        mock_spi = detector._spi  # save reference before close() nulls it
        detector.close()
        mock_spi.close.assert_called_once()
        assert detector._spi is None

    def test_close_twice_is_safe(self):
        detector = _make_detector()
        detector.close()
        detector.close()  # Should not raise

    def test_context_manager_closes_on_exit(self):
        detector = _make_detector()
        mock_spi = detector._spi
        with detector:
            pass
        mock_spi.close.assert_called_once()
