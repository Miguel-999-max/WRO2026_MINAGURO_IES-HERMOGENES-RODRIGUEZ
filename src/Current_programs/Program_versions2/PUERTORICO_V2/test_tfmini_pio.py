"""
TEST_TFMINI_PIO.PY - Prueba del TFmini-S derecho por un TERCER puerto UART
hecho con PIO (la Pico 2 solo tiene dos UART nativas, ya ocupadas por el
frontal y el izquierdo). Subimos tambien tfmini.py a la Pico: usamos sus
funciones de decodificar y filtrar, igual que en el robot.

Cableado del derecho (ya configurado en UART a demanda, frame rate 0):
  blanco (RXD del sensor) -> GPIO6  (TX de la Pico, por PIO)
  verde  (TXD del sensor) -> GPIO7  (RX de la Pico, por PIO)
  rojo -> 5V, negro -> GND
El izquierdo sigue en UART1 (GPIO8/GPIO9) para compararlos.

Como funciona: dos maquinas de estado PIO hacen de UART a 115200 baudios
(8N1). Los bits los genera y los lee el hardware PIO con la temporizacion
exacta; nosotros solo metemos y sacamos bytes de sus colas (FIFO).
Ojo: la cola de recepcion tiene 8 huecos (la unimos para tener 8 en vez de
4) y la trama del TFmini tiene 9 bytes. Por eso, tras el disparo, vaciamos
la cola en un bucle continuo sin sleep_ms: a 115200 llega un byte cada
87 us, y si la cola se llenara la maquina de estado se pararia y
perderiamos bits.

Medimos cada sensor 100 veces (tiempo por lectura y lecturas no validas) y
luego los dos alternados, como en navegar_calle_por_rumbo. Apuntamos cada
uno a una pared a distancia conocida (por ejemplo 30 cm y 100 cm).
"""
from machine import Pin, UART
import rp2
import time
from tfmini import TFminiUART, _decodificar, _filtrar

BAUDIOS = 115200


@rp2.asm_pio(sideset_init=rp2.PIO.OUT_HIGH, out_init=rp2.PIO.OUT_HIGH,
             out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def uart_tx():
    # 8 ciclos de PIO por bit. Linea en reposo a nivel alto.
    pull()
    set(x, 7).side(0)        [7]   # bit de start (bajo)
    label("bitloop")
    out(pins, 1)             [6]   # 8 bits de datos, el menos significativo primero
    jmp(x_dec, "bitloop")
    nop().side(1)            [6]   # bit de stop (alto)


@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_RIGHT, fifo_join=rp2.PIO.JOIN_RX)
def uart_rx():
    label("start")
    wait(0, pin, 0)                # esperamos el bit de start
    set(x, 7)                [10]  # nos situamos en mitad del primer bit de datos
    label("bitloop")
    in_(pins, 1)
    jmp(x_dec, "bitloop")    [6]
    jmp(pin, "good_stop")          # el bit de stop debe estar alto
    wait(1, pin, 0)                # trama mal formada: esperamos reposo y la descartamos
    jmp("start")
    label("good_stop")
    push(block)


class TFminiPIO:
    """TFmini-S a demanda por una UART hecha con PIO. Misma forma de uso que
    TFminiUART: leer(max_cm) devuelve cm o None."""
    _CMD_DISPARO = b'\x5A\x04\x04\x62'

    def __init__(self, pin_tx, pin_rx, sm_tx=0, sm_rx=1, timeout_ms=25):
        self.tx = rp2.StateMachine(sm_tx, uart_tx, freq=8 * BAUDIOS,
                                   sideset_base=Pin(pin_tx), out_base=Pin(pin_tx))
        rx_pin = Pin(pin_rx, Pin.IN, Pin.PULL_UP)
        self.rx = rp2.StateMachine(sm_rx, uart_rx, freq=8 * BAUDIOS,
                                   in_base=rx_pin, jmp_pin=rx_pin)
        self.tx.active(1)
        self.rx.active(1)
        self.timeout_ms = timeout_ms

    def leer(self, max_cm=350):
        rx = self.rx
        while rx.rx_fifo():          # vaciamos lo que hubiera de antes
            rx.get()
        for b in self._CMD_DISPARO:
            self.tx.put(b)

        buf = bytearray()
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < self.timeout_ms:
            while rx.rx_fifo():
                buf.append(rx.get() >> 24)   # el byte entra por arriba del registro de 32 bits
            if len(buf) >= 9:
                medida = _decodificar(buf)
                if medida is not None:
                    return _filtrar(medida, max_cm)
        return None


def medir_100(nombre, sensor):
    tiempos, malas, ejemplos = [], 0, []
    for _ in range(100):
        t0 = time.ticks_us()
        d = sensor.leer()
        tiempos.append(time.ticks_diff(time.ticks_us(), t0))
        if d is None:
            malas += 1
        elif len(ejemplos) < 5:
            ejemplos.append(d)
        time.sleep_ms(25)
    print("{}: media {:.2f} ms, max {:.2f} ms, no validas {}/100, ejemplos {}".format(
        nombre, sum(tiempos) / len(tiempos) / 1000, max(tiempos) / 1000, malas, ejemplos))


derecho = TFminiPIO(pin_tx=6, pin_rx=7)
izquierdo = TFminiUART(UART(1, baudrate=115200, tx=Pin(8), rx=Pin(9)))

print("Prueba TFmini derecho por PIO (GPIO6/7) e izquierdo por UART1 (GPIO8/9)")
time.sleep_ms(300)

medir_100("derecho (PIO)", derecho)
medir_100("izquierdo (UART1)", izquierdo)

print("Los dos alternados, 20 veces (como en la navegacion por rumbo):")
for _ in range(20):
    d = derecho.leer()
    i = izquierdo.leer()
    print("  derecho {} cm   izquierdo {} cm".format(d, i))
    time.sleep_ms(100)
print("Fin de la prueba.")