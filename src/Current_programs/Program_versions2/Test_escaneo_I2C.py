"""
TEST_ESCANEO_I2C.PY - Escaneamos los dos buses I2C de la Pico 2 y, en las
direcciones tipicas de un giroscopio, leemos su registro de identificacion
(WHO_AM_I) para saber que chip es.

  I2C0 (GPIO4 SDA / GPIO5 SCL): magnetometro LSM303DLHC (0x1E), su
       acelerometro (0x19), sensor de color TCS34725 (0x29) y, si el modulo
       10 DOF lo lleva, el giroscopio y el barometro (0x77).
  I2C1 (GPIO14 SDA / GPIO15 SCL): Huskylens 2 (0x50).

No importamos hardware.py: solo creamos los dos buses, como en el robot.
"""
from machine import Pin, I2C

CONOCIDOS = {
    0x19: "acelerometro del LSM303DLHC",
    0x1E: "magnetometro del LSM303DLHC",
    0x29: "sensor de color TCS34725",
    0x50: "Huskylens 2",
    0x53: "acelerometro ADXL345 (GY-80)",
    0x68: "posible giroscopio ITG3205 / MPU6050",
    0x69: "posible giroscopio L3G4200D (GY-80) o ITG3205",
    0x6A: "posible giroscopio L3GD20 / L3GD20H",
    0x6B: "posible giroscopio L3GD20 / L3GD20H",
    0x77: "barometro BMP085 / BMP180",
}

# Registro de identificacion de cada familia y lo que deberia contestar
WHO_AM_I = {
    0x68: (0x00, {0x68: "ITG3205", 0x69: "ITG3205"}),
    0x69: (0x0F, {0xD3: "L3G4200D", 0xD4: "L3GD20", 0xD7: "L3GD20H"}),
    0x6A: (0x0F, {0xD4: "L3GD20", 0xD7: "L3GD20H"}),
    0x6B: (0x0F, {0xD4: "L3GD20", 0xD7: "L3GD20H"}),
}

buses = (
    ("I2C0 (GPIO4/GPIO5)", I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)),
    ("I2C1 (GPIO14/GPIO15)", I2C(1, sda=Pin(14), scl=Pin(15), freq=100000)),
)

for nombre, bus in buses:
    direcciones = bus.scan()
    print("===", nombre, "===")
    if not direcciones:
        print("  ningun dispositivo")
        continue
    for d in direcciones:
        print("  {}  {}".format(hex(d), CONOCIDOS.get(d, "desconocido")))
        if d in WHO_AM_I:
            registro, esperados = WHO_AM_I[d]
            try:
                valor = bus.readfrom_mem(d, registro, 1)[0]
                chip = esperados.get(valor, "no reconocido")
                print("        WHO_AM_I (registro {}) = {} -> {}".format(hex(registro), hex(valor), chip))
            except OSError as e:
                print("        no hemos podido leer WHO_AM_I:", e)
print("Fin del escaneo.")