# Cable Setup -------------------------------------------------
# PIN1_VDD_Red____Pin02
# PIN2_GND_Black__Pin09
# PIN3_SDA_Green__Pin03
# PIN4_SCL_Yellow_Pin05
# PIN5_SEL_Blue___Pin14
# PIN6_NC_Purple__No connection

import time
from smbus2 import SMBus, i2c_msg
from display_manager import DisplayManager
from modules.sensor_reader import build_measurement
from modules.analysis import analyze_smoke, build_display_page_data
from modules.logging_utils import log_pre_smoke_window, log_smoke_event
from modules.notifications import process_push_notifications
from test_script import (
    TEST_MODE,
    ACTIVE_TEST_SCENARIO,
    TEST_ENABLE_DISPLAY,
    TEST_ENABLE_PUSHOVER,
    TEST_ENABLE_LOGGING,
    get_test_measurement,
)

# ============================================================
# Configuration
# ============================================================

REFRESH_RATE = 1  # seconds
PRE_TRIGGER_SECONDS = 30
PRE_TRIGGER_LEN = int(PRE_TRIGGER_SECONDS / REFRESH_RATE)

MAX_LOG_FILE_SIZE_MB = 5  # Max size of Logs
LOG_TRIM_TARGET_RATIO = 0.75  # after trimming, keep about 75% of max size

LONG_WINDOW_SECONDS = 5 * 60
SHORT_WINDOW_SECONDS = 15

LONG_MAX_LIST_LEN = int(LONG_WINDOW_SECONDS / REFRESH_RATE)
SHORT_MAX_LIST_LEN = int(SHORT_WINDOW_SECONDS / REFRESH_RATE)

BUS_ID = 1

SEN55_ADDR = 0x69
SCD41_ADDR = 0x62  # Placeholder address for future integration

DISPLAY_PORT = "/dev/ttyAMA0"
DISPLAY_BAUDRATE = 9600
DISPLAY_AUTO_PAGE_SECONDS = 5

DISPLAY_BACK_COMPONENT_ID = 2
DISPLAY_NEXT_COMPONENT_ID = 1

PUSHOVER_KEYS_FILE = "pushover_keys.txt"
PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_TIMEOUT_SECONDS = 10
PUSHOVER_SMOKE_PRIORITY = 1
PUSHOVER_DEFAULT_PRIORITY = 0

DISPLAY_ENABLED = True if not TEST_MODE else TEST_ENABLE_DISPLAY
PUSHOVER_ENABLED = True if not TEST_MODE else TEST_ENABLE_PUSHOVER
LOGGING_ENABLED = True if not TEST_MODE else TEST_ENABLE_LOGGING

long_window = []
short_window = []

bus = SMBus(BUS_ID)
display = DisplayManager(port=DISPLAY_PORT, baudrate=DISPLAY_BAUDRATE, timeout=0.1)


# ============================================================
# Window / Statistics Helpers
# ============================================================

def update_window(window_list, measurement, max_list_len):
    window_list.append(measurement)
    if len(window_list) > max_list_len:
        window_list.pop(0)


def calculate_avg_and_delta(window_list, fields):
    if len(window_list) <= 1:
        return None, None

    previous_entries = window_list[:-1]
    latest_entry = window_list[-1]

    avg_values = {}
    delta_values = {}

    for field in fields:
        valid_values = [entry[field] for entry in previous_entries if entry.get(field) is not None]

        if len(valid_values) == 0:
            avg_values[field] = None
            delta_values[field] = None
            continue

        avg = round(sum(valid_values) / len(valid_values), 1)
        avg_values[field] = avg

        latest_value = latest_entry.get(field)
        if latest_value is None:
            delta_values[field] = None
        else:
            delta_values[field] = round(latest_value - avg, 1)

    return avg_values, delta_values


# ============================================================
# Event Handling
# ============================================================

def handle_environment_event(event_type):
    if event_type == "smoke":
        print("Fenster schließt")


