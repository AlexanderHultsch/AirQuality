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

    with open(file_name, "r", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    if not rows:
        return

    header = rows[0]
    data_rows = rows[1:]

    if not data_rows:
        with open(file_name, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
        return

    kept_rows = []
    kept_size_estimate = len(",".join(header)) + 1

    for row in reversed(data_rows):
        row_size = len(",".join("" if value is None else str(value) for value in row)) + 1
        if kept_rows and (kept_size_estimate + row_size > target_bytes):
            break
        kept_rows.append(row)
        kept_size_estimate += row_size

    kept_rows.reverse()

    print(f"Log cleanup: {file_name} exceeded {max_log_file_size_mb} MB, old entries removed.")

    with open(file_name, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(kept_rows)


def append_csv_row(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio):
    ensure_log_directory_exists()
    trim_csv_if_oversize(file_name, max_log_file_size_mb, log_trim_target_ratio)
    needs_header = csv_needs_header(file_name)

    with open(file_name, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if needs_header:
            writer.writerow(header)

        writer.writerow(row)


def append_csv_rows(file_name, header, rows, max_log_file_size_mb, log_trim_target_ratio):
    if not rows:
        return

    ensure_log_directory_exists()
    trim_csv_if_oversize(file_name, max_log_file_size_mb, log_trim_target_ratio)
    needs_header = csv_needs_header(file_name)

    with open(file_name, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if needs_header:
            writer.writerow(header)

        writer.writerows(rows)


def log_event(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio):
    append_csv_row(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio)


def _measurement_row(measurement):
    return [
        measurement.get("pm1_0"),
        measurement.get("pm2_5"),
        measurement.get("pm4_0"),
        measurement.get("pm10"),
        measurement.get("sen55_humidity"),
        measurement.get("sen55_temperature"),
        measurement.get("voc"),
        measurement.get("nox"),
        measurement.get("co2"),
        measurement.get("scd41_temperature"),
        measurement.get("scd41_humidity"),
        measurement.get("pi5_temp"),
    ]


def _measurement_header():
    return [
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


def _averages_row(values):
    return [
        values.get("pm1_0"),
        values.get("pm2_5"),
        values.get("pm4_0"),
        values.get("pm10"),
        values.get("sen55_humidity"),
        values.get("sen55_temperature"),
        values.get("voc"),
        values.get("nox"),
        values.get("co2"),
        values.get("scd41_temperature"),
        values.get("scd41_humidity"),
        values.get("pi5_temp"),
    ]


def _averages_header(prefix):
    return [
        f"{prefix}_pm1_0",
        f"{prefix}_pm2_5",
        f"{prefix}_pm4_0",
        f"{prefix}_pm10",
        f"{prefix}_sen55_humidity",
        f"{prefix}_sen55_temperature",
        f"{prefix}_voc",
        f"{prefix}_nox",
        f"{prefix}_co2",
        f"{prefix}_scd41_temperature",
        f"{prefix}_scd41_humidity",
        f"{prefix}_pi5_temp",
    ]


def log_pre_smoke_window(window_list, smoke_state, smoke_score, pre_trigger_len, max_log_file_size_mb, log_trim_target_ratio):
    if not window_list:
        return

    file_name = os.path.join(LOGS_DIR, "pre_smoke.csv")
    header = [
        "trigger_timestamp",
        "trigger_state",
        "trigger_score",
        "entry_timestamp",
        *_measurement_header(),
    ]

    rows = []
    trigger_timestamp = window_list[-1]["timestamp"]

    for measurement in window_list[-pre_trigger_len:]:
        rows.append([
            trigger_timestamp,
            smoke_state,
            smoke_score,
            measurement.get("timestamp"),
            *_measurement_row(measurement),
        ])

    append_csv_rows(file_name, header, rows, max_log_file_size_mb, log_trim_target_ratio)


def log_pre_co2_window(window_list, co2_state, co2_score, pre_trigger_len, max_log_file_size_mb, log_trim_target_ratio):
    if not window_list:
        return

    file_name = os.path.join(LOGS_DIR, "pre_co2.csv")
    header = [
        "trigger_timestamp",
        "trigger_state",
        "trigger_score",
        "entry_timestamp",
        *_measurement_header(),
    ]

    rows = []
    trigger_timestamp = window_list[-1]["timestamp"]

    for measurement in window_list[-pre_trigger_len:]:
        rows.append([
            trigger_timestamp,
            co2_state,
            co2_score,
            measurement.get("timestamp"),
            *_measurement_row(measurement),
        ])

    append_csv_rows(file_name, header, rows, max_log_file_size_mb, log_trim_target_ratio)


def log_pre_voc_window(window_list, trigger_value, pre_trigger_len, max_log_file_size_mb, log_trim_target_ratio):
    if not window_list:
        return

    file_name = os.path.join(LOGS_DIR, "pre_voc.csv")
    header = [
        "trigger_timestamp",
        "trigger_value",
        "entry_timestamp",
        *_measurement_header(),
    ]

    rows = []
    trigger_timestamp = window_list[-1]["timestamp"]

    for measurement in window_list[-pre_trigger_len:]:
        rows.append([
            trigger_timestamp,
            trigger_value,
            measurement.get("timestamp"),
            *_measurement_row(measurement),
        ])

    append_csv_rows(file_name, header, rows, max_log_file_size_mb, log_trim_target_ratio)


def log_smoke_event(
    timestamp,
    smoke_state,
    smoke_score,
    latest_measurement,
    short_avg,
    long_avg,
    short_delta,
    long_delta,
    criteria,
    max_log_file_size_mb,
    log_trim_target_ratio,
):
    file_name = os.path.join(LOGS_DIR, "smoke_events.csv")

    header = [
        "timestamp",
        "state",
        "score",
        *_measurement_header(),
        *_averages_header("short_avg"),
        *_averages_header("short_delta"),
        *_averages_header("long_avg"),
        *_averages_header("long_delta"),
        "pm1_vs_pm25_ratio",
        "pm25_vs_pm10_ratio",
        "rel_pm1_long",
        "rel_pm25_long",
        "rel_voc_long",
        "pm_present_suspicious",
        "pm_present_smoke",
        "pm_long_rise_suspicious",
        "pm_long_rise_smoke",
        "pm_short_rise_suspicious",
        "pm_short_rise_smoke",
        "pm_relative_suspicious",
        "pm_relative_smoke",
        "fine_particle_profile",
        "very_fine_particle_profile",
        "voc_support_light",
        "voc_support_strong",
        "voc_without_pm",
        "coarse_particle_hint",
        "co2_only_hint",
        "suspicious_score",
        "smoke_score_detected",
        "probable_smoke",
        "strong_smoke",
        "falling_back_to_clear",
        "detector_state",
        "suspicious_hold",
        "smoke_hold",
        "clear_hold",
    ]

    row = [
        timestamp,
        smoke_state,
        smoke_score,
        *_measurement_row(latest_measurement),
        *_averages_row(short_avg),
        *_averages_row(short_delta),
        *_averages_row(long_avg),
        *_averages_row(long_delta),
        criteria.get("pm1_vs_pm25_ratio"),
        criteria.get("pm25_vs_pm10_ratio"),
        criteria.get("rel_pm1_long"),
        criteria.get("rel_pm25_long"),
        criteria.get("rel_voc_long"),
        criteria.get("pm_present_suspicious"),
        criteria.get("pm_present_smoke"),
        criteria.get("pm_long_rise_suspicious"),
        criteria.get("pm_long_rise_smoke"),
        criteria.get("pm_short_rise_suspicious"),
        criteria.get("pm_short_rise_smoke"),
        criteria.get("pm_relative_suspicious"),
        criteria.get("pm_relative_smoke"),
        criteria.get("fine_particle_profile"),
        criteria.get("very_fine_particle_profile"),
        criteria.get("voc_support_light"),
        criteria.get("voc_support_strong"),
        criteria.get("voc_without_pm"),
        criteria.get("coarse_particle_hint"),
        criteria.get("co2_only_hint"),
        criteria.get("suspicious_score"),
        criteria.get("smoke_score"),
        criteria.get("probable_smoke"),
        criteria.get("strong_smoke"),
        criteria.get("falling_back_to_clear"),
        criteria.get("state"),
        criteria.get("suspicious_hold"),
        criteria.get("smoke_hold"),
        criteria.get("clear_hold"),
    ]

    log_event(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio)


def log_co2_event(
    timestamp,
    co2_state,
    co2_score,
    latest_measurement,
    short_avg,
    long_avg,
    short_delta,
    long_delta,
    criteria,
    max_log_file_size_mb,
    log_trim_target_ratio,
):
    file_name = os.path.join(LOGS_DIR, "co2_events.csv")

    header = [
        "timestamp",
        "state",
        "score",
        *_measurement_header(),
        *_averages_header("short_avg"),
        *_averages_header("short_delta"),
        *_averages_header("long_avg"),
        *_averages_header("long_delta"),
        "co2_abs_1000",
        "co2_abs_1200",
        "co2_abs_1500",
        "co2_long_delta_150",
        "co2_short_delta_80",
    ]

    row = [
        timestamp,
        co2_state,
        co2_score,
        *_measurement_row(latest_measurement),
        *_averages_row(short_avg),
        *_averages_row(short_delta),
        *_averages_row(long_avg),
        *_averages_row(long_delta),
        criteria.get("co2_abs_1000"),
        criteria.get("co2_abs_1200"),
        criteria.get("co2_abs_1500"),
        criteria.get("co2_long_delta_150"),
        criteria.get("co2_short_delta_80"),
    ]

    log_event(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio)


def log_voc_event(timestamp, latest_measurement, short_avg, long_avg, short_delta, long_delta, max_log_file_size_mb, log_trim_target_ratio):
    file_name = os.path.join(LOGS_DIR, "voc_events.csv")
    header = [
        "timestamp",
        *_measurement_header(),
        *_averages_header("short_avg"),
        *_averages_header("short_delta"),
        *_averages_header("long_avg"),
        *_averages_header("long_delta"),
    ]

    row = [
        timestamp,
        *_measurement_row(latest_measurement),
        *_averages_row(short_avg),
        *_averages_row(short_delta),
        *_averages_row(long_avg),
        *_averages_row(long_delta),
    ]

    log_event(file_name, header, row, max_log_file_size_mb, log_trim_target_ratio)