"""
TEST STANDALONE - Prueba de la Huskylens 2 en modo RECONOCIMIENTO DE COLOR
con el driver huskylens2.py (verificado contra el hardware real el
15/10/2026). La Huskylens 2 debe estar en protocolo I2C.

Cableado: bus I2C1 de la Pico (SDA=GPIO14, SCL=GPIO15), el mismo bus donde
va el TFmini lateral derecho (0x10).

Que hace, en orden:
  1. Escanea el bus I2C1: esperamos 0x10 (TFmini) y 0x50 (Huskylens 2).
  2. Manda KNOCK.
  3. Pide el modo reconocimiento de color y mide cuanto tarda en confirmarlo.
  4. En bucle, pide resultados y los imprime con el tiempo de cada consulta.
     Mostramos tambien los bloques con id 0 (colores no aprendidos), que el
     programa del robot descarta: solo cuentan el id 1 (rojo) y el id 2 (verde).

Antes de lanzarlo, aprendemos los colores en la propia Huskylens 2:
  - Entramos en "Color Recognition" y borramos con "Forget ID".
  - Apuntamos el "+" central al pilar rojo y pulsamos A -> ID 1.
  - Apuntamos el "+" central al pilar verde y pulsamos A -> ID 2.
"""
from machine import Pin, I2C
import time
from huskylens2 import HuskyLensV2, ALGORITHM_COLOR_RECOGNITION

I2C_BUS = 1
SDA_PIN = 14
SCL_PIN = 15

i2c = I2C(I2C_BUS, sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100000, timeout=100000)

print("--- Paso 1: escaneo I2C ---")
direcciones = i2c.scan()
print("Direcciones encontradas:", [hex(d) for d in direcciones])
if 0x50 not in direcciones:
    print("AVISO: 0x50 no aparece - comprobamos que la Huskylens 2 esta en protocolo I2C y bien cableada.")

husky = HuskyLensV2(i2c, address=0x50)

print("\n--- Paso 2: KNOCK ---")
print("knock() ->", husky.knock())

print("\n--- Paso 3: cambiar a ALGORITHM_COLOR_RECOGNITION ---")
t0 = time.ticks_ms()
ok = husky.switch_algorithm(ALGORITHM_COLOR_RECOGNITION)
print("switch_algorithm() -> {} ({} ms)".format(ok, time.ticks_diff(time.ticks_ms(), t0)))

print("\n--- Paso 4: bucle de lectura (Ctrl+C para parar) ---")
print("Apuntamos la camara al pilar rojo y al verde mientras corre.")
time.sleep_ms(500)

while True:
    t0 = time.ticks_us()
    bloques = husky.get_blocks(ALGORITHM_COLOR_RECOGNITION, solo_aprendidos=False)
    ms = time.ticks_diff(time.ticks_us(), t0) / 1000
    if bloques:
        for b in bloques:
            marca = "" if b.id in (1, 2) else "  <- id sin aprender: el robot lo ignora"
            print(b, marca)
        print("   consulta: {:.1f} ms".format(ms))
    else:
        print("(sin bloques)  consulta: {:.1f} ms".format(ms))
    time.sleep_ms(300)
