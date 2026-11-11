"""
Prueba de los tres TFmini-S con el driver tfmini.py (subimos tambien tfmini.py
a la Pico). Cableado:
  frontal   : UART0, TX=GPIO0, RX=GPIO1 (continuo, 100 Hz)
  derecho   : I2C1, SDA=GPIO14, SCL=GPIO15 (a demanda)
  izquierdo : UART1, TX=GPIO8, RX=GPIO9 (a demanda)
Medimos cada sensor 100 veces para ver cuanto tarda cada lectura y cuantas
salen invalidas. Apuntamos cada uno a una pared a distancia conocida.
Esperamos que el frontal (continuo) tarde casi 0 ms y que los otros dos
tarden unos 12 ms por lectura.
"""
from machine import Pin, I2C, UART
import time
from tfmini import TFminiI2C, TFminiUART, TFminiUARTContinuo

i2c1 = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000)
sensores = {
    'frontal (UART0 continuo)': TFminiUARTContinuo(UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))),
    'derecho (I2C)': TFminiI2C(i2c1, 0x10),
    'izquierdo (UART1)': TFminiUART(UART(1, baudrate=115200, tx=Pin(8), rx=Pin(9))),
}

for nombre, s in sensores.items():
    tiempos, malas, ejemplos = [], 0, []
    for _ in range(100):
        t0 = time.ticks_us()
        d = s.leer()
        tiempos.append(time.ticks_diff(time.ticks_us(), t0))
        if d is None:
            malas += 1
        elif len(ejemplos) < 5:
            ejemplos.append(d)
        time.sleep_ms(25)
    print("{}: media {:.2f} ms, max {:.2f} ms, no validas {}/100, ejemplos {}".format(
        nombre, sum(tiempos) / len(tiempos) / 1000, max(tiempos) / 1000, malas, ejemplos))
