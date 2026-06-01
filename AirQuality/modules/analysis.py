def safe_round(value, digits=1):
    if value is None:
        return None
    return round(value, digits)


def format_display_value(value):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def get_numeric_trend(current_value, average_value, deadband=0.5):
    if current_value is None or average_value is None:
        return ""

    delta = current_value - average_value

    if delta > deadband:
        return "Rising"
    if delta < -deadband:
        return "Falling"
    return "Stable"


def classify_temperature(value):
    if value is None:
        return "Error", "Read error"
    if value >= 30.0:
        return "Critical", "Too hot"
    if value >= 27.0:
        return "Elevated", "Warm"
    if value < 17.0:
        return "Low", "Cool"
    return "Good", "Comfortable"


def classify_humidity(value):
    if value is None:
        return "Error", "Read error"
    if value >= 70:
        return "Critical", "Too humid"
    if value >= 60:
        return "Elevated", "Humid"
    if value < 30:
        return "Low", "Too dry"
    return "Good", "Comfortable"


def classify_co2(value):
    if value is None:
        return "Error", "Read error"
    if value >= 1500:
        return "Critical", "Open window"
    if value >= 1000:
        return "Elevated", "Ventilate"
    return "Good", "Air ok"


def classify_particulate(value, elevated_threshold, critical_threshold):
    if value is None:
        return "Error", "Read error"
    if value >= critical_threshold:
        return "Critical", "High particles"
    if value >= elevated_threshold:
        return "Elevated", "Raised particles"
    return "Good", "Particles ok"


def classify_voc(value):
    if value is None:
        return "Error", "Read error"
    if value >= 400:
        return "Critical", "VOC high"
    if value >= 200:
        return "Elevated", "VOC raised"
    return "Good", "VOC ok"


def classify_nox(value):
    if value is None:
        return "Error", "Read error"
    if value >= 10:
        return "Critical", "NOx high"
    if value >= 5:
        return "Elevated", "NOx raised"
    return "Good", "NOx ok"


def classify_pi5_temp(value):
    if value is None:
        return "Error", "Read error"
    if value >= 75:
        return "Critical", "System hot"
    if value >= 60:
        return "Elevated", "System warm"
    return "Good", "System temp"


