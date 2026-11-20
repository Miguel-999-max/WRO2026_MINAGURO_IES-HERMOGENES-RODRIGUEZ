"""
CALIBRACION - Magnetometro LSM303DLHC (correccion de hierro duro)

Gira el ROBOT COMPLETO (no solo el sensor) 360 grados despacio, un par de
vueltas completas para asegurar cobertura. El script va registrando el
maximo y minimo de X e Y que ha visto hasta el momento, y en cada linea
imprime el offset que se aplicaria con esos datos - vereis como el offset
se va estabilizando a medida que completáis la vuelta.

Cuando el offset ya no cambie entre vueltas, anotad los ultimos valores de
OFFSET_X y OFFSET_Y que aparezcan y pasadmelos para meterlos en el driver.

Requiere subir tambien lsm303_mag.py a la Pico.
"""
from machine import Pin, I2C
from lsm303_mag import LSM303Mag
import time

i2c0 = I2C(0, sda=Pin(4), scl=Pin(5))
mag = LSM303Mag(i2c0)
print("Magnetometro listo. Gira el robot 360 grados, un par de vueltas...")

x_min = x_max = None
y_min = y_max = None

while True:
    x, y, z = mag.read_raw()

    if x_min is None:
        x_min = x_max = x
        y_min = y_max = y
    else:
        x_min = min(x_min, x)
        x_max = max(x_max, x)
        y_min = min(y_min, y)
        y_max = max(y_max, y)

    offset_x = (x_max + x_min) // 2
    offset_y = (y_max + y_min) // 2

    print(f"x={x:6d} y={y:6d}  |  x_min={x_min:6d} x_max={x_max:6d} y_min={y_min:6d} y_max={y_max:6d}  |  OFFSET_X={offset_x} OFFSET_Y={offset_y}")
    time.sleep_ms(200)