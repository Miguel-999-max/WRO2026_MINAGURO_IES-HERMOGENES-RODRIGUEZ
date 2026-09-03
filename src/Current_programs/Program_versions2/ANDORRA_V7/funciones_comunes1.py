"""
FUNCIONES_COMUNES1.PY - Busqueda y aproximacion a pilares: deteccion rapida
sin barrer, barrido completo, ultimo recurso hacia la zona mas despejada,
aproximacion con seguimiento visual, y el retroceso con seguimiento visual
que usa esquivar_pilar() (en funciones_comunes2.py).

Segunda parte del troceo de funciones_comunes.py (ver ese archivo para el
resto de piezas). Todas usan "import hardware" y acceden a pines/constantes
con hardware.X
"""
import time
import hardware
from funciones_comunes import pulso_barrido, _mejor_bloque, _obtener_bloques, leer_tfmini, _comprobar_lineas


def pilar_visible_ahora():
    """Comprueba si ya hay un pilar visible con la camara centrada, sin
    necesidad de barrer (optimizacion: si ya lo vemos, no hace falta escanear).
    Si ve mas de uno a la vez, se queda con el de mayor area (Caso 3).
    Devuelve (angulo=0, color_id), o (None, None) si no ve nada."""
    hardware.SERVOcam.duty_u16(pulso_barrido(0))
    time.sleep_ms(80)

    bloques = _obtener_bloques()
    if len(bloques) == 0:
        print("PILAR_VISIBLE_AHORA: nada a la vista")
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

        bloques = _obtener_bloques()

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
            confirmacion = _obtener_bloques()
            if len(confirmacion) > 0:
                confirmado = True
                break
            time.sleep_ms(30)

        if not confirmado:
            print(f"BUSCAR_PILAR: candidato en angulo={mejor_angulo} NO confirmado, se descarta")
            mejor_angulo = None
            mejor_id = None

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

        while hardware.uart0.any():
            hardware.uart0.read(hardware.uart0.any())
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

        bloques = hardware.husky.get_blocks()
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


