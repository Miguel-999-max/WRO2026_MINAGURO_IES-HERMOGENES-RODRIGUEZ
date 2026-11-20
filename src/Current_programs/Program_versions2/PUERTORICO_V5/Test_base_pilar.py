"""
TEST_BASE_PILAR.PY - Calibracion del filtro de pilares lejanos y distracciones
(_bloques_cercanos en funciones_comunes.py).

Con el robot parado, la camara al centro y el foco al 50 % (como en la
aproximacion a unos 50 cm: alli bajamos el foco con la distancia, al
distancia/100), imprimimos cada segundo la DISTANCIA que mide el
TFmini frontal (va en el servo de la camara, asi que mide desde la camara
hasta el pilar) y los bloques que ve la Huskylens 2 (id 1 = rojo, id 2 =
verde) con su BASE: el borde inferior de la caja, y_center + height/2, donde
el pilar toca el suelo. El 0 de la Y esta arriba: cuanto mas cerca el pilar,
mayor es su base.

Tambien nos sirve para dejar la camara siempre con la misma inclinacion:
apuntamos la base del pilar a 20, 50 y 100 cm y, si la camara se mueve,
la volvemos a colocar hasta que den los mismos numeros. El pilar tiene que
estar centrado delante, para que el haz del TFmini le de (por debajo de unos
10 cm el TFmini no mide bien).

Como lo usamos:
  1. Colocamos un pilar delante a varias distancias (por ejemplo 40, 60, 80,
     100, 150 cm) y apuntamos la base que da en cada una.
  2. Miramos tambien que base dan las distracciones que la camara ve por
     encima del muro (objetos de color fuera del campo).
  3. Elegimos como umbral la base del pilar a la distancia a partir de la
     cual queremos tenerlo en cuenta (mas o menos 80-100 cm), comprobando
     que queda por debajo (Y mayor) de las distracciones.
  4. Ponemos ese numero en _bloques_cercanos (funciones_comunes.py), donde
     ahora pone >= 0.
Paramos con Ctrl+C: al final imprimimos la base minima y maxima vista de
cada id.

Necesitamos huskylens2.py y tfmini.py en la Pico. No movemos el robot: dejamos la
traccion parada y la direccion recta.
"""
from machine import Pin, PWM, I2C
import time
from machine import UART
from huskylens2 import HuskyLensV2, ALGORITHM_COLOR_RECOGNITION
from tfmini import TFminiUARTContinuo

# Mismos valores que hardware.py
traccion = PWM(Pin(13))
direccion = PWM(Pin(20))
camara = PWM(Pin(21))
for servo in (traccion, direccion, camara):
    servo.freq(50)
traccion.duty_u16(4900)    # Para
direccion.duty_u16(5300)   # Recto
camara.duty_u16(4675)      # Cam_Centro

foco = PWM(Pin(17))
foco.freq(20000)
foco.duty_u16(int(0.5 * 65535))  # foco al 50 %: 0 para apagarlo, 1.0 para ponerlo a tope

# TFmini frontal, igual que en hardware.py: UART0 en lectura continua
frontal = TFminiUARTContinuo(UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1)))


def distancia_frontal():
    """Media de las lecturas validas del TFmini frontal durante 100 ms, en
    cm, o None si no hay ninguna."""
    lecturas = []
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 100:
        d = frontal.leer()
        if d is not None:
            lecturas.append(d)
        time.sleep_ms(10)
    return sum(lecturas) / len(lecturas) if lecturas else None


i2c1 = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000, timeout=100000)
husky = HuskyLensV2(i2c1, address=0x50)

print("Esperamos a la Huskylens 2 ...")
lista = False
for _ in range(100):
    try:
        husky.vaciar()
        if husky.knock():
            lista = True
            break
    except OSError:
        pass
    time.sleep_ms(300)
print("Huskylens 2 lista" if lista else "Aviso: la Huskylens 2 no responde al knock, lo intentamos igual")
try:
    husky.switch_algorithm(ALGORITHM_COLOR_RECOGNITION)
except OSError:
    pass

extremos = {}  # id -> [base minima, base maxima]
y_maxima = 0   # para saber hasta donde llega la Y (alto de la imagen)

try:
    while True:
        d = distancia_frontal()
        print("DISTANCIA (TFmini frontal) = {}".format("{:.0f} cm".format(d) if d is not None else "sin lectura"))
        bloques = husky.get_blocks()
        if not bloques:
            print("(nada)")
        for b in bloques:
            base = b.y_center + b.height // 2
            color = 'ROJO ' if b.id == 1 else 'VERDE' if b.id == 2 else 'id{}'.format(b.id)
            print("{}  x={:3d}  y={:3d}  w={:3d}  h={:3d}  BASE={:3d}".format(
                color, b.x_center, b.y_center, b.width, b.height, base))
            e = extremos.setdefault(b.id, [base, base])
            e[0] = min(e[0], base)
            e[1] = max(e[1], base)
            y_maxima = max(y_maxima, base)
        print("-")
        time.sleep_ms(900)  # con los 100 ms de la medida, una lectura por segundo
except KeyboardInterrupt:
    pass

foco.duty_u16(0)
print()
print("Resumen (base minima / maxima vista):")
for id_, (mn, mx) in extremos.items():
    print("  id {}: {} / {}".format(id_, mn, mx))
print("Base mas baja en la imagen vista en toda la prueba:", y_maxima)