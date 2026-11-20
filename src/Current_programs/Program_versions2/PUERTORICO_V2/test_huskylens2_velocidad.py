"""
TEST DE VELOCIDAD - Huskylens 2 (reconocimiento de color) por I2C1.

No modifica el driver huskylens2.py: solo lo usa para probar varias
combinaciones de espera y de bytes leidos tras pedir el resultado, a 100 kHz y
a 400 kHz de bus, y comprobar cuanto tarda cada consulta y si la respuesta
llega COMPLETA. Una respuesta es completa si trae la trama INFO y tantas
tramas de bloque como indica INFO (contando tambien el bloque id 0).

Como prepararlo:
  - Aprendemos antes los dos colores (id 1 rojo, id 2 verde) y dejamos la
    camara QUIETA apuntando a una escena con los dos pilares a la vez.
  - Subimos huskylens2.py a la Pico y ejecutamos este archivo (tarda ~1 min).
  - No movemos nada hasta que imprima el resumen final.

Las variantes que leen pocos bytes pueden dejar restos en el bus y estropear
las consultas siguientes: eso lo detecta el porcentaje de respuestas completas.

Variante F: pedimos primero solo la trama INFO (16 bytes), que dice cuantos
bloques vienen, y despues leemos exactamente esos bloques (23 bytes cada uno).

Formato de la trama INFO, visto en las capturas reales: cinco campos de 2
bytes (little-endian). El primero es el numero de colores aprendidos (2 en
nuestro caso) y el segundo es el numero total de bloques que acompanan a la
trama, incluido el bloque id 0. La version anterior de este test confundio
el primer campo con el numero de bloques y por eso sus resultados no valian.

La variante A0 es la referencia: la lectura actual del driver con 300 ms de
pausa entre consultas, como en test_huskylens2.py, que funcionaba bien. Las
demas usan la pausa corta (la del robot en marcha). Si A0 sale bien y A mal,
el problema es consultar demasiado deprisa.

A 400 kHz la Huskylens 2 no respondio en la prueba anterior, asi que solo
probamos 100 kHz, que es la frecuencia actual del robot.
"""
from machine import Pin, I2C
import time
from huskylens2 import (HuskyLensV2, ALGORITHM_COLOR_RECOGNITION, CMD_GET_RESULT,
                        CMD_RETURN_INFO, CMD_RETURN_BLOCKS)

PRUEBAS_POR_VARIANTE = 30
PAUSA_ENTRE_CONSULTAS_MS = 40
UMBRAL_COMPLETAS = 95          # % minimo de respuestas completas para aceptar una variante
FRECUENCIAS = (100000,)
BYTES_INFO = 16                # trama INFO: 5 de cabecera + 10 de datos + 1 de checksum
BYTES_BLOQUE = 23              # trama de bloque con el nombre "Color": 5 + 17 + 1

# (nombre, espera en ms tras la peticion, bytes a leer (None = por partes),
#  pausa en ms entre consultas)
VARIANTES = (
    ("A0 actual, pausa larga (referencia)", 20, 250, 300),
    ("A actual: espera 20 ms, lee 250", 20, 250, PAUSA_ENTRE_CONSULTAS_MS),
    ("B espera 20 ms, lee 100", 20, 100, PAUSA_ENTRE_CONSULTAS_MS),
    ("C espera 10 ms, lee 100", 10, 100, PAUSA_ENTRE_CONSULTAS_MS),
    ("D espera 5 ms, lee 100", 5, 100, PAUSA_ENTRE_CONSULTAS_MS),
    ("E espera 5 ms, lee 64", 5, 64, PAUSA_ENTRE_CONSULTAS_MS),
    ("F por partes: INFO y luego bloques", None, None, PAUSA_ENTRE_CONSULTAS_MS),
)


def vaciar(husky):
    """Leemos hasta que ya no quedan tramas pendientes en la Huskylens 2."""
    for _ in range(6):
        if b'\x55\xaa' not in husky._leer_bruto(250):
            break


