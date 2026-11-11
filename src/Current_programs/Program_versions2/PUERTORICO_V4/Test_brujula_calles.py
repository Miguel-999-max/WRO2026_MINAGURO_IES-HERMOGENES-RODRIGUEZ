"""
TEST_BRUJULA_CALLES.PY - Comprobamos la brujula en todo el tablero, despues
de calibrarla (calibrar_magnetometro.py y los valores nuevos en
lsm303_mag.py).

Como lo hacemos (robot encendido como en carrera, foco a tope):
  1. Ponemos el robot en el aparcamiento, alineado con el muro como en la
     salida de la ronda, y lanzamos el script. Durante 3 segundos, sin
     tocarlo, medimos el rumbo de REFERENCIA (calle 1).
  2. Calculamos los rumbos de las 4 calles como hace el programa
     (referencia + 90 grados por esquina, sentido horario como en la
     Mision 3).
  3. Movemos el robot a mano y lo dejamos quieto, bien alineado con la calle
     en la que este (con una regla o contra el muro), en varios puntos: el
     centro de cada calle, cerca de las esquinas, y sobre todo en la calle 1
     y en la esquina entre la calle 4 y la calle 1.
  4. Cada medio segundo imprimimos el rumbo medido, la calle mas cercana y
     el ERROR respecto al rumbo que el programa espera para esa calle.

Que buscamos: errores de pocos grados (menos de unos 3-4) en todo el
tablero. Si en una calle o en una zona el error es mucho mayor, ahi la
brujula engana al robot: puede ser la calibracion o algo metalico bajo el
tablero o cerca de el.

Solo necesitamos lsm303_mag.py en la Pico. Paramos con Ctrl+C.
"""
from machine import Pin, I2C, PWM
import math
import time
from lsm303_mag import LSM303Mag

foco = PWM(Pin(17))
foco.freq(20000)
foco.duty_u16(65535)   # foco a tope, como al escanear

i2c0 = I2C(0, sda=Pin(4), scl=Pin(5))
mag = LSM303Mag(i2c0)


def rumbo_medio(muestras=10):
    """Media de varias lecturas del rumbo, sumando vectores (asi la media de
    359 y 1 grados sale 0 y no 180)."""
    sx = sy = 0.0
    for _ in range(muestras):
        r = math.radians(mag.heading())
        sx += math.cos(r)
        sy += math.sin(r)
        time.sleep_ms(20)
    return math.degrees(math.atan2(sy, sx)) % 360


def diferencia(a, b):
    """Diferencia con signo en [-180, 180]."""
    return (a - b + 180) % 360 - 180


print("Robot en el aparcamiento, alineado como en la salida. No lo tocamos 3 s...")
time.sleep_ms(500)
lecturas = [rumbo_medio() for _ in range(5)]
sx = sum(math.cos(math.radians(r)) for r in lecturas)
sy = sum(math.sin(math.radians(r)) for r in lecturas)
referencia = math.degrees(math.atan2(sy, sx)) % 360
calles = [(referencia + 90 * i) % 360 for i in range(4)]
print("Referencia (calle 1) = {:.1f}. Rumbos esperados: calle 1 {:.1f}, calle 2 {:.1f}, "
      "calle 3 {:.1f}, calle 4 {:.1f}".format(referencia, *calles))
print("Ahora movemos el robot por el tablero, siempre alineado con su calle.")

try:
    while True:
        r = rumbo_medio()
        errores = [diferencia(r, c) for c in calles]
        i = min(range(4), key=lambda k: abs(errores[k]))
        print("rumbo = {:6.1f}   calle mas cercana = {}   error = {:+5.1f} grados".format(r, i + 1, errores[i]))
        time.sleep_ms(300)
except KeyboardInterrupt:
    pass

foco.duty_u16(0)
print("Fin.")