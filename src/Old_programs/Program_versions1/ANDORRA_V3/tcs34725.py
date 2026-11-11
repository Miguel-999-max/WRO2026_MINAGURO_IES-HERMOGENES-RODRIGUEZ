import time

class TCS34725:
    def __init__(self, i2c, address=0x29):
        self.i2c = i2c
        self.address = address
        
        # Verificar que el sensor responde (ID del dispositivo)
        # El comando requiere sumarle 0x80 (128) al registro
        try:
            device_id = self.i2c.readfrom_mem(self.address, 0x12 | 0x80, 1)[0]
        except Exception:
            raise RuntimeError("Fallo físico: No se detecta el sensor en el bus I2C.")
            
        if device_id not in [0x44, 0x4D]:
            raise RuntimeError(f"Sensor incorrecto detectado (ID: {hex(device_id)})")
            
        # Encender el sensor (PON = Power ON)
        self.i2c.writeto_mem(self.address, 0x00 | 0x80, b'\x01')
        time.sleep_ms(3)
        # Habilitar el ADC (AEN = RGBC Enable)
        self.i2c.writeto_mem(self.address, 0x00 | 0x80, b'\x03')
        # Configurar tiempo de integración a 24ms (aproximado)
        self.i2c.writeto_mem(self.address, 0x01 | 0x80, b'\xF6')
        # Configurar ganancia a 1x
        self.i2c.writeto_mem(self.address, 0x0F | 0x80, b'\x00')

    def read_rgbc(self):
        # Leer 8 bytes de datos desde el registro inicial 0x14
        data = self.i2c.readfrom_mem(self.address, 0x14 | 0x80, 8)
        
        # Unir bytes bajos y altos para formar enteros de 16 bits
        c = (data[1] << 8) | data[0]
        r = (data[3] << 8) | data[2]
        g = (data[5] << 8) | data[6] # Corrección de índice
        g = (data[5] << 8) | data[4]
        b = (data[7] << 8) | data[6]
        
        return r, g, b, c