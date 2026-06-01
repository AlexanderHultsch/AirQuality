#!/bin/bash

cd /home/alex/Documents/AirQuality || exit 1

python3 AirQuality_Main.py &
PY_PID=$!

echo "AirQuality läuft. Tippe 'end' und drücke Enter zum Beenden."

while true; do
    read -r CMD
    if [ "$CMD" = "end" ]; then
        echo "Beende AirQuality..."
        kill "$PY_PID" 2>/dev/null
        sleep 2
        kill -9 "$PY_PID" 2>/dev/null
        break
    fi
done