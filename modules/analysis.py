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
        return "Error", ""
    if value >= 30.0:
        return "Critical", "Cool room"
    if value >= 27.0:
        return "Elevated", "Warm room"
    if value < 17.0:
        return "Low", "Heat room"
    return "Good", ""


def classify_humidity(value):
    if value is None:
        return "Error", ""
    if value >= 70:
        return "Critical", "Dry room"
    if value >= 60:
        return "Elevated", "Less humidity"
    if value < 30:
        return "Low", "Add humidity"
    return "Good", ""


def classify_co2(value):
    if value is None:
        return "Error", ""
    if value >= 1500:
        return "Critical", "Open window"
    if value >= 1000:
        return "Elevated", "Open window"
    return "Good", ""


def classify_particulate(value, elevated_threshold, critical_threshold):
    if value is None:
        return "Error", ""
    if value >= critical_threshold:
        return "Critical", "Close window"
    if value >= elevated_threshold:
        return "Elevated", "Watch particles"
    return "Good", ""


def classify_voc(value):
    if value is None:
        return "Error", ""
    if value >= 400:
        return "Critical", "Ventilate now"
    if value >= 200:
        return "Elevated", "Ventilate"
    return "Good", ""


def classify_nox(value):
    if value is None:
        return "Error", ""
    if value >= 10:
        return "Critical", "Close window"
    if value >= 5:
        return "Elevated", "Watch air"
    return "Good", ""


def classify_pi5_temp(value):
    if value is None:
        return "Error", ""
    if value >= 75:
        return "Critical", "Check cooling"
    if value >= 60:
        return "Elevated", "Warm system"
    return "Good", ""


def _ratio(a, b):
    if a is None or b is None or b <= 0:
        return None
    return round(a / b, 2)


def _rel_above(current, baseline, min_baseline=0.5):
    if current is None or baseline is None:
        return None
    return round(current / max(baseline, min_baseline), 2)


