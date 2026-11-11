"""
Configura un TFmini-S que ya esta en modo I2C (direccion 0x10) para medir
SOLO BAJO DEMANDA:
  - frame rate = 0  -> el sensor deja de emitir en continuo
  - se guarda en flash
  - despues comprobamos que responde a la peticion de medida 5A 05 00 01 60

Lo ejecutamos con el sensor cableado a I2C1 de la Pico, como en el robot:
  SDA = GPIO14, SCL = GPIO15, rojo 5V, negro GND.
Los comandos se mandan por I2C (en modo I2C el sensor ya no escucha por UART).

Por seguridad: si despues de ponerlo a demanda NO responde a la peticion de
medida, volvemos a dejarlo a 100 Hz y lo guardamos, para no perder el sensor.
"""
from machine import Pin, I2C
import time

DIRECCION = 0x10
CMD_DATOS = b'\x5A\x05\x00\x01\x60'    # peticion de medida por I2C

i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000, timeout=100000)


def trama(*datos):
    b = bytes(datos)
    return b + bytes([sum(b) & 0xFF])


def fmt(b):
    return ' '.join('{:02X}'.format(x) for x in b) if b else None


def enviar(cmd, n_resp, espera_ms=20):
    """Mandamos cmd por I2C y leemos n_resp bytes de respuesta (o None si falla)."""
    try:
        i2c.writeto(DIRECCION, cmd)
        time.sleep_ms(espera_ms)
        return i2c.readfrom(DIRECCION, n_resp)
    except OSError as e:
        print("  error I2C:", e)
        return None


def medir():
    """Pedimos una medida y devolvemos (dist_cm, fuerza) o None."""
    try:
        i2c.writeto(DIRECCION, CMD_DATOS)
        time.sleep_ms(2)
        buf = i2c.readfrom(DIRECCION, 9)
    except OSError:
        return None
    for i in range(len(buf) - 8):
        if buf[i] == 0x59 and buf[i + 1] == 0x59 and (sum(buf[i:i + 8]) & 0xFF) == buf[i + 8]:
            return buf[i + 2] | (buf[i + 3] << 8), buf[i + 4] | (buf[i + 5] << 8)
    return None


def probar(titulo, n=5):
    """Hacemos n peticiones de medida y contamos las que salen validas."""
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


print("Configurando TFmini-S en I2C1 (a demanda) ...")
direcciones = i2c.scan()
print("Direcciones I2C:", [hex(d) for d in direcciones])
if DIRECCION not in direcciones:
    print("No vemos el 0x10: revisamos cableado (SDA=GPIO14, SCL=GPIO15), 5V y GND.")
else:
    probar("Antes (continuo). Apuntamos a una pared a mas de 15 cm:")

    # Frame rate = 0 (a demanda). Eco esperado: 5A 06 03 00 00 63
    r = enviar(trama(0x5A, 0x06, 0x03, 0x00, 0x00), 6)
    print("Frame rate 0. Respuesta:", fmt(r), "(esperado: 5A 06 03 00 00 63)")

    # Guardar en flash. Respuesta esperada: 5A 05 11 00 70
    r = enviar(trama(0x5A, 0x04, 0x11), 5, 100)
    print("Guardar. Respuesta:", fmt(r), "(esperado: 5A 05 11 00 70)")
    time.sleep_ms(500)

    validas = probar("Despues (a demanda):")
    if validas >= 4:
        print("Correcto: responde a la peticion de medida estando a demanda.")
        print("Apagamos el sensor 2 s, lo volvemos a encender y relanzamos el script:")
        print("la parte 'Antes' debe seguir dando medidas validas.")
    else:
        print("Atencion: a demanda NO responde bien. Lo dejamos otra vez a 100 Hz.")
        r = enviar(trama(0x5A, 0x06, 0x03, 0x64, 0x00), 6)
        print("Frame rate 100. Respuesta:", fmt(r), "(esperado: 5A 06 03 64 00 C7)")
        r = enviar(trama(0x5A, 0x04, 0x11), 5, 100)
        print("Guardar. Respuesta:", fmt(r))
        probar("Tras restaurar:")
        print("Nos cuentas el resultado antes de seguir.")
