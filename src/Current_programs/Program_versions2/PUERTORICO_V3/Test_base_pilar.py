"""
TEST_BASE_PILAR.PY - Calibracion del filtro de pilares lejanos y distracciones
(_bloques_cercanos en funciones_comunes.py).

Con el robot parado, la camara al centro y el foco a tope (como al escanear
en las misiones 3 y 4), imprimimos cada 300 ms los bloques que ve la
Huskylens 2 (id 1 = rojo, id 2 = verde) con su BASE: el borde inferior de
la caja, y_center + height/2, donde el pilar toca el suelo. El 0 de la Y
esta arriba: cuanto mas cerca el pilar, mayor es su base.

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

Solo necesitamos huskylens2.py en la Pico. No movemos el robot: dejamos la
traccion parada y la direccion recta.
"""
from machine import Pin, PWM, I2C
import time
from huskylens2 import HuskyLensV2, ALGORITHM_COLOR_RECOGNITION

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
foco.duty_u16(65535)       # foco a tope, como al escanear

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
        time.sleep_ms(300)
except KeyboardInterrupt:
    pass

foco.duty_u16(0)
print()
print("Resumen (base minima / maxima vista):")
for id_, (mn, mx) in extremos.items():
    print("  id {}: {} / {}".format(id_, mn, mx))
print("Base mas baja en la imagen vista en toda la prueba:", y_maxima)