"""
Configura un TFmini-S (modo UART) para medir en CONTINUO a 100 Hz. Es el
frontal: lo leemos sin esperar, quedandonos con la ultima trama recibida.
  - frame rate = 100 Hz (0x64)
  - se guarda en flash (sobrevive a apagar/encender)
  - despues comprobamos que llegan tramas validas a unos 100 por segundo

Ejecutamos con UN sensor cada vez, cableado a la UART0 de la Pico:
  blanco (RXD) -> GPIO0 (TX0), verde (TXD) -> GPIO1 (RX0), rojo 5V, negro GND.
El sensor debe estar en modo UART (como vienen de fabrica y como lo
dejamos al configurarlos a demanda).
"""
from machine import UART, Pin
import time

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))


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


def enviar(cmd, timeout_ms=1500):
    """Mandamos cmd y devolvemos la trama de respuesta con la misma ID, o None.
    Ignoramos las tramas de datos (59 59) que el sensor emite en continuo."""
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


def contar_tramas(ventana_ms=1000):
    """Contamos las tramas de datos validas (59 59 ... SU) que llegan en la
    ventana. Devolvemos (numero_de_tramas, ultima_distancia_cm, ultima_fuerza)."""
    vaciar()
    buf = b''
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ventana_ms:
        if uart.any():
            buf += uart.read(uart.any())
        time.sleep_ms(2)
    n = 0
    ultima = None
    i = 0
    while i + 9 <= len(buf):
        if buf[i] == 0x59 and buf[i + 1] == 0x59 and (sum(buf[i:i + 8]) & 0xFF) == buf[i + 8]:
            n += 1
            ultima = (buf[i + 2] | (buf[i + 3] << 8), buf[i + 4] | (buf[i + 5] << 8))
            i += 9
        else:
            i += 1
    return n, ultima


print("Configurando TFmini-S en UART0 (continuo, 100 Hz) ...")
time.sleep_ms(500)

v = enviar(trama(0x5A, 0x04, 0x01))
if v is None:
    print("Sin respuesta a 'version': revisamos cableado (blanco->GPIO0, verde->GPIO1), 5V y GND.")
else:
    print("Version (V1 V2 V3):", v[3], v[4], v[5])

    # Frame rate = 100 Hz. Eco esperado: 5A 06 03 64 00 C7
    r = enviar(trama(0x5A, 0x06, 0x03, 0x64, 0x00))
    print("Frame rate 100. Respuesta:", fmt(r), "(esperado: 5A 06 03 64 00 C7)")

    # Guardar en flash. Respuesta esperada: 5A 05 11 00 70
    r = enviar(trama(0x5A, 0x04, 0x11))
    print("Guardar. Respuesta:", fmt(r), "(esperado: 5A 05 11 00 70)")
    time.sleep_ms(500)

    # Comprobacion: tramas por segundo (esperamos unas 100)
    n, ultima = contar_tramas(1000)
    print("Tramas validas en 1 s:", n, "(esperado: cerca de 100)")
    if ultima:
        print("Ultima medida: {} cm (fuerza {})".format(ultima[0], ultima[1]))

    print("Hecho. Apagamos el sensor 2 s, lo volvemos a encender y relanzamos este script:")
    print("las tramas por segundo deben seguir cerca de 100 (confirma que quedo grabado).")
