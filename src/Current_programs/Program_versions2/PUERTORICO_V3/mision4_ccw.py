"""MISION4_CCW.PY - Obstaculos, sentido CCW. Navega por deteccion de pilares
(busca -> se aproxima -> esquiva -> confirma -> vuelve a buscar). Arranca
ya en la calle - el arranque comun a las 4 misiones lo hace main.py.

Diferencias con la Mision 3 (no es un espejo exacto):
- Usamos la linea azul en vez de la naranja: es la primera de cada esquina
  en CCW. main.py fija hardware.color_esquina y hardware.color_conteo a
  'AZUL' antes de llamar: la misma linea cambia de calle y cuenta vueltas
  (4 por vuelta x 3 vueltas = 12). La naranja no la usamos: queda pegada a
  la calle siguiente y, al esquivar un pilar cerca de la esquina, el sensor
  podia pisarla varias veces.
- navegar_calle_por_rumbo() vigila la pared DERECHA (TFmini lateral derecho,
  por la UART hecha con PIO en GPIO6/7), no la izquierda.
- El esquive de pilares (esquivar_pilar) no cambia: rojo siempre por la
  derecha, verde siempre por la izquierda, sea CW o CCW."""
import time
import hardware
from funciones_comunes import navegar_calle_por_rumbo
from funciones_comunes1 import pilar_visible_ahora, buscar_pilar, buscar_direccion_mas_despejada, dirigirse_a_zona_despejada, aproximarse_a_pilar
from funciones_comunes2 import esquivar_pilar


def _buscar_objetivo(primero_derecha=False):
    """Caso 1: encontrar el proximo pilar. Ver _buscar_objetivo() de
    mision3_cw.py - misma logica, solo cambia el lado de pared vigilado.
    primero_derecha: el primer barrido de navegar_calle_por_rumbo() va hacia
    la derecha en vez de hacia la izquierda (ver ejecutar_mision_4_ccw)."""
    if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
        return None, None

    angulo, color = pilar_visible_ahora()
    if angulo is not None:
        return angulo, color

    if hardware.mag is not None:
        return navegar_calle_por_rumbo(lado_pared='derecha', primero_derecha=primero_derecha)

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
    rumbo con el barrido de siempre durante 1450 ms; si aparece un pilar, nos
    aproximamos y lo esquivamos como en el resto de la carrera. El tiempo de
    navegacion y de aproximacion cuenta (en los dos avanzamos hacia la meta);
    el del esquive no (avanzamos poco, en diagonal, y la recolocacion va
    marcha atras). Antes era un avance recto a Avanza_lento de 2500 ms; ahora
    navegamos a Avanza_crucero, mas rapido, por eso el tiempo es menor."""
    restante_ms = 1450  # AJUSTAR EN PISTA: para quedar parados en la seccion de salida
    while restante_ms > 0:
        t0 = time.ticks_ms()
        angulo, color = pilar_visible_ahora()
        if angulo is None:
            angulo, color = navegar_calle_por_rumbo(lado_pared='derecha', tiempo_max_ms=restante_ms)
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


def ejecutar_mision_4_ccw(angulo_inicial=None, color_inicial=None):
    """MISION 4 (CCW): navega por deteccion de pilares (no por pared): busca el
    pilar mas cercano, se aproxima manteniendolo centrado con la Huskylens, lo
    esquiva por el lado que marca su color (regla oficial: ROJO=derecha,
    VERDE=izquierda), y vuelve a buscar el siguiente.
    angulo_inicial/color_inicial: si main.py ya localizo el primer pilar, se
    va directo a aproximarse_a_pilar() sin barrer de nuevo. rumbo_calle y
    color_esquina y color_conteo ('AZUL' en esta mision) los prepara main.py
    antes de llamar.

    Caso especial del arranque: si el PRIMER pilar que esquivamos tras
    desaparcar es VERDE y aun no hemos cruzado la primera linea azul, al
    terminar el esquive quedamos mirando casi de frente al muro interior y la
    calle siguiente nos queda a la derecha. Entonces paramos 500 ms y el
    siguiente barrido empieza hacia la derecha. Solo una vez por carrera."""
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

    angulo_pendiente = angulo_inicial
    color_pendiente = color_inicial
    primer_esquive = True        # aun no hemos esquivado ningun pilar tras desaparcar
    barrer_primero_derecha = False

    while True:
        if angulo_pendiente is not None:
            angulo_encontrado, color_encontrado = angulo_pendiente, color_pendiente
            angulo_pendiente = None
            color_pendiente = None
            print(f"--- pilar ya localizado al esquivar el anterior: angulo={angulo_encontrado} color={color_encontrado} ---")
        else:
            print("--- _buscar_objetivo() ---")
            angulo_encontrado, color_encontrado = _buscar_objetivo(barrer_primero_derecha)
            barrer_primero_derecha = False  # solo para la busqueda siguiente al primer verde
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

        if primer_esquive:
            primer_esquive = False
            if color_real == 2 and hardware.contadorLineas == 0:
                print("--- primer pilar VERDE al desaparcar: paramos 500 ms y barremos primero a la derecha ---")
                time.sleep_ms(500)  # AJUSTAR EN PISTA (el robot ya esta parado tras esquivar)
                barrer_primero_derecha = True

        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            break

        if angulo_siguiente is not None:
            angulo_pendiente = angulo_siguiente
            color_pendiente = color_siguiente

    print("¡Lineas completadas! Tramo final atentos a los pilares...")
    _tramo_final()
    print("--- MISION 4 COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)