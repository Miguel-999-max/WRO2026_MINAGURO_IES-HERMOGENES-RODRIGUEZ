"""MISION3_CW.PY - Obstaculos, sentido CW. Desaparca y navega por deteccion
de pilares (busca -> se aproxima -> esquiva -> vuelve a buscar)."""
import time
import hardware
from funciones_comunes import leer_tfmini, buscar_pilar, aproximarse_a_pilar, esquivar_pilar


def ejecutar_mision_3_cw():
    """MISION 3 (CW): Desaparca y despues navega por deteccion de pilares (no por
    pared, que de momento no es fiable con el chasis desalineado tras aparcar):
    busca el pilar mas cercano, se aproxima hasta 12cm mantenendolo centrado con
    la Huskylens, lo esquiva por el lado que marca su color (regla oficial:
    ROJO=derecha, VERDE=izquierda) y vuelve a buscar el siguiente."""
    DISTANCIA_FRENO_ATRAS = 19  # cm, frenar la marcha atras al llegar a esta distancia

    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    time.sleep_ms(300)

    # === PASO 1: MARCHA ATRAS CONTROLADA POR LIDAR FRONTAL ===
    print("PASO 1: Marcha atras controlada por LiDAR...")
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
    print(f"PASO 1: completado, distancia frontal final = {distancia_frontal}cm")

    # === PASO 2: GIRO DELANTERO HACIA EL INTERIOR (derecha) ===
    print("PASO 2: Giro delantero hacia el interior...")
    hardware.servoDireccion.duty_u16(hardware.Dcha)
    hardware.servoTraccion.duty_u16(4000)
    time.sleep_ms(1500)
    hardware.servoTraccion.duty_u16(hardware.Para)
    print("PASO 2: completado.")

    # === PASO 3: INCORPORACION AL PASILLO ===
    print("PASO 3: Enderezando en el pasillo...")
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Para)
    print("PASO 3: completado.")

    # === PASO 4: BUCLE BUSCAR -> APROXIMAR -> ESQUIVAR ===
    print("Entrando en bucle de obstaculos Mision 3 (CW)...")
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

    while True:
        print("BUSCANDO: escaneando en busca de pilar...")
        angulo_encontrado, color_encontrado = buscar_pilar()
        print(f"BUSCANDO: resultado -> angulo={angulo_encontrado} color={color_encontrado}")

        if angulo_encontrado is None:
            print("BUSCANDO: no se encontro ningun pilar, se reintenta.")
            if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
                break
            continue

        color_real = aproximarse_a_pilar(angulo_encontrado)

        if color_real is None:
            print("Pilar perdido durante la aproximacion, se vuelve a buscar.")
            continue

        esquivar_pilar(color_real)
        hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
        print("EVASION: completada.")

        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            break

    print("¡Lineas completadas! Esperando para clavar la meta...")
    time.sleep_ms(1500)
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    print("--- MISION 3 COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)
