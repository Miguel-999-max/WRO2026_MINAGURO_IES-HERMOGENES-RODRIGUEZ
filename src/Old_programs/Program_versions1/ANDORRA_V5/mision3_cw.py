"""MISION3_CW.PY - Obstaculos, sentido CW. Desaparca y navega por deteccion
de pilares (busca -> se aproxima -> esquiva -> confirma -> vuelve a buscar)."""
import time
import hardware
from funciones_comunes import (
    leer_tfmini,
    pilar_visible_ahora,
    medir_rumbos_calles,
    navegar_calle_por_rumbo,
    buscar_pilar,
    buscar_direccion_mas_despejada,
    dirigirse_a_zona_despejada,
    aproximarse_a_pilar,
    esquivar_pilar,
)


def _buscar_objetivo(forzar_escaneo=False):
    """Caso 1: encontrar el proximo pilar.
    forzar_escaneo=True (justo tras esquivar un pilar): el atajo de 'ya lo
    veo de frente' NO es de fiar aqui - puede haber otro pilar mas cerca
    pero a un lado, fuera de la vista inmediata. Se hace un escaneo
    OBLIGATORIO de 180 grados en pasos de 20, sin usar pilar_visible_ahora().
    forzar_escaneo=False (caso normal): 0. si ya se ve uno sin barrer, se usa
    directamente.
    A partir de ahi, en ambos casos:
    1. Modo crucero por rumbo absoluto (magnetometro): mantiene el chasis
       alineado con la calle actual mientras vigila con un barrido de
       camara, sin dejar de avanzar. Cambia de calle en la linea naranja
       (la primera que aparece en Mision 3), cuenta lineas azules de paso.
    2. Red de seguridad si el magnetometro no esta disponible: la escalada
       antigua de barridos (90 grados -> 180 grados -> zona mas despejada).
    Devuelve (angulo, color_id) listo para aproximarse_a_pilar(), o (None, None)
    si se completaron las vueltas sin encontrar mas pilares."""
    if forzar_escaneo:
        angulo, color = buscar_pilar(hardware.ANGULO_BUSQUEDA_180_INICIO, hardware.ANGULO_BUSQUEDA_180_FIN,
                                      paso=hardware.PASO_BUSQUEDA_ESQUINA)
        if angulo is not None:
            return angulo, color
    else:
        angulo, color = pilar_visible_ahora()
        if angulo is not None:
            return angulo, color

    if hardware.mag is not None:
        return navegar_calle_por_rumbo()

    # --- Red de seguridad: solo si el magnetometro no esta disponible ---
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

    # === MEDICION INICIAL DE RUMBOS (antes de desaparcar) ===
    # El robot esta ahora mismo perfectamente paralelo a la calle de salida
    # (asi se coloca en el aparcamiento) - es el mejor momento para tomar la
    # referencia de rumbo de la que se derivan las otras 3 calles.
    hardware.color_esquina = 'NARANJA'  # Mision 3: la naranja es la primera linea de cada esquina
    if hardware.mag is not None:
        medir_rumbos_calles(hardware.GIRO_POR_ESQUINA_DEG)

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

    justo_tras_esquive = False

    while True:
        print("--- _buscar_objetivo() ---")
        angulo_encontrado, color_encontrado = _buscar_objetivo(forzar_escaneo=justo_tras_esquive)
        justo_tras_esquive = False
        print(f"--- _buscar_objetivo() resultado: angulo={angulo_encontrado} color={color_encontrado} ---")

        if angulo_encontrado is None:
            print("--- nada encontrado, se reintenta ---")
            if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
                break
            continue

        print("--- aproximarse_a_pilar() ---")
        color_real = aproximarse_a_pilar(angulo_encontrado)

        if color_real is None:
            print("--- pilar perdido durante la aproximacion, se reintenta ---")
            continue

        print(f"--- esquivar_pilar(color={color_real}) ---")
        esquivar_pilar(color_real)  # incluye la confirmacion por sensor lateral mientras avanza
        hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
        justo_tras_esquive = True
        print(f"--- ciclo completado, contadorLineas={hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META} ---")

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