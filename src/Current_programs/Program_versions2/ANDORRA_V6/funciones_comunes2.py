"""
FUNCIONES_COMUNES2.PY - Maniobra de esquive: esquivar_pilar(). Tercera parte
del troceo de funciones_comunes.py (ver ese archivo para el resto de
piezas). Usa "import hardware" y accede a pines/constantes con hardware.X
"""
import time
import hardware
from funciones_comunes import pulso_barrido, _mejor_bloque, _obtener_bloques, leer_tfmini, leer_tof_derecho_mm, _comprobar_lineas
from funciones_comunes1 import _retroceder_hasta_distancia


def esquivar_pilar(color_id):
    """Maniobra de evasion segun el color del pilar (regla oficial WRO 2026):
    ROJO (id=1)  -> mantener el lado DERECHO del carril -> esquivar por la derecha.
    VERDE (id=2) -> mantener el lado IZQUIERDO del carril -> esquivar por la izquierda.

    Si al empezar (o en cualquier momento de la Fase 1) la distancia real al
    pilar es demasiado pequeña, retrocede (con seguimiento visual, ver
    _retroceder_hasta_distancia) antes de intentar - o volver a intentar - el
    giro. Se permiten hasta MAX_INTENTOS_RETROCESO rondas de
    retroceder+intentar el giro: pasar un pilar por el lado incorrecto para
    la competicion, asi que merece la pena reintentar varias veces antes de
    rendirse.

    FASE 1 (giro proporcional a la distancia real, con seguimiento visual):
    la camara sigue apuntando al pilar (igual que en aproximarse_a_pilar)
    para que el TFmini de una distancia real fiable en todo momento. En vez
    de un angulo y velocidad fijos, ambos se calculan de forma CONTINUA segun
    lo lejos que este la distancia actual de DISTANCIA_OBJETIVO_ESQUIVE_CM:
    cuanto mas cerca del pilar, giro mas cerrado y mas velocidad; cuanto mas
    lejos (ya a salvo), giro suave y velocidad de crucero. El robot NUNCA se
    para del todo (salvo al retroceder). Termina cuando ocurre cualquiera de
    estas cosas: la Huskylens pierde el pilar de vista (limite fisico del
    servo), el sensor lateral contrario ya lo ve cerca (pasa a Fase 2), o la
    distancia vuelve a caer por debajo de DISTANCIA_EVASION_CM en pleno giro
    (senal de que el giro no esta abriendo hueco - se reintenta el retroceso).

    FASE 2 (confirmacion): camara al frente, sigue recto vigilando el lateral
    contrario hasta confirmar el patron cerca->lejos (pilar superado), con
    timeout de seguridad por si nunca se completa."""
    usar_izquierdo = (color_id == 1)  # ROJO esquivado por la derecha -> pilar queda a la izquierda
    lado_evasion = hardware.Dcha if color_id == 1 else hardware.Izda
    lado_contrario = hardware.Izda if color_id == 1 else hardware.Dcha  # para el retroceso, en sentido opuesto
    # El giro a la derecha (ROJO) parece necesitar mas angulo real que a la
    # izquierda (VERDE) para la misma separacion lateral - puede ser una
    # asimetria mecanica del diferencial. Intensidad base mas alta para rojo.
    intensidad_base = hardware.INTENSIDAD_GIRO_BASE_ROJO if color_id == 1 else hardware.INTENSIDAD_GIRO_BASE

    if color_id == 1:  # ROJO
        hardware.ledR.value(1)
        hardware.ledV.value(0)
    else:  # VERDE (o cualquier otro id, por seguridad)
        hardware.ledV.value(1)
        hardware.ledR.value(0)

    # Vaciamos el bufer antes de esta primera lectura: es la primera del
    # UART0 tras el cambio de contexto desde aproximarse_a_pilar(), y una
    # lectura con el bufer atrasado puede dar un valor completamente
    # distinto al real.
    while hardware.uart0.any():
        hardware.uart0.read(hardware.uart0.any())
    time.sleep_ms(10)
    distancia_actual = leer_tfmini()
    print(f"ESQUIVAR_PILAR: id={color_id} distancia_inicial={distancia_actual}")

    detectado_cerca = False
    intentos_retroceso = 0

    while True:
        # === RETROCESO (si hace falta) ===
        if distancia_actual is not None and distancia_actual <= hardware.DISTANCIA_EVASION_CM \
                and intentos_retroceso < hardware.MAX_INTENTOS_RETROCESO:
            intentos_retroceso += 1
            print(f"ESQUIVAR_PILAR: demasiado cerca ({distancia_actual}cm), retrocediendo "
                  f"(intento {intentos_retroceso}/{hardware.MAX_INTENTOS_RETROCESO})...")
            distancia_actual = _retroceder_hasta_distancia(lado_contrario, hardware.DISTANCIA_RETROCESO_OBJETIVO_CM)
            print(f"ESQUIVAR_PILAR: retroceso completado, distancia={distancia_actual}")

        # === FASE 1: giro proporcional a la distancia real + seguimiento visual ===
        # Giro de partida GARANTIZADO hacia el lado correcto, antes de entrar
        # en el bucle: si la Huskylens pierde el pilar justo en la primera
        # comprobacion (tipico en angulos extremos, cerca del limite del
        # servo), el bucle puede acabar en un "break" sin haber mandado ni un
        # solo comando de giro - dejando al robot yendo recto en vez de
        # esquivar. Con esto, aunque eso pase, ya se ha iniciado el giro
        # hacia el lado bueno.
        hardware.servoDireccion.duty_u16(lado_evasion)
        hardware.servoTraccion.duty_u16(hardware.Avanza_lento)
        time.sleep_ms(150)

        angulo_camara = 0  # el pilar deberia estar mas o menos centrado al empezar
        distancia_frontal = hardware.DISTANCIA_OBJETIVO_ESQUIVE_CM  # valor de partida conservador
        volver_a_retroceder = False
        t0 = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_ESQUIVE_MS:
            # Sensor lateral contrario: si ya ve el pilar cerca, la evasion ha
            # llegado a su punto critico - pasamos a la Fase 2 de inmediato.
            dist_lateral_mm = (hardware.tof_izquierdo.read_distance_mm() if usar_izquierdo and hardware.tof_izquierdo is not None
                                else (None if usar_izquierdo else leer_tof_derecho_mm()))
            if dist_lateral_mm is not None and (dist_lateral_mm / 10) < hardware.DISTANCIA_LATERAL_CERCA_CM:
                detectado_cerca = True
                print(f"ESQUIVAR_PILAR Fase1: lateral ya ve el pilar cerca ({dist_lateral_mm/10:.1f}cm) -> Fase 2")
                break

            bloques = _obtener_bloques()
            if len(bloques) == 0:
                # La Huskylens ha perdido el pilar (limite fisico del servo) - salimos.
                print("ESQUIVAR_PILAR Fase1: Huskylens perdio el pilar de vista -> Fase 2")
                break

            objetivo = _mejor_bloque(bloques)
            error_px = objetivo.x_center - hardware.FRAME_CENTRO_X

            if abs(error_px) > hardware.DEADBAND_PX:
                correccion = error_px * hardware.PX_A_GRADOS_CAMARA
                correccion = max(-hardware.MAX_CORRECCION_CAMARA_DEG, min(correccion, hardware.MAX_CORRECCION_CAMARA_DEG))
                correccion *= hardware.FACTOR_SUAVIZADO_CAMARA
                angulo_camara += correccion
                angulo_camara = max(hardware.ANGULO_SERVO_MIN, min(angulo_camara, hardware.ANGULO_SERVO_MAX))
                hardware.SERVOcam.duty_u16(pulso_barrido(angulo_camara))

            nueva_distancia = leer_tfmini()
            if nueva_distancia is not None:
                # Correccion geometrica: el TFmini esta mas metido hacia el
                # centro que el borde del chasis, asi que su lectura hay que
                # reducirla para reflejar la distancia real desde el borde.
                distancia_frontal = nueva_distancia - hardware.OFFSET_TFMINI_LATERAL_CM

            # Si en pleno giro la distancia vuelve a caer por debajo del
            # umbral de evasion, el giro no esta abriendo hueco de verdad -
            # mejor cortar aqui y reintentar el retroceso, en vez de seguir
            # girando cada vez mas cerca hasta acabar pasando por el lado
            # incorrecto (o chocando).
            if distancia_frontal <= hardware.DISTANCIA_EVASION_CM and intentos_retroceso < hardware.MAX_INTENTOS_RETROCESO:
                print(f"ESQUIVAR_PILAR Fase1: sigue demasiado cerca ({distancia_frontal:.1f}cm) en pleno giro -> reintentar retroceso")
                distancia_actual = distancia_frontal
                volver_a_retroceder = True
                break

            # Control proporcional continuo: INTENSIDAD_GIRO_BASE = giro
            # minimo que se mantiene siempre (para poder rodear el pilar
            # aunque ya estemos a la distancia de seguridad); por encima de
            # eso, cuanto mas cerca del pilar, mas se intensifica el giro y
            # la velocidad, hasta el maximo si estamos pegados. Sin ningun
            # escalon ni parada.
            cercania = (hardware.DISTANCIA_OBJETIVO_ESQUIVE_CM - distancia_frontal) / hardware.DISTANCIA_OBJETIVO_ESQUIVE_CM
            cercania = max(0, min(1, cercania))
            intensidad = intensidad_base + (1 - intensidad_base) * cercania

            pulso_dir = hardware.Recto + intensidad * (lado_evasion - hardware.Recto)
            hardware.servoDireccion.duty_u16(int(pulso_dir))

            velocidad = hardware.Avanza_lento + intensidad * (hardware.Avanza_tope - hardware.Avanza_lento)
            hardware.servoTraccion.duty_u16(int(velocidad))

            # Antes esquivar_pilar() no comprobaba el color en absoluto - si
            # el robot cruzaba la linea de esquina o una linea azul durante
            # el giro, se perdia por completo. Con esto queda cubierto
            # tambien aqui.
            _comprobar_lineas()

            time.sleep_ms(20)
        else:
            # El bucle termino sin "break": se agoto TIEMPO_ESQUIVE_MS sin que
            # el lateral viera el pilar cerca ni la Huskylens lo perdiera de
            # vista - antes esto pasaba completamente en silencio.
            print("ESQUIVAR_PILAR Fase1: se agoto el tiempo sin confirmar nada -> Fase 2")

        if volver_a_retroceder:
            continue  # vuelve al principio del while True: reintenta el retroceso

        break  # Fase 1 termino con normalidad (lateral cerca o Husky perdida) o se agotaron los intentos

    # === FASE 2: confirmacion por el TFmini-S apuntado al lado correspondiente ===
    # El TFmini-S resulto ser mas rapido que los DOS TOF400F para esto, no
    # solo que el izquierdo (que ya sabiamos que era mas lento) - tambien le
    # gana al derecho por 5-10cm de diferencia en la practica. Se deja de
    # usar cualquiera de los dos TOF aqui: camara fija hacia el lado
    # correspondiente (izquierda para rojo, derecha para verde) y TFmini-S.
    if usar_izquierdo:
        hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_IZQUIERDA)
    else:
        hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_DERECHA)
    hardware.servoDireccion.duty_u16(hardware.Recto)

    # Asentamiento del servo ANTES de avanzar y de fiarse de ninguna lectura:
    # el salto de camara aqui puede ser grande (viene de Fase 1, siguiendo al
    # pilar en cualquier angulo), y sin esta espera el robot ya esta avanzando
    # y leyendo distancias mientras la camara todavia esta de camino al
    # lateral - para cuando llega, el pilar puede haber quedado atras.
    time.sleep_ms(200)

    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    t0 = time.ticks_ms()

    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIMEOUT_CONFIRMACION_ESQUIVE_MS:
        dist_cm = leer_tfmini()

        if dist_cm is not None:
            if not detectado_cerca:
                if dist_cm < hardware.DISTANCIA_LATERAL_CERCA_CM:
                    detectado_cerca = True
            else:
                if dist_cm > hardware.DISTANCIA_LATERAL_LEJOS_CM:
                    print(f"ESQUIVAR_PILAR Fase2: CONFIRMADO, pilar superado ({dist_cm:.1f}cm)")
                    break  # confirmado: pilar superado

        _comprobar_lineas()

        time.sleep_ms(20)

    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.ledR.value(0)
    hardware.ledV.value(0)
    print("ESQUIVAR_PILAR: maniobra completada")