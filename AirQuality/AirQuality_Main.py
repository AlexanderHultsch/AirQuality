# Cable Setup -------------------------------------------------
# PIN1_VDD_Red____Pin02
# PIN2_GND_Black__Pin09
# PIN3_SDA_Green__Pin03
# PIN4_SCL_Yellow_Pin05
# PIN5_SEL_Blue___Pin14
# PIN6_NC_Purple__No connection

import math
import time
from datetime import datetime, time as dt_time
from smbus2 import SMBus, i2c_msg
from display_manager import DisplayManager
from modules.sensor_reader import build_measurement, start_scd41_periodic_measurement
from modules.analysis import (
    analyze_CO2,
    build_display_page_data,
    create_smoke_detector,
)
from modules.logging_utils import (
    log_pre_smoke_window,
    log_smoke_event,
    log_pre_co2_window,
    log_co2_event,
    log_pre_voc_window,
    log_voc_event,
)
from modules.notifications import (
    process_push_notifications,
    send_pushover_notification,
)
from test_script import (
    TEST_MODE,
    ACTIVE_TEST_SCENARIO,
    TEST_ENABLE_DISPLAY,
    TEST_ENABLE_PUSHOVER,
    TEST_ENABLE_LOGGING,
    get_test_measurement,
)

REFRESH_RATE = 1
PRE_TRIGGER_SECONDS = 30
PRE_TRIGGER_LEN = max(1, math.ceil(PRE_TRIGGER_SECONDS / REFRESH_RATE))

MAX_LOG_FILE_SIZE_MB = 5
LOG_TRIM_TARGET_RATIO = 0.75

LONG_WINDOW_SECONDS = 5 * 60
SHORT_WINDOW_SECONDS = 15

LONG_MAX_LIST_LEN = max(1, math.ceil(LONG_WINDOW_SECONDS / REFRESH_RATE))
SHORT_MAX_LIST_LEN = max(1, math.ceil(SHORT_WINDOW_SECONDS / REFRESH_RATE))

BUS_ID = 1

SEN55_ADDR = 0x69
SCD41_ADDR = 0x62

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

NIGHT_START = dt_time(22, 0)
NIGHT_END = dt_time(7, 0)

CO2_MINUTES_THRESHOLD_1 = 1000
CO2_MINUTES_THRESHOLD_2 = 1200

CO2_EVENT_COOLDOWN_SECONDS = 5 * 60
VOC_LOG_THRESHOLD = 200
VOC_EVENT_COOLDOWN_SECONDS = 10 * 60

long_window = []
short_window = []

bus = SMBus(BUS_ID)
display = DisplayManager(port=DISPLAY_PORT, baudrate=DISPLAY_BAUDRATE, timeout=0.1)

night_stats = {
    "active": False,
    "date_label": None,
    "smoke_suspicious_count": 0,
    "smoke_critical_count": 0,
    "co2_min": None,
    "co2_max": None,
    "co2_sum": 0.0,
    "co2_count": 0,
    "seconds_above_threshold_1": 0,
    "seconds_above_threshold_2": 0,
    "temperature_min": None,
    "temperature_max": None,
    "temperature_sum": 0.0,
    "temperature_count": 0,
    "humidity_min": None,
    "humidity_max": None,
    "humidity_sum": 0.0,
    "humidity_count": 0,
    "voc_min": None,
    "voc_max": None,
    "voc_sum": 0.0,
    "voc_count": 0,
}

last_night_push_label = None


def is_night_time(now_dt):
    current_t = now_dt.time()
    return current_t >= NIGHT_START or current_t < NIGHT_END


def get_night_label(now_dt):
    return now_dt.strftime("%Y-%m-%d")


def reset_night_stats(now_dt):
    night_stats["active"] = True
    night_stats["date_label"] = get_night_label(now_dt)

    night_stats["smoke_suspicious_count"] = 0
    night_stats["smoke_critical_count"] = 0

    night_stats["co2_min"] = None
    night_stats["co2_max"] = None
    night_stats["co2_sum"] = 0.0
    night_stats["co2_count"] = 0
    night_stats["seconds_above_threshold_1"] = 0
    night_stats["seconds_above_threshold_2"] = 0

    night_stats["temperature_min"] = None
    night_stats["temperature_max"] = None
    night_stats["temperature_sum"] = 0.0
    night_stats["temperature_count"] = 0

    night_stats["humidity_min"] = None
    night_stats["humidity_max"] = None
    night_stats["humidity_sum"] = 0.0
    night_stats["humidity_count"] = 0

    night_stats["voc_min"] = None
    night_stats["voc_max"] = None
    night_stats["voc_sum"] = 0.0
    night_stats["voc_count"] = 0


