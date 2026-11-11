"""
FUNCIONES_COMUNES1.PY - Busqueda y aproximacion a pilares: deteccion rapida
sin barrer, barrido completo, ultimo recurso hacia la zona mas despejada y
aproximacion con seguimiento visual.

Segunda parte del troceo de funciones_comunes.py (ver ese archivo para el
resto de piezas). Todas usan "import hardware" y acceden a pines/constantes
con hardware.X
"""
import time
import hardware
from funciones_comunes import pulso_barrido, _mejor_bloque, _bloque_seguido, _bloques_cercanos, _obtener_bloques, leer_tfmini, _comprobar_lineas


def pilar_visible_ahora():
    """Comprueba si ya hay un pilar visible con la camara centrada, sin
    necesidad de barrer (optimizacion: si ya lo vemos, no hace falta escanear).
    Si ve mas de uno a la vez, se queda con el de mayor area (Caso 3).
    Devuelve (angulo=0, color_id), o (None, None) si no ve nada."""
    hardware.SERVOcam.duty_u16(pulso_barrido(0))
    time.sleep_ms(80)

    bloques = _bloques_cercanos(_obtener_bloques())  # solo pilares cercanos
    if len(bloques) == 0:
        print("PILAR_VISIBLE_AHORA: nada cercano a la vista")
        return None, None

    candidato = _mejor_bloque(bloques)
    print(f"PILAR_VISIBLE_AHORA: SI -> id={candidato.id} x={candidato.x_center} y={candidato.y_center} area={candidato.width * candidato.height}")
    return 0, candidato.id


def buscar_pilar(angulo_inicio=None, angulo_fin=None, paso=None):
    """Barre el rango indicado (por defecto ANGULO_BUSQUEDA_INICIO..FIN, 90
    grados centrados, en pasos de PASO_BUSQUEDA) buscando pilares con la
    Huskylens. Si en una misma lectura ve varios bloques a la vez (su propio
    campo de vision es ancho), se queda con el de mayor Y (Caso 3, mas abajo
    en pantalla = mas cerca) - sin necesitar centrar ni medir con el TFmini
    para elegir. El mismo bloque visto en varios pasos del barrido se
    resuelve solo, porque siempre gana la Y mayor vista hasta el momento,
    sin necesidad de agrupar detecciones.
    Devuelve (angulo, color_id) del pilar mas cercano, o (None, None)."""
    if angulo_inicio is None:
        angulo_inicio = hardware.ANGULO_BUSQUEDA_INICIO
    if angulo_fin is None:
        angulo_fin = hardware.ANGULO_BUSQUEDA_FIN
    if paso is None:
        paso = hardware.PASO_BUSQUEDA

    hardware.ledR.value(0)
    hardware.ledV.value(0)

    mejor_angulo = None
    mejor_y = -1
    mejor_id = None

    angulo = angulo_inicio
    while angulo >= angulo_fin:
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo))
        time.sleep_ms(80)  # paso grande: el servo necesita mas asentamiento que en la aproximacion

        bloques = _bloques_cercanos(_obtener_bloques())  # solo pilares cercanos

        if len(bloques) > 0:
            candidato = _mejor_bloque(bloques)
            print(f"BUSCAR_PILAR [{angulo}]: DETECTADO id={candidato.id} y={candidato.y_center} (mejor hasta ahora={mejor_y})")

            if candidato.id == 1:
                hardware.ledR.value(1)
                hardware.ledV.value(0)
            else:
                hardware.ledV.value(1)
                hardware.ledR.value(0)

            if candidato.y_center > mejor_y:
                mejor_y = candidato.y_center
                mejor_angulo = angulo
                mejor_id = candidato.id
                print(f"BUSCAR_PILAR [{angulo}]: nuevo MEJOR -> angulo={mejor_angulo} id={mejor_id} y={mejor_y}")
        else:
            hardware.ledR.value(0)
            hardware.ledV.value(0)

        angulo -= paso

    # El barrido recorre todo el rango aunque encuentre el pilar pronto, asi
    # que la camara puede quedar fisicamente muy lejos del angulo ganador
    # (hasta 140-180 grados de salto). La reorientamos aqui, antes de
    # devolver el resultado, para que aproximarse_a_pilar() ya la encuentre
    # apuntando (casi) donde toca.
    if mejor_angulo is not None:
        hardware.SERVOcam.duty_u16(pulso_barrido(mejor_angulo))
        time.sleep_ms(250)  # igual que aproximarse_a_pilar: el salto puede ser grande

        # Confirmacion: una sola lectura puede ser un espejismo puntual
        # (fusion de bordes, ruido) en vez del pilar real. Volvemos a
        # preguntar justo aqui - si no confirma nada, descartamos el
        # candidato en vez de devolver un angulo fantasma que luego
        # aproximarse_a_pilar() no podra encontrar por mucho que se reposicione.
        # Varios intentos: un solo fallo aqui es demasiado caro (obliga a
        # descartar un candidato que puede ser perfectamente real).
        confirmado = False
        for _ in range(3):
            confirmacion = _bloques_cercanos(_obtener_bloques())
            if len(confirmacion) > 0:
                confirmado = True
                break
            time.sleep_ms(30)

        if not confirmado:
            print(f"BUSCAR_PILAR: candidato en angulo={mejor_angulo} NO confirmado, se descarta")
            mejor_angulo = None
            mejor_id = None
            hardware.ledR.value(0)
            hardware.ledV.value(0)

    print(f"BUSCAR_PILAR: resultado final -> angulo={mejor_angulo} id={mejor_id} y={mejor_y}")
    return mejor_angulo, mejor_id


