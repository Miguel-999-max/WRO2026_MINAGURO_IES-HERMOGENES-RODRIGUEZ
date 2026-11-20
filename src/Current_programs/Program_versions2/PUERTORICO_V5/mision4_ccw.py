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
from funciones_comunes import navegar_calle_por_rumbo, leer_tfmini
from funciones_comunes1 import pilar_visible_ahora, buscar_pilar, buscar_direccion_mas_despejada, dirigirse_a_zona_despejada, aproximarse_a_pilar
from funciones_comunes2 import esquivar_pilar, escanear_calle_0, fase_final_si_toca, final_pilar_esquivado

# Escaneo de la calle 0 tras desaparcar (ver escanear_calle_0 en
# funciones_comunes2.py). Con la maniobra de salida de tres movimientos el
# robot queda girado unos 71-79 grados a la IZQUIERDA respecto a la calle 0,
# mirando al muro interior (el aparcamiento no esta centrado en la calle 0).
# Medido en pista (M4, 0VaVbRc, tres rondas):
#     c:  +5 a +18 grados (casi delante),        31-40 cm, base 280
#     b: -55 a -66 grados (izquierda),           42-46 cm, base 219-223
#     a: -81 a -96 grados (a veces algo mas alla del tope del servo, pero
#        dentro de la imagen),                   84 cm, base ~120
# El sitio donde queda el robot varia unos 10 grados (segun la bateria), asi
# que las ventanas son anchas y a y b, que se solapan en direccion, los
# separamos por la DISTANCIA (b a unos 45 cm, a a unos 85).
# A la derecha del todo (+97 grados) se ve muy cerca la pieza magenta del
# aparcamiento como rojo: ninguna mirada llega alli.
# AJUSTAR EN PISTA si la camara cambia de inclinacion o el robot de sitio al desaparcar.
# (asiento, camara, direccion min, max, distancia TFmini min, max, base min, max)
MIRADAS_CALLE_0 = (
    ('c', 5, -20, 35, 15, 50, 220, 480),
    ('b', -60, -85, -45, 30, 65, 150, 330),
    ('a', -90, -120, -70, 65, 120, 95, 175),
)


def _buscar_objetivo(primero_derecha=False):
    """Caso 1: encontrar el proximo pilar. Ver _buscar_objetivo() de
    mision3_cw.py - misma logica, solo cambia el lado de pared vigilado.
    primero_derecha: el primer barrido de navegar_calle_por_rumbo() va hacia
    la derecha en vez de hacia la izquierda (ver ejecutar_mision_4_ccw)."""
    if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
        return None, None

    # En la fase final no miramos al frente sin mas: NAVEGAR_CALLE filtra los
    # pilares (solo el del asiento a) y se para a 110 cm de la pared del fondo
    if not getattr(hardware, 'fase_final', False):
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


