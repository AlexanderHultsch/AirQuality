from datetime import datetime

TEST_MODE = False

ACTIVE_TEST_SCENARIO = "voc_critical_after_5_loops"

TEST_ENABLE_DISPLAY = True
TEST_ENABLE_PUSHOVER = True
TEST_ENABLE_LOGGING = True


def _measurement(
    pm1_0,
    pm2_5,
    pm4_0,
    pm10,
    sen55_humidity=45.0,
    sen55_temperature=22.0,
    voc=80.0,
    nox=60.0,
    co2=650,
    scd41_temperature=22.0,
    scd41_humidity=45.0,
    pi5_temp=48.0,
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
        "pi5_temp": pi5_temp,
    }


def normal_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        co2=650,
        scd41_temperature=22.1,
        scd41_humidity=45.2,
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
        co2=900,
        scd41_temperature=23.0,
        scd41_humidity=46.0,
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
        co2=800,
        scd41_temperature=22.5,
        scd41_humidity=45.5,
    )


def co2_ventilate_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        co2=1250,
        scd41_temperature=22.5,
        scd41_humidity=45.0,
    )


def co2_critical_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        co2=1800,
        scd41_temperature=22.8,
        scd41_humidity=45.0,
    )

def voc_critical_measurement():
    return _measurement(
        pm1_0=2.0,
        pm2_5=3.0,
        pm4_0=4.0,
        pm10=5.0,
        sen55_humidity=44.0,
        sen55_temperature=22.8,
        voc=450.0,
        nox=65.0,
        co2=700,
        scd41_temperature=22.7,
        scd41_humidity=44.5,
        pi5_temp=50.0,
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

    if scenario_name == "smoke_after_5_loops":
        phase = _scenario_window(loop_count, start_loop=5, critical_len=3, recovery_len=3)
        if phase == "critical":
            return smoke_measurement()
        if phase == "recovery":
            return suspicious_smoke_measurement()
        return normal_measurement()

    if scenario_name == "co2_ventilate_after_5_loops":
        phase = _scenario_window(loop_count, start_loop=5, critical_len=4, recovery_len=3)
        if phase == "critical":
            return co2_ventilate_measurement()
        if phase == "recovery":
            return normal_measurement()
        return normal_measurement()

    if scenario_name == "co2_critical_after_5_loops":
        phase = _scenario_window(loop_count, start_loop=5, critical_len=4, recovery_len=3)
        if phase == "critical":
            return co2_critical_measurement()
        if phase == "recovery":
            return co2_ventilate_measurement()
        return normal_measurement()

    if scenario_name == "smoke_then_co2":
        if loop_count < 5:
            return normal_measurement()
        if loop_count < 8:
            return smoke_measurement()
        if loop_count < 11:
            return suspicious_smoke_measurement()
        if loop_count < 15:
            return co2_ventilate_measurement()
        if loop_count < 19:
            return co2_critical_measurement()
        return normal_measurement()
    
    if scenario_name == "voc_critical_after_5_loops":
        phase = _scenario_window(loop_count, start_loop=5, critical_len=4, recovery_len=3)
        if phase == "critical":
            return voc_critical_measurement()
        if phase == "recovery":
            return normal_measurement()
        return normal_measurement()

    return normal_measurement()