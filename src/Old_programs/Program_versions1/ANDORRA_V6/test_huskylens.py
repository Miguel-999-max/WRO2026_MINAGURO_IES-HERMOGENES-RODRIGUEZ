"""
TEST STANDALONE - Datos crudos de la Huskylens por terminal
Muestra en tiempo real los 5 campos que manda cada bloque detectado:
id, x_center, y_center, width, height.

Requiere subir tambien huskylens.py a la Pico.

Conexion:
  SDA1 -> GPIO14
  SCL1 -> GPIO15
"""

from machine import Pin, I2C
from huskylens import HuskyLens
import time

i2c1 = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000, timeout=100000)
hl = HuskyLens(i2c1)

print("Dispositivos I2C1 encontrados:", [hex(a) for a in i2c1.scan()])
print("Knock:", hl.knock())
print("--- Lectura continua ---")

while True:
    bloques = hl.get_blocks()

    if len(bloques) == 0:
        print("Sin bloques detectados.")
    else:
        for b in bloques:
            color = "ROJO" if b.id == 1 else ("VERDE" if b.id == 2 else "ID%d" % b.id)
            area = b.width * b.height
            print("%s -> id=%d x=%d y=%d w=%d h=%d (area=%d)" % (
                color, b.id, b.x_center, b.y_center, b.width, b.height, area))

    time.sleep_ms(200)