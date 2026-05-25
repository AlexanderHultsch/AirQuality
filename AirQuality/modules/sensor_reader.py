from smbus2 import i2c_msg
from datetime import datetime
import time


def read_sen55_data(bus, sen55_addr):
    """
    Reads data from the existing PM / VOC / NOX sensor.
    Returns a dict or None if data is not ready.
    """
    bus.i2c_rdwr(i2c_msg.write(sen55_addr, [0x02, 0x02]))
    time.sleep(0.01)

    ready = i2c_msg.read(sen55_addr, 3)
    bus.i2c_rdwr(ready)
    r = list(ready)

    if ((r[0] << 8) | r[1]) == 1:
        bus.i2c_rdwr(i2c_msg.write(sen55_addr, [0x03, 0xC4]))
        time.sleep(0.01)

        data = i2c_msg.read(sen55_addr, 24)
        bus.i2c_rdwr(data)
        d = list(data)

        return {
            "pm1_0": round(((d[0] << 8) | d[1]) / 10.0, 1),
            "pm2_5": round(((d[3] << 8) | d[4]) / 10.0, 1),
            "pm4_0": round(((d[6] << 8) | d[7]) / 10.0, 1),
            "pm10": round(((d[9] << 8) | d[10]) / 10.0, 1),
            "sen55_humidity": round(((d[12] << 8) | d[13]) / 100.0, 1),
            "sen55_temperature": round(((d[15] << 8) | d[16]) / 200.0, 1),
            "voc": round(((d[18] << 8) | d[19]) / 10.0, 1),
            "nox": round(((d[21] << 8) | d[22]) / 10.0, 1),
        }

    return None


def read_scd41_data():
    """
    Placeholder for future SCD41 integration.
    Returns a dict with reserved fields.
    """
    return {
        "co2": None,
        "scd41_temperature": None,
        "scd41_humidity": None,
    }


def build_measurement(bus, sen55_addr):
    """
    Reads all available sensors and returns one merged measurement dict.
    Returns None if the primary sensor has no new data yet.
    """
    sen55_data = read_sen55_data(bus, sen55_addr)
    if sen55_data is None:
        return None

    scd41_data = read_scd41_data()

    measurement = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **sen55_data,
        **scd41_data,
    }

    return measurement