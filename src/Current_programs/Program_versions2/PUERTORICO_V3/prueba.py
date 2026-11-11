from machine import I2C, Pin
from huskylens2 import HuskyLensV2, ALGORITHM_COLOR_RECOGNITION
i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000, timeout=100000)
h = HuskyLensV2(i2c, address=0x50)
h.vaciar()
print(h.knock())
print(h.switch_algorithm(ALGORITHM_COLOR_RECOGNITION))