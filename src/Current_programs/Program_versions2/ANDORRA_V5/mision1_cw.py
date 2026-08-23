"""MISION1_CW.PY - Reto Libre, giro a derechas (CW)."""
import time
import hardware
from funciones_comunes import leer_tfmini, clasificar_color


def ejecutar_mision_1_cw():
    """MISION 1: Giro a derechas siguiendo pared con filtro estricto de lineas AZULES."""
    print("--- EJECUTANDO MISION 1 CW (GIRO A DERECHAS) ---")

    hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_DERECHA)

    print("Movimiento Inicial 1: Avanzando a la derecha...")
    hardware.servoDireccion.duty_u16(3900)
    hardware.servoTraccion.duty_u16(4000)
    time.sleep_ms(2100)

    print("Movimiento Inicial 2: Avanzando a la izquierda...")
    hardware.servoDireccion.duty_u16(4700)
    hardware.servoTraccion.duty_u16(4000)
    time.sleep_ms(2400)

    print("Salida completada. Entrando en bucle de carrera...")
    distancia_actual = hardware.DISTANCIA_OBJETIVO

    # === FASE 1: sigue pared, termina por CONTEO DE VUELTAS (sin tocar) ===
    while True:
        hardware.servoTraccion.duty_u16(hardware.Avanza_tope)

        nueva_distancia = leer_tfmini()
        if nueva_distancia is not None:
            distancia_actual = nueva_distancia

        error = distancia_actual - hardware.DISTANCIA_OBJETIVO
        pulso_dir = hardware.Recto - (error * hardware.GANANCIA_KP)
        pulso_dir = max(hardware.Dcha, min(pulso_dir, hardware.Izda))
        hardware.servoDireccion.duty_u16(pulso_dir)

        if hardware.sensor_color is None:
            r = g = b = claro = 0
        else:
            r, g, b, claro = hardware.sensor_color.read_rgbc()

        color = clasificar_color(r, g, b)

        if not hardware.sobre_linea:
            if color == 'AZUL':
                hardware.contadorLineas += 1
                hardware.sobre_linea = True
                hardware.ledR.value(1)
                print(f"¡LINEA AZUL DETECTADA! -> Total lineas: {hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META}")
        else:
            if color == 'BLANCO':
                hardware.sobre_linea = False
                hardware.ledR.value(0)

        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            print("¡Lineas completadas! Pasando a la fase final por tiempo...")
            break

        time.sleep_ms(20)

    # === FASE 2: el MISMO sigue pared, ahora termina por TIEMPO (2000ms) ===
    # para clavar la meta sin perder la orientacion respecto a la pared.
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 2000:
        hardware.servoTraccion.duty_u16(hardware.Avanza_tope)

        nueva_distancia = leer_tfmini()
        if nueva_distancia is not None:
            distancia_actual = nueva_distancia

        error = distancia_actual - hardware.DISTANCIA_OBJETIVO
        pulso_dir = hardware.Recto - (error * hardware.GANANCIA_KP)
        pulso_dir = max(hardware.Dcha, min(pulso_dir, hardware.Izda))
        hardware.servoDireccion.duty_u16(pulso_dir)

        time.sleep_ms(20)

    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    print("--- CARRERA COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)