# ============================================================
# Display Helpers
# ============================================================

DISPLAY_PAGES = [
    {"name": "temperature", "page_id": DisplayManager.PAGE_TEMPERATURE},
    {"name": "humidity", "page_id": DisplayManager.PAGE_HUMIDITY},
    {"name": "co2", "page_id": DisplayManager.PAGE_CO2},
    {"name": "pm1_0", "page_id": DisplayManager.PAGE_PM1_0},
    {"name": "pm2_5", "page_id": DisplayManager.PAGE_PM2_5},
    {"name": "pm4_0", "page_id": DisplayManager.PAGE_PM4_0},
    {"name": "pm10", "page_id": DisplayManager.PAGE_PM10},
    {"name": "voc", "page_id": DisplayManager.PAGE_VOC},
    {"name": "nox", "page_id": DisplayManager.PAGE_NOX},
    {"name": "smoke", "page_id": DisplayManager.PAGE_SMOKE},
]


def render_display_page(page_name, page_data, critical_transition=False):
    content = page_data[page_name]

    if page_name == "temperature":
        display.show_temperature_page(content["value"], content["status"], content["trend"], content["other"])
    elif page_name == "humidity":
        display.show_humidity_page(content["value"], content["status"], content["trend"], content["other"])
    elif page_name == "co2":
        display.show_co2_page(content["value"], content["status"], content["trend"], content["other"])
    elif page_name == "smoke":
        display.show_smoke_page(content["value"], content["status"], content["trend"], content["other"])
    elif page_name == "pm1_0":
        display.show_pm1_0_page(content["value"], content["status"], content["trend"], content["other"])
    elif page_name == "pm2_5":
        display.show_pm2_5_page(content["value"], content["status"], content["trend"], content["other"])
    elif page_name == "pm4_0":
        display.show_pm4_0_page(content["value"], content["status"], content["trend"], content["other"])
    elif page_name == "pm10":
        display.show_pm10_page(content["value"], content["status"], content["trend"], content["other"])
    elif page_name == "voc":
        display.show_voc_page(content["value"], content["status"], content["trend"], content["other"])
    elif page_name == "nox":
        display.show_nox_page(content["value"], content["status"], content["trend"], content["other"])

    if content["critical"]:
        if critical_transition:
            display.flash_critical_alert(step_delay=0.2)
        else:
            display.apply_critical_theme()
    else:
        display.apply_normal_theme()


def get_page_index_by_name(page_name):
    for index, page in enumerate(DISPLAY_PAGES):
        if page["name"] == page_name:
            return index
    return 0


def get_priority_critical_page_name(page_data):
    if page_data["smoke"]["critical"]:
        return "smoke"

    for page in DISPLAY_PAGES:
        if page_data[page["name"]]["critical"]:
            return page["name"]

    return None


# ============================================================
# Measurement Source Helper
# ============================================================

def get_measurement(loop_count):
    if TEST_MODE:
        return get_test_measurement(loop_count, ACTIVE_TEST_SCENARIO)
    return build_measurement(bus, SEN55_ADDR)


# ============================================================
# Main
# ============================================================

# Start SEN55 measurement: 0x0021
bus.i2c_rdwr(i2c_msg.write(SEN55_ADDR, [0x00, 0x21]))
print("Messung gestartet...")
time.sleep(1)

last_smoke_state = "CLEAR"
loop_count = 0

analysis_fields = [
    "pm1_0",
    "pm2_5",
    "pm4_0",
    "pm10",
    "sen55_humidity",
    "sen55_temperature",
    "voc",
    "nox",
    "co2",
    "scd41_temperature",
    "scd41_humidity"
]

alert_states = {
    "temperature": False,
    "humidity": False,
    "co2": False,
    "pm1_0": False,
    "pm2_5": False,
    "pm4_0": False,
    "pm10": False,
    "voc": False,
    "nox": False,
    "smoke": False,
}

current_page_index = 0
last_page_change_time = time.time()
last_critical_page_name = None
last_rendered_page_name = None