def analyze_smoke(measurement, long_avg, short_avg, long_delta, short_delta):
    pm1_0 = measurement.get("pm1_0")
    pm2_5 = measurement.get("pm2_5")
    voc = measurement.get("voc")

    long_pm1_0 = long_avg.get("pm1_0")
    long_pm2_5 = long_avg.get("pm2_5")
    short_pm1_0 = short_avg.get("pm1_0")
    short_pm2_5 = short_avg.get("pm2_5")
    long_voc = long_avg.get("voc")
    short_voc = short_avg.get("voc")

    pm1_0_long_delta = long_delta.get("pm1_0")
    pm2_5_long_delta = long_delta.get("pm2_5")
    pm1_0_short_delta = short_delta.get("pm1_0")
    pm2_5_short_delta = short_delta.get("pm2_5")
    voc_long_delta = long_delta.get("voc")
    voc_short_delta = short_delta.get("voc")

    pm_ratio = None
    pm10 = measurement.get("pm10")
    if pm2_5 is not None and pm10 is not None and pm10 > 0:
        pm_ratio = round(pm2_5 / pm10, 2)

    pm_abs_suspicious = (
        (pm2_5 is not None and pm2_5 >= 6.0) or
        (pm1_0 is not None and pm1_0 >= 5.0)
    )

    pm_abs_smoke = (
        (pm2_5 is not None and pm2_5 >= 10.0) or
        (pm1_0 is not None and pm1_0 >= 8.0)
    )

    pm_delta_suspicious = (
        (pm2_5_long_delta is not None and pm2_5_long_delta >= 2.5) or
        (pm1_0_long_delta is not None and pm1_0_long_delta >= 2.0)
    )

    pm_delta_smoke = (
        (pm2_5_long_delta is not None and pm2_5_long_delta >= 5.0) or
        (pm1_0_long_delta is not None and pm1_0_long_delta >= 4.0)
    )

    pm_short_spike = (
        (pm2_5_short_delta is not None and pm2_5_short_delta >= 2.0) or
        (pm1_0_short_delta is not None and pm1_0_short_delta >= 1.5)
    )

    pm_short_spike_strong = (
        (pm2_5_short_delta is not None and pm2_5_short_delta >= 4.0) or
        (pm1_0_short_delta is not None and pm1_0_short_delta >= 3.0)
    )

    short_vs_long_raised = (
        short_pm2_5 is not None and long_pm2_5 is not None and short_pm2_5 >= long_pm2_5 * 1.6
    ) or (
        short_pm1_0 is not None and long_pm1_0 is not None and short_pm1_0 >= long_pm1_0 * 1.6
    )

    short_vs_long_strong = (
        short_pm2_5 is not None and long_pm2_5 is not None and short_pm2_5 >= long_pm2_5 * 2.2
    ) or (
        short_pm1_0 is not None and long_pm1_0 is not None and short_pm1_0 >= long_pm1_0 * 2.0
    )

    voc_support = (
        (voc is not None and voc >= 180) or
        (voc_long_delta is not None and voc_long_delta >= 35) or
        (voc_short_delta is not None and voc_short_delta >= 20) or
        (
            short_voc is not None and long_voc is not None and
            short_voc >= long_voc * 1.2 and short_voc >= 140
        )
    )

    pm_ratio_criteria = pm_ratio is not None and pm_ratio >= 0.75

    suspicious_score = 0
    smoke_score = 0

    if pm_abs_suspicious:
        suspicious_score += 2
    if pm_delta_suspicious:
        suspicious_score += 2
    if pm_short_spike:
        suspicious_score += 1
    if short_vs_long_raised:
        suspicious_score += 2
    if pm_ratio_criteria:
        suspicious_score += 1
    if voc_support:
        suspicious_score += 1

    if pm_abs_smoke:
        smoke_score += 3
    if pm_delta_smoke:
        smoke_score += 3
    if pm_short_spike_strong:
        smoke_score += 2
    if short_vs_long_strong:
        smoke_score += 2
    if pm_ratio_criteria:
        smoke_score += 1
    if voc_support:
        smoke_score += 1

    probable_smoke = (
        pm_abs_suspicious and
        pm_delta_suspicious and
        (pm_short_spike or short_vs_long_raised)
    )

    strong_smoke = (
        pm_abs_smoke and
        (pm_delta_smoke or pm_short_spike_strong or short_vs_long_strong)
    )

    if strong_smoke or smoke_score >= 6:
        state = "SMOKE"
        score = smoke_score
    elif probable_smoke or suspicious_score >= 4:
        state = "SUSPICIOUS"
        score = suspicious_score
    else:
        state = "CLEAR"
        score = max(suspicious_score, smoke_score)

    criteria = {
        "pm_abs_suspicious": pm_abs_suspicious,
        "pm_abs_smoke": pm_abs_smoke,
        "pm_delta_suspicious": pm_delta_suspicious,
        "pm_delta_smoke": pm_delta_smoke,
        "pm_short_spike": pm_short_spike,
        "pm_short_spike_strong": pm_short_spike_strong,
        "short_vs_long_raised": short_vs_long_raised,
        "short_vs_long_strong": short_vs_long_strong,
        "pm_ratio_criteria": pm_ratio_criteria,
        "voc_support": voc_support,
        "pm_ratio": pm_ratio,
        "suspicious_score": suspicious_score,
        "smoke_score": smoke_score,
        "probable_smoke": probable_smoke,
        "strong_smoke": strong_smoke,
    }

    return state, score, criteria


def analyze_CO2(measurement, long_avg, short_avg, long_delta, short_delta):
    co2 = measurement.get("co2")
    co2_long_delta = long_delta.get("co2")
    co2_short_delta = short_delta.get("co2")

    score = 0
    criteria = {
        "co2_abs_1000": co2 is not None and co2 >= 1000,
        "co2_abs_1200": co2 is not None and co2 >= 1200,
        "co2_abs_1500": co2 is not None and co2 >= 1500,
        "co2_long_delta_150": co2_long_delta is not None and co2_long_delta >= 150,
        "co2_short_delta_80": co2_short_delta is not None and co2_short_delta >= 80,
    }

    if criteria["co2_abs_1000"]:
        score += 1
    if criteria["co2_abs_1200"]:
        score += 1
    if criteria["co2_abs_1500"]:
        score += 2
    if criteria["co2_long_delta_150"]:
        score += 1
    if criteria["co2_short_delta_80"]:
        score += 1

    if co2 is not None and co2 >= 1500:
        return "CRITICAL", score, criteria
    if co2 is not None and co2 >= 1000:
        return "VENTILATE", score, criteria
    return "GOOD", score, criteria


