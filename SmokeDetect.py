# Cable Setup -------------------------------------------------
# PIN1_VDD_Red____Pin02
# PIN2_GND_Black__Pin09
# PIN3_SDA_Green__Pin03
# PIN4_SCL_Yellow_Pin05
# PIN5_SEL_Blue___Pin14
# PIN6_NC_Purple__No connection

import time
from smbus2 import SMBus, i2c_msg
from datetime import datetime
import csv
import os
from display_manager import DisplayManager

# ============================================================
# Configuration
# ============================================================

REFRESH_RATE = 1  # seconds
PRE_TRIGGER_SECONDS = 30
PRE_TRIGGER_LEN = int(PRE_TRIGGER_SECONDS / REFRESH_RATE)

DEBUG_TRIGGER_ENABLED = True
DEBUG_TRIGGER_AFTER_LOOPS = 2

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

long_window = []
short_window = []

bus = SMBus(BUS_ID)
display = DisplayManager(port=DISPLAY_PORT, baudrate=DISPLAY_BAUDRATE, timeout=0.1)


# ============================================================
# Sensor Read Functions
# ============================================================

def read_sen55_data():
    """
    Reads data from the existing PM / VOC / NOX sensor.
    Returns a dict or None if data is not ready.
    """
    bus.i2c_rdwr(i2c_msg.write(SEN55_ADDR, [0x02, 0x02]))
    time.sleep(0.01)

    ready = i2c_msg.read(SEN55_ADDR, 3)
    bus.i2c_rdwr(ready)
    r = list(ready)

    if ((r[0] << 8) | r[1]) == 1:
        bus.i2c_rdwr(i2c_msg.write(SEN55_ADDR, [0x03, 0xC4]))
        time.sleep(0.01)

        data = i2c_msg.read(SEN55_ADDR, 24)
        bus.i2c_rdwr(data)
        d = list(data)

        return {
            "pm1_0": round(((d[0] << 8) | d[1]) / 10.0, 1),
            "pm2_5": round(((d[3] << 8) | d[4]) / 10.0, 1),
            "pm4_0": round(((d[6] << 8) | d[7]) / 10.0, 1),
            "pm10": round(((d[9] << 8) | d[10]) / 10.0, 1),
            "sen55_humidity": round(((d[12] << 8) | d[13]) / 100.0, 1),
            "sen55_temperature": round(((d[15] << 8) | d[16]) / 200.0, 1),
            "voc": round(((d[18] << 8) | d[19]) / 10.0, 1),
            "nox": round(((d[21] << 8) | d[22]) / 10.0, 1),
        }

    return None


def read_scd41_data():
    """
    Placeholder for future SCD41 integration.
    Returns a dict with reserved fields.
    """
    return {
        "co2": None,
        "scd41_temperature": None,
        "scd41_humidity": None,
    }


def build_measurement():
    """
    Reads all available sensors and returns one merged measurement dict.
    Returns None if the primary sensor has no new data yet.
    """
    sen55_data = read_sen55_data()
    if sen55_data is None:
        return None

    scd41_data = read_scd41_data()

    measurement = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **sen55_data,
        **scd41_data,
    }

    return measurement


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
# Analysis Functions
# ============================================================

