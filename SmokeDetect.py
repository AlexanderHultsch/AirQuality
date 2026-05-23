# Cable Setup----------------------
# PIN1_VDD_Red____Pin02
# PIN2_GND_Black__Pin09
# PIN3_SDA_Green__Pin03
# PIN4_SCL_Yellow_Pin05
# PIN5_SEL_Blue___Pin14
# PIN6_NC_Purple__No connection

import time
from smbus2 import SMBus, i2c_msg
from datetime import datetime

Refresh_rate = 1  # in sec
pre_trigger_len = int(30 / Refresh_rate) # Number of previous datapoints to be logged once smoke is detected

Long_max_list_len = int((5 * 60) / Refresh_rate)   # change first int for duration in min
Short_max_list_len = int((0.25 * 60) / Refresh_rate)  # change first int for duration in min

Long_window_list = []
Short_window_list = []

BUS = 1
ADDR = 0x69
bus = SMBus(BUS)


def read_sensor_data():
    # Data ready?
    bus.i2c_rdwr(i2c_msg.write(ADDR, [0x02, 0x02]))
    time.sleep(0.01)
    ready = i2c_msg.read(ADDR, 3)
    bus.i2c_rdwr(ready)
    r = list(ready)

    if (((r[0] << 8) | r[1]) == 1):
        bus.i2c_rdwr(i2c_msg.write(ADDR, [0x03, 0xC4]))
        time.sleep(0.01)
        data = i2c_msg.read(ADDR, 24)
        bus.i2c_rdwr(data)
        d = list(data)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pm1_0 = round(((d[0] << 8) | d[1]) / 10.0, 1)
        pm2_5 = round(((d[3] << 8) | d[4]) / 10.0, 1)
        pm4_0 = round(((d[6] << 8) | d[7]) / 10.0, 1)
        pm10 = round(((d[9] << 8) | d[10]) / 10.0, 1)
        humidity = round(((d[12] << 8) | d[13]) / 100.0, 1)
        temperature = round(((d[15] << 8) | d[16]) / 200.0, 1)
        voc = round(((d[18] << 8) | d[19]) / 10.0, 1)
        nox = round(((d[21] << 8) | d[22]) / 10.0, 1)

        return [timestamp, pm1_0, pm2_5, pm4_0, pm10, humidity, temperature, voc, nox]

    return None


def update_window(window_list, entry, max_list_len):
    window_list.append(entry)
    if len(window_list) > max_list_len:
        window_list.pop(0)


def calculate_avg_and_delta(window_list):
    if len(window_list) <= 1:
        return None, None

    avg_pm1_0 = round(sum(entry[1] for entry in window_list[:-1]) / len(window_list[:-1]), 1)
    avg_pm2_5 = round(sum(entry[2] for entry in window_list[:-1]) / len(window_list[:-1]), 1)
    avg_pm4_0 = round(sum(entry[3] for entry in window_list[:-1]) / len(window_list[:-1]), 1)
    avg_pm10 = round(sum(entry[4] for entry in window_list[:-1]) / len(window_list[:-1]), 1)
    avg_humidity = round(sum(entry[5] for entry in window_list[:-1]) / len(window_list[:-1]), 1)
    avg_temperature = round(sum(entry[6] for entry in window_list[:-1]) / len(window_list[:-1]), 1)
    avg_voc = round(sum(entry[7] for entry in window_list[:-1]) / len(window_list[:-1]), 1)
    avg_nox = round(sum(entry[8] for entry in window_list[:-1]) / len(window_list[:-1]), 1)

    latest_entry = window_list[-1]

    delta_pm1_0 = round(latest_entry[1] - avg_pm1_0, 1)
    delta_pm2_5 = round(latest_entry[2] - avg_pm2_5, 1)
    delta_pm4_0 = round(latest_entry[3] - avg_pm4_0, 1)
    delta_pm10 = round(latest_entry[4] - avg_pm10, 1)
    delta_humidity = round(latest_entry[5] - avg_humidity, 1)
    delta_temperature = round(latest_entry[6] - avg_temperature, 1)
    delta_voc = round(latest_entry[7] - avg_voc, 1)
    delta_nox = round(latest_entry[8] - avg_nox, 1)

    avg_values = [
        avg_pm1_0,
        avg_pm2_5,
        avg_pm4_0,
        avg_pm10,
        avg_humidity,
        avg_temperature,
        avg_voc,
        avg_nox
    ]

    delta_values = [
        delta_pm1_0,
        delta_pm2_5,
        delta_pm4_0,
        delta_pm10,
        delta_humidity,
        delta_temperature,
        delta_voc,
        delta_nox
    ]

    return avg_values, delta_values