def aproximarse_a_pilar(angulo_inicial):
    """Avanza hacia el pilar detectado, corrigiendo el rumbo de forma continua con
    la coordenada X de la Huskylens (reencuadrando la camara), hasta quedar a
    DISTANCIA_EVASION_CM del pilar segun el TFmini. La direccion del chasis es
    proporcional al angulo que le queda a la camara, con una ganancia alta
    (GANANCIA_KP_VISUAL_APROX) para que la transicion sea rapida sin llegar a
    ser un salto brusco de todo/nada - un punto intermedio entre el
    proporcional original (demasiado lento, no completaba el giro a tiempo
    con poco espacio) y el todo/nada (demasiado brusco, a veces no se quedaba
    bien centrado por el propio salto). De paso cuenta las lineas azules,
    igual que en el resto del programa.
    Devuelve el color (id) del pilar alcanzado, o None si lo pierde de vista antes."""
    angulo_camara = angulo_inicial
    hardware.SERVOcam.duty_u16(pulso_barrido(angulo_camara))
    time.sleep_ms(250)  # el salto desde el ultimo angulo del barrido puede ser grande
    print(f"APROXIMARSE_A_PILAR: iniciando desde angulo={angulo_inicial}")

    fallos_seguidos = 0
    MAX_FALLOS_SEGUIDOS = 5  # tolera lecturas vacias puntuales antes de dar el pilar por perdido

    while True:
        bloques = _obtener_bloques()

        if len(bloques) == 0:
            fallos_seguidos += 1
            print(f"APROXIMARSE_A_PILAR: sin bloque ({fallos_seguidos}/{MAX_FALLOS_SEGUIDOS})")
            if fallos_seguidos >= MAX_FALLOS_SEGUIDOS:
                hardware.servoTraccion.duty_u16(hardware.Para)
                print("APROXIMARSE_A_PILAR: PERDIDO, se devuelve None")
                return None
            time.sleep_ms(20)
            continue

        fallos_seguidos = 0
        objetivo = _mejor_bloque(bloques)  # Caso 3: si aparecen dos, seguimos el mas grande
        color_id = objetivo.id
        error_px = objetivo.x_center - hardware.FRAME_CENTRO_X

        # Reencuadra la camara sobre el pilar: deadband para ignorar errores
        # pequeños (ruido cerca del centro), limite de correccion por ciclo
        # (evita saltos bruscos) y suavizado (solo se aplica una fraccion de
        # la correccion cada ciclo, para que el movimiento no sea brusco).
        if abs(error_px) > hardware.DEADBAND_PX:
            correccion = error_px * hardware.PX_A_GRADOS_CAMARA
            correccion = max(-hardware.MAX_CORRECCION_CAMARA_DEG, min(correccion, hardware.MAX_CORRECCION_CAMARA_DEG))
            correccion *= hardware.FACTOR_SUAVIZADO_CAMARA
            angulo_camara += correccion
            angulo_camara = max(hardware.ANGULO_SERVO_MIN, min(angulo_camara, hardware.ANGULO_SERVO_MAX))
            hardware.SERVOcam.duty_u16(pulso_barrido(angulo_camara))

        # Dirige el chasis de forma PROPORCIONAL al angulo que le queda a la
        # camara, pero con una ganancia mayor que la original
        # (GANANCIA_KP_VISUAL) para que la transicion sea mas rapida sin
        # llegar a ser un salto brusco de todo/nada. El todo/nada (tope hasta
        # el umbral, recto de golpe) alineaba demasiado deprisa y a veces no
        # se quedaba bien centrado por el propio salto; el proporcional
        # original (ganancia 15) alineaba tan despacio que no le daba tiempo
        # a completarse si el siguiente pilar estaba muy cerca del anterior.
        pulso_dir = hardware.Recto - (angulo_camara * hardware.GANANCIA_KP_VISUAL_APROX)
        pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
        hardware.servoDireccion.duty_u16(pulso_dir)

        # Distancia real al pilar con el TFmini (mismo eje que la camara).
        # Se lee ANTES de decidir la velocidad, porque ahora la velocidad
        # tambien depende de la distancia, no solo del angulo.
        distancia = leer_tfmini()

        # Llegada: parar si esta alineado a 15cm, o si baja de
        # DISTANCIA_EMERGENCIA_APROX_CM aunque no lo este (dispara el
        # retroceso propio de esquivar_pilar al ser < 12cm).
        alineado = abs(angulo_camara) <= hardware.UMBRAL_ALINEACION_APROX
        if distancia is not None and (
                (distancia <= hardware.DISTANCIA_EVASION_CM and alineado)
                or distancia <= hardware.DISTANCIA_EMERGENCIA_APROX_CM):
            hardware.servoTraccion.duty_u16(hardware.Para)
            print(f"APROXIMARSE_A_PILAR: LLEGADA a {distancia}cm, id={color_id}, "
                  f"angulo={angulo_camara:.1f}, alineado={alineado}")
            return color_id

        # Mientras la camara siga muy desviada, el chasis todavia no esta
        # alineado con el pilar - avanzamos despacio para darle tiempo a girar
        # antes de que la distancia se cierre (el paralaje se dispara si nos
        # acercamos sin apuntar bien). Ademas, aunque ya este bien alineado,
        # frenamos por DISTANCIA en el tramo final: sin esto, se acercaba
        # siempre a Avanza_tope hasta el mismo instante de la parada, y la
        # inercia hacia que se pasara de largo del punto de parada real
        # (por eso el retroceso previo se disparaba practicamente siempre).
        cerca_de_parar = distancia is not None and distancia <= (hardware.DISTANCIA_EVASION_CM + hardware.MARGEN_FRENADO_APROX_CM)
        if cerca_de_parar:
            hardware.servoTraccion.duty_u16(hardware.Avanza_lento)
        elif abs(angulo_camara) <= hardware.UMBRAL_ALINEACION_APROX:
            hardware.servoTraccion.duty_u16(hardware.Avanza_tope)
        else:
            hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

        # Antes solo contaba la linea azul aqui; ahora usa la comprobacion
        # compartida, que ademas detecta la linea de esquina si se cruza
        # durante la aproximacion (antes se perdia por completo ese caso).
        _comprobar_lineas()

        # Testigo LED: color del pilar que se esta siguiendo AHORA MISMO.
        # Si el LED cambia de color a media aproximacion, es señal de que el
        # objetivo ha cambiado de bloque (por ejemplo si aparece un segundo
        # pilar mas grande en pantalla).
        if color_id == 1:
            hardware.ledR.value(1)
            hardware.ledV.value(0)
        else:
            hardware.ledV.value(1)
            hardware.ledR.value(0)

        time.sleep_ms(20)


