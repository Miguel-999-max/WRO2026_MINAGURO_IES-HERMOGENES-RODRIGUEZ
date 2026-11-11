"""
FUNCIONES_COMUNES2.PY - Maniobra de esquive: esquivar_pilar(). Tercera parte
del troceo de funciones_comunes.py (ver ese archivo para el resto de
piezas). Usa "import hardware" y accede a pines/constantes con hardware.X
"""
import time
import hardware
from funciones_comunes import pulso_barrido, leer_tfmini, diferencia_angular, _comprobar_lineas, _mejor_bloque
from funciones_comunes1 import _retroceder_hasta_distancia


def esquivar_pilar(color_id):
    """Maniobra de evasion segun el color del pilar (regla oficial WRO 2026):
    ROJO (id=1)  -> mantener el lado DERECHO del carril -> esquivar por la derecha.
    VERDE (id=2) -> mantener el lado IZQUIERDO del carril -> esquivar por la izquierda.

    Si al empezar la distancia real al pilar es demasiado pequeña, retrocede
    (con seguimiento visual, ver _retroceder_hasta_distancia) antes de
    intentar el giro. Se permiten hasta MAX_INTENTOS_RETROCESO rondas en total,
    contando tanto los retrocesos previos como los disparados por la
    vigilancia de emergencia de mitad de giro (ver mas abajo).

    Las dos fases del esquive se deciden con la BRUJULA, no con el pilar
    (camara/TFmini/TOF) - las versiones anteriores basadas en sensores del
    pilar resultaron poco fiables (o "se quedaban mirando" al pilar sin
    completar el giro real, o el tramo recto final avanzaba una distancia
    impredecible antes de confirmar nada). El robot mismo es una fuente de
    informacion mucho mas determinista que el pilar.

    FASE 1: gira hacia el lado de evasion (a tope) hasta que el rumbo ha
    cambiado ANGULO_GIRO_ESQUIVE grados en el sentido esperado (rojo: rumbo
    aumenta / derecha; verde: rumbo disminuye / izquierda).

    FASE 2: gira hacia el lado contrario (a tope) hasta recuperar el rumbo
    inicial - un giro igual y opuesto que cancela al de la Fase 1, dejando
    al robot otra vez paralelo a la calle, pero ya al otro lado del pilar.
    Se salta por completo si en el tramo recto entre Fase 1 y Fase 2 ya se
    confirma un pilar distinto a la vista, con un barrido ESTRECHO
    (+-ANGULO_BUSQUEDA_TRANSICION) en vez de mirar solo al frente - un pilar
    mas cercano pero descentrado tras el giro podia quedar fuera de la vista.

    VIGILANCIA DE EMERGENCIA durante las dos fases de giro: la brujula por
    si sola no tiene ojos para el pilar - si la geometria real no coincide
    con lo esperado (por ejemplo, el retroceso previo no dejo suficiente
    margen), el robot puede completar el giro segun la brujula y aun asi
    haber empujado el pilar por el camino, sin que el log refleje ningun
    problema. Por eso, en cada ciclo de las Fases 1 y 2 (camara fija al
    frente todo el rato) se comprueba tambien el TFmini frontal: si baja de
    DISTANCIA_EMERGENCIA_GIRO_CM, se corta el giro de inmediato, se
    reintenta el retroceso, y se reinicia la maniobra completa desde la
    Fase 1 (con un rumbo_inicial nuevo, ya que la posicion ha cambiado).

    Devuelve (angulo, color_id) del siguiente pilar si ya se localizo en el
    tramo entre fases - quien llame puede ir directo a aproximarse_a_pilar()
    con ese dato, sin volver a barrer desde cero. Devuelve (None, None) si no
    se encontro ningun pilar distinto durante la maniobra."""
    lado_evasion = hardware.Dcha if color_id == 1 else hardware.Izda
    lado_contrario = hardware.Izda if color_id == 1 else hardware.Dcha
    signo_giro = 1 if color_id == 1 else -1  # rojo: rumbo aumenta (CW). verde: rumbo disminuye (CCW)

    if color_id == 1:  # ROJO
        hardware.ledR.value(1)
        hardware.ledV.value(0)
    else:  # VERDE (o cualquier otro id, por seguridad)
        hardware.ledV.value(1)
        hardware.ledR.value(0)

    while hardware.uart0.any():
        hardware.uart0.read(hardware.uart0.any())
    time.sleep_ms(10)
    distancia_actual = leer_tfmini()
    print(f"ESQUIVAR_PILAR: id={color_id} distancia_inicial={distancia_actual}")

    intentos_retroceso = 0
    pilar_visto_en_transicion = False
    color_siguiente_pilar = None
    angulo_siguiente_pilar = None

    while True:
        # === PASO PREVIO: retroceder si empieza (o sigue) demasiado cerca ===
        # None se trata como "sigue haciendo falta reintentar", NUNCA como
        # "ya esta bien" - una lectura fallida (Huskylens perdida tan rapido
        # que ni siquiera se consiguio una lectura valida del TFmini) no debe
        # dejar al robot avanzar hacia el giro sin haberse alejado de verdad.
        if distancia_actual is None or distancia_actual <= hardware.DISTANCIA_RETROCESO_TRIGGER_CM:
            if intentos_retroceso >= hardware.MAX_INTENTOS_RETROCESO:
                print(f"ESQUIVAR_PILAR: AVISO - se agotaron los {hardware.MAX_INTENTOS_RETROCESO} intentos de "
                      f"retroceso sin alejarse lo suficiente (distancia={distancia_actual}), se continua igualmente")
            else:
                intentos_retroceso += 1
                print(f"ESQUIVAR_PILAR: demasiado cerca ({distancia_actual}cm), retrocediendo "
                      f"(intento {intentos_retroceso}/{hardware.MAX_INTENTOS_RETROCESO})...")
                distancia_actual = _retroceder_hasta_distancia(lado_contrario, hardware.DISTANCIA_RETROCESO_OBJETIVO_CM)
                print(f"ESQUIVAR_PILAR: retroceso completado, distancia={distancia_actual}")
                continue  # vuelve a comprobar la distancia antes de intentar el giro

        # Camara al frente: ya no hace falta seguir al pilar, las dos fases
        # (y la vigilancia de emergencia) se deciden con la brujula + TFmini frontal.
        hardware.SERVOcam.duty_u16(pulso_barrido(0))

        # === FASE 1: gira hacia lado_evasion hasta sumar/restar ANGULO_GIRO_ESQUIVE ===
        rumbo_inicial = hardware.mag.heading()
        hardware.servoDireccion.duty_u16(lado_evasion)
        hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

        emergencia = False
        while True:
            rumbo_actual = hardware.mag.heading()
            cambio = diferencia_angular(rumbo_actual, rumbo_inicial)

            if cambio * signo_giro >= hardware.ANGULO_GIRO_ESQUIVE:
                print(f"ESQUIVAR_PILAR Fase1: giro completado ({cambio:.1f} grados)")
                break

            distancia_emergencia = leer_tfmini()
            if distancia_emergencia is not None and distancia_emergencia <= hardware.DISTANCIA_EMERGENCIA_GIRO_CM:
                print(f"ESQUIVAR_PILAR Fase1: EMERGENCIA, demasiado cerca en pleno giro "
                      f"({distancia_emergencia}cm) -> se corta y se reintenta el retroceso")
                distancia_actual = distancia_emergencia
                emergencia = True
                break

            _comprobar_lineas()
            time.sleep_ms(20)

        if emergencia:
            continue  # vuelve al principio: reintenta el retroceso y toda la maniobra desde cero

        # === TRAMO RECTO entre Fase 1 y Fase 2 ===
        hardware.servoDireccion.duty_u16(hardware.Recto)
        hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

        angulo_transicion = -hardware.ANGULO_BUSQUEDA_TRANSICION
        sentido_transicion = 1
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_RECTO_ENTRE_FASES_MS:
            # Barrido ESTRECHO (+-ANGULO_BUSQUEDA_TRANSICION, no el ancho de
            # navegar_calle_por_rumbo): si solo miraramos fijo al frente (0),
            # un pilar mas cercano pero ligeramente descentrado tras el giro
            # de la Fase 1 podia quedar fuera de la vista y perderse a favor
            # de uno mas lejano que si estuviera justo en el centro. Con este
            # barrido estrecho lo cubrimos, sin llegar a ser tan ancho como
            # para volver a encontrar el pilar que se acaba de esquivar (que
            # tras ANGULO_GIRO_ESQUIVE grados de giro deberia quedar bastante
            # mas alla de este rango).
            hardware.SERVOcam.duty_u16(pulso_barrido(angulo_transicion))
            bloques = hardware.husky.get_blocks()
            if len(bloques) > 0:
                distancia_bloque = leer_tfmini()
                # PERO: tras solo ANGULO_GIRO_ESQUIVE grados de giro, el
                # pilar que se acaba de esquivar puede seguir perfectamente a
                # la vista desde este angulo nuevo - "hay algo delante" no
                # basta para saber si es el SIGUIENTE pilar o el mismo de
                # antes. Se exige ademas que la distancia real (TFmini) sea
                # claramente mayor que la de evasion, signo de que es un
                # pilar distinto y no el que acabamos de dejar atras a un par
                # de pasos. Si hay mas de un bloque a la vista, se usa el
                # mismo criterio de cercania (Y en pantalla) que el resto del
                # programa para quedarnos con el mas cercano de los dos.
                if distancia_bloque is not None and distancia_bloque > hardware.DISTANCIA_MINIMA_SIGUIENTE_PILAR_CM:
                    pilar_visto_en_transicion = True
                    color_siguiente_pilar = _mejor_bloque(bloques).id
                    angulo_siguiente_pilar = angulo_transicion
                    print(f"ESQUIVAR_PILAR: pilar distinto a la vista en el tramo entre fases "
                          f"(angulo={angulo_transicion}, {distancia_bloque}cm, id={color_siguiente_pilar}) "
                          f"-> se salta la Fase 2, aproximacion directa")
                    break

            angulo_transicion += sentido_transicion * hardware.PASO_BARRIDO
            if angulo_transicion >= hardware.ANGULO_BUSQUEDA_TRANSICION or angulo_transicion <= -hardware.ANGULO_BUSQUEDA_TRANSICION:
                sentido_transicion *= -1

            _comprobar_lineas()
            time.sleep_ms(20)

        # === FASE 2: gira hacia lado_contrario hasta recuperar el rumbo inicial ===
        # (se salta por completo si ya se vio un pilar distinto en el tramo recto anterior)
        if not pilar_visto_en_transicion:
            hardware.servoDireccion.duty_u16(lado_contrario)
            hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

            emergencia = False
            while True:
                rumbo_actual = hardware.mag.heading()
                cambio = diferencia_angular(rumbo_actual, rumbo_inicial)

                if cambio * signo_giro <= 0:
                    print(f"ESQUIVAR_PILAR Fase2: rumbo recuperado ({cambio:.1f} grados)")
                    break

                distancia_emergencia = leer_tfmini()
                if distancia_emergencia is not None and distancia_emergencia <= hardware.DISTANCIA_EMERGENCIA_GIRO_CM:
                    print(f"ESQUIVAR_PILAR Fase2: EMERGENCIA, demasiado cerca en pleno giro "
                          f"({distancia_emergencia}cm) -> se corta y se reintenta el retroceso")
                    distancia_actual = distancia_emergencia
                    emergencia = True
                    break

                _comprobar_lineas()
                time.sleep_ms(20)

            if emergencia:
                continue  # vuelve al principio: reintenta el retroceso y toda la maniobra desde cero

            # === TRAMO RECTO tras Fase 2 (solo si de verdad se hizo la Fase 2) ===
            hardware.servoDireccion.duty_u16(hardware.Recto)
            hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_RECTO_TRAS_FASE2_MS:
                _comprobar_lineas()
                time.sleep_ms(20)

        break  # maniobra completada con normalidad

    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.ledR.value(0)
    hardware.ledV.value(0)
    print("ESQUIVAR_PILAR: maniobra completada")

    if pilar_visto_en_transicion:
        return angulo_siguiente_pilar, color_siguiente_pilar
    return None, None