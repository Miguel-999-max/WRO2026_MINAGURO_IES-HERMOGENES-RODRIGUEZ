"""
FUNCIONES_COMUNES2.PY - Maniobra de esquive: esquivar_pilar(), y la
recolocacion marcha atras que usamos cuando llegamos demasiado cerca de un
pilar (o de lado).
Tercera parte del troceo de funciones_comunes.py (ver ese archivo para el
resto de piezas). Usa "import hardware" y accede a pines/constantes con
hardware.X
"""
import time
import hardware
from funciones_comunes import pulso_barrido, leer_tfmini, diferencia_angular, _comprobar_lineas, _obtener_bloques, _bloque_seguido

def _recolocar_ante_pilar(color_id):
    """Nos recolocamos cuando hemos llegado demasiado cerca de un pilar (o de
    lado), antes de esquivarlo, sin volver a escanear:
      a. Camara al centro y fija: asi el error en pixeles del pilar mide
         directamente lo desalineado que esta el chasis.
      b. Marcha atras lenta con las ruedas giradas hacia el lado CONTRARIO al
         pilar, en proporcion al error (a tope con el pilar en el borde de la
         imagen), hasta que el pilar queda a menos de 40 px del centro. Marcha
         atras, con el pilar a la derecha y las ruedas a la izquierda, el morro
         gira a la derecha: hacia el pilar. Como la camara no se mueve, el giro
         se para solo en cuanto el pilar esta centrado.
      c. Marcha atras recta hasta que el TFmini (que ya apunta al pilar) mide
         17 cm o mas. Si ya estamos a esa distancia, nos lo saltamos.
    Topes de seguridad (no tenemos sensor trasero): 800 ms para el paso b y
    600 ms para el paso c; en el paso b cortamos tambien si perdemos el pilar
    5 veces seguidas. Pase lo que pase, despues esquivamos.
    Todo el retroceso va con hardware.marcha_atras = True: las lineas que
    crucemos se cuentan en negativo."""
    hardware.SERVOcam.duty_u16(pulso_barrido(0))
    hardware.servoTraccion.duty_u16(hardware.Para)
    time.sleep_ms(200)  # la camara llega al centro y la imagen se estabiliza

    hardware.marcha_atras = True

    # --- b. Centrar el pilar girando marcha atras ---
    hardware.servoTraccion.duty_u16(hardware.Retrocede_lento)
    x_previo = None
    fallos_seguidos = 0
    error_px = None
    motivo = 'tiempo agotado'
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 800:  # AJUSTAR EN PISTA: tope del paso b
        bloques = _obtener_bloques()
        objetivo = _bloque_seguido(bloques, x_previo, color_id) if len(bloques) > 0 else None  # solo nuestro pilar
        if objetivo is not None:
            fallos_seguidos = 0
            x_previo = objetivo.x_center
            error_px = objetivo.x_center - hardware.FRAME_CENTRO_X
            if abs(error_px) <= 40:  # AJUSTAR EN PISTA: tolerancia de centrado en px
                motivo = 'pilar centrado'
                break
            # Pilar a la derecha (error > 0) -> ruedas a la izquierda (pulso mayor que Recto)
            pulso_dir = hardware.Recto + error_px * 6  # AJUSTAR EN PISTA: a tope con ~200 px de error
            pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
            hardware.servoDireccion.duty_u16(pulso_dir)
        else:
            fallos_seguidos += 1
            if fallos_seguidos >= 5:
                motivo = 'pilar perdido'
                break
        _comprobar_lineas()
        time.sleep_ms(10)
    t_b = time.ticks_diff(time.ticks_ms(), t0)

    # --- c. Retroceso recto hasta 17 cm ---
    hardware.servoDireccion.duty_u16(hardware.Recto)
    distancia = leer_tfmini()
    t0 = time.ticks_ms()
    while (distancia is None or distancia < 17) and time.ticks_diff(time.ticks_ms(), t0) < 600:  # AJUSTAR EN PISTA: 17 cm y tope del paso c
        _comprobar_lineas()
        time.sleep_ms(10)
        distancia = leer_tfmini()
    t_c = time.ticks_diff(time.ticks_ms(), t0)

    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.marcha_atras = False
    print(f"RECOLOCAR: paso b fin por {motivo} en {t_b} ms (err={error_px}px), "
          f"paso c {t_c} ms, distancia={distancia}")


def _terminar_maniobra():
    """Dejamos el robot parado y recto, los LED apagados y el foco a tope
    (volvemos a escanear)."""
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.ledR.value(0)
    hardware.ledV.value(0)
    hardware.foco_brillo(1.0)