def _retroceder_hasta_distancia(lado_contrario, objetivo_cm):
    """Retrocede hasta que el TFmini mide objetivo_cm o mas, o hasta el
    timeout de seguridad. Dirige las ruedas para mantener al pilar CENTRADO
    en la pantalla de la Huskylens durante todo el retroceso (mismo dato de
    seguimiento que ya se usaba solo para la camara), con el signo
    INVERTIDO respecto a aproximarse_a_pilar(): marcha atras, si el pilar
    esta a la derecha en pantalla, se gira a la IZQUIERDA para centrarlo (al
    reves que avanzando). Antes se giraba a un lado fijo (lado_contrario)
    durante todo el retroceso sin vigilar la orientacion en ningun momento -
    en pista se vio que, tras varios intentos seguidos, el chasis podia
    acabar girado casi 180 grados de mas. Al ser ahora un control en bucle
    cerrado (centrar la imagen), el giro se autolimita solo: nunca gira mas
    de lo que hace falta para centrar al pilar. lado_contrario se usa solo
    como direccion de arranque, antes de tener ningun dato visual.

    Vacia el bufer del TFmini antes de cada lectura, para que sea una medida
    fresca de verdad, no un dato atrasado del bufer.

    Si la Huskylens pierde el pilar de vista varias veces seguidas, se corta
    el retroceso de inmediato en vez de seguir fiandose de una lectura del
    TFmini que puede estar midiendo el pasillo abierto (o cualquier otra
    cosa) en vez del pilar - sin este corte, el robot puede retroceder
    decenas o cientos de cm de mas antes de que salte el timeout.

    Ademas, "objetivo alcanzado" exige CONFIRMACION_OBJETIVO_RETROCESO
    lecturas seguidas por encima del objetivo, no solo una: se vio en pista
    un caso donde la Huskylens seguia viendo el pilar sin problema pero el
    TFmini dio una unica lectura puntual erronea (dentro del rango razonable
    de leer_tfmini, asi que no se filtraba) que daba el retroceso por
    completado de golpe, muy lejos del objetivo real.
    Devuelve la ultima distancia medida (o None si nunca hubo lectura)."""
    hardware.servoDireccion.duty_u16(lado_contrario)  # arranque, antes de tener dato visual
    hardware.servoTraccion.duty_u16(hardware.Retrocede_lento)

    angulo_camara_retroceso = 0  # el pilar deberia estar mas o menos centrado al empezar
    ultima_distancia = None
    fallos_seguidos = 0
    objetivo_alcanzado_veces = 0
    t0 = time.ticks_ms()

    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_MAX_RETROCESO_ESQUIVE_MS:
        bloques = _obtener_bloques()
        if len(bloques) > 0:
            fallos_seguidos = 0
            objetivo = _mejor_bloque(bloques)
            error_px = objetivo.x_center - hardware.FRAME_CENTRO_X
            if abs(error_px) > hardware.DEADBAND_PX:
                correccion = error_px * hardware.PX_A_GRADOS_CAMARA
                correccion = max(-hardware.MAX_CORRECCION_CAMARA_DEG, min(correccion, hardware.MAX_CORRECCION_CAMARA_DEG))
                correccion *= hardware.FACTOR_SUAVIZADO_CAMARA
                angulo_camara_retroceso += correccion
                angulo_camara_retroceso = max(hardware.ANGULO_SERVO_MIN, min(angulo_camara_retroceso, hardware.ANGULO_SERVO_MAX))
                hardware.SERVOcam.duty_u16(pulso_barrido(angulo_camara_retroceso))

            # Direccion de las ruedas: mismo angulo que mueve la camara,
            # pero signo INVERTIDO respecto a aproximarse_a_pilar() (marcha
            # atras en vez de hacia delante).
            pulso_dir = hardware.Recto + (angulo_camara_retroceso * hardware.GANANCIA_KP_VISUAL_APROX)
            pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
            hardware.servoDireccion.duty_u16(pulso_dir)
        else:
            fallos_seguidos += 1
            if fallos_seguidos >= hardware.MAX_FALLOS_SEGUIDOS_RETROCESO:
                print(f"RETROCEDER: Huskylens perdio el pilar {fallos_seguidos} veces seguidas, se corta el retroceso")
                break

        while hardware.uart0.any():
            hardware.uart0.read(hardware.uart0.any())
        time.sleep_ms(5)
        distancia = leer_tfmini()

        if distancia is not None and distancia <= hardware.DISTANCIA_RETROCESO_LECTURA_MAXIMA_CM:
            ultima_distancia = distancia
            if distancia >= objetivo_cm:
                objetivo_alcanzado_veces += 1
                # Exige CONFIRMACION_OBJETIVO_RETROCESO lecturas seguidas por
                # encima del objetivo antes de darlo por bueno: una sola
                # lectura del TFmini fuera de lo normal (aunque pase el
                # filtro de rango razonable de leer_tfmini) puede dar por
                # completado el retroceso de golpe aunque el pilar siga
                # perfectamente a la vista y cerca de verdad.
                if objetivo_alcanzado_veces >= hardware.CONFIRMACION_OBJETIVO_RETROCESO:
                    break
            else:
                objetivo_alcanzado_veces = 0
        else:
            # Por encima de DISTANCIA_RETROCESO_LECTURA_MAXIMA_CM: en este
            # contexto (recien empezando a retroceder desde muy cerca de un
            # pilar) es practicamente imposible que sea una lectura real del
            # pilar - se descarta sin mas, no cuenta como confirmacion ni
            # rompe la que ya llevara acumulada por error.
            objetivo_alcanzado_veces = 0

        time.sleep_ms(20)

    hardware.servoTraccion.duty_u16(hardware.Para)
    return ultima_distancia