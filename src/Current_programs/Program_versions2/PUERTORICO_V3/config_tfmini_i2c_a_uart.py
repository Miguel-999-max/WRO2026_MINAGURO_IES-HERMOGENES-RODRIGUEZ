"""
CONFIG_TFMINI_I2C_A_UART.PY - Pasamos un TFmini-S que esta en modo I2C
(direccion 0x10) a modo UART (115200 baudios, el de fabrica).

PASO 1 de 2. Despues ejecutamos config_tfmini_uart_demanda.py (PASO 2).

Cableado (como estaba el derecho en el robot, en I2C1):
  blanco (RXD/SDA) -> GPIO14 (SDA1)
  verde  (TXD/SCL) -> GPIO15 (SCL1)
  rojo -> 5V, negro -> GND
La Huskylens 2 puede seguir conectada al bus (esta en 0x50, no molesta).
Las pull-up de 5k1 del bus nos sirven tambien para el TFmini.

Mientras el sensor esta en modo I2C solo escucha comandos por I2C: por eso
mandamos aqui el cambio de interfaz. Comandos (manual Benewake TFmini-S):
  5A 05 0A 00 69  -> interfaz de comunicacion = UART
  5A 04 11 6F     -> guardar en flash
Al cambiar de interfaz, el sensor puede dejar de contestar por I2C en el
mismo instante: no nos preocupa no recibir respuesta. Lo que confirma que
ha funcionado es el PASO 2 (que conteste por UART).

Si algo saliera mal y el sensor no contestara ni por I2C ni por UART, el
comando de restaurar fabrica (5A 04 10 6E) lo devuelve a UART a 115200.
"""
from machine import Pin, I2C
import time

DIRECCION = 0x10

i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000, timeout=100000)


def trama(*datos):
    """Anadimos el checksum (suma de 8 bits) al final de la trama."""
    b = bytes(datos)
    return b + bytes([sum(b) & 0xFF])


def fmt(b):
    return ' '.join('{:02X}'.format(x) for x in b) if b else None


def enviar(cmd, n_resp, espera_ms=100):
    """Mandamos cmd por I2C y leemos n_resp bytes. Si el bus falla (lo normal
    justo despues de cambiar a UART), devolvemos None sin parar el script."""
    try:
        i2c.writeto(DIRECCION, cmd)
    except OSError as e:
        print("  error I2C al escribir:", e)
        return None
    time.sleep_ms(espera_ms)
    try:
        return i2c.readfrom(DIRECCION, n_resp)
    except OSError as e:
        print("  error I2C al leer (puede ser normal tras el cambio):", e)
        return None


print("PASO 1: pasamos el TFmini-S de I2C a UART ...")
direcciones = i2c.scan()
print("Direcciones I2C:", [hex(d) for d in direcciones])

if DIRECCION not in direcciones:
    print("No vemos el 0x10. Revisamos cableado (blanco->GPIO14, verde->GPIO15), 5V y GND.")
    print("Si el sensor ya estuviera en UART, no aparece en I2C: pasamos directamente al PASO 2.")
else:
    # Interfaz = UART. Respuesta esperada (si llega): 5A 05 0A 00 69
    r = enviar(trama(0x5A, 0x05, 0x0A, 0x00), 5)
    print("Interfaz UART. Respuesta:", fmt(r), "(esperado: 5A 05 0A 00 69, o nada)")

    # Guardar en flash. Respuesta esperada (si llega): 5A 05 11 00 70
    r = enviar(trama(0x5A, 0x04, 0x11), 5)
    print("Guardar. Respuesta:", fmt(r), "(esperado: 5A 05 11 00 70, o nada)")
    time.sleep_ms(500)

    direcciones = i2c.scan()
    print("Direcciones I2C ahora:", [hex(d) for d in direcciones])
    if DIRECCION in direcciones:
        print("El 0x10 sigue en el bus: es normal hasta que apaguemos el sensor.")
    else:
        print("El 0x10 ya no esta en el bus: el sensor ha pasado a UART.")

    print()
    print("Ahora: desconectamos el sensor, lo dejamos 2 s sin alimentacion y")
    print("lo conectamos a la UART1 para el PASO 2 (config_tfmini_uart_demanda.py):")
    print("  blanco (RXD) -> GPIO8 (TX1), verde (TXD) -> GPIO9 (RX1), rojo 5V, negro GND")
    print("  (desconectamos antes el TFmini izquierdo de esos pines)")