def buscar_direccion_mas_despejada():
    """Ultimo recurso del Caso 1: barre SOLO con el TFmini (sin Huskylens,
    mas rapido) buscando la direccion con mayor distancia libre. Tipico en
    esquinas, justo tras esquivar un pilar, donde no queda ninguno a la vista.
    Devuelve el angulo con mayor distancia encontrada (0 si no se leyo nada)."""
    mejor_angulo = 0
    mejor_distancia = -1

    angulo = hardware.ANGULO_BUSQUEDA_180_INICIO
    while angulo >= hardware.ANGULO_BUSQUEDA_180_FIN:
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo))
        time.sleep_ms(80)

        # No vaciamos el bufer de la UART0: el TFmini frontal emite en continuo y
        # el driver ya se queda con la ultima trama recibida.
        time.sleep_ms(10)

        distancia = None
        t0 = time.ticks_ms()
        while distancia is None and time.ticks_diff(time.ticks_ms(), t0) < 50:
            distancia = leer_tfmini()

        if distancia is not None and distancia > mejor_distancia:
            mejor_distancia = distancia
            mejor_angulo = angulo

        angulo -= hardware.PASO_BUSQUEDA

    return mejor_angulo


def dirigirse_a_zona_despejada(angulo_objetivo):
    """Gira el chasis hacia la direccion mas despejada y avanza, vigilando con
    un pequeno barrido oscilante alrededor de ese rumbo: la Huskylens por si
    aparece un pilar (en cuyo caso se aborta la maniobra) y el TFmini para no
    chocar con una pared. Devuelve True si aparecio un pilar durante la
    maniobra, False si se completo el tiempo o se freno por seguridad."""
    pulso_dir = hardware.Recto - (angulo_objetivo * hardware.GANANCIA_KP_VISUAL)
    pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
    hardware.servoDireccion.duty_u16(pulso_dir)

    angulo_oscilacion = -hardware.ANGULO_MAX_BARRIDO
    sentido = 1
    t0 = time.ticks_ms()

    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_MANIOBRA_DESPEJADA_MS:
        hardware.servoTraccion.duty_u16(hardware.Avanza_tope)

        angulo_cam = angulo_objetivo + angulo_oscilacion
        angulo_cam = max(hardware.ANGULO_SERVO_MIN, min(angulo_cam, hardware.ANGULO_SERVO_MAX))
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo_cam))

        bloques = _bloques_cercanos(hardware.husky.get_blocks())
        if len(bloques) > 0:
            hardware.servoTraccion.duty_u16(hardware.Para)
            return True

        distancia = leer_tfmini()
        if distancia is not None and distancia < hardware.DISTANCIA_SEGURIDAD_CM:
            hardware.servoTraccion.duty_u16(hardware.Para)
            return False

        angulo_oscilacion += sentido * hardware.PASO_BARRIDO
        if angulo_oscilacion >= hardware.ANGULO_MAX_BARRIDO or angulo_oscilacion <= -hardware.ANGULO_MAX_BARRIDO:
            sentido *= -1

        time.sleep_ms(20)

    hardware.servoTraccion.duty_u16(hardware.Para)
    return False


