# test_touch.py

import time
from display_manager import DisplayManager

display = DisplayManager(port="/dev/ttyAMA0", baudrate=9600, timeout=0.1)

try:
    print("Touch test started. Press back/next on the display.")

    while True:
        event = display.read_touch_event()

        if event is not None:
            print(event)

        time.sleep(0.05)

except KeyboardInterrupt:
    print("Touch test stopped.")

finally:
    display.close()