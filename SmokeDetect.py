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
import csv
import os

Refresh_rate = 1  # in sec
pre_trigger_len = int(30 / Refresh_rate) # Number of previous datapoints to be logged once smoke is detected

DEBUG_TRIGGER_ENABLED = False # True to trigger Smoke Detection  
DEBUG_TRIGGER_AFTER_LOOPS = 5 # Iterations before artificial Smoke Detection is triggered 

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

    short_avg_pm1_0 = short_avg[0]
    short_avg_pm2_5 = short_avg[1]

    long_delta_pm1_0 = long_delta[0]
    long_delta_pm2_5 = long_delta[1]

    if pm2_5 > 12:
        pm_ratio_value = pm1_0 / pm2_5
    else:
        pm_ratio_value = 0

    criteria = {
        # Alte Namen beibehalten, aber neue Bedeutung
        "pm2_5_abs": pm2_5 > 12 or pm1_0 > 10,
        "pm2_5_long_delta": long_delta_pm2_5 > 3.0,
        "pm1_0_long_delta": long_delta_pm1_0 > 3.0,
        "pm2_5_spike": pm2_5 > long_avg_pm2_5 * 1.45,
        "pm1_0_spike": pm1_0 > long_avg_pm1_0 * 1.45,
        "pm2_5_short_vs_long": short_avg_pm2_5 > long_avg_pm2_5 * 1.20,
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

def log_pre_smoke_window(window_list, smoke_state, smoke_score):
    file_name = "pre_smoke_log.csv"
    file_exists = os.path.isfile(file_name)

    with open(file_name, "a", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "trigger_timestamp", "trigger_state", "trigger_score",
                "entry_timestamp", "pm1_0", "pm2_5", "pm4_0", "pm10",
                "humidity", "temperature", "voc", "nox"
            ])

        trigger_timestamp = window_list[-1][0]

        for entry in window_list[-pre_trigger_len:]:
            writer.writerow([
                trigger_timestamp, smoke_state, smoke_score,
                entry[0], entry[1], entry[2], entry[3], entry[4],
                entry[5], entry[6], entry[7], entry[8]
            ])

def log_smoke_event(timestamp, smoke_state, smoke_score, latest_entry, short_avg, long_avg, short_delta, long_delta, criteria):
    file_name = "smoke_log.csv"
    file_exists = os.path.isfile(file_name)

    if latest_entry[2] > 0:
        pm_ratio = round(latest_entry[1] / latest_entry[2], 2)
    else:
        pm_ratio = 0

    with open(file_name, "a", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "timestamp", "state", "score",
                "pm1_0", "pm2_5", "pm4_0", "pm10", "humidity", "temperature", "voc", "nox",
                "short_avg_pm1_0", "short_avg_pm2_5", "short_avg_pm4_0", "short_avg_pm10", "short_avg_humidity", "short_avg_temperature", "short_avg_voc", "short_avg_nox",
                "short_delta_pm1_0", "short_delta_pm2_5", "short_delta_pm4_0", "short_delta_pm10", "short_delta_humidity", "short_delta_temperature", "short_delta_voc", "short_delta_nox",
                "long_avg_pm1_0", "long_avg_pm2_5", "long_avg_pm4_0", "long_avg_pm10", "long_avg_humidity", "long_avg_temperature", "long_avg_voc", "long_avg_nox",
                "long_delta_pm1_0", "long_delta_pm2_5", "long_delta_pm4_0", "long_delta_pm10", "long_delta_humidity", "long_delta_temperature", "long_delta_voc", "long_delta_nox",
                "pm2_5_abs", "pm2_5_long_delta", "pm1_0_long_delta", "pm2_5_spike", "pm1_0_spike", "pm2_5_short_vs_long", "pm_ratio_point", "voc_spike",
                "pm_ratio"
            ])

        writer.writerow([
            timestamp, smoke_state, smoke_score,
            latest_entry[1], latest_entry[2], latest_entry[3], latest_entry[4], latest_entry[5], latest_entry[6], latest_entry[7], latest_entry[8],
            short_avg[0], short_avg[1], short_avg[2], short_avg[3], short_avg[4], short_avg[5], short_avg[6], short_avg[7],
            short_delta[0], short_delta[1], short_delta[2], short_delta[3], short_delta[4], short_delta[5], short_delta[6], short_delta[7],
            long_avg[0], long_avg[1], long_avg[2], long_avg[3], long_avg[4], long_avg[5], long_avg[6], long_avg[7],
            long_delta[0], long_delta[1], long_delta[2], long_delta[3], long_delta[4], long_delta[5], long_delta[6], long_delta[7],
            criteria["pm2_5_abs"], criteria["pm2_5_long_delta"], criteria["pm1_0_long_delta"], criteria["pm2_5_spike"],
            criteria["pm1_0_spike"], criteria["pm2_5_short_vs_long"], criteria["pm_ratio"], criteria["voc_spike"],
            pm_ratio
        ])
#Events=========================================
def handle_environment_event(event_type):
    if event_type == "smoke":
        print("Fenster schließt")       
        
#Main===========================================
# Start Measurement: 0x0021
bus.i2c_rdwr(i2c_msg.write(ADDR, [0x00, 0x21]))
print("Messung gestartet...")
time.sleep(1)

last_smoke_state = "CLEAR" # Default CLEAR
debug_loop_count = 0 # For debugging only

while True:
    smoke_state = "CLEAR"
    smoke_score = 0
    criteria = {}
    
    entry = read_sensor_data()

    if entry is None:
        print("Noch keine fertigen Daten")
        time.sleep(Refresh_rate)
        continue
    
    debug_loop_count += 1 #Debugging Counter 


    update_window(Long_window_list, entry, Long_max_list_len)
    update_window(Short_window_list, entry, Short_max_list_len)

    print(str(entry))

    long_avg, long_delta = calculate_avg_and_delta(Long_window_list)
    short_avg, short_delta = calculate_avg_and_delta(Short_window_list)

    if long_avg is not None and short_avg is not None:
        if DEBUG_TRIGGER_ENABLED and debug_loop_count >= DEBUG_TRIGGER_AFTER_LOOPS:
            smoke_state = "SMOKE"
            smoke_score = 999
            criteria = {
                "pm2_5_abs": True,
                "pm2_5_long_delta": True,
                "pm1_0_long_delta": True,
                "pm2_5_spike": True,
                "pm1_0_spike": True,
                "pm2_5_short_vs_long": True,
                "pm_ratio": True,
                "voc_spike": True
            }
            DEBUG_TRIGGER_ENABLED = False
        else:
            smoke_state, smoke_score, criteria = analyze_smoke(entry, long_avg, short_avg, long_delta, short_delta)
        
        print("smoke_state:", smoke_state)
        print("smoke_score:", smoke_score)
        
        if last_smoke_state != "SMOKE" and smoke_state == "SMOKE":
            log_pre_smoke_window(Long_window_list, smoke_state, smoke_score)

        if smoke_state == "SMOKE":
            log_smoke_event(entry[0], smoke_state, smoke_score, entry, short_avg, long_avg, short_delta, long_delta, criteria)

        last_smoke_state = smoke_state
        
#Trigger Events==============     
    if smoke_state == "SMOKE":
        handle_environment_event("smoke")   


    time.sleep(Refresh_rate)
