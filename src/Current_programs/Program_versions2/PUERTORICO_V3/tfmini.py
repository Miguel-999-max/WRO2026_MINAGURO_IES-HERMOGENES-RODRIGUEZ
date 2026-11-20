"""
TFMINI.PY - Driver de los TFmini-S del robot (los tres en modo UART):
  TFminiUARTContinuo : el frontal, por UART0. Lo configuramos a 100 Hz con
                       config_tfmini_uart_continuo.py: el sensor emite solo y
                       nosotros leemos sin esperar la ultima trama recibida.
  TFminiUART         : el lateral izquierdo, por UART1, a demanda. Lo
                       configuramos con config_tfmini_uart_demanda.py (frame
                       rate 0) y le pedimos cada medida con el comando de
                       disparo 5A 04 04 62.
  TFminiPIO          : el lateral derecho, a demanda, por una tercera UART
                       hecha con PIO (GPIO6 = TX de la Pico, GPIO7 = RX de la
                       Pico): la Pico 2 solo tiene dos UART nativas. Lo
                       configuramos igual que el izquierdo
                       (config_tfmini_i2c_a_uart.py si venia en I2C, y despues
                       config_tfmini_uart_demanda.py).

Los tres devuelven la distancia en cm, o None si no tenemos una lectura fiable.
"""
import time
from machine import Pin
import rp2

FUERZA_MIN = 100        # por debajo de esta senal no nos fiamos de la distancia
DISTANCIA_MAX_CM = 350  # el campo mide 300x300 cm: por encima de esto el dato es sospechoso

_CMD_DISPARO_UART = b'\x5A\x04\x04\x62'      # pedimos una medida (frame rate 0)


def _decodificar(buf):
    """Buscamos en buf una trama de datos valida (59 59 DL DH SL SH TL TH SU,
    con el checksum correcto) y devolvemos (distancia_cm, fuerza), o None."""
    for i in range(len(buf) - 8):
        if buf[i] == 0x59 and buf[i + 1] == 0x59:
            if (sum(buf[i:i + 8]) & 0xFF) == buf[i + 8]:
                dist = buf[i + 2] | (buf[i + 3] << 8)
                fuerza = buf[i + 4] | (buf[i + 5] << 8)
                return dist, fuerza
    return None


def _decodificar_ultima(buf):
    """Buscamos en buf la trama de datos valida MAS RECIENTE (la ultima) y
    devolvemos (distancia_cm, fuerza), o None."""
    for i in range(len(buf) - 9, -1, -1):
        if buf[i] == 0x59 and buf[i + 1] == 0x59:
            if (sum(buf[i:i + 8]) & 0xFF) == buf[i + 8]:
                return buf[i + 2] | (buf[i + 3] << 8), buf[i + 4] | (buf[i + 5] << 8)
    return None


def _filtrar(medida, max_cm=DISTANCIA_MAX_CM):
    """Descartamos las lecturas con poca senal o por encima de max_cm."""
    if medida is None:
        return None
    dist, fuerza = medida
    if fuerza < FUERZA_MIN or dist > max_cm:
        return None
    return dist


class TFminiUART:
    def __init__(self, uart, timeout_ms=25):
        self.uart = uart
        self.timeout_ms = timeout_ms

    def leer(self, max_cm=DISTANCIA_MAX_CM):
        """Vaciamos el bufer, disparamos una medida y esperamos su trama.
        Si no llega a tiempo, devolvemos None."""
        u = self.uart
        while u.any():
            u.read(u.any())
        u.write(_CMD_DISPARO_UART)

        buf = b''
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < self.timeout_ms:
            n = u.any()
            if n:
                datos = u.read(n)
                if datos:
                    buf += datos
                medida = _decodificar(buf)
                if medida is not None:
                    return _filtrar(medida, max_cm)
            time.sleep_ms(1)
        return None


