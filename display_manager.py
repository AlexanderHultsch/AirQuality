# display_manager.py

import serial
import time


class DisplayManager:
    PAGE_TEMPERATURE = 0
    PAGE_HUMIDITY = 1
    PAGE_SMOKE = 2
    

    EVENT_TOUCH = 0x65
    EVENT_RELEASE = 0x00
    EVENT_PRESS = 0x01

    COLOR_BLACK = 0
    COLOR_WHITE = 65535
    COLOR_RED = 63488

    def __init__(self, port="/dev/ttyAMA0", baudrate=9600, timeout=0.1):
        self.serial_port = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(0.5)

    # ============================================================
    # Low-level serial helpers
    # ============================================================

    def _sanitize_text(self, text: str) -> str:
        text = str(text)
        text = text.replace("°", "")
        text = text.replace("µ", "u")
        text = text.replace('"', "'")
        return text

    def _send_raw(self, command: str):
        self.serial_port.write(command.encode("ascii", errors="ignore"))
        self.serial_port.write(b"\xff\xff\xff")

    def _read_available(self) -> bytes:
        waiting = self.serial_port.in_waiting
        if waiting <= 0:
            return b""
        return self.serial_port.read(waiting)

    # ============================================================
    # Nextion command helpers
    # ============================================================

    def goto_page(self, page_id: int):
        self._send_raw(f"page {page_id}")

    def set_text(self, object_name: str, text: str):
        safe_text = self._sanitize_text(text)
        self._send_raw(f'{object_name}.txt="{safe_text}"')

    def set_value(self, object_name: str, value: int):
        self._send_raw(f"{object_name}.val={int(value)}")

    def set_background_color(self, object_name: str, color: int):
        self._send_raw(f"{object_name}.bco={int(color)}")

    def set_font_color(self, object_name: str, color: int):
        self._send_raw(f"{object_name}.pco={int(color)}")

    def set_page_background_color(self, color: int):
        self._send_raw(f"cls {int(color)}")

    def refresh_component(self, object_name: str):
        self._send_raw(f"ref {object_name}")

    # ============================================================
    # Page content helpers
    # ============================================================

    def update_page_content(
        self,
        title: str,
        value: str,
        unit: str,
        status: str,
        trend: str,
        other: str,
    ):
        self.set_text("title", title)
        self.set_text("value", value)
        self.set_text("unit", unit)
        self.set_text("status", status)
        self.set_text("trend", trend)
        self.set_text("other", other)

    def apply_normal_theme(self):
        self.set_page_background_color(self.COLOR_BLACK)

        for object_name in ["title", "value", "unit", "status", "trend", "other"]:
            self.set_background_color(object_name, self.COLOR_BLACK)
            self.set_font_color(object_name, self.COLOR_WHITE)
            self.refresh_component(object_name)

        for object_name in ["back", "next"]:
            self.set_background_color(object_name, self.COLOR_BLACK)
            self.set_font_color(object_name, self.COLOR_WHITE)
            self.refresh_component(object_name)

    def apply_white_theme(self):
        self.set_page_background_color(self.COLOR_WHITE)

        for object_name in ["title", "value", "unit", "status", "trend", "other"]:
            self.set_background_color(object_name, self.COLOR_WHITE)
            self.set_font_color(object_name, self.COLOR_BLACK)
            self.refresh_component(object_name)

        for object_name in ["back", "next"]:
            self.set_background_color(object_name, self.COLOR_WHITE)
            self.set_font_color(object_name, self.COLOR_BLACK)
            self.refresh_component(object_name)

    def apply_critical_theme(self):
        self.set_page_background_color(self.COLOR_RED)

        for object_name in ["title", "value", "unit", "status", "trend", "other"]:
            self.set_background_color(object_name, self.COLOR_RED)
            self.set_font_color(object_name, self.COLOR_WHITE)
            self.refresh_component(object_name)

        for object_name in ["back", "next"]:
            self.set_background_color(object_name, self.COLOR_RED)
            self.set_font_color(object_name, self.COLOR_WHITE)
            self.refresh_component(object_name)

    def flash_critical_alert(self, step_delay=0.2):
        self.apply_normal_theme()
        time.sleep(step_delay)

        self.apply_white_theme()
        time.sleep(step_delay)

        self.apply_normal_theme()
        time.sleep(step_delay)

        self.apply_white_theme()
        time.sleep(step_delay)

        self.apply_critical_theme()

    # ============================================================
    # Touch event parsing
    # ============================================================

    def read_touch_event(self):
        data = self._read_available()
        if not data:
            return None

        packets = data.split(b"\xff\xff\xff")

        for packet in packets:
            if len(packet) < 4:
                continue

            if packet[0] == self.EVENT_TOUCH:
                page_id = packet[1]
                component_id = packet[2]
                event_type = packet[3]

                return {
                    "type": "touch",
                    "page_id": page_id,
                    "component_id": component_id,
                    "event": "press" if event_type == self.EVENT_PRESS else "release",
                }

        return None

    # ============================================================
    # Button mapping helpers
    # ============================================================

    def interpret_navigation_event(self, event, back_component_id, next_component_id):
        if event is None:
            return None

        if event.get("type") != "touch":
            return None

        if event.get("event") != "release":
            return None

        component_id = event.get("component_id")

        if component_id == back_component_id:
            return "back"

        if component_id == next_component_id:
            return "next"

        return None

    # ============================================================
    # Convenience render helpers
    # ============================================================

    def show_humidity_page(self, value, status="", trend="", other=""):
        self.goto_page(self.PAGE_HUMIDITY)
        self.update_page_content(
            title="Humidity",
            value=value,
            unit="%",
            status=status,
            trend=trend,
            other=other,
        )

    def show_smoke_page(self, value, status="", trend="", other=""):
        self.goto_page(self.PAGE_SMOKE)
        self.update_page_content(
            title="Smoke",
            value=value,
            unit="",
            status=status,
            trend=trend,
            other=other,
        )

    def show_temperature_page(self, value, status="", trend="", other=""):
        self.goto_page(self.PAGE_TEMPERATURE)
        self.update_page_content(
            title="Temperature",
            value=value,
            unit="C",
            status=status,
            trend=trend,
            other=other,
        )

    # ============================================================
    # Cleanup
    # ============================================================

    def close(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()