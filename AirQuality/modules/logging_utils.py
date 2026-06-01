import csv
from pathlib import Path


def _append_dict_row(filename, fieldnames, row, max_log_file_size_mb, log_trim_target_ratio):
    project_dir = Path(__file__).resolve().parent.parent
    file_path = project_dir / filename

    file_exists = file_path.exists()

    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def log_pre_voc_window(
    long_window,
    trigger_state,
    trigger_value,
    pre_trigger_len,
    max_log_file_size_mb,
    log_trim_target_ratio
):
    fieldnames = [
        "trigger_timestamp",
        "trigger_state",
        "trigger_value",
        "entry_timestamp",
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

    for entry in long_window[-pre_trigger_len:]:
        row = {
            "trigger_timestamp": entry.get("timestamp"),
            "trigger_state": trigger_state,
            "trigger_value": trigger_value,
            "entry_timestamp": entry.get("timestamp"),
            "pm1_0": entry.get("pm1_0"),
            "pm2_5": entry.get("pm2_5"),
            "pm4_0": entry.get("pm4_0"),
            "pm10": entry.get("pm10"),
            "sen55_humidity": entry.get("sen55_humidity"),
            "sen55_temperature": entry.get("sen55_temperature"),
            "voc": entry.get("voc"),
            "nox": entry.get("nox"),
            "co2": entry.get("co2"),
            "scd41_temperature": entry.get("scd41_temperature"),
            "scd41_humidity": entry.get("scd41_humidity"),
            "pi5_temp": entry.get("pi5_temp"),
        }
        _append_dict_row("pre_voc.csv", fieldnames, row, max_log_file_size_mb, log_trim_target_ratio)


def log_voc_event(
    timestamp,
    measurement,
    short_avg,
    long_avg,
    short_delta,
    long_delta,
    max_log_file_size_mb,
    log_trim_target_ratio
):
    fieldnames = [
        "timestamp",
        "voc",
        "sen55_temperature",
        "sen55_humidity",
        "co2",
        "pm1_0",
        "pm2_5",
        "pm10",
        "nox",
        "pi5_temp",
        "short_avg_voc",
        "long_avg_voc",
        "short_delta_voc",
        "long_delta_voc",
    ]

    row = {
        "timestamp": timestamp,
        "voc": measurement.get("voc"),
        "sen55_temperature": measurement.get("sen55_temperature"),
        "sen55_humidity": measurement.get("sen55_humidity"),
        "co2": measurement.get("co2"),
        "pm1_0": measurement.get("pm1_0"),
        "pm2_5": measurement.get("pm2_5"),
        "pm10": measurement.get("pm10"),
        "nox": measurement.get("nox"),
        "pi5_temp": measurement.get("pi5_temp"),
        "short_avg_voc": short_avg.get("voc"),
        "long_avg_voc": long_avg.get("voc"),
        "short_delta_voc": short_delta.get("voc"),
        "long_delta_voc": long_delta.get("voc"),
    }

    _append_dict_row("voc_events.csv", fieldnames, row, max_log_file_size_mb, log_trim_target_ratio)