"""
HUSKYLENS2.PY - Driver MicroPython para la Huskylens 2 (protocolo propio de
DFRobot, distinto al de la V1), sobre I2C.

Basado en el protocolo oficial documentado por DFRobot:
  https://github.com/DFRobot/DFRobot_HuskylensV2/blob/master/HuskyLens2_Protocol_CN.md

VERIFICADO contra la Huskylens 2 real (test_huskylens2.py, 15/10/2026):
  - Direccion I2C 0x50 (aparece en el escaneo junto al TFmini en 0x10).
  - Checksum: suma de 8 bits de todos los bytes de la trama salvo el propio
    checksum. Lo comprobamos en las tramas KNOCK, INFO y BLOCKS.
  - Los campos de 2 bytes van en little-endian.
  - Peticion con writeto y respuesta con readfrom normales. Cuando no hay
    respuesta lista, la Huskylens 2 devuelve bytes 0xFF.
  - Resolucion de la imagen: 640 px de ancho (x_center llega a ~636).
  - Una respuesta de GET_RESULT trae una trama RETURN_INFO y despues una
    trama RETURN_BLOCKS por bloque. Datos de cada bloque: id, algoritmo,
    x_center, y_center, width, height (2 bytes cada uno) y el nombre.
  - En reconocimiento de color la camara tambien devuelve un bloque con id 0
    que ocupa casi toda la imagen (el color no aprendido). get_blocks() lo
    descarta por defecto, para que solo lleguen al programa los pilares
    aprendidos (id 1 y 2).
"""
import time
from machine import I2C

# === Cabecera de trama (protocolo V2, fija) ===
_HEAD0 = 0x55
_HEAD1 = 0xAA

# === Comandos (peticion) ===
CMD_KNOCK = 0x00
CMD_GET_RESULT = 0x01
CMD_SET_ALGORITHM = 0x0A
CMD_ACTION_LEARN = 0x22
CMD_ACTION_FORGET = 0x23

# === Comandos (respuesta) ===
CMD_RETURN_ARGS = 0x1A
CMD_RETURN_INFO = 0x1B
CMD_RETURN_BLOCKS = 0x1C
CMD_RETURN_ARROWS = 0x1D

# === IDs de algoritmo (los mas relevantes para deteccion de pilares) ===
ALGORITHM_NONE = 0                 # generico, para KNOCK/SET_ALGORITHM
ALGORITHM_OBJECT_RECOGNITION = 2
ALGORITHM_OBJECT_TRACKING = 3
ALGORITHM_COLOR_RECOGNITION = 4

# Lectura de un GET_RESULT (medida en test_huskylens2_velocidad.py, I2C a 100 kHz):
# esperamos 5 ms y leemos 100 bytes (trama INFO de 16 + 3 bloques de 23), lo que
# cuesta unos 16 ms por consulta y dio el 100 % de respuestas completas. Si la
# trama INFO anuncia mas bloques de los que caben, leemos aparte los que faltan.
_ESPERA_RESULTADO_MS = 5
_LECTURA_I2C_BYTES = 100
_BYTES_BLOQUE = 23          # trama RETURN_BLOCKS con el nombre "Color"
_MAX_BYTES_RESPUESTA = 300  # tope de seguridad de la respuesta completa


def _checksum(datos):
    """Suma de 8 bits de todos los bytes dados."""
    return sum(datos) & 0xFF


def _construir_trama(cmd, algo_id, data=b''):
    """Construye una trama de peticion completa, con cabecera y checksum."""
    cuerpo = bytes([_HEAD0, _HEAD1, cmd, algo_id, len(data)]) + data
    return cuerpo + bytes([_checksum(cuerpo)])


class Bloque:
    """Un resultado de RETURN_BLOCKS, con los campos que usa el resto del
    programa (mismos nombres que el driver de la V1: id, x_center, y_center,
    width, height)."""
    def __init__(self, id_, algo_id, x_center, y_center, width, height):
        self.id = id_
        self.algo_id = algo_id
        self.x_center = x_center
        self.y_center = y_center
        self.width = width
        self.height = height

    def __repr__(self):
        return f"Bloque(id={self.id} x={self.x_center} y={self.y_center} w={self.width} h={self.height})"


