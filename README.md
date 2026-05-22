# SmokeAlarm

A Raspberry Pi project that detects cigarette smoke on the balcony and
automatically activates countermeasures to clear the air.

---

## Features

| Countermeasure | Description |
|---|---|
| 🔔 Buzzer alarm | Activates an active buzzer for a configurable duration |
| 💨 Ventilation fan | Switches a relay to turn on a fan and keep it running after smoke clears |
| 📲 Push notification | Sends an alert to your phone via [ntfy.sh](https://ntfy.sh) |

---

## Hardware

### Components

| Component | Notes |
|---|---|
| Raspberry Pi (any model with GPIO) | Tested on Pi 3B+ and Pi 4 |
| MQ-2 smoke / gas sensor | Detects LPG, propane, methane, alcohol, hydrogen, and smoke |
| MCP3008 ADC | 10-bit, 8-channel SPI ADC (the Pi has no built-in ADC) |
| Active buzzer | Any 3.3 V / 5 V active buzzer |
| 5 V relay module | 1-channel relay board with optocoupler isolation |
| Ventilation fan | Powered through the relay (mains or 12 V DC) |

### Wiring diagram

```
Raspberry Pi          MCP3008 (ADC)
───────────           ────────────
3.3 V     ──────────► VDD / VREF
GND       ──────────► AGND / DGND
GPIO 11 (SCLK) ─────► CLK
GPIO 9  (MISO) ─────► DOUT
GPIO 10 (MOSI) ─────► DIN
GPIO 8  (CE0)  ─────► CS/SHDN

MCP3008 CH0  ◄──────  MQ-2 AOUT
5 V          ──────►  MQ-2 VCC
GND          ──────►  MQ-2 GND

GPIO 17  ──────────►  Buzzer (+)
GND      ──────────►  Buzzer (-)

GPIO 27  ──────────►  Relay IN
5 V      ──────────►  Relay VCC
GND      ──────────►  Relay GND
```

> **Note:** The MQ-2 sensor requires a 24-hour warm-up period for accurate
> readings after first power-on.  Allow ~30 seconds at a minimum before
> trusting the ADC values.

---

## Software

### Requirements

* Python 3.9+
* `requests` library
* `RPi.GPIO` and `spidev` (installed automatically on Raspberry Pi OS)

### Installation

```bash
# Clone the repository
git clone https://github.com/AlexanderHultsch/SmokeAlarm.git
cd SmokeAlarm

# Install Python dependencies
pip install -r requirements.txt

# On the Raspberry Pi, also install the hardware libraries
pip install RPi.GPIO spidev
```

### Running

```bash
# Run directly
python -m smoke_alarm

# Or use the console script after pip install -e .
smoke-alarm
```

### Configuration

All settings can be overridden via **environment variables**:

| Variable | Default | Description |
|---|---|---|
| `SMOKEALARM_SMOKE_THRESHOLD` | `300` | ADC value (0-1023) that triggers an alarm |
| `SMOKEALARM_CONSECUTIVE_READINGS` | `3` | Consecutive above-threshold readings needed |
| `SMOKEALARM_POLL_INTERVAL` | `1.0` | Seconds between sensor reads |
| `SMOKEALARM_SPI_BUS` | `0` | SPI bus for the MCP3008 |
| `SMOKEALARM_SPI_DEVICE` | `0` | SPI device (chip-select) |
| `SMOKEALARM_SENSOR_ADC_CHANNEL` | `0` | MCP3008 channel (0-7) |
| `SMOKEALARM_BUZZER_ENABLED` | `true` | Enable buzzer alarm |
| `SMOKEALARM_BUZZER_PIN` | `17` | BCM pin for the buzzer |
| `SMOKEALARM_BUZZER_DURATION` | `5.0` | Seconds buzzer sounds per alarm |
| `SMOKEALARM_RELAY_ENABLED` | `true` | Enable relay (fan) control |
| `SMOKEALARM_RELAY_PIN` | `27` | BCM pin for the relay |
| `SMOKEALARM_RELAY_DURATION` | `30.0` | Seconds fan runs after smoke clears |
| `SMOKEALARM_RELAY_ACTIVE_LOW` | `false` | Set `true` for active-low relay boards |
| `SMOKEALARM_NTFY_ENABLED` | `false` | Enable push notifications |
| `SMOKEALARM_NTFY_URL` | `https://ntfy.sh` | ntfy server URL |
| `SMOKEALARM_NTFY_TOPIC` | `smokealarm-alerts` | ntfy topic name |
| `SMOKEALARM_NTFY_TOKEN` | _(empty)_ | Bearer token for private ntfy topics |
| `SMOKEALARM_LOG_LEVEL` | `INFO` | Logging level |
| `SMOKEALARM_LOG_FILE` | _(empty)_ | Log file path (stdout if empty) |

Example – start with push notifications enabled:

```bash
SMOKEALARM_NTFY_ENABLED=true \
SMOKEALARM_NTFY_TOPIC=my-private-topic \
SMOKEALARM_NTFY_TOKEN=my-secret-token \
python -m smoke_alarm
```

### Running as a systemd service

```ini
# /etc/systemd/system/smoke-alarm.service
[Unit]
Description=SmokeAlarm – balcony cigarette smoke detector
After=network.target

[Service]
ExecStart=/usr/bin/python3 -m smoke_alarm
WorkingDirectory=/home/pi/SmokeAlarm
Environment=SMOKEALARM_NTFY_ENABLED=true
Environment=SMOKEALARM_NTFY_TOPIC=my-private-topic
Restart=on-failure
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now smoke-alarm
```

---

## Development

### Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

### Project structure

```
SmokeAlarm/
├── smoke_alarm/
│   ├── __init__.py      # Package metadata
│   ├── __main__.py      # python -m smoke_alarm entry-point
│   ├── config.py        # All configuration (env-var overridable)
│   ├── sensor.py        # MQ-2 sensor via MCP3008 ADC
│   ├── alarm.py         # Countermeasures (buzzer, relay, notifications)
│   └── main.py          # Polling loop and CLI entry-point
├── tests/
│   ├── test_sensor.py
│   ├── test_alarm.py
│   └── test_main.py
├── requirements.txt
├── requirements-dev.txt
├── setup.py
└── pytest.ini
```

---

## How it works

1. The main loop reads the MQ-2 sensor every second (configurable) via
   the MCP3008 ADC over SPI.
2. If the ADC reading exceeds `SMOKE_THRESHOLD` for
   `CONSECUTIVE_READINGS` samples in a row (to filter noise), the alarm
   is triggered.
3. All enabled countermeasures fire simultaneously:
   * The buzzer sounds for `BUZZER_DURATION` seconds.
   * The relay switches the ventilation fan on.
   * A push notification is sent to your phone.
4. Once the reading drops below the threshold, the fan continues running
   for `RELAY_DURATION` seconds to flush residual smoke, then switches off.

---

## License

MIT