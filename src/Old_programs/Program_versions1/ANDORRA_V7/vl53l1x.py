"""
Driver minimo para el sensor TOF VL53L1X (usado en el TOF400F en modo I2C).
Uso:
    from vl53l1x import VL53L1X
    tof = VL53L1X(i2c1)                          # periodo de medida 30ms por defecto
    tof = VL53L1X(i2c1, intermeasurement_ms=20)   # mas rapido, AJUSTAR EN PISTA con cuidado
    distancia_mm = tof.read_distance_mm()   # None si el dato aun no esta listo
"""

import time


class VL53L1X:

    # Secuencia de configuracion de fabrica (registros 0x2D a 0x87).
    # Es la tabla estandar del chip, igual en cualquier VL53L1X.
    _CONFIG = bytes([
        0x00, 0x00, 0x00, 0x01, 0x02, 0x00, 0x02, 0x08, 0x00, 0x08,
        0x10, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x0F,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x20, 0x0B, 0x00, 0x00, 0x02,
        0x0A, 0x21, 0x00, 0x00, 0x05, 0x00, 0x00, 0x00, 0x00, 0xC8,
        0x00, 0x00, 0x38, 0xFF, 0x01, 0x00, 0x08, 0x00, 0x00, 0x01,
        0xDB, 0x0F, 0x01, 0xF1, 0x0D, 0x01, 0x68, 0x00, 0x80, 0x08,
        0xB8, 0x00, 0x00, 0x00, 0x00, 0x0F, 0x89, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x0F, 0x0D, 0x0E, 0x0E, 0x00,
        0x00, 0x02, 0xC7, 0xFF, 0x9B, 0x00, 0x00, 0x00, 0x01, 0x00,
        0x00
    ])

    REG_MODEL_ID = 0x010F
    REG_SOFT_RESET = 0x0000
    REG_FIRMWARE_STATUS = 0x00E5
    REG_GPIO_HV_STATUS = 0x0031
    REG_INTERRUPT_POLARITY = 0x0030
    REG_SYSTEM_START = 0x0087
    REG_INTERRUPT_CLEAR = 0x0086
    REG_RESULT_DISTANCE = 0x0096
    REG_CONFIG_START = 0x002D
    REG_OSC_CALIBRATE_VAL = 0x00DE          # calibracion propia de cada unidad de silicio
    REG_INTERMEASUREMENT_PERIOD = 0x006C    # registro de 32 bits

    def __init__(self, i2c, address=0x29, intermeasurement_ms=30):
        self.i2c = i2c
        self.addr = address
        self._soft_reset()
        self._check_id()
        self._load_default_config()
        self._set_intermeasurement_period_ms(intermeasurement_ms)
        self._start_ranging()

    # --- utilidades de bajo nivel (registros de 16 bits) ---
    def _write8(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]), addrsize=16)

    def _write32(self, reg, val):
        datos = bytes([(val >> 24) & 0xFF, (val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF])
        self.i2c.writeto_mem(self.addr, reg, datos, addrsize=16)

    def _read8(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1, addrsize=16)[0]

    def _read16(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 2, addrsize=16)
        return (data[0] << 8) | data[1]

    def _set_intermeasurement_period_ms(self, period_ms):
        """Fija el tiempo real entre medidas (por defecto la tabla de fabrica
        deja unos ~140ms, demasiado lento para vigilar un hueco mientras el
        robot avanza a velocidad de crucero). Formula oficial de ST: hay que
        leer primero la calibracion de reloj propia de esta unidad concreta
        del chip (OSC_CALIBRATE_VAL) porque varia de una unidad a otra, y
        con ella convertir los ms deseados al valor que hay que escribir en
        el registro de periodo."""
        osc_calibrate_val = self._read16(self.REG_OSC_CALIBRATE_VAL) & 0x3FF
        if osc_calibrate_val == 0:
            return  # no se pudo leer la calibracion: se deja el periodo de fabrica
        periodo_registro = int(osc_calibrate_val * period_ms * 1.075)
        self._write32(self.REG_INTERMEASUREMENT_PERIOD, periodo_registro)

    # --- inicializacion ---
    def _soft_reset(self):
        self._write8(self.REG_SOFT_RESET, 0x00)
        time.sleep_ms(1)
        self._write8(self.REG_SOFT_RESET, 0x01)
        t0 = time.ticks_ms()
        while (self._read8(self.REG_FIRMWARE_STATUS) & 0x01) == 0:
            if time.ticks_diff(time.ticks_ms(), t0) > 1000:
                raise RuntimeError("VL53L1X: timeout esperando arranque del firmware")
            time.sleep_ms(2)

    def _check_id(self):
        model = self._read16(self.REG_MODEL_ID)
        if model != 0xEACC:
            raise RuntimeError("VL53L1X: ID incorrecto (%s), revisa el cableado I2C" % hex(model))

    def _load_default_config(self):
        # Escritura en bloques de 8 bytes: mas tolerante con cableado marginal
        # que una unica transaccion larga de 91 bytes.
        chunk = 8
        for i in range(0, len(self._CONFIG), chunk):
            reg = self.REG_CONFIG_START + i
            data = self._CONFIG[i:i + chunk]
            self.i2c.writeto_mem(self.addr, reg, data, addrsize=16)
            time.sleep_ms(1)

    def _start_ranging(self):
        self._write8(self.REG_SYSTEM_START, 0x40)  # modo continuo

    def data_ready(self):
        pol = self._read8(self.REG_INTERRUPT_POLARITY) & 0x10
        pol = 0 if pol else 1
        status = self._read8(self.REG_GPIO_HV_STATUS) & 0x01
        return status == pol

    def read_distance_mm(self):
        """Devuelve distancia en mm, o None si el dato aun no esta listo."""
        if not self.data_ready():
            return None
        dist = self._read16(self.REG_RESULT_DISTANCE)
        self._write8(self.REG_INTERRUPT_CLEAR, 0x01)  # limpia interrupcion, prepara siguiente medida
        return dist