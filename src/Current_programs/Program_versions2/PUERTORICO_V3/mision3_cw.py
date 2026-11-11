"""MISION3_CW.PY - Obstaculos, sentido CW. Navega por deteccion de pilares
(busca -> se aproxima -> esquiva -> confirma -> vuelve a buscar). Arranca
ya en la calle - el arranque comun a las 4 misiones lo hace main.py.

Lineas: la naranja (la primera de cada esquina en CW) cambia de calle y
cuenta vueltas (4 por vuelta x 3 vueltas = 12); main.py fija
hardware.color_esquina y hardware.color_conteo a 'NARANJA' antes de llamar.
La azul no la usamos: queda pegada a la calle siguiente y, al esquivar un
pilar cerca de la esquina, el sensor podia pisarla varias veces."""
import time
import hardware
from funciones_comunes import navegar_calle_por_rumbo
from funciones_comunes1 import pilar_visible_ahora, buscar_pilar, buscar_direccion_mas_despejada, dirigirse_a_zona_despejada, aproximarse_a_pilar
from funciones_comunes2 import esquivar_pilar


def _buscar_objetivo():
    """Caso 1: encontrar el proximo pilar.
    0. Si ya se ve uno sin barrer (camara centrada), se usa directamente.
    1. Modo crucero por rumbo absoluto (magnetometro): mantiene el chasis
       alineado con la calle actual mientras vigila con un barrido de
       camara +-60, sin dejar de avanzar. Cambia de calle en la linea
       naranja (la primera que aparece en Mision 3), cuenta lineas azules
       de paso. Se usa TAMBIEN justo tras esquivar - antes habia una parada
       + barrido de 180 grados aparte, que arrastraba de cuando no habia
       magnetometro; se quito porque perdia demasiado tiempo por vuelta.
    2. Red de seguridad si el magnetometro no esta disponible: la escalada
       antigua de barridos (90 grados -> 180 grados -> zona mas despejada).
    Devuelve (angulo, color_id) listo para aproximarse_a_pilar(), o (None, None)
    si se completaron las vueltas sin encontrar mas pilares."""
    if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
        return None, None

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


def _tramo_final():
    """Tramo final, despues de contar la ultima linea: seguimos atentos a los
    pilares de la seccion de salida en vez de avanzar a ciegas. Navegamos por
    rumbo con el barrido de siempre durante 1650 ms; si aparece un pilar, nos
    aproximamos y lo esquivamos como en el resto de la carrera. El tiempo de
    navegacion y de aproximacion cuenta (en los dos avanzamos hacia la meta);
    el del esquive no (avanzamos poco, en diagonal, y la recolocacion va
    marcha atras). Antes era un avance recto a Avanza_lento de 2800 ms; ahora
    navegamos a Avanza_crucero, mas rapido, por eso el tiempo es menor."""
    restante_ms = 1650  # AJUSTAR EN PISTA: para quedar parados en la seccion de salida
    while restante_ms > 0:
        t0 = time.ticks_ms()
        angulo, color = pilar_visible_ahora()
        if angulo is None:
            angulo, color = navegar_calle_por_rumbo(lado_pared='izquierda', tiempo_max_ms=restante_ms)
        if angulo is None:
            break  # se acabo el tiempo sin mas pilares
        color_real, alineado = aproximarse_a_pilar(angulo, color)
        restante_ms -= time.ticks_diff(time.ticks_ms(), t0)
        if color_real is not None:
            print(f"--- TRAMO FINAL: esquivar_pilar(color={color_real}), quedan {restante_ms} ms ---")
            esquivar_pilar(color_real, alineado)
            hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)


def ejecutar_mision_3_cw(angulo_inicial=None, color_inicial=None):
    """MISION 3 (CW): navega por deteccion de pilares (no por pared): busca el
    pilar mas cercano, se aproxima manteniendolo centrado con la Huskylens, lo
    esquiva por el lado que marca su color (regla oficial: ROJO=derecha,
    VERDE=izquierda), y vuelve a buscar el siguiente.
    angulo_inicial/color_inicial: si main.py ya localizo el primer pilar, se
    va directo a aproximarse_a_pilar() sin barrer de nuevo. rumbo_calle,
    color_esquina y color_conteo los prepara main.py antes de llamar."""
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

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
            angulo_encontrado, color_encontrado = _buscar_objetivo()
            print(f"--- _buscar_objetivo() resultado: angulo={angulo_encontrado} color={color_encontrado} ---")

        if angulo_encontrado is None:
            print("--- nada encontrado, se reintenta ---")
            if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
                break
            continue

        print("--- aproximarse_a_pilar() ---")
        color_real, alineado = aproximarse_a_pilar(angulo_encontrado, color_encontrado)

        if color_real is None:
            print("--- pilar perdido durante la aproximacion, se reintenta ---")
            continue

        print(f"--- esquivar_pilar(color={color_real}) ---")
        angulo_siguiente, color_siguiente = esquivar_pilar(color_real, alineado)
        hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
        print(f"--- ciclo completado, contadorLineas={hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META} ---")

        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            break

        if angulo_siguiente is not None:
            angulo_pendiente = angulo_siguiente
            color_pendiente = color_siguiente

    print("¡Lineas completadas! Tramo final atentos a los pilares...")
    _tramo_final()
    print("--- MISION 3 COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)