import csv
import os


LOGS_DIR = "Logs"


def ensure_log_directory_exists():
    os.makedirs(LOGS_DIR, exist_ok=True)


def csv_needs_header(file_name):
    return not os.path.isfile(file_name) or os.path.getsize(file_name) == 0


def trim_csv_if_oversize(file_name, max_log_file_size_mb, log_trim_target_ratio):
    ensure_log_directory_exists()

    if not os.path.isfile(file_name):
        return

    max_bytes = max_log_file_size_mb * 1024 * 1024
    current_size = os.path.getsize(file_name)

    if current_size <= max_bytes:
        return

    target_bytes = int(max_bytes * log_trim_target_ratio)

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

    print(f"Log cleanup: {file_name} exceeded {max_log_file_size_mb} MB, old entries removed.")

    with open(file_name, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(kept_rows)


def append_csv_row(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio):
    ensure_log_directory_exists()
    trim_csv_if_oversize(file_name, max_log_file_size_mb, log_trim_target_ratio)
    needs_header = csv_needs_header(file_name)

    with open(file_name, "a", newline="") as f:
        writer = csv.writer(f)

        if needs_header:
            writer.writerow(header)

        writer.writerow(row)


def append_csv_rows(file_name, header, rows, max_log_file_size_mb, log_trim_target_ratio):
    ensure_log_directory_exists()
    trim_csv_if_oversize(file_name, max_log_file_size_mb, log_trim_target_ratio)
    needs_header = csv_needs_header(file_name)

    with open(file_name, "a", newline="") as f:
        writer = csv.writer(f)

        if needs_header:
            writer.writerow(header)

        writer.writerows(rows)


def log_pre_smoke_window(window_list, smoke_state, smoke_score, pre_trigger_len, max_log_file_size_mb, log_trim_target_ratio):
    file_name = os.path.join(LOGS_DIR, "pre_smoke.csv")
    header = [
        "trigger_timestamp", "trigger_state", "trigger_score",
        "entry_timestamp",
        "pm1_0", "pm2_5", "pm4_0", "pm10",
        "sen55_humidity", "sen55_temperature", "voc", "nox",
        "co2", "scd41_temperature", "scd41_humidity"
    ]

    rows = []
    trigger_timestamp = window_list[-1]["timestamp"]

    for measurement in window_list[-pre_trigger_len:]:
        rows.append([
            trigger_timestamp, smoke_state, smoke_score,
            measurement["timestamp"],
            measurement["pm1_0"], measurement["pm2_5"], measurement["pm4_0"], measurement["pm10"],
            measurement["sen55_humidity"], measurement["sen55_temperature"], measurement["voc"], measurement["nox"],
            measurement["co2"], measurement["scd41_temperature"], measurement["scd41_humidity"]
        ])

    append_csv_rows(file_name, header, rows, max_log_file_size_mb, log_trim_target_ratio)


def log_pre_co2_window(window_list, co2_state, co2_score, pre_trigger_len, max_log_file_size_mb, log_trim_target_ratio):
    file_name = os.path.join(LOGS_DIR, "pre_co2.csv")
    header = [
        "trigger_timestamp", "trigger_state", "trigger_score",
        "entry_timestamp",
        "pm1_0", "pm2_5", "pm4_0", "pm10",
        "sen55_humidity", "sen55_temperature", "voc", "nox",
        "co2", "scd41_temperature", "scd41_humidity"
    ]

    rows = []
    trigger_timestamp = window_list[-1]["timestamp"]

    for measurement in window_list[-pre_trigger_len:]:
        rows.append([
            trigger_timestamp, co2_state, co2_score,
            measurement["timestamp"],
            measurement["pm1_0"], measurement["pm2_5"], measurement["pm4_0"], measurement["pm10"],
            measurement["sen55_humidity"], measurement["sen55_temperature"], measurement["voc"], measurement["nox"],
            measurement["co2"], measurement["scd41_temperature"], measurement["scd41_humidity"]
        ])

    append_csv_rows(file_name, header, rows, max_log_file_size_mb, log_trim_target_ratio)


def log_event(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio):
    append_csv_row(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio)


def log_smoke_event(timestamp, smoke_state, smoke_score, latest_measurement, short_avg, long_avg, short_delta, long_delta, criteria, max_log_file_size_mb, log_trim_target_ratio):
    file_name = os.path.join(LOGS_DIR, "smoke_events.csv")

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

    log_event(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio)


def log_co2_event(timestamp, co2_state, co2_score, latest_measurement, short_avg, long_avg, short_delta, long_delta, criteria, max_log_file_size_mb, log_trim_target_ratio):
    file_name = os.path.join(LOGS_DIR, "co2_events.csv")

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

        "co2_above_800", "co2_above_1000", "co2_above_1200", "co2_above_1500",
        "co2_long_delta_high", "co2_short_delta_high", "co2_short_vs_long"
    ]

    row = [
        timestamp, co2_state, co2_score,
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

        criteria["co2_above_800"], criteria["co2_above_1000"], criteria["co2_above_1200"], criteria["co2_above_1500"],
        criteria["co2_long_delta_high"], criteria["co2_short_delta_high"], criteria["co2_short_vs_long"]
    ]

    log_event(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio)