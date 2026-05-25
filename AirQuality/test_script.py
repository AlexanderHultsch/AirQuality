from datetime import datetime

TEST_MODE = False
ACTIVE_TEST_SCENARIO = "smoke_after_5_loops"

TEST_ENABLE_DISPLAY = True
TEST_ENABLE_PUSHOVER = True
TEST_ENABLE_LOGGING = False


def _measurement(
    pm1_0,
    pm2_5,
    pm4_0,
    pm10,
    sen55_humidity,
    sen55_temperature,
    voc,
    nox,
    co2=None,
    scd41_temperature=None,
    scd41_humidity=None,
):
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pm1_0": pm1_0,
        "pm2_5": pm2_5,
        "pm4_0": pm4_0,
        "pm10": pm10,
        "sen55_humidity": sen55_humidity,
        "sen55_temperature": sen55_temperature,
        "voc": voc,
        "nox": nox,
        "co2": co2,
        "scd41_temperature": scd41_temperature,
        "scd41_humidity": scd41_humidity,
    }


def normal_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        sen55_humidity=45.0,
        sen55_temperature=22.0,
        voc=80.0,
        nox=60.0,
    )


def smoke_measurement():
    return _measurement(
        pm1_0=45.0,
        pm2_5=48.0,
        pm4_0=52.0,
        pm10=60.0,
        sen55_humidity=46.0,
        sen55_temperature=23.0,
        voc=120.0,
        nox=70.0,
    )


def suspicious_smoke_measurement():
    return _measurement(
        pm1_0=16.0,
        pm2_5=18.0,
        pm4_0=20.0,
        pm10=24.0,
        sen55_humidity=45.0,
        sen55_temperature=22.5,
        voc=95.0,
        nox=65.0,
    )


def temperature_critical_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        sen55_humidity=45.0,
        sen55_temperature=31.0,
        voc=80.0,
        nox=60.0,
    )


def temperature_elevated_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        sen55_humidity=45.0,
        sen55_temperature=28.0,
        voc=80.0,
        nox=60.0,
    )


def humidity_critical_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        sen55_humidity=75.0,
        sen55_temperature=22.0,
        voc=80.0,
        nox=60.0,
    )


def humidity_elevated_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        sen55_humidity=62.0,
        sen55_temperature=22.0,
        voc=80.0,
        nox=60.0,
    )


def pm25_critical_measurement():
    return _measurement(
        pm1_0=15.0,
        pm2_5=40.0,
        pm4_0=42.0,
        pm10=45.0,
        sen55_humidity=45.0,
        sen55_temperature=22.0,
        voc=90.0,
        nox=70.0,
    )


def pm25_elevated_measurement():
    return _measurement(
        pm1_0=8.0,
        pm2_5=16.0,
        pm4_0=18.0,
        pm10=20.0,
        sen55_humidity=45.0,
        sen55_temperature=22.0,
        voc=85.0,
        nox=65.0,
    )


def voc_critical_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        sen55_humidity=45.0,
        sen55_temperature=22.0,
        voc=320.0,
        nox=60.0,
    )


def voc_elevated_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        sen55_humidity=45.0,
        sen55_temperature=22.0,
        voc=180.0,
        nox=60.0,
    )


def smoke_with_temp_critical_measurement():
    return _measurement(
        pm1_0=45.0,
        pm2_5=50.0,
        pm4_0=55.0,
        pm10=65.0,
        sen55_humidity=46.0,
        sen55_temperature=31.0,
        voc=140.0,
        nox=70.0,
    )


def _scenario_window(loop_count, start_loop, critical_len=3, recovery_len=3):
    if loop_count < start_loop:
        return "normal"
    if loop_count < start_loop + critical_len:
        return "critical"
    if loop_count < start_loop + critical_len + recovery_len:
        return "recovery"
    return "normal"


def get_test_measurement(loop_count, scenario_name):
    if scenario_name == "normal_operation":
        return normal_measurement()

    if scenario_name == "smoke_after_2_loops":
        phase = _scenario_window(loop_count, start_loop=2, critical_len=3, recovery_len=3)
        if phase == "critical":
            return smoke_measurement()
        if phase == "recovery":
            return suspicious_smoke_measurement()
        return normal_measurement()

    if scenario_name == "smoke_after_5_loops":
        phase = _scenario_window(loop_count, start_loop=5, critical_len=3, recovery_len=3)
        if phase == "critical":
            return smoke_measurement()
        if phase == "recovery":
            return suspicious_smoke_measurement()
        return normal_measurement()

    if scenario_name == "smoke_after_10_loops":
        phase = _scenario_window(loop_count, start_loop=10, critical_len=3, recovery_len=3)
        if phase == "critical":
            return smoke_measurement()
        if phase == "recovery":
            return suspicious_smoke_measurement()
        return normal_measurement()

    if scenario_name == "smoke_with_other_critical":
        if loop_count < 5:
            return normal_measurement()
        if loop_count < 8:
            return smoke_measurement()
        if loop_count < 11:
            return smoke_with_temp_critical_measurement()
        if loop_count < 14:
            return temperature_elevated_measurement()
        return normal_measurement()

    if scenario_name == "temperature_critical_only":
        phase = _scenario_window(loop_count, start_loop=5, critical_len=4, recovery_len=3)
        if phase == "critical":
            return temperature_critical_measurement()
        if phase == "recovery":
            return temperature_elevated_measurement()
        return normal_measurement()

    if scenario_name == "humidity_critical_only":
        phase = _scenario_window(loop_count, start_loop=5, critical_len=4, recovery_len=3)
        if phase == "critical":
            return humidity_critical_measurement()
        if phase == "recovery":
            return humidity_elevated_measurement()
        return normal_measurement()

    if scenario_name == "pm25_critical_only":
        phase = _scenario_window(loop_count, start_loop=5, critical_len=4, recovery_len=3)
        if phase == "critical":
            return pm25_critical_measurement()
        if phase == "recovery":
            return pm25_elevated_measurement()
        return normal_measurement()

    if scenario_name == "voc_critical_only":
        phase = _scenario_window(loop_count, start_loop=5, critical_len=4, recovery_len=3)
        if phase == "critical":
            return voc_critical_measurement()
        if phase == "recovery":
            return voc_elevated_measurement()
        return normal_measurement()

    if scenario_name == "smoke_recovery":
        if loop_count < 5:
            return normal_measurement()
        if loop_count < 9:
            return smoke_measurement()
        if loop_count < 13:
            return suspicious_smoke_measurement()
        return normal_measurement()

    if scenario_name == "push_blocked_by_smoke":
        if loop_count < 4:
            return normal_measurement()
        if loop_count < 6:
            return temperature_critical_measurement()
        if loop_count < 9:
            return smoke_with_temp_critical_measurement()
        if loop_count < 12:
            return temperature_elevated_measurement()
        return normal_measurement()

    return normal_measurement()