def update_night_stats(measurement):
    co2_value = measurement.get("co2")
    temperature_value = measurement.get("sen55_temperature")
    humidity_value = measurement.get("sen55_humidity")
    voc_value = measurement.get("voc")

    if co2_value is not None:
        if night_stats["co2_min"] is None or co2_value < night_stats["co2_min"]:
            night_stats["co2_min"] = co2_value
        if night_stats["co2_max"] is None or co2_value > night_stats["co2_max"]:
            night_stats["co2_max"] = co2_value

        night_stats["co2_sum"] += co2_value
        night_stats["co2_count"] += 1

        if co2_value > CO2_MINUTES_THRESHOLD_1:
            night_stats["seconds_above_threshold_1"] += REFRESH_RATE
        if co2_value > CO2_MINUTES_THRESHOLD_2:
            night_stats["seconds_above_threshold_2"] += REFRESH_RATE

    if temperature_value is not None:
        if night_stats["temperature_min"] is None or temperature_value < night_stats["temperature_min"]:
            night_stats["temperature_min"] = temperature_value
        if night_stats["temperature_max"] is None or temperature_value > night_stats["temperature_max"]:
            night_stats["temperature_max"] = temperature_value

        night_stats["temperature_sum"] += temperature_value
        night_stats["temperature_count"] += 1

    if humidity_value is not None:
        if night_stats["humidity_min"] is None or humidity_value < night_stats["humidity_min"]:
            night_stats["humidity_min"] = humidity_value
        if night_stats["humidity_max"] is None or humidity_value > night_stats["humidity_max"]:
            night_stats["humidity_max"] = humidity_value

        night_stats["humidity_sum"] += humidity_value
        night_stats["humidity_count"] += 1

    if voc_value is not None:
        if night_stats["voc_min"] is None or voc_value < night_stats["voc_min"]:
            night_stats["voc_min"] = voc_value
        if night_stats["voc_max"] is None or voc_value > night_stats["voc_max"]:
            night_stats["voc_max"] = voc_value

        night_stats["voc_sum"] += voc_value
        night_stats["voc_count"] += 1


def count_night_smoke_transition(last_smoke_state, smoke_state):
    if last_smoke_state != "SUSPICIOUS" and smoke_state == "SUSPICIOUS":
        night_stats["smoke_suspicious_count"] += 1

    if last_smoke_state != "SMOKE" and smoke_state == "SMOKE":
        night_stats["smoke_critical_count"] += 1


def build_night_summary_message():
    def avg_or_na(sum_value, count_value):
        if count_value > 0:
            return round(sum_value / count_value, 1)
        return "n/a"

    def value_or_na(value):
        return value if value is not None else "n/a"

    avg_co2 = avg_or_na(night_stats["co2_sum"], night_stats["co2_count"])
    min_co2 = value_or_na(night_stats["co2_min"])
    max_co2 = value_or_na(night_stats["co2_max"])

    avg_temperature = avg_or_na(night_stats["temperature_sum"], night_stats["temperature_count"])
    min_temperature = value_or_na(night_stats["temperature_min"])
    max_temperature = value_or_na(night_stats["temperature_max"])

    avg_humidity = avg_or_na(night_stats["humidity_sum"], night_stats["humidity_count"])
    min_humidity = value_or_na(night_stats["humidity_min"])
    max_humidity = value_or_na(night_stats["humidity_max"])

    avg_voc = avg_or_na(night_stats["voc_sum"], night_stats["voc_count"])
    min_voc = value_or_na(night_stats["voc_min"])
    max_voc = value_or_na(night_stats["voc_max"])

    minutes_above_1 = round(night_stats["seconds_above_threshold_1"] / 60)
    minutes_above_2 = round(night_stats["seconds_above_threshold_2"] / 60)

    title = f"Nachtbericht {night_stats['date_label']}"
    message = (
        f"CO2\n"
        f"Max: {max_co2} ppm\n"
        f"Min: {min_co2} ppm\n"
        f"Avg: {avg_co2} ppm\n"
        f"> {CO2_MINUTES_THRESHOLD_1}: {minutes_above_1} min\n"
        f"> {CO2_MINUTES_THRESHOLD_2}: {minutes_above_2} min\n"
        f"---\n"
        f"Temperature\n"
        f"Max: {max_temperature} C\n"
        f"Min: {min_temperature} C\n"
        f"Avg: {avg_temperature} C\n"
        f"---\n"
        f"Humidity\n"
        f"Max: {max_humidity} %\n"
        f"Min: {min_humidity} %\n"
        f"Avg: {avg_humidity} %\n"
        f"---\n"
        f"VOC\n"
        f"Max: {max_voc}\n"
        f"Min: {min_voc}\n"
        f"Avg: {avg_voc}\n"
        f"---\n"
        f"Smoke\n"
        f"Suspicious: {night_stats['smoke_suspicious_count']}\n"
        f"Critical: {night_stats['smoke_critical_count']}"
    )
    return title, message


