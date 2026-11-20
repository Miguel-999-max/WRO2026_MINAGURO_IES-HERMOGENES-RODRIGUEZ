"""
Driver minimo para el magnetometro del LSM303DLHC (modulo 10DOF) - SOLO la
parte de brujula, no incluye acelerometro ni giroscopio.
Direccion I2C: 0x1E.

Uso:
    from lsm303_mag import LSM303Mag
    mag = LSM303Mag(i2c0)
    x, y, z = mag.read_raw()
    rumbo_deg = mag.heading()   # ya corregido de hierro duro y blando
"""
import math

_MR_REG_M = 0x02
_OUT_X_H_M = 0x03

# Calibracion, girando el robot completo (encendido como en carrera) con
# calibrar_magnetometro.py:
#   OFFSET_X / OFFSET_Y: hierro duro (el centro del circulo de lecturas no
#   esta en 0).
#   ESCALA_X / ESCALA_Y: hierro blando (el circulo se ha deformado en una
#   elipse; con estas escalas lo volvemos a dejar redondo y los 4 rumbos de
#   las calles quedan a 90 grados).
# Si se vuelve a montar el sensor en otra posicion o cambia lo que hay
# alrededor (bucks, rele, cables...), hay que repetir la calibracion.
OFFSET_X_DEFAULT = -66  
OFFSET_Y_DEFAULT = -155
ESCALA_X_DEFAULT = 1.015
ESCALA_Y_DEFAULT = 0.986


class LSM303Mag:
    def __init__(self, i2c, address=0x1E, offset_x=OFFSET_X_DEFAULT, offset_y=OFFSET_Y_DEFAULT,
                 escala_x=ESCALA_X_DEFAULT, escala_y=ESCALA_Y_DEFAULT):
        self.i2c = i2c
        self.addr = address
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.escala_x = escala_x
        self.escala_y = escala_y
        # Modo de conversion continua. El chip puede arrancar en modo
        # reposo por defecto - sin esto no llegan lecturas nuevas.
        self.i2c.writeto_mem(self.addr, _MR_REG_M, bytes([0x00]))

    def read_raw(self):
        """Devuelve (x, y, z) en crudo, SIN corregir hierro duro.
        OJO: el LSM303DLHC transmite los registros en el orden X, Z, Y
        (no X,Y,Z) - es una peculiaridad conocida de este chip concreto,
        no un error de este driver."""
        datos = self.i2c.readfrom_mem(self.addr, _OUT_X_H_M, 6)

        def s16(hi, lo):
            val = (hi << 8) | lo
            if val >= 0x8000:
                val -= 0x10000
            return val

        x = s16(datos[0], datos[1])
        z = s16(datos[2], datos[3])
        y = s16(datos[4], datos[5])
        return x, y, z

    def heading(self):
        """Rumbo en grados (0-360), corregido de hierro duro (restamos el
        offset) y de hierro blando (multiplicamos por la escala). Sigue sin
        compensar inclinacion (asume el sensor mas o menos horizontal, que
        es el caso en este robot)."""
        x, y, z = self.read_raw()
        rumbo = math.degrees(math.atan2((y - self.offset_y) * self.escala_y,
                                        (x - self.offset_x) * self.escala_x))
        if rumbo < 0:
            rumbo += 360
        return rumbo