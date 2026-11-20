"""
L3G4200D.PY - Driver minimo para el giroscopio L3G4200D del modulo 10 DOF
(GY-80), en el I2C0 con el magnetometro y el sensor de color.
Direccion I2C: 0x69 (WHO_AM_I = 0xD3).

Solo usamos el eje Z (el vertical, con el modulo plano): nos da la velocidad
de giro del robot. Integrandola en el tiempo sabemos cuanto ha girado desde
la salida. A diferencia de la brujula, no le afectan los objetos metalicos ni
las corrientes cercanas; a cambio, el pequeno error de cero que tiene se va
acumulando poco a poco (deriva). Por eso lo calibramos con el robot quieto
antes de empezar.

Uso:
    from l3g4200d import L3G4200D
    giro = L3G4200D(i2c0)
    giro.calibrar()              # robot QUIETO, 5 s
    giro.iniciar(rumbo_inicial)  # empezamos a integrar en segundo plano
    rumbo = giro.heading()       # 0-360, girar a la derecha suma (como la brujula)
    total = giro.acumulado()     # grados girados desde iniciar(), sin dar la vuelta a 360
"""
import time
from machine import Timer

_WHO_AM_I = 0x0F
_CTRL_REG1 = 0x20
_CTRL_REG4 = 0x23
_OUT_Z_L = 0x2C

_SENSIBILIDAD = 0.0175  # grados/s por unidad, con el rango de +-500 grados/s (dato del fabricante)


class L3G4200D:
    def __init__(self, i2c, address=0x69, signo=-1, escala=1.013):
        """signo: el L3G4200D da positivo al girar a la izquierda (visto desde
        arriba, con el chip boca arriba); con -1 lo pasamos al convenio de la
        brujula (a la derecha suma). Si en la prueba sale al reves (por
        ejemplo, el modulo esta montado boca abajo), ponemos signo=1.
        escala: correccion de la sensibilidad de NUESTRO chip (la del
        fabricante tiene unos pocos tanto por ciento de tolerancia). Medida
        dando 4 vueltas exactas a cada lado: el giroscopio marcaba de media
        un 1,3 % menos de lo girado, asi que multiplicamos por 1.013."""
        self.i2c = i2c
        self.addr = address
        self.signo = signo
        self.escala = escala
        self.bias = 0.0          # error de cero en unidades brutas
        self._angulo = 0.0       # grados girados desde iniciar()
        self._rumbo_inicial = 0.0
        self._t_anterior = None
        self._timer = None
        quien = self.i2c.readfrom_mem(self.addr, _WHO_AM_I, 1)[0]
        if quien != 0xD3:
            print("L3G4200D: WHO_AM_I = {} (esperabamos 0xd3)".format(hex(quien)))
        # 200 Hz, filtro de 25 Hz, encendido, ejes X, Y y Z activos
        self.i2c.writeto_mem(self.addr, _CTRL_REG1, bytes([0x5F]))
        # Lectura de bloque (sin mezclar bytes de dos medidas) y rango +-500 grados/s
        self.i2c.writeto_mem(self.addr, _CTRL_REG4, bytes([0x90]))
        # Tras configurarlo, el chip tarda en estabilizarse: durante 1,5 s sus
        # lecturas salen desplazadas. Las leemos y las tiramos.
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < 1500:
            self.leer_z_bruto()
            time.sleep_ms(5)

    def leer_z_bruto(self):
        """Velocidad de giro del eje Z en unidades brutas (con signo)."""
        d = self.i2c.readfrom_mem(self.addr, _OUT_Z_L | 0x80, 2)  # 0x80 = leer varios registros seguidos
        v = d[0] | (d[1] << 8)
        if v >= 0x8000:
            v -= 0x10000
        return v

    def velocidad(self):
        """Velocidad de giro en grados/s, ya sin el error de cero; positiva
        girando a la derecha."""
        return self.signo * (self.leer_z_bruto() - self.bias) * _SENSIBILIDAD * self.escala

    def calibrar(self, ms=5000):
        """Con el robot QUIETO, medimos el error de cero (media de las
        lecturas durante ms milisegundos)."""
        suma = 0
        n = 0
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < ms:
            suma += self.leer_z_bruto()
            n += 1
            time.sleep_ms(5)
        self.bias = suma / n if n else 0.0
        return self.bias

    def _integrar(self, _t):
        ahora = time.ticks_us()
        if self._t_anterior is not None:
            dt = time.ticks_diff(ahora, self._t_anterior) / 1000000
            try:
                self._angulo += self.velocidad() * dt
            except OSError:
                pass  # un fallo puntual del bus: perdemos solo este paso
        self._t_anterior = ahora

    def iniciar(self, rumbo_inicial=0.0):
        """Empezamos a sumar el giro cada 10 ms con un temporizador, en
        segundo plano. rumbo_inicial: el rumbo que damos al punto de partida
        (por ejemplo, el de la brujula en ese momento, para compararlos)."""
        self._angulo = 0.0
        self._rumbo_inicial = rumbo_inicial
        self._t_anterior = None
        self._timer = Timer(period=10, mode=Timer.PERIODIC, callback=self._integrar)

    def parar(self):
        if self._timer is not None:
            self._timer.deinit()
            self._timer = None

    def acumulado(self):
        """Grados girados desde iniciar(), sin dar la vuelta a 360."""
        return self._angulo

    def heading(self):
        """Rumbo en grados (0-360) con el mismo convenio que la brujula."""
        return (self._rumbo_inicial + self._angulo) % 360