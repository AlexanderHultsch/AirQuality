def analyze_smoke(latest_measurement, long_avg, short_avg, long_delta, short_delta):
    pm1_0 = latest_measurement["pm1_0"]
    pm2_5 = latest_measurement["pm2_5"]

    long_avg_pm1_0 = long_avg["pm1_0"]
    long_avg_pm2_5 = long_avg["pm2_5"]

    short_avg_pm2_5 = short_avg["pm2_5"]

    long_delta_pm1_0 = long_delta["pm1_0"]
    long_delta_pm2_5 = long_delta["pm2_5"]

    if pm2_5 > 10:
        pm_ratio_value = pm1_0 / pm2_5
    else:
        pm_ratio_value = 0

    criteria = {
        "pm2_5_abs": pm2_5 > 10 or pm1_0 > 8,
        "pm2_5_long_delta": long_delta_pm2_5 is not None and long_delta_pm2_5 > 3.0,
        "pm1_0_long_delta": long_delta_pm1_0 is not None and long_delta_pm1_0 > 3.0,
        "pm2_5_spike": long_avg_pm2_5 is not None and pm2_5 > long_avg_pm2_5 * 1.45,
        "pm1_0_spike": long_avg_pm1_0 is not None and pm1_0 > long_avg_pm1_0 * 1.45,
        "pm2_5_short_vs_long": (
            short_avg_pm2_5 is not None and
            long_avg_pm2_5 is not None and
            short_avg_pm2_5 > long_avg_pm2_5 * 1.20
        ),
        "pm_ratio": pm2_5 > 10 and pm_ratio_value > 0.88,
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
    elif criteria["pm2_5_abs"] and trend_signals >= 1:
        smoke_state = "SUSPICIOUS"
    else:
        smoke_state = "CLEAR"

    smoke_score = strong_signals * 2 + trend_signals + support_signals

    return smoke_state, smoke_score, criteria


def analyze_CO2(latest_measurement, long_avg, short_avg, long_delta, short_delta):
    co2 = latest_measurement["co2"]

    long_avg_co2 = long_avg["co2"]
    short_avg_co2 = short_avg["co2"]
    long_delta_co2 = long_delta["co2"]
    short_delta_co2 = short_delta["co2"]

    criteria = {
        "co2_above_800": co2 is not None and co2 > 800,
        "co2_above_1000": co2 is not None and co2 > 1000,
        "co2_above_1200": co2 is not None and co2 > 1200,
        "co2_above_1500": co2 is not None and co2 > 1500,
        "co2_long_delta_high": long_delta_co2 is not None and long_delta_co2 > 120,
        "co2_short_delta_high": short_delta_co2 is not None and short_delta_co2 > 80,
        "co2_short_vs_long": (
            short_avg_co2 is not None and
            long_avg_co2 is not None and
            short_avg_co2 > long_avg_co2 * 1.08
        ),
    }

    strong_signals = sum([
        criteria["co2_above_1200"],
        criteria["co2_above_1500"],
        criteria["co2_long_delta_high"],
    ])

    trend_signals = sum([
        criteria["co2_short_delta_high"],
        criteria["co2_short_vs_long"],
    ])

    if co2 is None:
        co2_state = "GOOD"
    elif criteria["co2_above_1500"]:
        co2_state = "CRITICAL"
    elif criteria["co2_above_1200"] and trend_signals >= 1:
        co2_state = "CRITICAL"
    elif criteria["co2_above_1200"]:
        co2_state = "VENTILATE"
    elif criteria["co2_above_1000"] and trend_signals >= 1:
        co2_state = "VENTILATE"
    elif criteria["co2_above_1000"]:
        co2_state = "ELEVATED"
    elif criteria["co2_above_800"]:
        co2_state = "ELEVATED"
    else:
        co2_state = "GOOD"

    co2_score = strong_signals * 2 + trend_signals

    return co2_state, co2_score, criteria


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
    if value > 1200:
        return "Critical", "Air quality"
    if value > 800:
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


def build_display_page_data(measurement, long_avg, smoke_state, last_smoke_state, co2_state="GOOD"):
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
            "critical": co2_state in ["VENTILATE", "CRITICAL"],
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