"""
TEST DE BANCO - Foco delantero (LED) con regulacion de intensidad por
potenciometro, en la Pico 2 de reserva.

Cableado:
  - Foco (a traves de su circuito de potencia): GPIO17, salida PWM.
  - Potenciometro: extremos a 3V3 (OUT, pin 36) y GND, cursor (pin central)
    al GPIO26 (ADC0).


Si el foco se enciende con nivel BAJO en el circuito (al reves de lo
normal), ponemos INVERTIR_FOCO = True.
"""
from machine import Pin, PWM, ADC
import time

PIN_FOCO = 17
PIN_POTENCIOMETRO = 26      # solo 26, 27 o 28 (ADC0, ADC1, ADC2)
FRECUENCIA_PWM_HZ = 1000    # por encima de lo que el ojo y la camara perciben como parpadeo
INVERTIR_FOCO = False       # True si el circuito enciende el foco con nivel bajo
CORRECCION_GAMMA = True     # el ojo percibe el brillo de forma no lineal: elevamos al cuadrado para que el potenciometro "se sienta" lineal
MUESTRAS_PROMEDIO = 8       # promediamos lecturas para suavizar el ruido del ADC
UMBRAL_APAGADO = 0.01       # por debajo de este nivel (0-1) apagamos del todo el foco

foco = PWM(Pin(PIN_FOCO))
foco.freq(FRECUENCIA_PWM_HZ)
potenciometro = ADC(Pin(PIN_POTENCIOMETRO))


def leer_nivel():
    """Devuelve el nivel del potenciometro entre 0.0 y 1.0, promediando varias lecturas."""
    suma = 0
    for _ in range(MUESTRAS_PROMEDIO):
        suma += potenciometro.read_u16()
    return suma / (MUESTRAS_PROMEDIO * 65535)


def aplicar_foco(nivel):
    """Pone el foco al nivel indicado (0.0 apagado, 1.0 maximo)."""
    if nivel < UMBRAL_APAGADO:
        nivel = 0.0
    if CORRECCION_GAMMA:
        nivel = nivel * nivel
    duty = int(nivel * 65535)
    if INVERTIR_FOCO:
        duty = 65535 - duty
    foco.duty_u16(duty)


print("Foco en GPIO{} | potenciometro en GPIO{} (ADC) | Ctrl+C para parar".format(PIN_FOCO, PIN_POTENCIOMETRO))

ultimo_print_ms = time.ticks_ms()
try:
    while True:
        nivel = leer_nivel()
        aplicar_foco(nivel)
        if time.ticks_diff(time.ticks_ms(), ultimo_print_ms) >= 300:
            print("Potenciometro: {:5.1f} %".format(nivel * 100))
            ultimo_print_ms = time.ticks_ms()
        time.sleep_ms(10)
except KeyboardInterrupt:
    pass
finally:
    # Dejamos el foco apagado al salir
    aplicar_foco(0.0)
    foco.deinit()
    print("Foco apagado")