def _build_smoke_features(measurement, long_avg, short_avg, long_delta, short_delta):
    pm1_0 = measurement.get("pm1_0")
    pm2_5 = measurement.get("pm2_5")
    pm4_0 = measurement.get("pm4_0")
    pm10 = measurement.get("pm10")
    voc = measurement.get("voc")
    co2 = measurement.get("co2")

    long_pm1_0 = long_avg.get("pm1_0")
    long_pm2_5 = long_avg.get("pm2_5")
    long_pm10 = long_avg.get("pm10")
    long_voc = long_avg.get("voc")

    pm1_0_long_delta = long_delta.get("pm1_0")
    pm2_5_long_delta = long_delta.get("pm2_5")
    pm10_long_delta = long_delta.get("pm10")
    voc_long_delta = long_delta.get("voc")
    co2_long_delta = long_delta.get("co2")

    pm1_0_short_delta = short_delta.get("pm1_0")
    pm2_5_short_delta = short_delta.get("pm2_5")
    pm10_short_delta = short_delta.get("pm10")
    voc_short_delta = short_delta.get("voc")

    pm1_vs_pm25_ratio = _ratio(pm1_0, pm2_5)
    pm25_vs_pm10_ratio = _ratio(pm2_5, pm10)

    rel_pm1_long = _rel_above(pm1_0, long_pm1_0)
    rel_pm25_long = _rel_above(pm2_5, long_pm2_5)
    rel_pm10_long = _rel_above(pm10, long_pm10)
    rel_voc_long = _rel_above(voc, long_voc, min_baseline=50.0)

    baseline_low_particles = (
        long_pm2_5 is not None and long_pm2_5 <= 4.0 and
        long_pm10 is not None and long_pm10 <= 5.0
    )

    pm_present_suspicious = (
        (pm1_0 is not None and pm1_0 >= 8.0) or
        (pm2_5 is not None and pm2_5 >= 10.0) or
        (pm10 is not None and pm10 >= 12.0)
    )

    pm_present_smoke = (
        (pm1_0 is not None and pm1_0 >= 20.0) or
        (pm2_5 is not None and pm2_5 >= 25.0) or
        (pm10 is not None and pm10 >= 30.0)
    )

    pm_long_rise_suspicious = (
        (pm1_0_long_delta is not None and pm1_0_long_delta >= 6.0) or
        (pm2_5_long_delta is not None and pm2_5_long_delta >= 8.0) or
        (pm10_long_delta is not None and pm10_long_delta >= 10.0)
    )

    pm_long_rise_smoke = (
        (pm1_0_long_delta is not None and pm1_0_long_delta >= 15.0) or
        (pm2_5_long_delta is not None and pm2_5_long_delta >= 20.0) or
        (pm10_long_delta is not None and pm10_long_delta >= 25.0)
    )

    pm_short_rise_suspicious = (
        (pm1_0_short_delta is not None and pm1_0_short_delta >= 5.0) or
        (pm2_5_short_delta is not None and pm2_5_short_delta >= 6.0) or
        (pm10_short_delta is not None and pm10_short_delta >= 8.0)
    )

    pm_short_rise_smoke = (
        (pm1_0_short_delta is not None and pm1_0_short_delta >= 12.0) or
        (pm2_5_short_delta is not None and pm2_5_short_delta >= 15.0) or
        (pm10_short_delta is not None and pm10_short_delta >= 18.0)
    )

    pm_relative_suspicious = (
        (rel_pm1_long is not None and rel_pm1_long >= 2.2) or
        (rel_pm25_long is not None and rel_pm25_long >= 2.2) or
        (rel_pm10_long is not None and rel_pm10_long >= 2.0)
    )

    pm_relative_smoke = (
        (rel_pm1_long is not None and rel_pm1_long >= 4.0) or
        (rel_pm25_long is not None and rel_pm25_long >= 4.0) or
        (rel_pm10_long is not None and rel_pm10_long >= 3.5)
    )

    fine_particle_profile = (
        (pm1_vs_pm25_ratio is not None and pm1_vs_pm25_ratio >= 0.72) or
        (pm25_vs_pm10_ratio is not None and pm25_vs_pm10_ratio >= 0.80)
    )

    very_fine_particle_profile = (
        (pm1_vs_pm25_ratio is not None and pm1_vs_pm25_ratio >= 0.82) or
        (pm25_vs_pm10_ratio is not None and pm25_vs_pm10_ratio >= 0.90)
    )

    voc_support_light = (
        (voc_long_delta is not None and voc_long_delta >= 25) or
        (voc_short_delta is not None and voc_short_delta >= 15) or
        (rel_voc_long is not None and rel_voc_long >= 1.15 and voc is not None and voc >= 140)
    )

    voc_support_strong = (
        (voc_long_delta is not None and voc_long_delta >= 50) or
        (voc_short_delta is not None and voc_short_delta >= 30) or
        (rel_voc_long is not None and rel_voc_long >= 1.30 and voc is not None and voc >= 180)
    )

    voc_without_pm = (
        (voc is not None and voc >= 180) and
        not pm_present_suspicious and
        not pm_long_rise_suspicious and
        not pm_short_rise_suspicious and
        not pm_relative_suspicious
    )

    coarse_particle_hint = False
    if pm10 is not None and pm2_5 is not None and pm10 > 0:
        if (pm2_5 / pm10) < 0.55:
            coarse_particle_hint = True

    co2_only_hint = (
        (co2 is not None and co2 >= 1000) and
        (co2_long_delta is not None and co2_long_delta >= 80) and
        not pm_present_suspicious and
        not pm_long_rise_suspicious
    )

    sustained_mid_pm = (
        pm2_5 is not None and pm2_5 >= 12.0 and
        long_pm2_5 is not None and long_pm2_5 >= 8.0
    )

    sudden_clean_air_spike = (
        baseline_low_particles and
        (
            (pm2_5 is not None and pm2_5 >= 10.0) or
            (pm1_0 is not None and pm1_0 >= 8.0)
        )
    )

    suspicious_score = 0
    smoke_score = 0

    if pm_present_suspicious:
        suspicious_score += 2
    if pm_long_rise_suspicious:
        suspicious_score += 2
    if pm_short_rise_suspicious:
        suspicious_score += 2
    if pm_relative_suspicious:
        suspicious_score += 2
    if fine_particle_profile:
        suspicious_score += 1
    if sustained_mid_pm:
        suspicious_score += 1
    if voc_support_light and pm_present_suspicious:
        suspicious_score += 1

    if pm_present_smoke:
        smoke_score += 3
    if pm_long_rise_smoke:
        smoke_score += 3
    if pm_short_rise_smoke:
        smoke_score += 2
    if pm_relative_smoke:
        smoke_score += 2
    if very_fine_particle_profile:
        smoke_score += 1
    if sustained_mid_pm and pm_short_rise_suspicious:
        smoke_score += 1
    if voc_support_strong and pm_present_suspicious:
        smoke_score += 1

    if sudden_clean_air_spike:
        suspicious_score -= 1
    if voc_without_pm:
        suspicious_score -= 3
        smoke_score -= 5
    if coarse_particle_hint:
        suspicious_score -= 1
        smoke_score -= 2
    if co2_only_hint:
        suspicious_score -= 1
        smoke_score -= 2

    suspicious_score = max(suspicious_score, 0)
    smoke_score = max(smoke_score, 0)

    probable_smoke = (
        pm_present_suspicious and
        (
            (pm_long_rise_suspicious and pm_short_rise_suspicious) or
            (pm_relative_suspicious and pm_short_rise_suspicious)
        ) and
        (fine_particle_profile or sustained_mid_pm or voc_support_light)
    )

    strong_smoke = (
        pm_present_smoke and
        (pm_long_rise_smoke or pm_short_rise_smoke or pm_relative_smoke) and
        (very_fine_particle_profile or sustained_mid_pm or voc_support_light)
    )

    falling_back_to_clear = (
        (pm2_5 is None or pm2_5 < 8.0) and
        (pm1_0 is None or pm1_0 < 6.0) and
        (pm10 is None or pm10 < 10.0) and
        not pm_long_rise_suspicious and
        not pm_short_rise_suspicious and
        suspicious_score <= 1 and
        smoke_score <= 1
    )

    return {
        "pm1_vs_pm25_ratio": pm1_vs_pm25_ratio,
        "pm25_vs_pm10_ratio": pm25_vs_pm10_ratio,
        "rel_pm1_long": rel_pm1_long,
        "rel_pm25_long": rel_pm25_long,
        "rel_pm10_long": rel_pm10_long,
        "rel_voc_long": rel_voc_long,
        "baseline_low_particles": baseline_low_particles,
        "pm_present_suspicious": pm_present_suspicious,
        "pm_present_smoke": pm_present_smoke,
        "pm_long_rise_suspicious": pm_long_rise_suspicious,
        "pm_long_rise_smoke": pm_long_rise_smoke,
        "pm_short_rise_suspicious": pm_short_rise_suspicious,
        "pm_short_rise_smoke": pm_short_rise_smoke,
        "pm_relative_suspicious": pm_relative_suspicious,
        "pm_relative_smoke": pm_relative_smoke,
        "fine_particle_profile": fine_particle_profile,
        "very_fine_particle_profile": very_fine_particle_profile,
        "voc_support_light": voc_support_light,
        "voc_support_strong": voc_support_strong,
        "voc_without_pm": voc_without_pm,
        "coarse_particle_hint": coarse_particle_hint,
        "co2_only_hint": co2_only_hint,
        "sustained_mid_pm": sustained_mid_pm,
        "sudden_clean_air_spike": sudden_clean_air_spike,
        "suspicious_score": suspicious_score,
        "smoke_score": smoke_score,
        "probable_smoke": probable_smoke,
        "strong_smoke": strong_smoke,
        "falling_back_to_clear": falling_back_to_clear,
    }