try:
    while True:
        smoke_state = "CLEAR"
        smoke_score = 0
        smoke_criteria = {}

        touch_event = display.read_touch_event()
        navigation_action = display.interpret_navigation_event(
            touch_event,
            DISPLAY_BACK_COMPONENT_ID,
            DISPLAY_NEXT_COMPONENT_ID
        )

        measurement = get_measurement(loop_count)

        if measurement is None:
            print("Noch keine fertigen Daten")
            time.sleep(REFRESH_RATE)
            continue

        loop_count += 1

        update_window(long_window, measurement, LONG_MAX_LIST_LEN)
        update_window(short_window, measurement, SHORT_MAX_LIST_LEN)

        print(str(measurement))

        long_avg, long_delta = calculate_avg_and_delta(long_window, analysis_fields)
        short_avg, short_delta = calculate_avg_and_delta(short_window, analysis_fields)

        if long_avg is not None and short_avg is not None:
            smoke_state, smoke_score, smoke_criteria = analyze_smoke(
                measurement, long_avg, short_avg, long_delta, short_delta
            )

            print("smoke_state:", smoke_state)
            print("smoke_score:", smoke_score)

            if last_smoke_state != "SMOKE" and smoke_state == "SMOKE":
                if LOGGING_ENABLED:
                    log_pre_smoke_window(
                        long_window,
                        smoke_state,
                        smoke_score,
                        PRE_TRIGGER_LEN,
                        MAX_LOG_FILE_SIZE_MB,
                        LOG_TRIM_TARGET_RATIO
                    )
                handle_environment_event("smoke")

            if smoke_state == "SMOKE" and LOGGING_ENABLED:
                log_smoke_event(
                    measurement["timestamp"],
                    smoke_state,
                    smoke_score,
                    measurement,
                    short_avg,
                    long_avg,
                    short_delta,
                    long_delta,
                    smoke_criteria,
                    MAX_LOG_FILE_SIZE_MB,
                    LOG_TRIM_TARGET_RATIO
                )

            page_data = build_display_page_data(measurement, long_avg, smoke_state, last_smoke_state)

            process_push_notifications(
                page_data,
                alert_states,
                PUSHOVER_ENABLED,
                PUSHOVER_KEYS_FILE,
                PUSHOVER_API_URL,
                PUSHOVER_TIMEOUT_SECONDS,
                PUSHOVER_SMOKE_PRIORITY,
                PUSHOVER_DEFAULT_PRIORITY,
            )

            current_critical_page_name = get_priority_critical_page_name(page_data)

            force_render = False
            critical_transition = False

            if navigation_action == "back":
                current_page_index = (current_page_index - 1) % len(DISPLAY_PAGES)
                last_page_change_time = time.time()
                force_render = True

            elif navigation_action == "next":
                current_page_index = (current_page_index + 1) % len(DISPLAY_PAGES)
                last_page_change_time = time.time()
                force_render = True

            elif current_critical_page_name is not None and current_critical_page_name != last_critical_page_name:
                current_page_index = get_page_index_by_name(current_critical_page_name)
                last_page_change_time = time.time()
                force_render = True
                critical_transition = True

            elif current_critical_page_name is None and (time.time() - last_page_change_time) >= DISPLAY_AUTO_PAGE_SECONDS:
                current_page_index = (current_page_index + 1) % len(DISPLAY_PAGES)
                last_page_change_time = time.time()
                force_render = True

            page_name = DISPLAY_PAGES[current_page_index]["name"]

            if (force_render or page_name != last_rendered_page_name) and DISPLAY_ENABLED:
                render_display_page(page_name, page_data, critical_transition=critical_transition)
                last_rendered_page_name = page_name

            last_critical_page_name = current_critical_page_name
            last_smoke_state = smoke_state

        time.sleep(REFRESH_RATE)

except KeyboardInterrupt:
    print("Programm beendet durch Benutzer.")

finally:
    display.close()
    bus.close()