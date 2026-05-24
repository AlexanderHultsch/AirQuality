# test_display.py

import time
from display_manager import DisplayManager

display = DisplayManager(port="/dev/ttyAMA0", baudrate=9600, timeout=0.1)

try:
    display.show_humidity_page(
        value="54.4",
        status="Good",
        trend="Stable",
        other="Test"
    )
    display.apply_normal_theme()
    time.sleep(3)

    display.show_smoke_page(
        value="CLEAR",
        status="Good",
        trend="Stable",
        other="No smoke"
    )
    display.apply_normal_theme()
    time.sleep(3)

    display.show_temperature_page(
        value="25.8",
        status="Elevated",
        trend="Rising",
        other="Warm room"
    )
    display.apply_normal_theme()
    time.sleep(3)

    display.show_temperature_page(
        value="31.2",
        status="Critical",
        trend="Rising",
        other="Alert"
    )
    display.flash_critical_alert(step_delay=0.25)
    time.sleep(2)

    display.show_smoke_page(
        value="CLEAR",
        status="Good",
        trend="Stable",
        other="Done"
    )
    display.apply_normal_theme()

    print("Display test finished.")

except KeyboardInterrupt:
    print("Test interrupted by user.")

finally:
    display.close()