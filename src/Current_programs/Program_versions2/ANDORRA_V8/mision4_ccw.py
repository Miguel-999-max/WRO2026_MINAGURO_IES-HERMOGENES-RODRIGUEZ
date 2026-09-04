"""MISION4_CCW.PY - Obstaculos, sentido CCW. Navega por deteccion de pilares
(busca -> se aproxima -> esquiva -> confirma -> vuelve a buscar). Arranca
ya en la calle - el arranque comun a las 4 misiones lo hace main.py.

Diferencias con la Mision 3 (no es un espejo exacto):
- El cambio de calle y el conteo de vueltas usan el MISMO color (AZUL) en
  vez de dos colores distintos - main.py fija hardware.color_esquina='AZUL'
  antes de llamar, y _comprobar_lineas() ya cuenta AZUL de por si, sin
  ningun cambio necesario en esa funcion compartida.
- navegar_calle_por_rumbo() vigila la pared DERECHA (TOF derecho), no la
  izquierda.
- El esquive de pilares (esquivar_pilar) no cambia: rojo siempre por la
  derecha, verde siempre por la izquierda, sea CW o CCW."""
import time
import hardware
from funciones_comunes import navegar_calle_por_rumbo
from funciones_comunes1 import pilar_visible_ahora, buscar_pilar, buscar_direccion_mas_despejada, dirigirse_a_zona_despejada, aproximarse_a_pilar
from funciones_comunes2 import esquivar_pilar


def _buscar_objetivo(forzar_escaneo=False):
    """Caso 1: encontrar el proximo pilar. Ver _buscar_objetivo() de
    mision3_cw.py - misma logica, solo cambia el lado de pared vigilado."""
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
        return navegar_calle_por_rumbo(lado_pared='derecha')

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


def ejecutar_mision_4_ccw(angulo_inicial=None, color_inicial=None):
    """MISION 4 (CCW): navega por deteccion de pilares (no por pared): busca el
    pilar mas cercano, se aproxima manteniendolo centrado con la Huskylens, lo
    esquiva por el lado que marca su color (regla oficial: ROJO=derecha,
    VERDE=izquierda), y vuelve a buscar el siguiente.
    angulo_inicial/color_inicial: si main.py ya localizo el primer pilar, se
    va directo a aproximarse_a_pilar() sin barrer de nuevo. rumbo_calle y
    color_esquina ('AZUL' en esta mision) los prepara main.py antes de llamar."""
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

    justo_tras_esquive = False
    angulo_pendiente = angulo_inicial
    color_pendiente = color_inicial

    while True:
        if angulo_pendiente is not None:
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
    print("--- MISION 4 COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)