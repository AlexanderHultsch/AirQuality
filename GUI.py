import serial
import time

ser = serial.Serial("/dev/ttyAMA0", 9600, timeout=1)
time.sleep(0.5)

ser.write(b'value.txt="123"')
ser.write(b"\xff\xff\xff")

ser.close()