class TFminiUARTContinuo:
    """TFmini-S que emite solo a 100 Hz. leer() no espera: vaciamos lo que haya
    en el bufer y nos quedamos con la ultima trama valida. Si no ha llegado
    ninguna trama nueva completa, devolvemos None."""
    UMBRAL_BUFER_LLENO = 200  # bytes: el bufer de la UART es de 256 y se llena en ~280 ms

    def __init__(self, uart, timeout_ms=15):
        self.uart = uart
        self.timeout_ms = timeout_ms
        self.ultima_medida = None  # (distancia, fuerza) sin filtrar, para diagnostico
        self._resto = b''          # ultimos bytes leidos: pueden ser el comienzo de una trama

    def leer(self, max_cm=DISTANCIA_MAX_CM):
        u = self.uart
        if u.any() >= self.UMBRAL_BUFER_LLENO:
            # Llevamos un rato sin leer: el bufer esta lleno de tramas antiguas y,
            # al llenarse, descarta las nuevas. Lo vaciamos y esperamos una fresca.
            while u.any():
                u.read(u.any())
            buf = b''
            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < self.timeout_ms:
                if u.any():
                    buf += u.read(u.any())
                    medida = _decodificar_ultima(buf)
                    if medida is not None:
                        self._resto = buf[-8:]
                        self.ultima_medida = medida
                        return _filtrar(medida, max_cm)
                time.sleep_ms(1)
            self._resto = buf[-8:]
            return None

        n = u.any()
        datos = u.read(n) if n else b''
        buf = self._resto + (datos or b'')
        self._resto = buf[-8:]
        medida = _decodificar_ultima(buf)
        if medida is not None:
            self.ultima_medida = medida
        return _filtrar(medida, max_cm)


# ==========================================
# UART hecha con PIO (para el TFmini derecho)
# ==========================================
# Dos maquinas de estado PIO hacen de UART 8N1, a 8 ciclos de PIO por bit.
# Los bits los genera y los lee el hardware PIO con la temporizacion exacta;
# nosotros solo metemos y sacamos bytes de sus colas (FIFO).

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_HIGH, out_init=rp2.PIO.OUT_HIGH,
             out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def _uart_tx_pio():
    # Linea en reposo a nivel alto.
    pull()
    set(x, 7).side(0)        [7]   # bit de start (bajo)
    label("bitloop")
    out(pins, 1)             [6]   # 8 bits de datos, el menos significativo primero
    jmp(x_dec, "bitloop")
    nop().side(1)            [6]   # bit de stop (alto)


@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_RIGHT, fifo_join=rp2.PIO.JOIN_RX)
def _uart_rx_pio():
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
    """TFmini-S a demanda por una UART hecha con PIO. Se usa igual que
    TFminiUART: leer(max_cm) devuelve cm o None.

    Ojo: la cola de recepcion tiene 8 huecos (la unimos para tener 8 en vez
    de 4) y la trama del TFmini tiene 9 bytes. Por eso, tras el disparo,
    vaciamos la cola en un bucle continuo, sin sleep_ms: a 115200 llega un
    byte cada 87 us y, si la cola se llenara, la maquina de estado se pararia
    y perderiamos bits."""

    def __init__(self, pin_tx, pin_rx, sm_tx=0, sm_rx=1, baudios=115200, timeout_ms=25):
        self.tx = rp2.StateMachine(sm_tx, _uart_tx_pio, freq=8 * baudios,
                                   sideset_base=Pin(pin_tx), out_base=Pin(pin_tx))
        rx_pin = Pin(pin_rx, Pin.IN, Pin.PULL_UP)
        self.rx = rp2.StateMachine(sm_rx, _uart_rx_pio, freq=8 * baudios,
                                   in_base=rx_pin, jmp_pin=rx_pin)
        self.tx.active(1)
        self.rx.active(1)
        self.timeout_ms = timeout_ms

    def leer(self, max_cm=DISTANCIA_MAX_CM):
        """Vaciamos la cola, disparamos una medida y esperamos su trama.
        Si no llega a tiempo, devolvemos None."""
        rx = self.rx
        while rx.rx_fifo():          # vaciamos lo que hubiera de antes
            rx.get()
        for b in _CMD_DISPARO_UART:
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