def _aparcar():
    """Aparcamiento final de la Mision 4 (PENDIENTE). Por ahora solo nos
    quedamos parados y rectos donde hemos contado la ultima linea: el
    escaneo de la calle 1 y las maniobras de cada caso las anadimos aqui."""
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    print("APARCAR: pendiente, nos quedamos parados")


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
    siguiente barrido empieza hacia la derecha. Solo una vez por carrera.

    Final (como en la Mision 3): al contar la ultima linea pasamos a la FASE
    FINAL (fase_final_si_toca en funciones_comunes2.py): seguimos hasta la
    calle 0, esquivamos solo el pilar del asiento a (si lo hay, segun el
    escaneo de la salida) y NAVEGAR_CALLE se para a 110 cm de la pared del
    fondo."""
    escanear_calle_0(MIRADAS_CALLE_0)  # recien desaparcados: miramos que pilares hay en la calle 0
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    hardware.distancia_parada_final = 110  # fase final: nos paramos a 110 cm de la pared del fondo de la calle 0 (AJUSTAR EN PISTA)
    hardware.asientos_finales = ('a', 'b')  # fase final: asientos de la calle 0 que pasamos antes de pararnos

    angulo_pendiente = angulo_inicial
    color_pendiente = color_inicial
    # Si hay pilar en el asiento c (justo delante al desaparcar), vamos
    # directos a por el en la direccion que nos ha dado el escaneo, sin
    # depender de volver a verlo al frente
    pilar_c = (getattr(hardware, 'pilares_calle0', None) or {}).get('c')
    direccion_c = (getattr(hardware, 'direcciones_calle0', None) or {}).get('c')
    if angulo_pendiente is None and pilar_c in ('R', 'V') and direccion_c is not None:
        angulo_pendiente = max(hardware.ANGULO_SERVO_MIN, min(direccion_c, hardware.ANGULO_SERVO_MAX))
        color_pendiente = 1 if pilar_c == 'R' else 2
        print(f"--- pilar en el asiento c ({pilar_c}) segun el escaneo: vamos a por el a {angulo_pendiente:.1f} grados ---")
    primer_esquive = True        # aun no hemos esquivado ningun pilar tras desaparcar
    # Primer pilar = el del asiento c (el escaneo lo ha visto y vamos a por el):
    # lo esquivamos AL REVES que el resto en M4 (rojo solo con la fase 1, verde
    # con las dos), para quedar casi paralelos a la calle 0 y no perder el
    # primer pilar de la calle 1. Si no, el rojo, con la fase 2, nos dejaba
    # alineados con la calle 1 y pasabamos 1Rd sin verlo.
    esquive_asiento_c = angulo_pendiente is not None and angulo_inicial is None
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
            if fase_final_si_toca():
                break
            print("--- nada encontrado, se reintenta ---")
            continue

        print("--- aproximarse_a_pilar() ---")
        color_real, alineado = aproximarse_a_pilar(angulo_encontrado, color_encontrado)

        if color_real is None:
            esquive_asiento_c = False  # lo hemos perdido: el siguiente ya no es el del asiento c
            if fase_final_si_toca():
                break
            print("--- pilar perdido durante la aproximacion, se reintenta ---")
            continue

        print(f"--- esquivar_pilar(color={color_real}) ---")
        if getattr(hardware, 'fase_final', False):
            final_pilar_esquivado()  # uno menos de los que quedaban en la calle 0
        # Sin Fase 2 para el VERDE: lo esquivamos por el lado hacia el que gira el
        # circuito y asi quedamos ya orientados hacia la esquina. Excepcion: el
        # pilar del asiento c al salir, al reves (ver esquive_asiento_c).
        era_asiento_c = esquive_asiento_c
        rumbo_fase2 = None
        if esquive_asiento_c:
            esquive_asiento_c = False
            fase2 = (color_real == 2)
            if fase2:
                # Verde: la fase 2 gira hasta el rumbo de la CALLE 0 (no hasta el
                # que teniamos al empezar el esquive), para quedar paralelos a ella.
                # Si por el camino cruzamos la primera linea azul, la contamos igual
                # (esquivar_pilar vigila las lineas en todas sus fases).
                rumbo_fase2 = hardware.rumbo_calle[0]
            print(f"--- pilar del asiento c al salir: esquive {'con fase 2 hasta el rumbo de la calle 0' if fase2 else 'sin fase 2'} ---")
        elif getattr(hardware, 'fase_final', False):
            # Fase final: el ultimo esquive siempre con fase 2, hasta el rumbo de
            # la calle 0, para seguir rectos y separados de los muros
            fase2 = True
            rumbo_fase2 = hardware.rumbo_calle[0]
        else:
            fase2 = (color_real != 2)
        angulo_siguiente, color_siguiente = esquivar_pilar(color_real, alineado, fase2=fase2, rumbo_fase2=rumbo_fase2)
        hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
        print(f"--- ciclo completado, contadorLineas={hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META} ---")

        if primer_esquive:
            primer_esquive = False
            # (No si era el del asiento c: con la fase 2 ya quedamos paralelos a la calle 0)
            if color_real == 2 and hardware.contadorLineas == 0 and not era_asiento_c:
                print("--- primer pilar VERDE al desaparcar: paramos 500 ms y barremos primero a la derecha ---")
                time.sleep_ms(500)  # AJUSTAR EN PISTA (el robot ya esta parado tras esquivar)
                barrer_primero_derecha = True

        if fase_final_si_toca():
            break

        if angulo_siguiente is not None and not getattr(hardware, 'fase_final', False):
            angulo_pendiente = angulo_siguiente
            color_pendiente = color_siguiente

    # Parados en la zona de salida (_aparcar(), el aparcamiento entre las
    # paredes, queda para mas adelante): medimos donde nos hemos quedado
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    time.sleep_ms(500)
    lecturas = [d for d in (leer_tfmini() for _ in range(5)) if d is not None]
    final = sum(lecturas) / len(lecturas) if lecturas else None
    print(f"ZONA DE SALIDA: PARADOS a {final} cm de la pared del fondo, rumbo {hardware.mag.heading():.1f} "
          f"(calle 0 = {hardware.rumbo_calle[0]:.1f}), calle {hardware.calle_actual}, lineas {hardware.contadorLineas}")
    print("--- MISION 4 COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)