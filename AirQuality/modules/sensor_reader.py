from smbus2 import i2c_msg
from datetime import datetime
import time


SCD41_READ_INTERVAL_SECONDS = 5.0

_last_scd41_read_time = 0.0
_last_scd41_data = {
    "co2": None,
    "scd41_temperature": None,
    "scd41_humidity": None,
}


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


def _scd41_crc8(data_bytes):
    crc = 0xFF
    for byte in data_bytes:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x31) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def _scd41_write_command(bus, scd41_addr, command):
    bus.i2c_rdwr(i2c_msg.write(scd41_addr, [(command >> 8) & 0xFF, command & 0xFF]))


def _scd41_read_words(bus, scd41_addr, command, word_count):
    _scd41_write_command(bus, scd41_addr, command)
    time.sleep(0.001)

    raw = i2c_msg.read(scd41_addr, word_count * 3)
    bus.i2c_rdwr(raw)
    data = list(raw)

    words = []
    for i in range(word_count):
        msb = data[i * 3]
        lsb = data[i * 3 + 1]
        crc = data[i * 3 + 2]

        if _scd41_crc8([msb, lsb]) != crc:
            raise ValueError("SCD41 CRC check failed")

        words.append((msb << 8) | lsb)

    return words


def start_scd41_periodic_measurement(bus, scd41_addr):
    """
    Starts periodic measurement mode on the SCD41.
    If the sensor is already running, continue without aborting.
    """
    try:
        _scd41_write_command(bus, scd41_addr, 0x21B1)
        time.sleep(0.05)
        print("SCD41 periodische Messung gestartet.")
    except OSError as e:
        print("SCD41 Start übersprungen / möglicherweise bereits aktiv:", e)
    except Exception as e:
        print("SCD41 Start fehlgeschlagen:", e)


def read_scd41_data(bus, scd41_addr):
    """
    Reads SCD41 values.
    Important: real sensor readout happens at most every 5 seconds.
    Between reads, the last valid values are returned.
    """
    global _last_scd41_read_time, _last_scd41_data

    now = time.time()
    if now - _last_scd41_read_time < SCD41_READ_INTERVAL_SECONDS:
        return dict(_last_scd41_data)

    _last_scd41_read_time = now

    try:
        ready_word = _scd41_read_words(bus, scd41_addr, 0xE4B8, 1)[0]

        if (ready_word & 0x07FF) == 0:
            return dict(_last_scd41_data)

        co2_raw, temp_raw, humidity_raw = _scd41_read_words(bus, scd41_addr, 0xEC05, 3)

        scd41_data = {
            "co2": int(co2_raw),
            "scd41_temperature": round(-45 + 175 * (temp_raw / 65535.0), 1),
            "scd41_humidity": round(100 * (humidity_raw / 65535.0), 1),
        }

        _last_scd41_data = scd41_data
        return dict(_last_scd41_data)

    except Exception as e:
        print("SCD41 Lesefehler:", e)
        return dict(_last_scd41_data)


def build_measurement(bus, sen55_addr, scd41_addr):
    """
    Reads all available sensors and returns one merged measurement dict.
    Returns None if the primary sensor has no new data yet.
    """
    sen55_data = read_sen55_data(bus, sen55_addr)
    if sen55_data is None:
        return None

    scd41_data = read_scd41_data(bus, scd41_addr)

    measurement = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **sen55_data,
        **scd41_data,
    }

    return measurement