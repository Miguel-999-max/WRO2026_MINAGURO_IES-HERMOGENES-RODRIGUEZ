"""
Configura un TFmini-S (modo UART de fabrica) para medir SOLO BAJO DEMANDA:
  - frame rate = 0  -> el sensor deja de emitir en continuo
  - se guarda en flash (sobrevive a apagar/encender)
  - despues se comprueba: silencio en el bus + medida disparada con 5A 04 04 62

Ejecutamos con UN sensor cada vez, cableado a la Pico asi:
  blanco (RXD) -> TX de la Pico, verde (TXD) -> RX de la Pico, rojo 5V, negro GND.
  UART0: TX=GPIO0, RX=GPIO1      UART1: TX=GPIO8, RX=GPIO9
Tenemos que cambiar UART_ID abajo segun donde lo conectes. Repetir para cada sensor.

Uso posterior (en el robot), para medir:
  uart.write(b'\\x5A\\x04\\x04\\x62')  -> responde 1 trama de 9 bytes (59 59 ...)
"""
from machine import UART, Pin
import time

UART_ID = 0   # 0 -> GPIO0/GPIO1 ; 1 -> GPIO8/GPIO9

if UART_ID == 0:
    uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
else:
    uart = UART(1, baudrate=115200, tx=Pin(8), rx=Pin(9))


def trama(*datos):
    b = bytes(datos)
    return b + bytes([sum(b) & 0xFF])


def fmt(b):
    return ' '.join('{:02X}'.format(x) for x in b) if b else None


def vaciar():
    while uart.any():
        uart.read(uart.any())


def buscar(buf, id_):
    """Trama de comando/respuesta (5A LEN ID ... SU) con ID y checksum validos."""
    for i in range(len(buf) - 3):
        if buf[i] == 0x5A:
            n = buf[i + 1]
            if 4 <= n <= 32 and i + n <= len(buf):
                f = buf[i:i + n]
                if f[2] == id_ and (sum(f[:-1]) & 0xFF) == f[-1]:
                    return f
    return None


def buscar_dato(buf):
    """Trama de datos (59 59 DL DH SL SH TL TH SU) valida -> (dist_cm, fuerza)."""
    for i in range(len(buf) - 8):
        if buf[i] == 0x59 and buf[i + 1] == 0x59:
            f = buf[i:i + 9]
            if (sum(f[:8]) & 0xFF) == f[8]:
                return f[2] | (f[3] << 8), f[4] | (f[5] << 8)
    return None


def enviar(cmd, timeout_ms=1500):
    """Manda cmd y devuelve la trama de respuesta con la misma ID, o None.
    Ignora las tramas de datos que el sensor emite en continuo."""
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


def medir_disparo(timeout_ms=300):
    """Dispara una medida y devuelve (dist_cm, fuerza) o None."""
    vaciar()
    uart.write(trama(0x5A, 0x04, 0x04))
    buf = b''
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if uart.any():
            buf += uart.read(uart.any())
            d = buscar_dato(buf)
            if d:
                return d
        time.sleep_ms(2)
    return None


print("Configurando TFmini-S en UART{} ...".format(UART_ID))
time.sleep_ms(500)

v = enviar(trama(0x5A, 0x04, 0x01))
if v is None:
    print("Sin respuesta a 'version': revisar cableado (blanco->TX, verde->RX), 5V y GND.")
else:
    print("Version (V1 V2 V3):", v[3], v[4], v[5])

    # Frame rate = 0 (modo disparo). Eco esperado: 5A 06 03 00 00 63
    r = enviar(trama(0x5A, 0x06, 0x03, 0x00, 0x00))
    print("Frame rate 0. Respuesta:", fmt(r), "(esperado: 5A 06 03 00 00 63)")

    # Guardar en flash. Respuesta esperada: 5A 05 11 00 70
    r = enviar(trama(0x5A, 0x04, 0x11))
    print("Guardar. Respuesta:", fmt(r), "(esperado: 5A 05 11 00 70)")
    time.sleep_ms(500)

    # Comprobacion 1: el bus debe quedar en silencio
    vaciar()
    time.sleep_ms(500)
    n = uart.any()
    print("Bytes recibidos en 500 ms sin pedir nada:", n, "(esperado: 0)")

    # Comprobacion 2: medida bajo demanda
    print("Medidas disparadas (apunta a una pared a >15 cm):")
    for _ in range(5):
        d = medir_disparo()
        if d:
            print("  {} cm  (fuerza {})".format(d[0], d[1]))
        else:
            print("  sin respuesta al disparo")
        time.sleep_ms(200)

    print("Hecho. Apaga el sensor 2 s, vuelve a encenderlo y relanza este script:")
    print("el punto 'Bytes recibidos' debe seguir en 0 (confirma que quedo grabado).")