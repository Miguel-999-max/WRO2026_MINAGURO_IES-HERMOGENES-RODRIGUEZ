"""
TEST STANDALONE - Fiabilidad del magnetometro LSM303DLHC frente a
interferencias de los motores del propio robot.

Alterna automaticamente entre "motor parado" y "motor en marcha" mientras
imprime el rumbo en todo momento - comparad si el rumbo se mantiene estable
o "salta" cuando el motor arranca.

Requiere subir tambien lsm303_mag.py a la Pico.

Conexion (I2C0, compartido con el sensor de color):
  SDA0 -> GPIO4
  SCL0 -> GPIO5
"""
from machine import Pin, I2C, PWM
from lsm303_mag import LSM303Mag
import time

i2c0 = I2C(0, sda=Pin(4), scl=Pin(5))
print("Dispositivos I2C0 encontrados:", [hex(a) for a in i2c0.scan()])

mag = LSM303Mag(i2c0)
print("Magnetometro listo.")

# Servo de traccion, igual que en hardware.py, para probar interferencia real
servoTraccion = PWM(Pin(13))
servoTraccion.freq(50)
Para = 4900
Avanza_tope = 3200

servoDireccion = PWM(Pin(20))
servoDireccion.freq(50)
Recto = 4950

servoDireccion.duty_u16(Recto)
servoTraccion.duty_u16(Para)

DURACION_FASE_MS = 3000
LECTURAS_POR_SEGUNDO = 5

while True:
    print("--- FASE: MOTOR PARADO ---")
    servoTraccion.duty_u16(Para)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < DURACION_FASE_MS:
        x, y, z = mag.read_raw()
        print(f"[PARADO] x={x:6d} y={y:6d} z={z:6d}  rumbo={mag.heading():.1f}")
        time.sleep_ms(1000 // LECTURAS_POR_SEGUNDO)

    print("--- FASE: MOTOR EN MARCHA ---")
    servoTraccion.duty_u16(Avanza_tope)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < DURACION_FASE_MS:
        x, y, z = mag.read_raw()
        print(f"[MOTOR ] x={x:6d} y={y:6d} z={z:6d}  rumbo={mag.heading():.1f}")
        time.sleep_ms(1000 // LECTURAS_POR_SEGUNDO)

    servoTraccion.duty_u16(Para)
