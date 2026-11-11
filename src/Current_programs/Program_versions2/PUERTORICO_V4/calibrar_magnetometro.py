"""
CALIBRAR_MAGNETOMETRO.PY - Calibracion del magnetometro LSM303DLHC:
hierro duro (OFFSET_X, OFFSET_Y) y hierro blando (ESCALA_X, ESCALA_Y).

IMPORTANTE: calibramos con el robot ENCENDIDO COMO EN CARRERA (fuente con el
pulsador, rele cerrado, los dos bucks, la Huskylens 2 y los TFmini en
marcha). Encendemos tambien el foco a tope, como cuando escanea. Todo lo que
lleva corriente cerca del sensor desvia el campo, y queremos medirlo tal y
como estara en la ronda. Los motores no los movemos.

Como lo hacemos:
  1. Ponemos el robot en el suelo del tablero, lejos de objetos metalicos
     grandes (patas de mesa, ordenador, cajas de herramientas).
  2. Lanzamos el script y giramos el ROBOT COMPLETO (no solo el sensor)
     sobre si mismo, muy despacio y plano, 3 vueltas completas.
  3. Cada medio segundo imprimimos los valores que tendriamos con lo medido
     hasta ese momento. Cuando dejen de cambiar de una vuelta a otra,
     paramos con Ctrl+C: imprimimos el resultado final.
  4. Copiamos OFFSET_X, OFFSET_Y, ESCALA_X y ESCALA_Y en lsm303_mag.py
     (OFFSET_X_DEFAULT, etc.).

Que es cada cosa:
  - Hierro duro: el circulo que dibujan las lecturas X-Y al girar no esta
    centrado en 0. El offset es su centro.
  - Hierro blando: el circulo se ha aplastado en una elipse. Con las escalas
    lo dejamos redondo: asi los rumbos de las 4 calles quedan separados 90
    grados de verdad.
Tambien imprimimos la relacion entre los dos ejes: si sale muy lejos de 1
(por ejemplo, menos de 0.8 o mas de 1.25), hay mucho hierro blando y conviene
alejar del sensor cables o piezas metalicas.

Solo necesitamos lsm303_mag.py en la Pico.
"""
from machine import Pin, I2C, PWM
import time
from lsm303_mag import LSM303Mag

# Foco a tope, como al escanear (GPIO17, PWM a 20 kHz)
foco = PWM(Pin(17))
foco.freq(20000)
foco.duty_u16(65535)

i2c0 = I2C(0, sda=Pin(4), scl=Pin(5))
mag = LSM303Mag(i2c0)
print("Magnetometro listo. Giramos el robot completo 360 grados, despacio, 3 vueltas.")
print("Ctrl+C para terminar y ver el resultado final.")

x_min = x_max = y_min = y_max = None
n = 0


def resultado():
    """Calculamos offset y escalas con los extremos medidos."""
    offset_x = (x_max + x_min) // 2
    offset_y = (y_max + y_min) // 2
    radio_x = (x_max - x_min) / 2
    radio_y = (y_max - y_min) / 2
    if radio_x <= 0 or radio_y <= 0:
        return offset_x, offset_y, 1.0, 1.0, 1.0
    radio_medio = (radio_x + radio_y) / 2
    return offset_x, offset_y, radio_medio / radio_x, radio_medio / radio_y, radio_x / radio_y


t_impresion = time.ticks_ms()
try:
    while True:
        x, y, z = mag.read_raw()
        n += 1
        if x_min is None:
            x_min = x_max = x
            y_min = y_max = y
        else:
            x_min = min(x_min, x)
            x_max = max(x_max, x)
            y_min = min(y_min, y)
            y_max = max(y_max, y)

        if time.ticks_diff(time.ticks_ms(), t_impresion) >= 500:
            t_impresion = time.ticks_ms()
            ox, oy, ex, ey, rel = resultado()
            print("x={:6d} y={:6d} | x[{:6d},{:6d}] y[{:6d},{:6d}] | OFFSET_X={} OFFSET_Y={} "
                  "ESCALA_X={:.3f} ESCALA_Y={:.3f} (relacion ejes {:.2f})".format(
                      x, y, x_min, x_max, y_min, y_max, ox, oy, ex, ey, rel))
        time.sleep_ms(50)
except KeyboardInterrupt:
    pass

foco.duty_u16(0)
if x_min is not None:
    ox, oy, ex, ey, rel = resultado()
    print()
    print("========== RESULTADO ({} lecturas) ==========".format(n))
    print("OFFSET_X_DEFAULT = {}".format(ox))
    print("OFFSET_Y_DEFAULT = {}".format(oy))
    print("ESCALA_X_DEFAULT = {:.3f}".format(ex))
    print("ESCALA_Y_DEFAULT = {:.3f}".format(ey))
    print("Relacion entre ejes = {:.2f} (cerca de 1 es lo ideal)".format(rel))
    print("Copiamos estos cuatro valores en lsm303_mag.py.")