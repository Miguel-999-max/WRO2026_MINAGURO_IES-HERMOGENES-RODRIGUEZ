"""
CONFIG_TFMINI_UART_DEMANDA.PY - Configuramos un TFmini-S en modo UART para
medir SOLO BAJO DEMANDA (como el lateral izquierdo):
  - frame rate = 0  -> el sensor deja de emitir en continuo
  - se guarda en flash (sobrevive a apagar/encender)
  - despues comprobamos que responde al disparo de medida 5A 04 04 62

PASO 2 de 2 para el TFmini derecho (el PASO 1 es config_tfmini_i2c_a_uart.py).
Sirve tambien para cualquier TFmini-S que ya este en UART.

Ejecutamos con UN sensor cada vez, cableado a la UART1 de la Pico (la del
TFmini izquierdo, que desconectamos mientras tanto):
  blanco (RXD) -> GPIO8 (TX1), verde (TXD) -> GPIO9 (RX1), rojo 5V, negro GND.

Por seguridad: si despues de ponerlo a demanda NO responde al disparo,
volvemos a dejarlo a 100 Hz y lo guardamos, para no perder el sensor.
"""
from machine import UART, Pin
import time

uart = UART(1, baudrate=115200, tx=Pin(8), rx=Pin(9))

CMD_DISPARO = b'\x5A\x04\x04\x62'  # pedimos una medida (frame rate 0)


def trama(*datos):
    """Anadimos el checksum (suma de 8 bits) al final de la trama."""
    b = bytes(datos)
    return b + bytes([sum(b) & 0xFF])


def fmt(b):
    return ' '.join('{:02X}'.format(x) for x in b) if b else None


def vaciar():
    while uart.any():
        uart.read(uart.any())


def buscar(buf, id_):
    """Buscamos una trama de comando/respuesta (5A LEN ID ... SU) con la ID
    y el checksum correctos."""
    for i in range(len(buf) - 3):
        if buf[i] == 0x5A:
            n = buf[i + 1]
            if 4 <= n <= 32 and i + n <= len(buf):
                f = buf[i:i + n]
                if f[2] == id_ and (sum(f[:-1]) & 0xFF) == f[-1]:
                    return f
    return None


def enviar(cmd, timeout_ms=1500):
    """Mandamos cmd y devolvemos la respuesta con la misma ID, o None.
    Ignoramos las tramas de datos (59 59) si el sensor esta en continuo."""
    vaciar()
    uart.write(cmd)
    buf = b''
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if uart.any():
            buf += uart.read(uart.any())
            r = buscar(buf, cmd[2])
            if r:
                return r
        time.sleep_ms(5)
    return None


def medir():
    """Disparamos una medida y devolvemos (dist_cm, fuerza), o None."""
    vaciar()
    uart.write(CMD_DISPARO)
    buf = b''
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 50:
        if uart.any():
            buf += uart.read(uart.any())
            for i in range(len(buf) - 8):
                if buf[i] == 0x59 and buf[i + 1] == 0x59 and (sum(buf[i:i + 8]) & 0xFF) == buf[i + 8]:
                    return buf[i + 2] | (buf[i + 3] << 8), buf[i + 4] | (buf[i + 5] << 8)
        time.sleep_ms(1)
    return None


def probar(titulo, n=5):
    """Hacemos n disparos y contamos las medidas validas."""
    print(titulo)
    validas = 0
    for _ in range(n):
        d = medir()
        if d and d[1] >= 100:
            validas += 1
            print("  {} cm  (fuerza {})".format(d[0], d[1]))
        else:
            print("  sin lectura valida:", d)
        time.sleep_ms(200)
    return validas


print("PASO 2: TFmini-S en UART1, lo ponemos a demanda ...")
time.sleep_ms(500)

v = enviar(trama(0x5A, 0x04, 0x01))
if v is None:
    print("Sin respuesta a 'version' por UART.")
    print("Revisamos cableado (blanco->GPIO8, verde->GPIO9), 5V y GND.")
    print("Si el cableado esta bien, el sensor sigue en I2C: le quitamos la")
    print("alimentacion 2 s, repetimos el PASO 1 y nos cuentas lo que imprime.")
else:
    print("Version (V1 V2 V3):", v[3], v[4], v[5], "-> el sensor ya esta en UART")

    # Frame rate = 0 (a demanda). Eco esperado: 5A 06 03 00 00 63
    r = enviar(trama(0x5A, 0x06, 0x03, 0x00, 0x00))
    print("Frame rate 0. Respuesta:", fmt(r), "(esperado: 5A 06 03 00 00 63)")

    # Guardar en flash. Respuesta esperada: 5A 05 11 00 70
    r = enviar(trama(0x5A, 0x04, 0x11))
    print("Guardar. Respuesta:", fmt(r), "(esperado: 5A 05 11 00 70)")
    time.sleep_ms(500)

    validas = probar("A demanda. Apuntamos a una pared a mas de 15 cm:")
    if validas >= 4:
        print("Correcto: responde al disparo estando a demanda.")
        print("Comprobacion final: le quitamos la alimentacion 2 s y relanzamos")
        print("este script; debe seguir contestando igual (confirma que quedo grabado).")
        print("Despues: devolvemos el TFmini izquierdo a GPIO8/9 y el derecho")
        print("lo cableamos a GPIO6/GPIO7 para la prueba por PIO.")
    else:
        print("Atencion: a demanda NO responde bien. Lo dejamos otra vez a 100 Hz.")
        r = enviar(trama(0x5A, 0x06, 0x03, 0x64, 0x00))
        print("Frame rate 100. Respuesta:", fmt(r), "(esperado: 5A 06 03 64 00 C7)")
        r = enviar(trama(0x5A, 0x04, 0x11))
        print("Guardar. Respuesta:", fmt(r))
        print("Nos cuentas el resultado antes de seguir.")