def analyze_smoke(latest_measurement, long_avg, short_avg, long_delta, short_delta):
    pm1_0 = latest_measurement["pm1_0"]
    pm2_5 = latest_measurement["pm2_5"]

    long_avg_pm1_0 = long_avg["pm1_0"]
    long_avg_pm2_5 = long_avg["pm2_5"]

    short_avg_pm2_5 = short_avg["pm2_5"]

    long_delta_pm1_0 = long_delta["pm1_0"]
    long_delta_pm2_5 = long_delta["pm2_5"]

    if pm2_5 > 12:
        pm_ratio_value = pm1_0 / pm2_5
    else:
        pm_ratio_value = 0

    criteria = {
        "pm2_5_abs": pm2_5 > 12 or pm1_0 > 10,
        "pm2_5_long_delta": long_delta_pm2_5 is not None and long_delta_pm2_5 > 3.0,
        "pm1_0_long_delta": long_delta_pm1_0 is not None and long_delta_pm1_0 > 3.0,
        "pm2_5_spike": long_avg_pm2_5 is not None and pm2_5 > long_avg_pm2_5 * 1.45,
        "pm1_0_spike": long_avg_pm1_0 is not None and pm1_0 > long_avg_pm1_0 * 1.45,
        "pm2_5_short_vs_long": (
            short_avg_pm2_5 is not None and
            long_avg_pm2_5 is not None and
            short_avg_pm2_5 > long_avg_pm2_5 * 1.20
        ),
        "pm_ratio": pm2_5 > 12 and pm_ratio_value > 0.92,
        "voc_spike": False
    }

    strong_signals = sum([
        criteria["pm2_5_long_delta"],
        criteria["pm1_0_long_delta"],
        criteria["pm2_5_spike"],
        criteria["pm1_0_spike"]
    ])

    trend_signals = sum([
        criteria["pm2_5_short_vs_long"]
    ])

    support_signals = sum([
        criteria["pm_ratio"]
    ])

    if not criteria["pm2_5_abs"]:
        smoke_state = "CLEAR"
    elif strong_signals >= 2:
        smoke_state = "SMOKE"
    elif strong_signals >= 1 and trend_signals >= 1:
        smoke_state = "SMOKE"
    elif strong_signals >= 1:
        smoke_state = "SUSPICIOUS"
    elif trend_signals >= 1 and support_signals >= 1:
        smoke_state = "SUSPICIOUS"
    else:
        smoke_state = "CLEAR"

    smoke_score = strong_signals * 2 + trend_signals + support_signals

    return smoke_state, smoke_score, criteria


def analyze_CO2(latest_measurement, long_avg, short_avg, long_delta, short_delta):
    """
    Placeholder for future CO2 analysis.
    """
    return None, None, {}


# ============================================================
# Logging Helpers
# ============================================================

def csv_needs_header(file_name):
    return not os.path.isfile(file_name) or os.path.getsize(file_name) == 0