class HuskyLensV2:
    def __init__(self, i2c, address=0x50, board_type=0):
        """i2c: objeto machine.I2C ya inicializado.
        address: direccion I2C de la Huskylens 2 (0x50).
        board_type: 0=MCU de RAM pequena (Pico 2 por defecto), 1=RAM grande."""
        self.i2c = i2c
        self.address = address
        self.board_type = board_type
        self.errores_i2c = 0           # fallos de bus acumulados en get_blocks, para el registro
        self._fallos_seguidos = 0      # consultas seguidas que han fallado tras el reintento

    # === Bajo nivel ===

    def _enviar(self, cmd, algo_id, data=b''):
        trama = _construir_trama(cmd, algo_id, data)
        self.i2c.writeto(self.address, trama)

    def _leer_bruto(self, n=_LECTURA_I2C_BYTES):
        """Lee hasta n bytes crudos de respuesta. Puede contener una o
        varias tramas concatenadas (RETURN_INFO + RETURN_BLOCKS...)."""
        try:
            return self.i2c.readfrom(self.address, n)
        except OSError:
            return b''

    def vaciar(self):
        """Leemos hasta que ya no queden tramas pendientes en la Huskylens 2
        (el bus I2C se comporta como una cola FIFO: lo que no leemos se
        entrega en la siguiente lectura y desplaza las respuestas)."""
        for _ in range(6):
            if b'\x55\xaa' not in self._leer_bruto(250):
                break

    def _bytes_esperados(self, buf):
        """Si buf contiene la trama INFO de un GET_RESULT, devolvemos cuantos
        bytes tiene que tener la respuesta completa desde esa trama (INFO mas
        un bloque por cada uno anunciado) y la posicion donde empieza. Si no
        encontramos INFO devolvemos (None, 0)."""
        n = len(buf)
        i = 0
        while i + 5 <= n:
            if buf[i] == _HEAD0 and buf[i + 1] == _HEAD1 and buf[i + 2] == CMD_RETURN_INFO:
                data_len = buf[i + 4]
                fin = i + 5 + data_len
                if data_len >= 4 and fin + 1 <= n and _checksum(buf[i:fin]) == buf[fin]:
                    bloques = buf[i + 7] | (buf[i + 8] << 8)  # total de bloques (data[2:4])
                    return fin + 1 - i + bloques * _BYTES_BLOQUE, i
            i += 1
        return None, 0

    def _parsear_tramas(self, buf):
        """Separa un buffer crudo en una lista de (cmd, algo_id, data),
        localizando cada cabecera 0x55 0xAA dentro del buffer y comprobando
        el checksum. Descarta los bytes de relleno (0xFF) y las tramas
        corruptas."""
        tramas = []
        i = 0
        n = len(buf)
        while i + 5 <= n:
            if buf[i] != _HEAD0 or buf[i + 1] != _HEAD1:
                i += 1
                continue
            cmd = buf[i + 2]
            algo_id = buf[i + 3]
            data_len = buf[i + 4]
            fin_datos = i + 5 + data_len
            if fin_datos + 1 > n:
                break  # trama incompleta, no ha llegado entera en esta lectura
            if _checksum(buf[i:fin_datos]) != buf[fin_datos]:
                i += 1  # falsa cabecera o trama corrupta: seguimos buscando
                continue
            tramas.append((cmd, algo_id, buf[i + 5:fin_datos]))
            i = fin_datos + 1
        return tramas

    def _esperar_respuesta(self, cmd_esperado, timeout_ms):
        """Leemos cada 10 ms hasta que llegue una trama con cmd_esperado, o
        hasta el timeout. Devuelve (cmd, algo_id, data) o None."""
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            time.sleep_ms(10)
            for trama in self._parsear_tramas(self._leer_bruto(20)):
                if trama[0] == cmd_esperado:
                    return trama
        return None

    @staticmethod
    def _u16(data, offset):
        """Lee un entero de 2 bytes en little-endian."""
        return data[offset] | (data[offset + 1] << 8)

    # === API de alto nivel ===

    def knock(self):
        """Comprueba que la Huskylens 2 responde. Devuelve True/False."""
        self._enviar(CMD_KNOCK, ALGORITHM_NONE, bytes([self.board_type]) + bytes(9))
        r = self._esperar_respuesta(CMD_RETURN_ARGS, 300)
        return r is not None and len(r[2]) >= 2 and r[2][1] == 0  # retValue de exito

    def switch_algorithm(self, algo_id, timeout_ms=1000):
        """Cambia el algoritmo activo. Esperamos la confirmacion hasta
        timeout_ms: cambiar de algoritmo tarda mas que un knock. Devuelve
        True/False."""
        data = bytes([algo_id]) + bytes(9)
        self._enviar(CMD_SET_ALGORITHM, ALGORITHM_NONE, data)
        r = self._esperar_respuesta(CMD_RETURN_ARGS, timeout_ms)
        return r is not None and len(r[2]) >= 2 and r[2][1] == 0

    def get_blocks(self, algo_id=ALGORITHM_COLOR_RECOGNITION, solo_aprendidos=True):
        """Pide el resultado al algoritmo indicado y devuelve una lista de
        Bloque (vacia si no hay nada detectado). Con solo_aprendidos=True
        (por defecto) descartamos los bloques con id 0, que son colores no
        aprendidos.

        Un fallo del bus I2C (ETIMEDOUT, EIO...) no tumba el programa: lo
        contamos, lo imprimimos, vaciamos el bus y reintentamos una vez. Si
        el reintento tambien falla, devolvemos una lista vacia (como si no
        viesemos nada). Si ya llevamos 2 consultas seguidas fallidas, la
        Huskylens 2 esta colgada: no reintentamos, para no doblar el tiempo
        de cada ciclo mientras no responda."""
        try:
            bloques = self._get_blocks(algo_id, solo_aprendidos)
            self._fallos_seguidos = 0
            return bloques
        except OSError as e:
            self.errores_i2c += 1
            print(f"HUSKY: {e} (fallo de bus n={self.errores_i2c})")
            if self._fallos_seguidos >= 2:
                self._fallos_seguidos += 1
                return []
        time.sleep_ms(5)
        self.vaciar()
        try:
            bloques = self._get_blocks(algo_id, solo_aprendidos)
            self._fallos_seguidos = 0
            return bloques
        except OSError as e:
            self.errores_i2c += 1
            self._fallos_seguidos += 1
            print(f"HUSKY: el reintento tambien fallo: {e} (fallo de bus n={self.errores_i2c})")
            return []

    def _get_blocks(self, algo_id, solo_aprendidos):
        """Una consulta GET_RESULT completa, sin proteccion ante fallos del bus
        (los trata get_blocks)."""
        self._enviar(CMD_GET_RESULT, algo_id)
        time.sleep_ms(_ESPERA_RESULTADO_MS)
        buf = self._leer_bruto(_LECTURA_I2C_BYTES)

        esperados, inicio = self._bytes_esperados(buf)
        if esperados is None:
            # La respuesta aun no estaba lista: esperamos un poco mas.
            time.sleep_ms(10)
            buf += self._leer_bruto(_LECTURA_I2C_BYTES)
            esperados, inicio = self._bytes_esperados(buf)
        if esperados is not None and esperados <= _MAX_BYTES_RESPUESTA:
            # Hay mas bloques de los que caben en la primera lectura: leemos
            # solo los bytes que faltan.
            for _ in range(2):
                faltan = esperados - (len(buf) - inicio)
                if faltan <= 0:
                    break
                buf += self._leer_bruto(faltan)

        bloques = []
        for cmd, algo_id_resp, data in self._parsear_tramas(buf):
            if cmd != CMD_RETURN_BLOCKS:
                continue
            if len(data) < 10:
                continue
            id_ = data[0]
            if solo_aprendidos and id_ == 0:
                continue
            algo_bloque = data[1]
            x_center = self._u16(data, 2)
            y_center = self._u16(data, 4)
            width = self._u16(data, 6)
            height = self._u16(data, 8)
            bloques.append(Bloque(id_, algo_bloque, x_center, y_center, width, height))
        return bloques