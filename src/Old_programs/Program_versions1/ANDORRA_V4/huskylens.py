"""
Driver minimo para HUSKYLENS por I2C (protocolo DFRobot / HuskyLensProtocol).
Basado en la documentacion oficial del protocolo y contrastado contra una
implementacion de referencia probada en Raspberry Pi Pico.

Uso basico:
    from huskylens import HuskyLens
    hl = HuskyLens(i2c1)          # direccion I2C por defecto 0x32
    if hl.knock():
        bloques = hl.get_blocks()
        for b in bloques:
            print(b.id, b.x_center, b.y_center, b.width, b.height)

    # Solo los bloques de un ID concreto (ID1=rojo, ID2=verde en este proyecto):
    rojos = hl.get_blocks_by_id(1)
    verdes = hl.get_blocks_by_id(2)
"""
import time

_HEADER1 = 0x55
_HEADER2 = 0xAA
_DEVICE_ADDR = 0x11   # direccion "logica" del protocolo, NO la direccion I2C

COMMAND_REQUEST_BLOCKS_LEARNED = 0x24
COMMAND_RETURN_INFO = 0x29
COMMAND_RETURN_BLOCK = 0x2A
COMMAND_RETURN_OK = 0x2E
COMMAND_REQUEST_KNOCK = 0x2C


class HuskyLensBlock:
    def __init__(self, x_center, y_center, width, height, obj_id):
        self.x_center = x_center
        self.y_center = y_center
        self.width = width
        self.height = height
        self.id = obj_id

    def __repr__(self):
        return "Block(id=%d, x=%d, y=%d, w=%d, h=%d)" % (
            self.id, self.x_center, self.y_center, self.width, self.height)


class HuskyLens:
    def __init__(self, i2c, address=0x32):
        self.i2c = i2c
        self.addr = address

    def _checksum(self, datos):
        return sum(datos) & 0xFF

    def _build_frame(self, command, data=b''):
        cuerpo = bytes([_HEADER1, _HEADER2, _DEVICE_ADDR, len(data), command]) + data
        return cuerpo + bytes([self._checksum(cuerpo)])

    def _send(self, command, data=b''):
        frame = self._build_frame(command, data)
        try:
            self.i2c.writeto(self.addr, frame)
            return True
        except OSError:
            return False

    def _read_frame(self):
        """Lee una trama completa: 5 bytes de cabecera + N datos + 1 checksum.
        Devuelve (comando, datos) o None si algo fue mal."""
        try:
            cabecera = self.i2c.readfrom(self.addr, 5)
        except OSError:
            return None

        if len(cabecera) < 5 or cabecera[0] != _HEADER1 or cabecera[1] != _HEADER2:
            return None

        data_len = cabecera[3]
        comando = cabecera[4]

        try:
            resto = self.i2c.readfrom(self.addr, data_len + 1)  # datos + checksum
        except OSError:
            return None

        if len(resto) < data_len:
            return None

        return comando, resto[:data_len]

    def knock(self):
        """Comprueba la conexion. Devuelve True si el sensor responde correctamente."""
        if not self._send(COMMAND_REQUEST_KNOCK):
            return False
        time.sleep_ms(5)
        resultado = self._read_frame()
        return resultado is not None and resultado[0] == COMMAND_RETURN_OK

    def get_blocks(self):
        """Pide todos los bloques detectados (algoritmo actual del Huskylens).
        Devuelve una lista de HuskyLensBlock (vacia si no ve nada o hay error)."""
        if not self._send(COMMAND_REQUEST_BLOCKS_LEARNED):
            return []
        time.sleep_ms(5)

        info = self._read_frame()
        if info is None or info[0] != COMMAND_RETURN_INFO or len(info[1]) < 2:
            return []

        datos_info = info[1]
        num_bloques = datos_info[0] | (datos_info[1] << 8)

        bloques = []
        for _ in range(num_bloques):
            trama = self._read_frame()
            if trama is None:
                break
            comando, datos = trama
            if comando != COMMAND_RETURN_BLOCK or len(datos) < 10:
                continue
            x = datos[0] | (datos[1] << 8)
            y = datos[2] | (datos[3] << 8)
            w = datos[4] | (datos[5] << 8)
            h = datos[6] | (datos[7] << 8)
            obj_id = datos[8] | (datos[9] << 8)
            bloques.append(HuskyLensBlock(x, y, w, h, obj_id))
        return bloques

    def get_blocks_by_id(self, id_deseado):
        """Devuelve solo los bloques cuyo ID coincide (1=rojo, 2=verde en este proyecto)."""
        return [b for b in self.get_blocks() if b.id == id_deseado]