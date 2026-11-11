"""MISION4_CCW.PY - Obstaculos, sentido CCW. Version simetrica de la Mision 3
(desaparca y sigue la pared izquierda + barrido frontal). Pendiente de aplicar
el mismo rediseño de busqueda de pilares que la Mision 3."""
import time
import hardware
from funciones_comunes import leer_tfmini, pulso_barrido


def ejecutar_mision_4_ccw():
    """MISION 4 (CCW): version simetrica de la Mision 3. Desaparca, sigue la pared
    IZQUIERDA con el TOF400F #2 (I2C) y barre el frente con el TFmini.
    De momento solo detecta y señaliza, sin evasion todavia."""
    DISTANCIA_FRENO_ATRAS = 19

    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    time.sleep_ms(300)

    # === PASO 1: MARCHA ATRAS CONTROLADA POR LIDAR FRONTAL ===
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(5500)
    time.sleep_ms(200)

    while hardware.uart0.any():
        hardware.uart0.read(hardware.uart0.any())
    time.sleep_ms(10)

    distancia_frontal = 0
    while distancia_frontal < DISTANCIA_FRENO_ATRAS:
        lectura = leer_tfmini()
        if lectura is not None:
            distancia_frontal = lectura
        time.sleep_ms(5)

    hardware.servoTraccion.duty_u16(hardware.Para)
    time.sleep_ms(100)

    # === PASO 2: GIRO DELANTERO HACIA EL INTERIOR (izquierda) ===
    hardware.servoDireccion.duty_u16(hardware.Izda)
    hardware.servoTraccion.duty_u16(4000)
    time.sleep_ms(1500)

    # === PASO 3: INCORPORACION AL PASILLO ===
    print("Desaparca Paso 3: Enderezando en el pasillo...")
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Para)
    time.sleep_ms(300)

    # === PASO 4: BUCLE DE CARRERA (pared izquierda + barrido frontal) ===
    print("Entrando en bucle de carrera Mision 4 (CCW)...")
    distancia_pared_mm = hardware.DISTANCIA_OBJETIVO * 10
    angulo_barrido = -hardware.ANGULO_MAX_BARRIDO
    sentido_barrido = 1

    while True:
        hardware.servoTraccion.duty_u16(hardware.Avanza_tope)

        # --- Seguimiento de pared con el TOF400F izquierdo (I2C) ---
        if hardware.tof_izquierdo is not None:
            nueva_dist_mm = hardware.tof_izquierdo.read_distance_mm()
            if nueva_dist_mm is not None:
                distancia_pared_mm = nueva_dist_mm

        error = (distancia_pared_mm / 10) - hardware.DISTANCIA_OBJETIVO
        pulso_dir = hardware.Recto + (error * hardware.GANANCIA_KP)
        pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
        hardware.servoDireccion.duty_u16(pulso_dir)

        # --- Barrido frontal incremental (un paso por vuelta de bucle, no bloqueante) ---
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo_barrido))
        dist_frontal = leer_tfmini()
        if dist_frontal is not None and dist_frontal < hardware.UMBRAL_OBSTACULO_CM:
            hardware.ledV.value(1)
        else:
            hardware.ledV.value(0)

        angulo_barrido += sentido_barrido * hardware.PASO_BARRIDO
        if angulo_barrido >= hardware.ANGULO_MAX_BARRIDO or angulo_barrido <= -hardware.ANGULO_MAX_BARRIDO:
            sentido_barrido *= -1

        # --- Conteo de lineas azules (igual que en Reto Libre) ---
        if hardware.sensor_color is None:
            claro = 0
        else:
            r, g, b, claro = hardware.sensor_color.read_rgbc()

        if not hardware.sobre_linea:
            if claro < hardware.PUNTO_CORTE_COLORES:
                hardware.contadorLineas += 1
                hardware.sobre_linea = True
                hardware.ledR.value(1)
                print(f"¡LINEA AZUL DETECTADA! -> Total lineas: {hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META}")
        else:
            if claro >= hardware.UMBRAL_BLANCO_A_COLOR:
                hardware.sobre_linea = False
                hardware.ledR.value(0)

        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            print("¡Lineas completadas! Esperando para clavar la meta...")
            time.sleep_ms(1500)
            hardware.servoTraccion.duty_u16(hardware.Para)
            hardware.servoDireccion.duty_u16(hardware.Recto)
            print("--- MISION 4 COMPLETADA CON EXITO ---")
            while True:
                hardware.ledR.value(1)
                hardware.ledV.value(1)
                time.sleep_ms(500)

        time.sleep_ms(20)
