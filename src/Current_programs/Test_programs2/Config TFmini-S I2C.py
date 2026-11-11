"""
Configura un TFmini-S para modo I2C (direccion 0x10 por defecto, no se toca).
Ejecutamos con el sensor aun en modo UART de fabrica y cableado al UART0:
  blanco (RXD) -> GPIO0 (TX0), verde (TXD) -> GPIO1 (RX0), rojo 5V, negro GND.
Despues: desconectamos la alimentacion del sensor 2 s y pasamos a test_tfmini_i2c.py
"""
from machine import UART, Pin
import time

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))


def trama(*datos):
    b = bytes(datos)
    return b + bytes([sum(b) & 0xFF])


def fmt(b):
    return ' '.join('{:02X}'.format(x) for x in b) if b else None


def buscar(buf, id_):
    for i in range(len(buf) - 3):
        if buf[i] == 0x5A:
            n = buf[i + 1]
            if 4 <= n <= 32 and i + n <= len(buf):
                f = buf[i:i + n]
                if f[2] == id_ and (sum(f[:-1]) & 0xFF) == f[-1]:
                    return f
    return None


def enviar(cmd, timeout_ms=1500):
    """Manda cmd y devuelve la trama de respuesta con la misma ID, o None.
    Ignora las tramas de datos (59 59) que el sensor emite en continuo."""
    while uart.any():
        uart.read(uart.any())
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


time.sleep_ms(500)
v = enviar(trama(0x5A, 0x04, 0x01))
if v is None:
    print("Sin respuesta a 'version': revisar cableado (blanco->GPIO0, verde->GPIO1), 5V y GND.")
else:
    print("Version (V1 V2 V3):", v[3], v[4], v[5])
    r = enviar(trama(0x5A, 0x05, 0x0A, 0x01), 300)
    print("Modo I2C enviado. Respuesta:", fmt(r))
    r = enviar(trama(0x5A, 0x04, 0x11))
    print("Guardar. Respuesta:", fmt(r), "(esperado: 5A 05 11 00 70)")
    time.sleep(2)
    print("Hecho. Desconecta la alimentacion del sensor 2 s y recablea a I2C1.")