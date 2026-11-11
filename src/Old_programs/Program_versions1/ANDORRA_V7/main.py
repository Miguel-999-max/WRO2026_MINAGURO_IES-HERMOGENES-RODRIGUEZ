#Descomponemos el programa en varios archivos para que sea más legible y mantenible.
#Retocamos la lectura de las líneas de suelo. Ahora va por color.
#Reforzamos la lectura de los sensores de distancia. Ahora se leen varias veces y se descartan lecturas erráticas.
#Cambiamos la forma de detectar misión 1 - misión 2. Ahora se hace por distancias laterales en lugar de por color de línea.
#Introducimos el magnetómetro 10 DOF
#Troceamos funciones_comunes.py en 3 archivos para manejarlos mejor
#Hemos podido completar la primera vuelta de la zona de obstáculos.Ahora vamos a hacer que el robot no confunda el parking con un bloque rojo.



"""MAIN.PY - Punto de entrada. Inicializa hardware, espera el boton, decide
la zona (Reto Libre / Obstaculos) y el sentido (CW/CCW), y llama a la mision
correspondiente."""
import time
import hardware
from funciones_comunes import leer_tfmini, leer_tof_derecho_mm, determinar_zona
from mision1_cw import ejecutar_mision_1_cw
from mision2_ccw import ejecutar_mision_2_ccw
from mision3_cw import ejecutar_mision_3_cw
from mision4_ccw import ejecutar_mision_4_ccw

# ==========================================
# FASE DE INICIO (ESPERA DE BOTON)
# ==========================================
print("--- Robot Unificado Inicializado ---")
hardware.servoTraccion.duty_u16(hardware.Para)
hardware.servoDireccion.duty_u16(hardware.Recto)
hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

# Espera de boton parpadeando led
while hardware.pinBoton.value() == 0:
    hardware.ledR.value(1)
    hardware.ledV.value(0)
    time.sleep_ms(100)
    hardware.ledR.value(0)
    hardware.ledV.value(1)
    time.sleep_ms(100)

hardware.ledV.value(0)
hardware.ledR.value(0)
print("--- ¡ARRANQUE INTERNO! ---")

# ==========================================
# SCAN 1 Y DECISION INICIAL (frontal + lateral, con reintentos si no coinciden)
# ==========================================
es_zona_abierta = determinar_zona()

if es_zona_abierta:
    # --- ZONA ABIERTA (DESAFIO RETO LIBRE) ---
    hardware.ledV.value(1)
    time.sleep_ms(2000)
    hardware.ledV.value(0)

    # Avanza por el centro de la calle (sin frenar) buscando el hueco de la
    # esquina real: TOF400F derecho (fijo, UART1) para el lado derecho, y el
    # TFmini-S apuntado a la izquierda con el servo para el lado izquierdo -
    # mas rapido y constante que el VL53L1X para esta deteccion puntual.
    hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_IZQUIERDA)
    time.sleep_ms(300)  # asentamiento del servo antes de fiarnos de la lectura

    # Vacia el bufer de la UART0: puede haber lecturas frontales atrasadas de
    # determinar_zona() justo antes, y la primera lectura tiene que ser
    # fresca de la izquierda, no basura acumulada mirando al frente.
    while hardware.uart0.any():
        hardware.uart0.read(hardware.uart0.any())
    time.sleep_ms(10)

    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_tope)

    lado_hueco = None  # 'derecha' o 'izquierda'

    while lado_hueco is None:
        dist_der_mm = leer_tof_derecho_mm()
        dist_izq_cm = leer_tfmini()

        if dist_der_mm is not None and (dist_der_mm / 10) > hardware.DISTANCIA_HUECO_CM:
            lado_hueco = 'derecha'
        elif dist_izq_cm is not None and dist_izq_cm > hardware.DISTANCIA_HUECO_CM:
            lado_hueco = 'izquierda'

        time.sleep_ms(20)

    # La primera esquina (con su linea azul) se salta sin pasar por el
    # sensor de color - la damos ya por contada para que el resto de vueltas
    # se sigan contando con normalidad a partir de la maniobra de aproximacion.
    hardware.contadorLineas = 1

    if lado_hueco == 'derecha':
        ejecutar_mision_1_cw()
    else:
        ejecutar_mision_2_ccw()
else:
    # --- ZONA DE OBSTACULOS (APARCAMIENTO) ---
    hardware.ledR.value(1)
    time.sleep_ms(2000)
    hardware.ledR.value(0)

    # Lectura directa del TOF400F derecho (fijo, UART1/Modbus) - sin mover ningun servo
    dist_derecha = 100  # valor por defecto conservador si no hay lectura
    for _ in range(10):
        lectura_mm = leer_tof_derecho_mm()
        if lectura_mm is not None:
            dist_derecha = lectura_mm / 10
            break
        time.sleep_ms(20)

    if dist_derecha > 30:
        for _ in range(3):
            hardware.ledV.value(1)
            time.sleep_ms(150)
            hardware.ledV.value(0)
            time.sleep_ms(150)
        ejecutar_mision_3_cw()
    else:
        for _ in range(3):
            hardware.ledR.value(1)
            time.sleep_ms(150)
            hardware.ledR.value(0)
            time.sleep_ms(150)
        ejecutar_mision_4_ccw()