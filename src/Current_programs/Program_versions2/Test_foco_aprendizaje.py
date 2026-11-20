"""
TEST_FOCO_APRENDIZAJE.PY - Foco frontal como en la ronda, para ensenar los
colores a la Huskylens 2 con la misma luz que tendra en las misiones 3 y 4.

Medimos la distancia con el TFmini frontal y ajustamos el foco con los
mismos parametros que aproximarse_a_pilar():
  - nivel objetivo = distancia / 100, entre 0.15 y 1.0
    (a 100 cm o mas, a tope; a 15 cm, al 15 %)
  - el foco se acerca a ese nivel como mucho 0.05 por ciclo (foco_hacia),
    asi que sube y baja poco a poco, igual que en carrera
  - si el TFmini no da lectura, dejamos el foco como esta (en carrera solo
    lo cambiamos con una distancia valida)
  - un ciclo cada 40 ms, mas o menos lo que dura una vuelta de la aproximacion

Como lo usamos: dejamos el robot parado, con la camara al centro (el TFmini
va montado con ella), colocamos el pilar a la distancia a la que queremos
que la Husky lo aprenda y lo ensenamos desde la propia Husky. Conviene
ensenarlo a varias distancias (lejos con el foco a tope, cerca con el foco
bajo), porque en carrera lo vera con todas esas luces.
Cada medio segundo imprimimos la distancia y el nivel del foco.
Paramos con Ctrl+C: el foco se apaga.

Solo necesitamos tfmini.py en la Pico. No importamos hardware.py para no
esperar a la Huskylens ni configurar el resto del robot.
"""
from machine import Pin, PWM, UART
import time
from tfmini import TFminiUARTContinuo

# Traccion parada, direccion recta y camara al centro (valores de hardware.py)
traccion = PWM(Pin(13))
direccion = PWM(Pin(20))
camara = PWM(Pin(21))
for servo in (traccion, direccion, camara):
    servo.freq(50)
traccion.duty_u16(4900)    # Para
direccion.duty_u16(5300)   # Recto
camara.duty_u16(4675)      # Cam_Centro

# Foco frontal: GPIO17, PWM a 20 kHz, como en hardware.py
foco = PWM(Pin(17))
foco.freq(20000)
nivel = 1.0                # en carrera, al escanear, el foco va a tope
foco.duty_u16(int(nivel * 65535))

# TFmini frontal: UART0 en lectura continua
tfmini = TFminiUARTContinuo(UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1)))

print("Foco como en la ronda. Ctrl+C para terminar.")
t_impresion = time.ticks_ms()
try:
    while True:
        distancia = tfmini.leer()
        if distancia == 0:
            distancia = None  # 0 cm no es una medida real

        if distancia is not None:
            objetivo = max(0.15, min(1.0, distancia / 100))
            # Igual que foco_hacia(): como mucho 0.05 por ciclo
            if objetivo > nivel:
                nivel = min(nivel + 0.05, objetivo)
            else:
                nivel = max(nivel - 0.05, objetivo)
            foco.duty_u16(int(nivel * 65535))

        if time.ticks_diff(time.ticks_ms(), t_impresion) >= 500:
            t_impresion = time.ticks_ms()
            print("distancia = {} cm   foco = {:.0f} %".format(distancia, nivel * 100))

        time.sleep_ms(40)
except KeyboardInterrupt:
    pass

foco.duty_u16(0)
print("Foco apagado. Fin.")