def maybe_handle_night_mode(now_dt, measurement, smoke_state, last_smoke_state):
    global last_night_push_label

    if is_night_time(now_dt):
        current_label = get_night_label(now_dt)

        if not night_stats["active"] or night_stats["date_label"] != current_label:
            reset_night_stats(now_dt)

        count_night_smoke_transition(last_smoke_state, smoke_state)
        update_night_stats(measurement)
        return

    if night_stats["active"] and night_stats["date_label"] != last_night_push_label:
        title, message = build_night_summary_message()

        send_pushover_notification(
            title,
            message,
            PUSHOVER_DEFAULT_PRIORITY,
            PUSHOVER_ENABLED,
            PUSHOVER_KEYS_FILE,
            PUSHOVER_API_URL,
            PUSHOVER_TIMEOUT_SECONDS,
        )

        last_night_push_label = night_stats["date_label"]
        night_stats["active"] = False


def is_display_sleep_time(now_dt):
    return is_night_time(now_dt)


def enter_display_sleep_mode():
    display.goto_page(DisplayManager.PAGE_TEMPERATURE)
    display.apply_normal_theme()
    display.set_text("title", "")
    display.set_text("value", "")
    display.set_text("unit", "")
    display.set_text("status", "")
    display.set_text("trend", "")
    display.set_text("other", "")
    display.set_text("back", "")
    display.set_text("next", "")


def exit_display_sleep_mode():
    pass


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


def handle_environment_event(event_type):
    if event_type == "smoke":
        print("Fenster schließt")
    elif event_type == "co2_ventilate":
        print("Fenster Öffnen Empfohlen")
    elif event_type == "co2_critical":
        print("Fenster öffnen!")


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
    {"name": "pi5_temp", "page_id": DisplayManager.PAGE_PI5_TEMP},
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
    elif page_name == "pi5_temp":
        display.show_pi5_temp_page(content["value"], content["status"], content["trend"], content["other"])

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


def get_measurement(loop_count):
    if TEST_MODE:
        return get_test_measurement(loop_count, ACTIVE_TEST_SCENARIO)
    return build_measurement(bus, SEN55_ADDR, SCD41_ADDR)


def cooldown_expired(last_timestamp, cooldown_seconds):
    if last_timestamp is None:
        return True
    return (time.time() - last_timestamp) >= cooldown_seconds


bus.i2c_rdwr(i2c_msg.write(SEN55_ADDR, [0x00, 0x21]))
print("SEN55 Messung gestartet...")

if not TEST_MODE:
    start_scd41_periodic_measurement(bus, SCD41_ADDR)

time.sleep(1)

last_smoke_state = "CLEAR"
last_co2_state = "GOOD"
last_priority_page_name = None
loop_count = 0

last_co2_event_time = {
    "VENTILATE": None,
    "CRITICAL": None,
}

last_voc_event_time = None

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
    "scd41_humidity",
    "pi5_temp",
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
    "pi5_temp": False,
}

current_page_index = 0
last_page_change_time = time.time()
last_rendered_page_name = None
display_sleep_active = False

smoke_detector = create_smoke_detector()