def build_display_page_data(measurement, long_avg, smoke_state, last_smoke_state, co2_state):
    room_temp_status, room_temp_other = classify_temperature(measurement["sen55_temperature"])
    humidity_status, humidity_other = classify_humidity(measurement["sen55_humidity"])
    co2_status, co2_other = classify_co2(measurement["co2"])
    pm1_status, pm1_other = classify_particulate(measurement["pm1_0"], 10, 20)
    pm25_status, pm25_other = classify_particulate(measurement["pm2_5"], 10, 25)
    pm4_status, pm4_other = classify_particulate(measurement["pm4_0"], 15, 30)
    pm10_status, pm10_other = classify_particulate(measurement["pm10"], 20, 40)
    voc_status, voc_other = classify_voc(measurement["voc"])
    nox_status, nox_other = classify_nox(measurement["nox"])
    pi5_temp_status, pi5_temp_other = classify_pi5_temp(measurement["pi5_temp"])

    if smoke_state == "SMOKE":
        smoke_display_status = "Critical"
        smoke_display_other = "Smoke detected"
        smoke_critical = True
    elif smoke_state == "SUSPICIOUS":
        smoke_display_status = "Suspicious"
        smoke_display_other = "Possible smoke"
        smoke_critical = False
    else:
        smoke_display_status = "Clear"
        smoke_display_other = "No smoke"
        smoke_critical = False

    return {
        "temperature": {
            "title": "Temperature",
            "value": format_display_value(measurement["sen55_temperature"]),
            "unit": "C",
            "status": room_temp_status,
            "trend": get_numeric_trend(measurement["sen55_temperature"], long_avg["sen55_temperature"], 0.3),
            "other": room_temp_other,
            "critical": room_temp_status == "Critical",
        },
        "humidity": {
            "title": "Humidity",
            "value": format_display_value(measurement["sen55_humidity"]),
            "unit": "%",
            "status": humidity_status,
            "trend": get_numeric_trend(measurement["sen55_humidity"], long_avg["sen55_humidity"], 2.0),
            "other": humidity_other,
            "critical": humidity_status == "Critical",
        },
        "co2": {
            "title": "CO2",
            "value": format_display_value(measurement["co2"]),
            "unit": "ppm",
            "status": co2_status,
            "trend": get_numeric_trend(measurement["co2"], long_avg["co2"], 30),
            "other": co2_other,
            "critical": co2_status == "Critical",
        },
        "pm1_0": {
            "title": "PM1.0",
            "value": format_display_value(measurement["pm1_0"]),
            "unit": "ug/m3",
            "status": pm1_status,
            "trend": get_numeric_trend(measurement["pm1_0"], long_avg["pm1_0"], 0.5),
            "other": pm1_other,
            "critical": pm1_status == "Critical",
        },
        "pm2_5": {
            "title": "PM2.5",
            "value": format_display_value(measurement["pm2_5"]),
            "unit": "ug/m3",
            "status": pm25_status,
            "trend": get_numeric_trend(measurement["pm2_5"], long_avg["pm2_5"], 0.5),
            "other": pm25_other,
            "critical": pm25_status == "Critical",
        },
        "pm4_0": {
            "title": "PM4.0",
            "value": format_display_value(measurement["pm4_0"]),
            "unit": "ug/m3",
            "status": pm4_status,
            "trend": get_numeric_trend(measurement["pm4_0"], long_avg["pm4_0"], 0.5),
            "other": pm4_other,
            "critical": pm4_status == "Critical",
        },
        "pm10": {
            "title": "PM10",
            "value": format_display_value(measurement["pm10"]),
            "unit": "ug/m3",
            "status": pm10_status,
            "trend": get_numeric_trend(measurement["pm10"], long_avg["pm10"], 0.5),
            "other": pm10_other,
            "critical": pm10_status == "Critical",
        },
        "voc": {
            "title": "VOC",
            "value": format_display_value(measurement["voc"]),
            "unit": "index",
            "status": voc_status,
            "trend": get_numeric_trend(measurement["voc"], long_avg["voc"], 10),
            "other": voc_other,
            "critical": voc_status == "Critical",
        },
        "nox": {
            "title": "NOX",
            "value": format_display_value(measurement["nox"]),
            "unit": "index",
            "status": nox_status,
            "trend": get_numeric_trend(measurement["nox"], long_avg["nox"], 1),
            "other": nox_other,
            "critical": nox_status == "Critical",
        },
        "smoke": {
            "title": "Smoke",
            "value": smoke_state,
            "unit": "",
            "status": smoke_display_status,
            "trend": "",
            "other": smoke_display_other,
            "critical": smoke_critical,
        },
        "pi5_temp": {
            "title": "PI5 Temp",
            "value": format_display_value(measurement["pi5_temp"]),
            "unit": "C",
            "status": pi5_temp_status,
            "trend": get_numeric_trend(measurement["pi5_temp"], long_avg["pi5_temp"], 1.0),
            "other": pi5_temp_other,
            "critical": pi5_temp_status == "Critical",
        },
    }