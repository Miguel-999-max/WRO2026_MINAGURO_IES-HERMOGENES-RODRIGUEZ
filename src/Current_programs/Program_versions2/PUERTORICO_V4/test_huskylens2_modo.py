"""
TEST STANDALONE - Comprobamos por que switch_algorithm() devuelve False
(1000 ms) cuando la Huskylens 2 ya esta en reconocimiento de color.

Hipotesis: al recibir SET_ALGORITHM la Huskylens 2 reinicia el algoritmo
aunque sea el mismo, y tarda mas de 1 s en confirmar.

Lo ejecutamos dos veces, cambiando MODO abajo:
  MODO = "CON_CAMBIO"  -> mandamos switch_algorithm con una espera de 5 s y
                          medimos cuanto tarda de verdad la confirmacion.
  MODO = "SIN_CAMBIO"  -> no mandamos switch_algorithm: solo knock y lectura.
                          Lo ejecutamos justo despues de apagar y encender la
                          Huskylens 2, para ver si recuerda el ultimo modo.

En los dos casos hacemos 60 consultas seguidas y damos un resumen: cuantas
devolvieron bloques, cuantas salieron vacias y en que posicion, y el tiempo.
Apuntamos la camara a los dos pilares y la dejamos quieta.
"""
from machine import Pin, I2C
import time
from huskylens2 import HuskyLensV2, ALGORITHM_COLOR_RECOGNITION

MODO = "CON_CAMBIO"      # "CON_CAMBIO" o "SIN_CAMBIO"
N_CONSULTAS = 60

i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000, timeout=100000)
husky = HuskyLensV2(i2c, address=0x50)

print("MODO:", MODO)
print("Direcciones I2C:", [hex(d) for d in i2c.scan()])

husky.vaciar()
ok_knock = False
for _ in range(3):
    ok_knock = husky.knock()
    if ok_knock:
        break
    time.sleep_ms(300)
print("knock() ->", ok_knock)

if MODO == "CON_CAMBIO":
    t0 = time.ticks_ms()
    ok = husky.switch_algorithm(ALGORITHM_COLOR_RECOGNITION, 5000)
    print("switch_algorithm(espera 5 s) -> {} ({} ms)".format(ok, time.ticks_diff(time.ticks_ms(), t0)))
else:
    print("Sin switch_algorithm.")

time.sleep_ms(500)

con_bloques = 0
vacias = []
tiempos = []
for n in range(N_CONSULTAS):
    t0 = time.ticks_us()
    bloques = husky.get_blocks(ALGORITHM_COLOR_RECOGNITION, solo_aprendidos=True)
    ms = time.ticks_diff(time.ticks_us(), t0) / 1000
    tiempos.append(ms)
    ids = sorted(b.id for b in bloques)
    if ids:
        con_bloques += 1
    else:
        vacias.append(n)
    print("{:2d}  {:5.1f} ms  ids {}".format(n, ms, ids))
    time.sleep_ms(100)

print("\n=== Resumen ({}) ===".format(MODO))
print("Consultas con pilares aprendidos:", con_bloques, "de", N_CONSULTAS)
print("Consultas vacias en las posiciones:", vacias)
print("Tiempo medio {:.1f} ms, maximo {:.1f} ms".format(sum(tiempos) / len(tiempos), max(tiempos)))
