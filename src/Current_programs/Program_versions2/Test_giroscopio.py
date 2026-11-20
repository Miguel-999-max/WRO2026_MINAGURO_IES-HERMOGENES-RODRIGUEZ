"""
TEST_GIROSCOPIO.PY - Comparamos el giroscopio L3G4200D con la brujula
(LSM303DLHC). No movemos el robot por programa: lo giramos a mano.

Necesitamos en la Pico: l3g4200d.py y lsm303_mag.py.
Robot encendido como en carrera (el foco lo encendemos a tope desde aqui).

1. Al arrancar dejamos el robot QUIETO unos 7 segundos: 1,5 s para que el
   chip se estabilice y 5 s para medir su error de cero.
2. Los dos empiezan en el mismo rumbo (el de la brujula en ese momento).
3. Cada medio segundo imprimimos: tiempo, rumbo del giroscopio, rumbo de la
   brujula, diferencia entre ellos, giro acumulado del giroscopio (sin dar la
   vuelta a 360) y velocidad de giro.

Cada 30 s imprimimos tambien un resumen: cuanto ha cambiado el giro
acumulado en esos 30 s y si el robot ha estado quieto todo ese tiempo. Si ha
estado quieto, ese cambio es la DERIVA real (la damos tambien en grados por
minuto).

Pruebas que hacemos (por separado, para que se vea claro cada una):
  a) SENTIDO: giramos el robot a la derecha. El rumbo del giroscopio debe
     SUBIR (como la brujula). Si baja, ponemos signo=1 en L3G4200D(...).
  b) DERIVA: lo dejamos quieto 3 minutos (lo que dura una ronda) y miramos
     los resumenes de 30 s.
  c) PRECISION: con un muro o una escuadra de referencia, damos 4 vueltas
     exactas de 360 grados a la derecha (el giro acumulado debe marcar
     +1440) y despues 4 a la izquierda (debe volver a 0). Al acabar cada
     tanda lo dejamos quieto unos segundos para leer el valor.
  d) TABLERO: lo movemos por las calles, siempre alineado con ellas, como en
     test_brujula_calles.py. Si la brujula se desvia en una zona y el
     giroscopio no, lo veremos en la columna de diferencia.
Paramos con Ctrl+C.
"""
from machine import Pin, I2C, PWM
import math
import time
from lsm303_mag import LSM303Mag
from l3g4200d import L3G4200D

foco = PWM(Pin(17))
foco.freq(20000)
foco.duty_u16(65535)  # foco a tope, como al escanear

i2c0 = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
mag = LSM303Mag(i2c0)
giro = L3G4200D(i2c0)


def rumbo_brujula(muestras=10):
    """Media de varias lecturas de la brujula, sumando vectores."""
    sx = sy = 0.0
    for _ in range(muestras):
        r = math.radians(mag.heading())
        sx += math.cos(r)
        sy += math.sin(r)
        time.sleep_ms(10)
    return math.degrees(math.atan2(sy, sx)) % 360


def diferencia(a, b):
    """Diferencia con signo en [-180, 180]."""
    return (a - b + 180) % 360 - 180


print("Robot QUIETO unos 7 s: medimos el error de cero del giroscopio...")
bias = giro.calibrar()
print("Error de cero = {:.1f} unidades ({:.2f} grados/s)".format(bias, bias * 0.0175))

inicio = rumbo_brujula()
giro.iniciar(inicio)
t0 = time.ticks_ms()
print("Rumbo inicial de los dos = {:.1f}. Ctrl+C para terminar.".format(inicio))
print("   t(s) | giroscopio | brujula | dif (bru-giro) | giro acumulado | velocidad")

t_bloque = time.ticks_ms()
acumulado_bloque = giro.acumulado()
quieto = True   # si en todo el bloque de 30 s el robot no ha girado
try:
    while True:
        b = rumbo_brujula()
        g = giro.heading()
        v = giro.velocidad()
        if abs(v) > 3:  # mas de 3 grados/s: lo estamos girando
            quieto = False
        t = time.ticks_diff(time.ticks_ms(), t0) / 1000
        print("{:7.1f} | {:9.1f}  | {:7.1f} | {:+8.1f}       | {:+9.1f}      | {:+6.1f} grados/s".format(
            t, g, b, diferencia(b, g), giro.acumulado(), v))

        if time.ticks_diff(time.ticks_ms(), t_bloque) >= 30000:
            cambio = giro.acumulado() - acumulado_bloque
            if quieto:
                print("----- ULTIMOS 30 s, ROBOT QUIETO: deriva = {:+.2f} grados ({:+.2f} grados/minuto) -----".format(
                    cambio, cambio * 2))
            else:
                print("----- ULTIMOS 30 s (el robot se ha movido): giro = {:+.1f} grados -----".format(cambio))
            t_bloque = time.ticks_ms()
            acumulado_bloque = giro.acumulado()
            quieto = True
        time.sleep_ms(400)
except KeyboardInterrupt:
    pass

giro.parar()
foco.duty_u16(0)
print("Fin. Giro acumulado total = {:+.1f} grados".format(giro.acumulado()))