def trim_csv_if_oversize(file_name):
    if not os.path.isfile(file_name):
        return

    max_bytes = MAX_LOG_FILE_SIZE_MB * 1024 * 1024
    current_size = os.path.getsize(file_name)

    if current_size <= max_bytes:
        return

    target_bytes = int(max_bytes * LOG_TRIM_TARGET_RATIO)

    with open(file_name, "r", newline="") as f:
        rows = list(csv.reader(f))

    if not rows:
        return

    header = rows[0]
    data_rows = rows[1:]

    if not data_rows:
        with open(file_name, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
        return

    kept_rows = []
    kept_size_estimate = 0

    for row in reversed(data_rows):
        row_size = len(",".join(row)) + 1
        if kept_size_estimate + row_size > target_bytes and kept_rows:
            break
        kept_rows.append(row)
        kept_size_estimate += row_size

    kept_rows.reverse()

    print(f"Log cleanup: {file_name} exceeded {MAX_LOG_FILE_SIZE_MB} MB, old entries removed.")

    with open(file_name, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(kept_rows)


def append_csv_row(file_name, header, row):
    trim_csv_if_oversize(file_name)
    needs_header = csv_needs_header(file_name)

    with open(file_name, "a", newline="") as f:
        writer = csv.writer(f)

        if needs_header:
            writer.writerow(header)

        writer.writerow(row)


def append_csv_rows(file_name, header, rows):
    trim_csv_if_oversize(file_name)
    needs_header = csv_needs_header(file_name)

    with open(file_name, "a", newline="") as f:
        writer = csv.writer(f)

        if needs_header:
            writer.writerow(header)

        writer.writerows(rows)


def log_pre_smoke_window(window_list, smoke_state, smoke_score):
    file_name = "pre_smoke_log.csv"
    header = [
        "trigger_timestamp", "trigger_state", "trigger_score",
        "entry_timestamp",
        "pm1_0", "pm2_5", "pm4_0", "pm10",
        "sen55_humidity", "sen55_temperature", "voc", "nox",
        "co2", "scd41_temperature", "scd41_humidity"
    ]

    rows = []
    trigger_timestamp = window_list[-1]["timestamp"]

    for measurement in window_list[-PRE_TRIGGER_LEN:]:
        rows.append([
            trigger_timestamp, smoke_state, smoke_score,
            measurement["timestamp"],
            measurement["pm1_0"], measurement["pm2_5"], measurement["pm4_0"], measurement["pm10"],
            measurement["sen55_humidity"], measurement["sen55_temperature"], measurement["voc"], measurement["nox"],
            measurement["co2"], measurement["scd41_temperature"], measurement["scd41_humidity"]
        ])

    append_csv_rows(file_name, header, rows)


def log_event(file_name, header, row):
    append_csv_row(file_name, header, row)


def log_smoke_event(timestamp, smoke_state, smoke_score, latest_measurement, short_avg, long_avg, short_delta, long_delta, criteria):
    file_name = "Smoke.csv"

    if latest_measurement["pm2_5"] > 0:
        pm_ratio_value = round(latest_measurement["pm1_0"] / latest_measurement["pm2_5"], 2)
    else:
        pm_ratio_value = 0

    header = [
        "timestamp", "state", "score",
        "pm1_0", "pm2_5", "pm4_0", "pm10",
        "sen55_humidity", "sen55_temperature", "voc", "nox",
        "co2", "scd41_temperature", "scd41_humidity",

        "short_avg_pm1_0", "short_avg_pm2_5", "short_avg_pm4_0", "short_avg_pm10",
        "short_avg_sen55_humidity", "short_avg_sen55_temperature", "short_avg_voc", "short_avg_nox",
        "short_avg_co2", "short_avg_scd41_temperature", "short_avg_scd41_humidity",

        "short_delta_pm1_0", "short_delta_pm2_5", "short_delta_pm4_0", "short_delta_pm10",
        "short_delta_sen55_humidity", "short_delta_sen55_temperature", "short_delta_voc", "short_delta_nox",
        "short_delta_co2", "short_delta_scd41_temperature", "short_delta_scd41_humidity",

        "long_avg_pm1_0", "long_avg_pm2_5", "long_avg_pm4_0", "long_avg_PM10",
        "long_avg_sen55_humidity", "long_avg_sen55_temperature", "long_avg_voc", "long_avg_nox",
        "long_avg_co2", "long_avg_scd41_temperature", "long_avg_scd41_humidity",

        "long_delta_pm1_0", "long_delta_pm2_5", "long_delta_pm4_0", "long_delta_pm10",
        "long_delta_sen55_humidity", "long_delta_sen55_temperature", "long_delta_voc", "long_delta_nox",
        "long_delta_co2", "long_delta_scd41_temperature", "long_delta_scd41_humidity",

        "pm2_5_abs", "pm2_5_long_delta", "pm1_0_long_delta", "pm2_5_spike",
        "pm1_0_spike", "pm2_5_short_vs_long", "pm_ratio_criteria", "voc_spike",
        "pm_ratio"
    ]

    row = [
        timestamp, smoke_state, smoke_score,
        latest_measurement["pm1_0"], latest_measurement["pm2_5"], latest_measurement["pm4_0"], latest_measurement["pm10"],
        latest_measurement["sen55_humidity"], latest_measurement["sen55_temperature"], latest_measurement["voc"], latest_measurement["nox"],
        latest_measurement["co2"], latest_measurement["scd41_temperature"], latest_measurement["scd41_humidity"],

        short_avg["pm1_0"], short_avg["pm2_5"], short_avg["pm4_0"], short_avg["pm10"],
        short_avg["sen55_humidity"], short_avg["sen55_temperature"], short_avg["voc"], short_avg["nox"],
        short_avg["co2"], short_avg["scd41_temperature"], short_avg["scd41_humidity"],

        short_delta["pm1_0"], short_delta["pm2_5"], short_delta["pm4_0"], short_delta["pm10"],
        short_delta["sen55_humidity"], short_delta["sen55_temperature"], short_delta["voc"], short_delta["nox"],
        short_delta["co2"], short_delta["scd41_temperature"], short_delta["scd41_humidity"],

        long_avg["pm1_0"], long_avg["pm2_5"], long_avg["pm4_0"], long_avg["pm10"],
        long_avg["sen55_humidity"], long_avg["sen55_temperature"], long_avg["voc"], long_avg["nox"],
        long_avg["co2"], long_avg["scd41_temperature"], long_avg["scd41_humidity"],

        long_delta["pm1_0"], long_delta["pm2_5"], long_delta["pm4_0"], long_delta["pm10"],
        long_delta["sen55_humidity"], long_delta["sen55_temperature"], long_delta["voc"], long_delta["nox"],
        long_delta["co2"], long_delta["scd41_temperature"], long_delta["scd41_humidity"],

        criteria["pm2_5_abs"], criteria["pm2_5_long_delta"], criteria["pm1_0_long_delta"], criteria["pm2_5_spike"],
        criteria["pm1_0_spike"], criteria["pm2_5_short_vs_long"], criteria["pm_ratio"], criteria["voc_spike"],
        pm_ratio_value
    ]

    log_event(file_name, header, row)


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


def classify_temperature(value):
    if value is None:
        return "Error", "Sensor error"
    if value <= 15 or value >= 30:
        return "Critical", ""
    if value <= 18 or value >= 27:
        return "Elevated", ""
    return "Good", ""


def classify_humidity(value):
    if value is None:
        return "Error", "Sensor error"
    if value < 25 or value > 70:
        return "Critical", ""
    if value < 35 or value > 60:
        return "Elevated", ""
    return "Good", ""

def classify_co2(value):
    if value is None:
        return "Error", "No sensor"
    if value >= 2000:
        return "Critical", "Air quality"
    if value >= 1000:
        return "Elevated", "Air quality"
    return "Good", "Air quality"


def classify_pm1_0(value):
    if value is None:
        return "Error", "Sensor error"
    if value >= 25:
        return "Critical", "Fine dust"
    if value >= 10:
        return "Elevated", "Fine dust"
    return "Good", "Fine dust"


def classify_pm2_5(value):
    if value is None:
        return "Error", "Sensor error"
    if value >= 35:
        return "Critical", "Particles"
    if value >= 12:
        return "Elevated", "Particles"
    return "Good", "Particles"


def classify_pm4_0(value):
    if value is None:
        return "Error", "Sensor error"
    if value >= 35:
        return "Critical", "Mid dust"
    if value >= 15:
        return "Elevated", "Mid dust"
    return "Good", "Mid dust"


def classify_pm10(value):
    if value is None:
        return "Error", "Sensor error"
    if value >= 50:
        return "Critical", "Coarse dust"
    if value >= 20:
        return "Elevated", "Coarse dust"
    return "Good", "Coarse dust"


def classify_voc(value):
    if value is None:
        return "Error", "Sensor error"
    if value >= 300:
        return "Critical", "Air gases"
    if value >= 150:
        return "Elevated", "Air gases"
    return "Good", "Air gases"


def classify_nox(value):
    if value is None:
        return "Error", "Sensor error"
    if value >= 300:
        return "Critical", "Exhaust"
    if value >= 150:
        return "Elevated", "Exhaust"
    return "Good", "Exhaust"


def classify_smoke_display(smoke_state):
    if smoke_state == "SMOKE":
        return "Critical", ""
    if smoke_state == "SUSPICIOUS":
        return "Elevated", ""
    if smoke_state == "CLEAR":
        return "Good", ""
    return "Error", "State error"


def get_numeric_trend(current_value, baseline_value, threshold):
    if current_value is None or baseline_value is None:
        return ""

    delta = current_value - baseline_value

    if delta > threshold:
        return "Rising"
    if delta < -threshold:
        return "Falling"
    return "Stable"


def get_smoke_trend(current_smoke_state, last_smoke_state):
    if current_smoke_state == "SMOKE":
        if last_smoke_state == "SMOKE":
            return "Stable"
        return "Rising"

    if current_smoke_state == "SUSPICIOUS":
        if last_smoke_state == "SMOKE":
            return "Falling"
        if last_smoke_state == "SUSPICIOUS":
            return "Stable"
        return "Rising"

    if current_smoke_state == "CLEAR":
        if last_smoke_state in ["SMOKE", "SUSPICIOUS"]:
            return "Falling"
        return "Stable"

    return ""


def format_display_value(value):
    if value is None:
        return "Error"
    return str(value)


def build_display_page_data(measurement, long_avg, smoke_state, last_smoke_state):
    temperature_status, temperature_other = classify_temperature(measurement["sen55_temperature"])
    humidity_status, humidity_other = classify_humidity(measurement["sen55_humidity"])
    co2_status, co2_other = classify_co2(measurement["co2"])
    smoke_status, smoke_other = classify_smoke_display(smoke_state)

    pm1_0_status, pm1_0_other = classify_pm1_0(measurement["pm1_0"])
    pm2_5_status, pm2_5_other = classify_pm2_5(measurement["pm2_5"])
    pm4_0_status, pm4_0_other = classify_pm4_0(measurement["pm4_0"])
    pm10_status, pm10_other = classify_pm10(measurement["pm10"])
    voc_status, voc_other = classify_voc(measurement["voc"])
    nox_status, nox_other = classify_nox(measurement["nox"])

    page_data = {
        "temperature": {
            "title": "Temperature",
            "value": format_display_value(measurement["sen55_temperature"]),
            "unit": "C",
            "status": temperature_status,
            "trend": get_numeric_trend(measurement["sen55_temperature"], long_avg["sen55_temperature"], 0.5),
            "other": temperature_other,
            "critical": temperature_status == "Critical",
        },
        "humidity": {
            "title": "Humidity",
            "value": format_display_value(measurement["sen55_humidity"]),
            "unit": "%",
            "status": humidity_status,
            "trend": get_numeric_trend(measurement["sen55_humidity"], long_avg["sen55_humidity"], 3.0),
            "other": humidity_other,
            "critical": humidity_status == "Critical",
        },
        "co2": {
        "title": "CO2",
        "value": format_display_value(measurement["co2"]),
        "unit": "ppm",
        "status": co2_status,
        "trend": get_numeric_trend(measurement["co2"], long_avg["co2"], 100.0),
        "other": co2_other,
        "critical": co2_status == "Critical",
        },
        "smoke": {
            "title": "Smoke",
            "value": smoke_state if smoke_state else "Error",
            "unit": "",
            "status": smoke_status,
            "trend": get_smoke_trend(smoke_state, last_smoke_state),
            "other": smoke_other,
            "critical": smoke_status == "Critical",
        },
        "pm1_0": {
            "title": "PM1.0",
            "value": format_display_value(measurement["pm1_0"]),
            "unit": "ug/m3",
            "status": pm1_0_status,
            "trend": get_numeric_trend(measurement["pm1_0"], long_avg["pm1_0"], 2.0),
            "other": pm1_0_other,
            "critical": pm1_0_status == "Critical",
        },
        "pm2_5": {
            "title": "PM2.5",
            "value": format_display_value(measurement["pm2_5"]),
            "unit": "ug/m3",
            "status": pm2_5_status,
            "trend": get_numeric_trend(measurement["pm2_5"], long_avg["pm2_5"], 2.0),
            "other": pm2_5_other,
            "critical": pm2_5_status == "Critical",
        },
        "pm4_0": {
            "title": "PM4.0",
            "value": format_display_value(measurement["pm4_0"]),
            "unit": "ug/m3",
            "status": pm4_0_status,
            "trend": get_numeric_trend(measurement["pm4_0"], long_avg["pm4_0"], 2.0),
            "other": pm4_0_other,
            "critical": pm4_0_status == "Critical",
        },
        "pm10": {
            "title": "PM10",
            "value": format_display_value(measurement["pm10"]),
            "unit": "ug/m3",
            "status": pm10_status,
            "trend": get_numeric_trend(measurement["pm10"], long_avg["pm10"], 2.0),
            "other": pm10_other,
            "critical": pm10_status == "Critical",
        },
        "voc": {
            "title": "VOC",
            "value": format_display_value(measurement["voc"]),
            "unit": "index",
            "status": voc_status,
            "trend": get_numeric_trend(measurement["voc"], long_avg["voc"], 20.0),
            "other": voc_other,
            "critical": voc_status == "Critical",
        },
        "nox": {
            "title": "NOX",
            "value": format_display_value(measurement["nox"]),
            "unit": "index",
            "status": nox_status,
            "trend": get_numeric_trend(measurement["nox"], long_avg["nox"], 20.0),
            "other": nox_other,
            "critical": nox_status == "Critical",
        },
    }

    return page_data


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


# ============================================================
# Main
# ============================================================

# Start SEN55 measurement: 0x0021
bus.i2c_rdwr(i2c_msg.write(SEN55_ADDR, [0x00, 0x21]))
print("Messung gestartet...")
time.sleep(1)

last_smoke_state = "CLEAR"
debug_loop_count = 0

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

        measurement = build_measurement()

        if measurement is None:
            print("Noch keine fertigen Daten")
            time.sleep(REFRESH_RATE)
            continue

        debug_loop_count += 1

        update_window(long_window, measurement, LONG_MAX_LIST_LEN)
        update_window(short_window, measurement, SHORT_MAX_LIST_LEN)

        print(str(measurement))

        long_avg, long_delta = calculate_avg_and_delta(long_window, analysis_fields)
        short_avg, short_delta = calculate_avg_and_delta(short_window, analysis_fields)

        if long_avg is not None and short_avg is not None:
            if DEBUG_TRIGGER_ENABLED and debug_loop_count >= DEBUG_TRIGGER_AFTER_LOOPS:
                smoke_state = "SMOKE"
                smoke_score = 999
                smoke_criteria = {
                    "pm2_5_abs": True,
                    "pm2_5_long_delta": True,
                    "pm1_0_long_delta": True,
                    "pm2_5_spike": True,
                    "pm1_0_spike": True,
                    "pm2_5_short_vs_long": True,
                    "pm_ratio": True,
                    "voc_spike": False
                }
                DEBUG_TRIGGER_ENABLED = False
            else:
                smoke_state, smoke_score, smoke_criteria = analyze_smoke(
                    measurement, long_avg, short_avg, long_delta, short_delta
                )

            print("smoke_state:", smoke_state)
            print("smoke_score:", smoke_score)

            if last_smoke_state != "SMOKE" and smoke_state == "SMOKE":
                log_pre_smoke_window(long_window, smoke_state, smoke_score)
                handle_environment_event("smoke")

            if smoke_state == "SMOKE":
                log_smoke_event(
                    measurement["timestamp"],
                    smoke_state,
                    smoke_score,
                    measurement,
                    short_avg,
                    long_avg,
                    short_delta,
                    long_delta,
                    smoke_criteria
                )

            page_data = build_display_page_data(measurement, long_avg, smoke_state, last_smoke_state)

            current_critical_page_name = None
            for page in DISPLAY_PAGES:
                if page_data[page["name"]]["critical"]:
                    current_critical_page_name = page["name"]
                    break

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

            if force_render or page_name != last_rendered_page_name:
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