def analyze_smoke(latest_entry, long_avg, short_avg, long_delta, short_delta):
    pm1_0 = latest_entry[1]
    pm2_5 = latest_entry[2]
    voc = latest_entry[7]

    long_avg_pm1_0 = long_avg[0]
    long_avg_pm2_5 = long_avg[1]
    long_avg_voc = long_avg[6]

    short_avg_pm2_5 = short_avg[1]

    long_delta_pm1_0 = long_delta[0]
    long_delta_pm2_5 = long_delta[1]

    criteria = {
        "pm2_5_abs": pm2_5 > 8,                                     # absolute PM2.5 level
        "pm2_5_long_delta": long_delta_pm2_5 > 2.0,                 # early rise vs long baseline
        "pm1_0_long_delta": long_delta_pm1_0 > 2.0,                 # fine particle rise vs long baseline
        "pm2_5_spike": pm2_5 > long_avg_pm2_5 * 1.6,                # current PM2.5 spike vs long average
        "pm1_0_spike": pm1_0 > long_avg_pm1_0 * 1.4,                # current PM1.0 spike vs long average
        "pm2_5_short_vs_long": short_avg_pm2_5 > long_avg_pm2_5 * 1.3,  # short trend above background
        "pm_ratio": pm2_5 > 10 and (pm1_0 / pm2_5) > 0.85,          # smoke-like fine particle fraction
        "voc_spike": voc > long_avg_voc * 1.25                      # optional VOC support
    }

    smoke_score = sum(criteria.values())

    if smoke_score >= 4:
        smoke_state = "SMOKE"
    elif smoke_score >= 3:
        smoke_state = "SUSPICIOUS"
    else:
        smoke_state = "CLEAR"

    return smoke_state, smoke_score, criteria

def log_pre_smoke_window(window_list, smoke_state, smoke_score):
    with open("pre_smoke_log.txt", "a") as f:
        f.write(f"Trigger state: {smoke_state}\n")
        f.write(f"Trigger score: {smoke_score}\n")
        f.write("Last 30 seconds before trigger:\n")

        for entry in window_list[-pre_trigger_len:]:
            f.write(
                f"{entry[0]} | pm1_0={entry[1]} | pm2_5={entry[2]} | pm4_0={entry[3]} | "
                f"pm10={entry[4]} | humidity={entry[5]} | temperature={entry[6]} | "
                f"voc={entry[7]} | nox={entry[8]}\n"
            )

        f.write("-----\n")

