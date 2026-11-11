"""
Prueba del TFmini-S en modo I2C, cableado a I2C1:
  blanco (SDA) -> GPIO14, verde (SCL) -> GPIO15, rojo 5V, negro GND.
Muestra el escaneo del bus, la version, lecturas sueltas y el tiempo real
que cuesta cada lectura (el dato de cadencia que faltaba).
"""
from machine import Pin, I2C
import time

ADDR = 0x10
CMD_DATOS = b'\x5A\x05\x00\x01\x60'
CMD_VERSION = b'\x5A\x04\x01\x5F'

i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000)


def leer():
    """(distancia_cm, fuerza) o None si la lectura no es valida."""
    i2c.writeto(ADDR, CMD_DATOS)
    time.sleep_ms(1)
    b = i2c.readfrom(ADDR, 9)
    if b[0] != 0x59 or b[1] != 0x59 or (sum(b[:8]) & 0xFF) != b[8]:
        return None
    dist = b[2] | (b[3] << 8)
    fuerza = b[4] | (b[5] << 8)
    if dist > 2000:  # 65535/65534/65532 = fuerza baja o saturacion
        return None
    return dist, fuerza


print("Escaneo I2C1:", [hex(a) for a in i2c.scan()])

try:
    i2c.writeto(ADDR, CMD_VERSION)
    time.sleep_ms(100)
    v = i2c.readfrom(ADDR, 7)
    print("Version (V1 V2 V3):", v[3], v[4], v[5])
except OSError as e:
    print("Sin respuesta a 'version' en 0x10:", e)

print("\n20 lecturas (en la plantilla de longitud conocida):")
for _ in range(20):
    try:
        print(leer())
    except OSError as e:
        print("Error I2C:", e)
    time.sleep_ms(100)

print("\nTiempo por lectura (100 lecturas, una cada 25 ms):")
tiempos, malas = [], 0
for _ in range(100):
    t0 = time.ticks_us()
    try:
        r = leer()
    except OSError:
        r = None
    tiempos.append(time.ticks_diff(time.ticks_us(), t0))
    if r is None:
        malas += 1
    time.sleep_ms(25)
print("media {:.2f} ms, max {:.2f} ms, no validas {}/100".format(
    sum(tiempos) / len(tiempos) / 1000, max(tiempos) / 1000, malas))