def aproximarse_a_pilar(angulo_inicial, color_inicial=None):
    """Avanzamos hacia el pilar detectado hasta quedar a DISTANCIA_EVASION_CM
    segun el TFmini, siguiendolo con la camara y dirigiendo el chasis hacia el.
    Devolvemos (color_id, alineado), o (None, None) si lo perdemos de vista.

    SIN CAMBIAR DE PILAR: seguimos solo el color con el que empezamos
    (color_inicial, o el del primer bloque si no nos lo dan) y, entre los de
    ese color, el mas cercano en X a donde estaba (_bloque_seguido). Si no
    esta en la imagen, contamos un fallo; tras 5 seguidos lo damos por perdido
    y volvemos a escanear.

    RUMBO REAL DEL PILAR con compensacion del retraso: la Huskylens 2 nos da
    la X de una imagen tomada unos 150 ms antes, cuando la camara estaba en
    otro angulo. Guardamos el angulo de la camara de los ultimos ciclos y
    calculamos donde esta el pilar respecto al chasis:
        rumbo_pilar = angulo de la camara hace 150 ms + error_px * 0.075
    La camara la llevamos directamente a ese angulo (no a base de pequenas
    correcciones) y el chasis lo dirigimos tambien hacia el (con tope de
    +-25 grados de volante). Antes dirigiamos el chasis solo con el angulo de
    la camara: mientras la camara se ponia al dia el robot giraba de mas y el
    pilar se iba al borde de la imagen.

    LLEGADA: a DISTANCIA_EVASION_CM o menos con el pilar a menos de 130 px del
    centro de la imagen (a esa distancia el haz del TFmini ya lo toca), o a
    DISTANCIA_EMERGENCIA_APROX_CM o menos en cualquier caso. alineado nos dice
    si el chasis esta encarado al pilar (rumbo_pilar dentro de
    UMBRAL_ALINEACION_APROX): si no lo esta, esquivar_pilar se recoloca antes.
    De paso vigilamos las lineas, igual que en el resto del programa."""
    angulo_camara = angulo_inicial
    hardware.SERVOcam.duty_u16(pulso_barrido(angulo_camara))
    time.sleep_ms(250)  # el salto desde el ultimo angulo del barrido puede ser grande
    print(f"APROXIMARSE_A_PILAR: iniciando desde angulo={angulo_inicial} id={color_inicial}")

    fallos_seguidos = 0
    t_inicio_ms = time.ticks_ms()  # solo para el registro de cada ciclo
    x_previo = None   # X del pilar que seguimos
    id_seguido = color_inicial
    # Angulos de camara de los ultimos ciclos: (instante_ms, angulo). La
    # camara ya lleva 250 ms quieta en angulo_inicial.
    historial = [(time.ticks_add(time.ticks_ms(), -250), angulo_camara)]

    while True:
        bloques = _obtener_bloques()
        objetivo = _bloque_seguido(bloques, x_previo, id_seguido) if len(bloques) > 0 else None

        if objetivo is None:
            fallos_seguidos += 1
            print(f"APROXIMARSE_A_PILAR: sin nuestro pilar ({fallos_seguidos}/5, bloques={len(bloques)})")
            if fallos_seguidos >= 5:
                hardware.servoTraccion.duty_u16(hardware.Para)
                print("APROXIMARSE_A_PILAR: PERDIDO, se devuelve None")
                hardware.foco_brillo(1.0)
                return None, None
            _comprobar_lineas()  # sin pilar tambien seguimos vigilando las lineas
            time.sleep_ms(20)
            continue

        fallos_seguidos = 0
        x_previo = objetivo.x_center
        color_id = objetivo.id
        id_seguido = color_id  # a partir de aqui, solo este color
        error_px = objetivo.x_center - hardware.FRAME_CENTRO_X

        # Angulo que tenia la camara cuando se tomo esta imagen (hace ~150 ms)
        ahora_ms = time.ticks_ms()
        t_imagen = time.ticks_add(ahora_ms, -150)  # AJUSTAR EN PISTA: retraso de la Huskylens 2
        angulo_imagen = historial[0][1]
        for t_h, a_h in historial:
            if time.ticks_diff(t_h, t_imagen) <= 0:
                angulo_imagen = a_h
        rumbo_pilar = angulo_imagen + error_px * hardware.PX_A_GRADOS_CAMARA
        rumbo_pilar = max(hardware.ANGULO_SERVO_MIN, min(rumbo_pilar, hardware.ANGULO_SERVO_MAX))

        # Camara directa al pilar, ignorando cambios menores de la zona
        # muerta (ruido) y con un tope de 15 grados por ciclo (por si una
        # lectura sale mal)
        cambio = rumbo_pilar - angulo_camara
        if abs(cambio) > hardware.DEADBAND_PX * hardware.PX_A_GRADOS_CAMARA:
            cambio = max(-15, min(cambio, 15))
            angulo_camara += cambio
            hardware.SERVOcam.duty_u16(pulso_barrido(angulo_camara))
        historial.append((ahora_ms, angulo_camara))
        if len(historial) > 12:
            historial.pop(0)

        # Chasis hacia el rumbo real del pilar (no hacia la camara)
        angulo_direccion = max(-25, min(rumbo_pilar, 25))
        pulso_dir = hardware.Recto - (angulo_direccion * hardware.GANANCIA_KP_VISUAL_APROX)
        pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
        hardware.servoDireccion.duty_u16(pulso_dir)

        # Distancia con el TFmini (mismo eje que la camara)
        distancia = leer_tfmini()
        if distancia == 0:
            distancia = None  # una lectura de 0 cm no es una medida real: la tratamos como sin dato

        # Foco: baja poco a poco al acercarnos al pilar (a 100 cm o mas, a
        # tope; a 15 cm, al 15 %). foco_hacia lo limita a 0.05 por ciclo.
        if distancia is not None:
            hardware.foco_hacia(max(0.15, min(1.0, distancia / 100)))

        alineado = abs(rumbo_pilar) <= hardware.UMBRAL_ALINEACION_APROX

        print(f"APROX t={time.ticks_diff(ahora_ms, t_inicio_ms)}ms id={color_id} x={objetivo.x_center} "
              f"err={error_px}px rumbo={rumbo_pilar:.1f} cam={angulo_camara:.1f} dist={distancia} bloques={len(bloques)}")

        # Llegada
        if distancia is not None and (
                (distancia <= hardware.DISTANCIA_EVASION_CM and abs(error_px) <= 130)  # AJUSTAR EN PISTA: px
                or distancia <= hardware.DISTANCIA_EMERGENCIA_APROX_CM):
            hardware.servoTraccion.duty_u16(hardware.Para)
            print(f"APROXIMARSE_A_PILAR: LLEGADA a {distancia}cm, id={color_id}, "
                  f"rumbo={rumbo_pilar:.1f}, err={error_px}px, alineado={alineado}")
            return color_id, alineado

        # Velocidad: a tope solo con el chasis encarado; despacio si no, y
        # frenando por distancia en el tramo final (a 20 cm o menos, muy
        # despacio: entre dos lecturas el robot avanza sin saber cuanto le falta)
        cerca_de_parar = distancia is not None and distancia <= (hardware.DISTANCIA_EVASION_CM + hardware.MARGEN_FRENADO_APROX_CM)
        if distancia is not None and distancia <= 20:  # AJUSTAR EN PISTA: inicio del tramo muy lento
            hardware.servoTraccion.duty_u16(4550)  # AJUSTAR EN PISTA: muy lento (Para = 4900); que no se quede parado
        elif cerca_de_parar:
            hardware.servoTraccion.duty_u16(hardware.Avanza_lento)
        elif alineado:
            hardware.servoTraccion.duty_u16(hardware.Avanza_tope)
        else:
            hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

        _comprobar_lineas()

        # Testigo LED: color del pilar que seguimos
        if color_id == 1:
            hardware.ledR.value(1)
            hardware.ledV.value(0)
        else:
            hardware.ledV.value(1)
            hardware.ledR.value(0)

        time.sleep_ms(20)