def log_smoke_event(timestamp, smoke_state, smoke_score, latest_entry, short_avg, long_avg, short_delta, long_delta, criteria):
    with open("smoke_log.txt", "a") as f:
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"State: {smoke_state}\n")
        f.write(f"Score: {smoke_score}\n")

        f.write(
            f"PM1.0 | measured={latest_entry[1]} µg/m³ | short_avg={short_avg[0]} | short_delta={short_delta[0]} | "
            f"long_avg={long_avg[0]} | long_delta={long_delta[0]} | "
            f"long_delta_point={'yes' if criteria['pm1_0_long_delta'] else 'no'} | "
            f"spike_point={'yes' if criteria['pm1_0_spike'] else 'no'}\n"
        )

        f.write(
            f"PM2.5 | measured={latest_entry[2]} µg/m³ | short_avg={short_avg[1]} | short_delta={short_delta[1]} | "
            f"long_avg={long_avg[1]} | long_delta={long_delta[1]} | "
            f"abs_point={'yes' if criteria['pm2_5_abs'] else 'no'} | "
            f"long_delta_point={'yes' if criteria['pm2_5_long_delta'] else 'no'} | "
            f"short_vs_long_point={'yes' if criteria['pm2_5_short_vs_long'] else 'no'} | "
            f"spike_point={'yes' if criteria['pm2_5_spike'] else 'no'}\n"
        )

        f.write(
            f"PM4.0 | measured={latest_entry[3]} µg/m³ | short_avg={short_avg[2]} | short_delta={short_delta[2]} | "
            f"long_avg={long_avg[2]} | long_delta={long_delta[2]} | point=no\n"
        )

        f.write(
            f"PM10 | measured={latest_entry[4]} µg/m³ | short_avg={short_avg[3]} | short_delta={short_delta[3]} | "
            f"long_avg={long_avg[3]} | long_delta={long_delta[3]} | point=no\n"
        )

        f.write(
            f"Humidity | measured={latest_entry[5]} %RH | short_avg={short_avg[4]} | short_delta={short_delta[4]} | "
            f"long_avg={long_avg[4]} | long_delta={long_delta[4]} | point=no\n"
        )

        f.write(
            f"Temperature | measured={latest_entry[6]} °C | short_avg={short_avg[5]} | short_delta={short_delta[5]} | "
            f"long_avg={long_avg[5]} | long_delta={long_delta[5]} | point=no\n"
        )

        f.write(
            f"VOC | measured={latest_entry[7]} index | short_avg={short_avg[6]} | short_delta={short_delta[6]} | "
            f"long_avg={long_avg[6]} | long_delta={long_delta[6]} | point={'yes' if criteria['voc_spike'] else 'no'}\n"
        )

        f.write(
            f"NOx | measured={latest_entry[8]} index | short_avg={short_avg[7]} | short_delta={short_delta[7]} | "
            f"long_avg={long_avg[7]} | long_delta={long_delta[7]} | point=no\n"
        )

        if latest_entry[2] > 0:
            pm_ratio = round(latest_entry[1] / latest_entry[2], 2)
        else:
            pm_ratio = 0

        f.write(f"PM1.0/PM2.5 ratio | measured={pm_ratio} | point={'yes' if criteria['pm_ratio'] else 'no'}\n")
        f.write("-----\n")
        
#Main===========================================
# Start Measurement: 0x0021
bus.i2c_rdwr(i2c_msg.write(ADDR, [0x00, 0x21]))
print("Messung gestartet...")
time.sleep(1)

last_smoke_state = "CLEAR" # Default 

while True:
    try:
        entry = read_sensor_data()

        if entry is None:
            print("Noch keine fertigen Daten")
            time.sleep(Refresh_rate)
            continue

        update_window(Long_window_list, entry, Long_max_list_len)
        update_window(Short_window_list, entry, Short_max_list_len)

        print(str(entry))

        long_avg, long_delta = calculate_avg_and_delta(Long_window_list)
        short_avg, short_delta = calculate_avg_and_delta(Short_window_list)

        if long_avg is not None and short_avg is not None:
            smoke_state, smoke_score, criteria = analyze_smoke(entry, long_avg, short_avg, long_delta, short_delta)
            print("smoke_state:", smoke_state)
            print("smoke_score:", smoke_score)
            
            if last_smoke_state == "CLEAR" and smoke_state in ["SUSPICIOUS", "SMOKE"]:
                log_pre_smoke_window(Long_window_list, smoke_state, smoke_score)

            if smoke_state in ["SUSPICIOUS", "SMOKE"]:
                log_smoke_event(entry[0], smoke_state, smoke_score, entry, short_avg, long_avg, short_delta, long_delta, criteria)

            last_smoke_state = smoke_state
            
    except Exception as e:
        print("Error in main loop:", e)

    time.sleep(Refresh_rate)