"""
TFMINI.PY - Driver de los TFmini-S del robot:
  TFminiUARTContinuo : el frontal, por UART0. Lo configuramos a 100 Hz con
                       config_tfmini_uart_continuo.py: el sensor emite solo y
                       nosotros leemos sin esperar la ultima trama recibida.
  TFminiI2C          : el lateral derecho, por I2C1 (direccion 0x10), a
                       demanda. Lo configuramos con config_tfmini_i2c.py y
                       config_tfmini_i2c_demanda.py.
  TFminiUART         : el lateral izquierdo, por UART1, a demanda. Lo
                       configuramos con config_tfmini_uart_demanda.py (frame
                       rate 0) y le pedimos cada medida con el comando de
                       disparo 5A 04 04 62.

Los tres devuelven la distancia en cm, o None si no tenemos una lectura fiable.
"""
import time

FUERZA_MIN = 100        # por debajo de esta senal no nos fiamos de la distancia
DISTANCIA_MAX_CM = 350  # el campo mide 300x300 cm: por encima de esto el dato es sospechoso

_CMD_DISPARO_UART = b'\x5A\x04\x04\x62'      # pedimos una medida (frame rate 0)
_CMD_DATOS_I2C = b'\x5A\x05\x00\x01\x60'     # pedimos una medida por I2C

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


class TFminiI2C:
    def __init__(self, i2c, direccion=0x10):
        self.i2c = i2c
        self.direccion = direccion
        self.ultimo_error = None  # guardamos el ultimo fallo del bus para poder diagnosticarlo

    def leer(self, max_cm=DISTANCIA_MAX_CM):
        """Pedimos una medida y la leemos. Si el bus falla, devolvemos None
        en lugar de parar el programa."""
        try:
            self.i2c.writeto(self.direccion, _CMD_DATOS_I2C)
            time.sleep_ms(1)
            buf = self.i2c.readfrom(self.direccion, 9)
        except OSError as e:
            self.ultimo_error = e
            return None
        return _filtrar(_decodificar(buf), max_cm)


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
