"""MISION3_CW.PY - Obstaculos, sentido CW. Navega por deteccion de pilares
(busca -> se aproxima -> esquiva -> confirma -> vuelve a buscar). Arranca
ya en la calle - el arranque comun a las 4 misiones lo hace main.py."""
import time
import hardware
from funciones_comunes import navegar_calle_por_rumbo
from funciones_comunes1 import pilar_visible_ahora, buscar_pilar, buscar_direccion_mas_despejada, dirigirse_a_zona_despejada, aproximarse_a_pilar
from funciones_comunes2 import esquivar_pilar


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
    if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
        return None, None

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
        return navegar_calle_por_rumbo(lado_pared='izquierda')

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


def ejecutar_mision_3_cw(angulo_inicial=None, color_inicial=None):
    """MISION 3 (CW): navega por deteccion de pilares (no por pared): busca el
    pilar mas cercano, se aproxima manteniendolo centrado con la Huskylens, lo
    esquiva por el lado que marca su color (regla oficial: ROJO=derecha,
    VERDE=izquierda), y vuelve a buscar el siguiente.
    angulo_inicial/color_inicial: si main.py ya localizo el primer pilar, se
    va directo a aproximarse_a_pilar() sin barrer de nuevo. rumbo_calle y
    color_esquina los prepara main.py antes de llamar."""
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

    justo_tras_esquive = False
    angulo_pendiente = angulo_inicial
    color_pendiente = color_inicial

    while True:
        if angulo_pendiente is not None:
            # esquivar_pilar() ya localizo el siguiente pilar mirando al
            # frente en su propio tramo entre fases - nos ahorramos volver a
            # barrear desde cero.
            angulo_encontrado, color_encontrado = angulo_pendiente, color_pendiente
            angulo_pendiente = None
            color_pendiente = None
            print(f"--- pilar ya localizado al esquivar el anterior: angulo={angulo_encontrado} color={color_encontrado} ---")
        else:
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
        angulo_siguiente, color_siguiente = esquivar_pilar(color_real)
        hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
        print(f"--- ciclo completado, contadorLineas={hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META} ---")

        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            break

        if angulo_siguiente is not None:
            angulo_pendiente = angulo_siguiente
            color_pendiente = color_siguiente
        else:
            justo_tras_esquive = True

    print("¡Lineas completadas! Esperando para clavar la meta...")
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)
    time.sleep_ms(1500)
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    print("--- MISION 3 COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)