def esquivar_pilar(color_id, alineado=True, fase2=True):
    """Maniobra de evasion segun el color del pilar (regla oficial WRO 2026):
    ROJO (id=1)  -> mantener el lado DERECHO del carril -> esquivar por la derecha.
    VERDE (id=2) -> mantener el lado IZQUIERDO del carril -> esquivar por la izquierda.

    DEMASIADO CERCA O SIN ENCARAR: si al empezar el TFmini mide
    DISTANCIA_RETROCESO_TRIGGER_CM o menos (o no da lectura), o si
    aproximarse_a_pilar nos dice que hemos llegado sin el chasis encarado al
    pilar (alineado=False), antes de esquivar nos recolocamos marcha atras
    (_recolocar_ante_pilar): centramos el pilar en la imagen girando hacia
    atras y retrocedemos recto hasta 17 cm. Despues esquivamos directamente,
    sin volver a escanear. Una vez empezado el giro (Fases 1 y 2) ya no
    vigilamos la distancia: el giro se completa siempre.

    Las dos fases del esquive se deciden con la BRUJULA, no con el pilar:
    FASE 1: giramos hacia el lado de evasion (a tope) hasta que el rumbo ha
    cambiado ANGULO_GIRO_ESQUIVE grados en el sentido esperado (rojo: rumbo
    aumenta / derecha; verde: rumbo disminuye / izquierda).
    FASE 2: giramos hacia el lado contrario (a tope) hasta recuperar el rumbo
    inicial, quedando otra vez paralelos a la calle pero ya al otro lado del
    pilar. Con fase2=False nos la saltamos (y su tramo recto final): tras el
    tramo recto entre fases terminamos y navegar_calle_por_rumbo() recupera el
    rumbo de la calle mientras busca el siguiente pilar. Lo usamos con el
    color que se esquiva por el lado hacia el que gira el circuito (rojo en
    Mision 3, verde en Mision 4): asi quedamos ya orientados hacia la esquina.

    Devolvemos siempre (None, None): el llamador hace una busqueda normal
    para el siguiente pilar."""

    lado_evasion = hardware.Dcha if color_id == 1 else hardware.Izda
    lado_contrario = hardware.Izda if color_id == 1 else hardware.Dcha
    signo_giro = 1 if color_id == 1 else -1  # rojo: rumbo aumenta (CW). verde: rumbo disminuye (CCW)

    if color_id == 1:  # ROJO
        hardware.ledR.value(1)
        hardware.ledV.value(0)
    else:  # VERDE (o cualquier otro id, por seguridad)
        hardware.ledV.value(1)
        hardware.ledR.value(0)

    # Mientras esquivamos, el foco va apagado (vuelve a tope al terminar).
    hardware.foco_apagar()

    # No vaciamos el bufer de la UART0: el TFmini frontal emite en continuo y
    # el driver ya se queda con la ultima trama recibida.
    time.sleep_ms(10)
    distancia_actual = leer_tfmini()
    print(f"ESQUIVAR_PILAR: id={color_id} distancia_inicial={distancia_actual} alineado={alineado}")

    # === DEMASIADO CERCA: nos recolocamos marcha atras y esquivamos ===
    # None (o 0) cuenta como demasiado cerca: por debajo de unos 10 cm el
    # TFmini-S no da una lectura fiable.
    if distancia_actual is None or distancia_actual <= hardware.DISTANCIA_RETROCESO_TRIGGER_CM or not alineado:
        print(f"ESQUIVAR_PILAR: demasiado cerca ({distancia_actual}cm) o sin encarar "
              f"(alineado={alineado}) -> nos recolocamos marcha atras")
        _recolocar_ante_pilar(color_id)

    # Camara al frente: las dos fases se deciden solo con la brujula.
    hardware.SERVOcam.duty_u16(pulso_barrido(0))

    # === FASE 1: giramos hacia lado_evasion hasta sumar/restar ANGULO_GIRO_ESQUIVE ===
    rumbo_inicial = hardware.mag.heading()
    hardware.servoDireccion.duty_u16(lado_evasion)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    while True:
        rumbo_actual = hardware.mag.heading()
        cambio = diferencia_angular(rumbo_actual, rumbo_inicial)

        if cambio * signo_giro >= hardware.ANGULO_GIRO_ESQUIVE:
            print(f"ESQUIVAR_PILAR Fase1: giro completado ({cambio:.1f} grados)")
            break

        _comprobar_lineas()
        time.sleep_ms(20)

    # === TRAMO RECTO entre Fase 1 y Fase 2 ===
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_RECTO_ENTRE_FASES_MS:
        _comprobar_lineas()
        time.sleep_ms(20)

    if not fase2:
        _terminar_maniobra()
        print("ESQUIVAR_PILAR: maniobra completada sin Fase 2")
        return None, None

    # === FASE 2: giramos hacia lado_contrario hasta recuperar el rumbo inicial ===
    hardware.servoDireccion.duty_u16(lado_contrario)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    while True:
        rumbo_actual = hardware.mag.heading()
        cambio = diferencia_angular(rumbo_actual, rumbo_inicial)

        if cambio * signo_giro <= 0:
            print(f"ESQUIVAR_PILAR Fase2: rumbo recuperado ({cambio:.1f} grados)")
            break

        _comprobar_lineas()
        time.sleep_ms(20)

    # === TRAMO RECTO tras Fase 2 ===
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_RECTO_TRAS_FASE2_MS:
        _comprobar_lineas()
        time.sleep_ms(20)

    _terminar_maniobra()
    print("ESQUIVAR_PILAR: maniobra completada")
    return None, None