"""
TEST_TFMINI_TODOS.PY - Prueba de los tres TFmini-S con las conexiones
actuales, pensada tambien para VER el punto del laser con el movil:
  - frontal:   UART0 (GPIO0/GPIO1), lectura continua, en el servo de la camara
  - izquierdo: UART1 (GPIO8/GPIO9), a demanda
  - derecho:   UART hecha con PIO (GPIO6/GPIO7), a demanda
Importamos hardware para que todo se inicialice igual que en las misiones.

Los laterales estan a demanda: solo emiten un instante cuando les pedimos
una medida. Leyendolos cada 200 ms el laser apenas se enciende y el movil no
llega a verlo. Por eso vamos sensor por sensor, 1 segundo cada uno, y
durante ese segundo le pedimos medidas sin parar (unas 80-90 por segundo):
asi su laser queda practicamente encendido y se ve en el papel.
El frontal esta en lectura continua y emite SIEMPRE (no lo podemos apagar);
en su turno solo leemos lo que va mandando.

El orden es: izquierdo 1 s -> derecho 1 s -> frontal 1 s -> otra vez. Al
final de cada turno imprimimos el resumen de ese segundo: medidas pedidas,
validas (ya filtradas como en carrera), minimo, maximo, media y la ultima
medida sin filtrar (distancia, fuerza). Asi distinguimos:
  - sin filtrar None  -> el sensor no contesta (cable, alimentacion, config)
  - fuerza < 100      -> contesta pero no ve bien la superficie (apunta mal o
                         esta a menos de unos 10 cm)
  - distancia correcta -> el sensor esta bien

Consejo para verlo: muchos moviles llevan un filtro de infrarrojos en la
camara principal; la camara delantera (la de los selfis) suele verlo mejor.
Con poca luz en la sala se ve mucho mejor.

Funciona en bucle, sin fin. Paramos con Ctrl+C.
"""
import time
import hardware
from tfmini import _decodificar


def crudo_uart(sensor):
    """Medida sin filtrar del lateral izquierdo (UART1 a demanda): mandamos
    el disparo y devolvemos (distancia, fuerza) o None."""
    u = sensor.uart
    while u.any():
        u.read(u.any())
    u.write(b'\x5A\x04\x04\x62')
    buf = b''
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 25:
        if u.any():
            buf += u.read(u.any())
            m = _decodificar(buf)
            if m is not None:
                return m
        time.sleep_ms(1)
    return None


def crudo_pio(sensor):
    """Medida sin filtrar del lateral derecho (UART por PIO a demanda)."""
    rx = sensor.rx
    while rx.rx_fifo():
        rx.get()
    for b in b'\x5A\x04\x04\x62':
        sensor.tx.put(b)
    buf = bytearray()
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 25:
        while rx.rx_fifo():
            buf.append(rx.get() >> 24)
        if len(buf) >= 9:
            m = _decodificar(buf)
            if m is not None:
                return m
    return None


def crudo_frontal(sensor):
    """Medida sin filtrar del frontal (continuo): leemos lo que haya llegado."""
    sensor.leer()
    return sensor.ultima_medida


def turno(nombre, leer_crudo):
    """Durante 1 segundo pedimos medidas sin parar a un sensor y despues
    imprimimos el resumen de ese segundo."""
    pedidas = 0
    validas = []
    ultimo = None
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 1000:
        m = leer_crudo()
        pedidas += 1
        if m is not None:
            ultimo = m
            dist, fuerza = m
            if fuerza >= 100 and 0 < dist <= 350:  # mismo filtro que en carrera
                validas.append(dist)
        if nombre == 'FRONTAL':
            time.sleep_ms(10)  # el frontal manda a 100 Hz: no hace falta mas
    if validas:
        print("{:9s}: {:3d} medidas, validas {:3d} | min {} | max {} | media {:.1f} cm | sin filtrar {}".format(
            nombre, pedidas, len(validas), min(validas), max(validas), sum(validas) / len(validas), ultimo))
    else:
        print("{:9s}: {:3d} medidas, ninguna valida | sin filtrar {}".format(nombre, pedidas, ultimo))


print("Escaneo I2C1:", [hex(a) for a in hardware.i2c1.scan()], "(esperamos solo 0x50, la Huskylens 2)")
hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
time.sleep_ms(800)  # camara al centro
print("Turnos de 1 s: IZQUIERDO -> DERECHO -> FRONTAL. Ctrl+C para terminar.")

try:
    while True:
        turno('IZQUIERDO', lambda: crudo_uart(hardware.tfmini_izquierdo))
        turno('DERECHO', lambda: crudo_pio(hardware.tfmini_derecho))
        turno('FRONTAL', lambda: crudo_frontal(hardware.tfmini_frontal))
        print()
except KeyboardInterrupt:
    print("Fin.")