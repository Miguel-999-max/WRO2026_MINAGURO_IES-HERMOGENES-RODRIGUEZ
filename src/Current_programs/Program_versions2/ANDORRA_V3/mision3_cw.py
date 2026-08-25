"""MISION3_CW.PY - Obstaculos, sentido CW. Desaparca y navega por deteccion
de pilares (busca -> se aproxima -> esquiva -> confirma -> vuelve a buscar)."""
import time
import hardware
from funciones_comunes import (
    leer_tfmini,
    pilar_visible_ahora,
    buscar_pilar,
    buscar_direccion_mas_despejada,
    dirigirse_a_zona_despejada,
    aproximarse_a_pilar,
    esquivar_pilar,
)


def _buscar_objetivo():
    """Caso 1 completo: escalada de 3 niveles para encontrar el proximo pilar.
    0. Si ya se ve uno sin barrer (optimizacion), se usa directamente.
    1. Escaneo centrado de 90 grados.
    2. Si no hay nada, escaneo ampliado de 180 grados.
    3. Si sigue sin haber nada, se dirige a la zona mas despejada (TFmini puro)
       vigilando con la Huskylens por si aparece un pilar en el camino.
    Devuelve (angulo, color_id) listo para aproximarse_a_pilar(), o (None, None)
    si ni el ultimo recurso encontro nada."""
    angulo, color = pilar_visible_ahora()
    if angulo is not None:
        return angulo, color

    angulo, color = buscar_pilar()  # 90 grados (rango por defecto)
    if angulo is not None:
        return angulo, color

    angulo, color = buscar_pilar(hardware.ANGULO_BUSQUEDA_180_INICIO, hardware.ANGULO_BUSQUEDA_180_FIN)
    if angulo is not None:
        return angulo, color

    angulo_despejado = buscar_direccion_mas_despejada()
    encontro_pilar = dirigirse_a_zona_despejada(angulo_despejado)
    if encontro_pilar:
        return pilar_visible_ahora()

    return None, None


def ejecutar_mision_3_cw():
    """MISION 3 (CW): Desaparca y despues navega por deteccion de pilares (no por
    pared, que de momento no es fiable con el chasis desalineado tras aparcar):
    busca el pilar mas cercano, se aproxima hasta 12cm mantenendolo centrado con
    la Huskylens, lo esquiva por el lado que marca su color (regla oficial:
    ROJO=derecha, VERDE=izquierda), confirma que lo ha superado con el sensor
    lateral contrario, y vuelve a buscar el siguiente."""
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

    # === PASO 4: BUSCAR -> APROXIMAR -> ESQUIVAR -> CONFIRMAR ===
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

    while True:
        angulo_encontrado, color_encontrado = _buscar_objetivo()

        if angulo_encontrado is None:
            if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
                break
            continue

        color_real = aproximarse_a_pilar(angulo_encontrado)

        if color_real is None:
            continue

        esquivar_pilar(color_real)  # incluye la confirmacion por sensor lateral mientras avanza
        hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

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