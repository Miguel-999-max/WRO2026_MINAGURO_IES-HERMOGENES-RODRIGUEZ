import time

class HuskyLens:
    def __init__(self, i2c, address=0x32):
        self.i2c = i2c
        self.address = address
        
    def _calcular_checksum(self, cmd):
        return sum(cmd) & 0xFF

    def knock(self):
        cmd = b'\x55\xAA\x11\x00\x2C'
        crc = self._calcular_checksum(cmd)
        paquete = cmd + bytes([crc])
        try:
            self.i2c.writeto(self.address, paquete)
            time.sleep_ms(50)
            res = self.i2c.readfrom(self.address, 10)
            if len(res) >= 6 and res[4] == 0x2E:
                return True
        except Exception:
            return False
        return False

    def leer_bloques(self):
        cmd = b'\x55\xAA\x11\x00\x24'
        crc = self._calcular_checksum(cmd)
        paquete = cmd + bytes([crc])
        try:
            self.i2c.writeto(self.address, paquete)
            time.sleep_ms(50)
            res = self.i2c.readfrom(self.address, 16)
            if len(res) >= 11 and res[4] == 0x2A:
                x = (res[6] << 8) | res[5]
                y = (res[8] << 8) | res[7]
                id_objeto = (res[10] << 8) | res[9]
                return {"x": x, "y": y, "id": id_objeto}
        except Exception:
            return None
        return None
