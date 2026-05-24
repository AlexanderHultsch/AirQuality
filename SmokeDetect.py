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

# ============================================================
# Configuration
# ============================================================

REFRESH_RATE = 1  # seconds
PRE_TRIGGER_SECONDS = 30
PRE_TRIGGER_LEN = int(PRE_TRIGGER_SECONDS / REFRESH_RATE)

DEBUG_TRIGGER_ENABLED = True
DEBUG_TRIGGER_AFTER_LOOPS = 2

MAX_LOG_FILE_SIZE_MB = 5 # Max size of Logs
LOG_TRIM_TARGET_RATIO = 0.75  # after trimming, keep about 75% of max size

LONG_WINDOW_SECONDS = 5 * 60
SHORT_WINDOW_SECONDS = 15

LONG_MAX_LIST_LEN = int(LONG_WINDOW_SECONDS / REFRESH_RATE)
SHORT_MAX_LIST_LEN = int(SHORT_WINDOW_SECONDS / REFRESH_RATE)

BUS_ID = 1

SEN55_ADDR = 0x69
SCD41_ADDR = 0x62  # Placeholder address for future integration

long_window = []
short_window = []

bus = SMBus(BUS_ID)


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

        "long_avg_pm1_0", "long_avg_pm2_5", "long_avg_pm4_0", "long_avg_pm10",
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

while True:
    smoke_state = "CLEAR"
    smoke_score = 0
    smoke_criteria = {}

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

        last_smoke_state = smoke_state

    time.sleep(REFRESH_RATE)