class SmokeDetector:
    def __init__(self):
        self.state = "CLEAR"
        self.suspicious_hold = 0
        self.smoke_hold = 0
        self.clear_hold = 0

        self.suspicious_enter_count = 3
        self.smoke_enter_count = 4
        self.clear_exit_count = 12
        self.smoke_exit_count = 2

    def update(self, measurement, long_avg, short_avg, long_delta, short_delta):
        features = _build_smoke_features(
            measurement, long_avg, short_avg, long_delta, short_delta
        )

        suspicious_score = features["suspicious_score"]
        smoke_score = features["smoke_score"]

        suspicious_trigger = (
            features["probable_smoke"] or
            suspicious_score >= 6 or
            (
                features["pm_present_suspicious"] and
                features["pm_short_rise_suspicious"] and
                features["pm_relative_suspicious"]
            )
        )

        smoke_trigger = (
            features["strong_smoke"] or
            smoke_score >= 8 or
            (
                features["pm_present_smoke"] and
                (
                    features["pm_long_rise_smoke"] or
                    features["pm_short_rise_smoke"]
                ) and
                (features["very_fine_particle_profile"] or features["sustained_mid_pm"])
            )
        )

        clear_trigger = features["falling_back_to_clear"]

        if suspicious_trigger:
            self.suspicious_hold += 1
        else:
            self.suspicious_hold = max(0, self.suspicious_hold - 1)

        if smoke_trigger:
            self.smoke_hold += 1
        else:
            self.smoke_hold = max(0, self.smoke_hold - 1)

        if clear_trigger:
            self.clear_hold += 1
        else:
            self.clear_hold = 0

        if self.state == "CLEAR":
            if self.smoke_hold >= self.smoke_enter_count:
                self.state = "SMOKE"
            elif self.suspicious_hold >= self.suspicious_enter_count:
                self.state = "SUSPICIOUS"

        elif self.state == "SUSPICIOUS":
            if self.smoke_hold >= self.smoke_enter_count:
                self.state = "SMOKE"
            elif self.clear_hold >= self.clear_exit_count:
                self.state = "CLEAR"

        elif self.state == "SMOKE":
            if self.smoke_hold < self.smoke_exit_count:
                if self.suspicious_hold >= 1:
                    self.state = "SUSPICIOUS"
                elif self.clear_hold >= self.clear_exit_count:
                    self.state = "CLEAR"

        if self.state == "SMOKE":
            score = smoke_score
        elif self.state == "SUSPICIOUS":
            score = suspicious_score
        else:
            score = max(suspicious_score, smoke_score)

        criteria = dict(features)
        criteria["state"] = self.state
        criteria["suspicious_hold"] = self.suspicious_hold
        criteria["smoke_hold"] = self.smoke_hold
        criteria["clear_hold"] = self.clear_hold

        return self.state, score, criteria


def create_smoke_detector():
    return SmokeDetector()


def analyze_smoke(measurement, long_avg, short_avg, long_delta, short_delta):
    features = _build_smoke_features(
        measurement, long_avg, short_avg, long_delta, short_delta
    )

    suspicious_score = features["suspicious_score"]
    smoke_score = features["smoke_score"]

    if features["strong_smoke"] or smoke_score >= 8:
        state = "SMOKE"
        score = smoke_score
    elif features["probable_smoke"] or suspicious_score >= 6:
        state = "SUSPICIOUS"
        score = suspicious_score
    else:
        state = "CLEAR"
        score = max(suspicious_score, smoke_score)

    criteria = dict(features)
    criteria["state"] = state
    criteria["suspicious_hold"] = 0
    criteria["smoke_hold"] = 0
    criteria["clear_hold"] = 0

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
        smoke_display_other = "Close window"
        smoke_critical = True
    elif smoke_state == "SUSPICIOUS":
        smoke_display_status = "Suspicious"
        smoke_display_other = "Watch air"
        smoke_critical = False
    else:
        smoke_display_status = "Clear"
        smoke_display_other = ""
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