try:
    while True:
        smoke_state = "CLEAR"
        smoke_score = 0
        smoke_criteria = {}

        co2_state = "GOOD"
        co2_score = 0
        co2_criteria = {}

        now_dt = datetime.now()

        measurement = get_measurement(loop_count)

        if measurement is None:
            print("Noch keine fertigen Daten")
            time.sleep(REFRESH_RATE)
            continue

        should_sleep_display = is_display_sleep_time(now_dt)

        if should_sleep_display and not display_sleep_active and DISPLAY_ENABLED:
            enter_display_sleep_mode()
            display_sleep_active = True
            last_rendered_page_name = None

        elif not should_sleep_display and display_sleep_active and DISPLAY_ENABLED:
            exit_display_sleep_mode()
            display_sleep_active = False
            last_rendered_page_name = None
            last_page_change_time = time.time()

        if not display_sleep_active and DISPLAY_ENABLED:
            touch_event = display.read_touch_event()
            navigation_action = display.interpret_navigation_event(
                touch_event,
                DISPLAY_BACK_COMPONENT_ID,
                DISPLAY_NEXT_COMPONENT_ID
            )
        else:
            navigation_action = None

        loop_count += 1

        update_window(long_window, measurement, LONG_MAX_LIST_LEN)
        update_window(short_window, measurement, SHORT_MAX_LIST_LEN)

        print(str(measurement))

        long_avg, long_delta = calculate_avg_and_delta(long_window, analysis_fields)
        short_avg, short_delta = calculate_avg_and_delta(short_window, analysis_fields)

        if long_avg is not None and short_avg is not None:
            smoke_state, smoke_score, smoke_criteria = smoke_detector.update(
                measurement, long_avg, short_avg, long_delta, short_delta
            )

            co2_state, co2_score, co2_criteria = analyze_CO2(
                measurement, long_avg, short_avg, long_delta, short_delta
            )

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

            if co2_state in ["VENTILATE", "CRITICAL"]:
                if cooldown_expired(last_co2_event_time[co2_state], CO2_EVENT_COOLDOWN_SECONDS):
                    if LOGGING_ENABLED:
                        log_pre_co2_window(
                            long_window,
                            co2_state,
                            co2_score,
                            PRE_TRIGGER_LEN,
                            MAX_LOG_FILE_SIZE_MB,
                            LOG_TRIM_TARGET_RATIO
                        )
                        log_co2_event(
                            measurement["timestamp"],
                            co2_state,
                            co2_score,
                            measurement,
                            short_avg,
                            long_avg,
                            short_delta,
                            long_delta,
                            co2_criteria,
                            MAX_LOG_FILE_SIZE_MB,
                            LOG_TRIM_TARGET_RATIO
                        )
                    last_co2_event_time[co2_state] = time.time()

            if last_co2_state != "VENTILATE" and co2_state == "VENTILATE":
                handle_environment_event("co2_ventilate")

            if last_co2_state != "CRITICAL" and co2_state == "CRITICAL":
                handle_environment_event("co2_critical")

            voc_value = measurement.get("voc")
            if voc_value is not None and voc_value >= VOC_LOG_THRESHOLD:
                if cooldown_expired(last_voc_event_time, VOC_EVENT_COOLDOWN_SECONDS):
                    if LOGGING_ENABLED:
                        log_pre_voc_window(
                            long_window,
                            voc_value,
                            PRE_TRIGGER_LEN,
                            MAX_LOG_FILE_SIZE_MB,
                            LOG_TRIM_TARGET_RATIO
                        )
                        log_voc_event(
                            measurement["timestamp"],
                            measurement,
                            short_avg,
                            long_avg,
                            short_delta,
                            long_delta,
                            MAX_LOG_FILE_SIZE_MB,
                            LOG_TRIM_TARGET_RATIO
                        )
                    last_voc_event_time = time.time()

            page_data = build_display_page_data(
                measurement,
                long_avg,
                smoke_state,
                last_smoke_state,
                co2_state,
            )

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

            if not display_sleep_active:
                current_priority_page_name = get_priority_critical_page_name(page_data)

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

                elif (
                    current_priority_page_name is not None and
                    current_priority_page_name != last_priority_page_name
                ):
                    current_page_index = get_page_index_by_name(current_priority_page_name)
                    last_page_change_time = time.time()
                    force_render = True
                    critical_transition = True

                elif (time.time() - last_page_change_time) >= DISPLAY_AUTO_PAGE_SECONDS:
                    current_page_index = (current_page_index + 1) % len(DISPLAY_PAGES)
                    last_page_change_time = time.time()
                    force_render = True

                page_name = DISPLAY_PAGES[current_page_index]["name"]

                if (force_render or page_name != last_rendered_page_name) and DISPLAY_ENABLED:
                    render_display_page(page_name, page_data, critical_transition=critical_transition)
                    last_rendered_page_name = page_name

                last_priority_page_name = current_priority_page_name

            maybe_handle_night_mode(now_dt, measurement, smoke_state, last_smoke_state)

            last_smoke_state = smoke_state
            last_co2_state = co2_state

        time.sleep(REFRESH_RATE)

except KeyboardInterrupt:
    print("Programm beendet durch Benutzer.")

finally:
    display.close()
    bus.close()