def consulta_fija(husky, espera_ms, n):
    husky._enviar(CMD_GET_RESULT, ALGORITHM_COLOR_RECOGNITION)
    time.sleep_ms(espera_ms)
    return husky._leer_bruto(n)


def consulta_por_partes(husky):
    husky._enviar(CMD_GET_RESULT, ALGORITHM_COLOR_RECOGNITION)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 100:
        time.sleep_ms(2)
        info = husky._leer_bruto(BYTES_INFO)
        if len(info) >= BYTES_INFO and info[0] == 0x55 and info[1] == 0xAA and info[2] == CMD_RETURN_INFO:
            n_bloques = info[7] | (info[8] << 8)  # segundo campo de INFO: bloques totales
            if n_bloques:
                return info + husky._leer_bruto(n_bloques * BYTES_BLOQUE)
            return info
    return b''


def evaluar(husky, buf):
    """Devuelve (bloques anunciados por INFO o None, bloques realmente recibidos)."""
    anunciados = None
    recibidos = 0
    for cmd, algo, data in husky._parsear_tramas(buf):
        if cmd == CMD_RETURN_INFO and len(data) >= 4:
            anunciados = data[2] | (data[3] << 8)
        elif cmd == CMD_RETURN_BLOCKS:
            recibidos += 1
    return anunciados, recibidos


resumen = []
for freq in FRECUENCIAS:
    i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=freq, timeout=100000)
    husky = HuskyLensV2(i2c, address=0x50)
    print("\n=== Bus I2C1 a {} kHz ===".format(freq // 1000))
    if not husky.knock():
        print("La Huskylens 2 no responde a esta frecuencia: se descartan todas las variantes.")
        continue
    husky.switch_algorithm(ALGORITHM_COLOR_RECOGNITION)

    for nombre, espera, n, pausa in VARIANTES:
        vaciar(husky)
        tiempos = []
        completas = 0
        sin_info = 0
        bloques_ref = 0
        for _ in range(PRUEBAS_POR_VARIANTE):
            t0 = time.ticks_us()
            if espera is None:
                buf = consulta_por_partes(husky)
            else:
                buf = consulta_fija(husky, espera, n)
            tiempos.append(time.ticks_diff(time.ticks_us(), t0) / 1000)
            anunciados, recibidos = evaluar(husky, buf)
            if anunciados is None:
                sin_info += 1
            elif anunciados == recibidos:
                completas += 1
                bloques_ref = max(bloques_ref, recibidos)
            time.sleep_ms(pausa)
        media = sum(tiempos) / len(tiempos)
        pct = completas * 100 // PRUEBAS_POR_VARIANTE
        print("{:<38} media {:5.1f} ms  max {:5.1f} ms  completas {:3d}%  sin INFO {}  bloques {}".format(
            nombre, media, max(tiempos), pct, sin_info, bloques_ref))
        resumen.append((freq, nombre, media, pct))

# Dejamos el bus como en el robot
I2C(1, sda=Pin(14), scl=Pin(15), freq=100000, timeout=100000)

print("\n=== Resumen ===")
validas = [r for r in resumen if r[3] >= UMBRAL_COMPLETAS]
if not validas:
    print("Ninguna variante llega al {}% de respuestas completas: revisamos la escena (pilares a la vista) y repetimos.".format(UMBRAL_COMPLETAS))
else:
    validas.sort(key=lambda r: r[2])
    for freq, nombre, media, pct in validas[:3]:
        print("{} kHz | {} | media {:.1f} ms | completas {}%".format(freq // 1000, nombre, media, pct))
    mejor100 = [r for r in validas if r[0] == 100000]
    if mejor100:
        print("La mejor a 100 kHz (la frecuencia actual del robot): {} -> {:.1f} ms".format(mejor100[0][1], mejor100[0][2]))
