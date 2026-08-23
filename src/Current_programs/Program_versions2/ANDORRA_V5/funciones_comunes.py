"""
FUNCIONES_COMUNES.PY - Funciones auxiliares usadas por varias misiones:
lectura de sensores de distancia, calculo de angulos de la camara, busqueda
y seguimiento de pilares con la Huskylens.

Todas usan "import hardware" y acceden a pines/constantes con hardware.X
"""
import time
import hardware


def clasificar_color(r, g, b):
    """Clasifica una lectura del sensor de color combinando proporcion (que
    color domina, con un MARGEN minimo) con el nivel total de luz (para
    distinguir una linea de color real del blanco, que tambien puede tener
    un canal ligeramente dominante). Devuelve 'AZUL', 'NARANJA' o 'BLANCO'.

    El margen es necesario porque el blanco real NO tiene r%=b% exactos -
    por calibracion real, blanco tiene una diferencia r%-b% de ~9 puntos
    (36% vs 27%), naranja de ~43 puntos (59% vs 16%) y azul de ~29 puntos
    al reves (48% vs 19%). Sin margen, un blanco algo oscurecido (sombra del
    propio robot al maniobrar cerca de un pilar, por ejemplo) puede colarse
    como naranja con solo un punto de diferencia - se vio en pista con
    varios falsos positivos de esquina que en realidad eran blanco oscuro."""
    total = r + g + b
    if total == 0:
        return 'BLANCO'

    pr = r / total
    pb = b / total
    MARGEN = 0.15  # AJUSTAR EN PISTA: entre el 9pts del blanco y el 29-43pts de los colores reales

    if pb > pr + MARGEN and total < 400:
        return 'AZUL'
    if pr > pb + MARGEN and total < 400:
        return 'NARANJA'
    return 'BLANCO'


def leer_tfmini():
    """Vacia el bufer de la UART0 buscando una lectura valida del LiDAR frontal (cm)."""
    if hardware.uart0.any():
        datos = hardware.uart0.read()
        if datos is not None:
            i = len(datos) - 9
            while i >= 0:
                if datos[i] == 89 and datos[i + 1] == 89:  # 0x59 0x59
                    fuerza = datos[i + 4] + (datos[i + 5] << 8)
                    if fuerza >= 100:
                        distancia = datos[i + 2] + (datos[i + 3] << 8)
                        if distancia <= 500:  # sanity: por encima de esto, dato sospechoso
                            return distancia
                    break
                i -= 1
    return None


def _crc16_modbus(datos):
    """CRC-16/MODBUS estandar (polinomio 0xA001, inicial 0xFFFF)."""
    crc = 0xFFFF
    for b in datos:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


# Comando Modbus precalculado: leer registro 0x0010 (distancia) del esclavo 0x01
_CMD_LEER_DIST_DER = bytes([0x01, 0x03, 0x00, 0x10, 0x00, 0x01])
_CMD_LEER_DIST_DER += _crc16_modbus(_CMD_LEER_DIST_DER).to_bytes(2, 'little')


def leer_tof_derecho_mm():
    """Pide una lectura de distancia al TOF400F derecho (Modbus RTU por UART1). Devuelve mm o None."""
    while hardware.uart1.any():
        hardware.uart1.read(hardware.uart1.any())
    hardware.uart1.write(_CMD_LEER_DIST_DER)

    t0 = time.ticks_ms()
    while hardware.uart1.any() < 7:
        if time.ticks_diff(time.ticks_ms(), t0) > 30:
            return None
        time.sleep_ms(1)

    resp = hardware.uart1.read(7)
    if resp is None or len(resp) < 7:
        return None
    if resp[0] == 0x01 and resp[1] == 0x03 and resp[2] == 0x02:
        distancia_mm = (resp[3] << 8) | resp[4]
        if distancia_mm <= 5000:  # sanity: por encima de esto (5m), dato sospechoso
            return distancia_mm
    return None


def determinar_zona():
    """Determina si estamos en Reto Libre o Reto Obstaculos con dos metodos
    independientes, para no depender de una unica lectura mala del TFmini:
      Metodo 1 (frontal): TFmini > DISTANCIA_ZONA_ABIERTA_CM -> Libre
      Metodo 2 (lateral): |derecha - izquierda| < DIFERENCIA_LATERAL_LIBRE_CM -> Libre
    Reintenta de forma indefinida hasta que ambos coincidan (sin cable no hay
    forma de avisar ni de intervenir tras pulsar el boton, asi que no tiene
    sentido rendirse con un valor por defecto).
    Devuelve True si es Reto Libre, False si es Reto Obstaculos."""
    while True:
        # --- Metodo 1: frontal ---
        distFR = None
        for _ in range(10):
            lectura = leer_tfmini()
            if lectura is not None:
                distFR = lectura
                break
            time.sleep_ms(50)
        if distFR is None:
            distFR = 0  # sin lectura: conservador, asumimos que NO es zona abierta

        metodo1_libre = distFR > hardware.DISTANCIA_ZONA_ABIERTA_CM

        # --- Metodo 2: lateral (derecha por Modbus, izquierda por I2C) ---
        dist_der = None
        for _ in range(10):
            lectura_mm = leer_tof_derecho_mm()
            if lectura_mm is not None:
                dist_der = lectura_mm / 10
                break
            time.sleep_ms(20)

        dist_izq = None
        if hardware.tof_izquierdo is not None:
            for _ in range(10):
                lectura_mm = hardware.tof_izquierdo.read_distance_mm()
                if lectura_mm is not None:
                    dist_izq = lectura_mm / 10
                    break
                time.sleep_ms(20)

        if dist_der is not None and dist_izq is not None:
            metodo2_libre = abs(dist_der - dist_izq) < hardware.DIFERENCIA_LATERAL_LIBRE_CM
        else:
            metodo2_libre = None  # no se pudo medir algun lateral

        if metodo2_libre is not None and metodo1_libre == metodo2_libre:
            return metodo1_libre

        time.sleep_ms(200)


def diferencia_angular(a, b):
    """Diferencia angular con signo en el rango [-180, 180]: cuanto hay que
    sumarle a b para llegar a a, girando por el camino mas corto."""
    return (a - b + 180) % 360 - 180


def medir_rumbos_calles(giro_por_esquina_deg):
    """Mide el rumbo actual (el robot esta recien colocado en el aparcamiento,
    perfectamente paralelo a la calle de salida) y calcula a partir de ahi,
    UNA SOLA VEZ, el rumbo absoluto de las otras 3 calles del circuito
    cuadrado. Esto NO es una calibracion del magnetometro (los offsets de
    hierro duro ya estan resueltos en lsm303_mag.py) - es solo la referencia
    de partida de esta carrera concreta.
    giro_por_esquina_deg: positivo para Mision 3 (CW, giros a la derecha),
    negativo para Mision 4 (CCW, giros a la izquierda)."""
    hardware.rumbo_calle[0] = hardware.mag.heading()
    for i in range(1, 4):
        hardware.rumbo_calle[i] = (hardware.rumbo_calle[0] + giro_por_esquina_deg * i) % 360
    hardware.calle_actual = 0
    print(f"MEDIR_RUMBOS_CALLES: {[f'{r:.1f}' for r in hardware.rumbo_calle]}")


def _comprobar_lineas():
    """Lee el sensor de color UNA VEZ y actualiza a la vez el conteo de
    lineas azules (vueltas) y el cambio de calle (linea de esquina de esta
    mision, en hardware.color_esquina) - pensada para llamarse desde
    CUALQUIER bucle que este avanzando (navegar_calle_por_rumbo,
    aproximarse_a_pilar, esquivar_pilar), para no perder ninguno de los dos
    eventos solo porque el robot cruce la linea mientras esta ocupado
    esquivando o aproximandose a un pilar en vez de navegando la calle."""
    if hardware.sensor_color is None:
        return

    r, g, b, claro = hardware.sensor_color.read_rgbc()
    color = clasificar_color(r, g, b)

    if not hardware.sobre_linea_esquina:
        if color == hardware.color_esquina:
            hardware.sobre_linea_esquina = True
            hardware.calle_actual = (hardware.calle_actual + 1) % 4
            print(f"ESQUINA detectada (r={r} g={g} b={b}) -> calle {hardware.calle_actual}, "
                  f"rumbo {hardware.rumbo_calle[hardware.calle_actual]:.1f}")
    else:
        if color == 'BLANCO':
            hardware.sobre_linea_esquina = False

    if not hardware.sobre_linea:
        if color == 'AZUL':
            hardware.contadorLineas += 1
            hardware.sobre_linea = True
            hardware.ledR.value(1)
            print(f"¡LINEA AZUL DETECTADA! -> Total lineas: {hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META}")
    else:
        if color == 'BLANCO':
            hardware.sobre_linea = False
            hardware.ledR.value(0)


def navegar_calle_por_rumbo():
    """Modo crucero: mientras no haya ningun pilar a la vista, corrige el
    rumbo del chasis (magnetometro, control proporcional continuo) hacia el
    rumbo absoluto de la calle actual, con la camara haciendo un barrido
    oscilante ancho (sin dejar de avanzar) para detectar pilares. El propio
    TFmini-S del barrido vigila la pared: si en la direccion hacia la que
    esta mirando ahora mismo mide menos de DISTANCIA_MINIMA_PARED_CM, corrige
    alejandose de ese lado (el TOF400F lateral es demasiado lento para esto,
    asi que no se usa aqui). Prioridad absoluta: en cuanto aparece un pilar,
    se devuelve su (angulo, color_id) de inmediato para que se vaya a por el.
    Devuelve (None, None) si contadorLineas llega a la meta antes de
    encontrar ningun pilar (fin de mision)."""
    angulo_oscilacion = -hardware.ANGULO_MAX_BARRIDO_CRUCERO
    sentido = 1

    while True:
        rumbo_objetivo = hardware.rumbo_calle[hardware.calle_actual]
        rumbo_actual = hardware.mag.heading()
        error = diferencia_angular(rumbo_objetivo, rumbo_actual)

        if abs(error) > hardware.DEADBAND_RUMBO_DEG:
            pulso_dir = hardware.Recto - (error * hardware.GANANCIA_RUMBO)
            pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
            hardware.servoDireccion.duty_u16(pulso_dir)
        else:
            hardware.servoDireccion.duty_u16(hardware.Recto)

        if abs(error) <= hardware.UMBRAL_ALINEACION_RUMBO:
            hardware.servoTraccion.duty_u16(hardware.Avanza_crucero)
        else:
            hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

        # Camara: barrido oscilante ancho (+-90, 180 grados totales, limite fisico)
        # buscando pilares sin dejar de avanzar
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo_oscilacion))
        bloques = hardware.husky.get_blocks()
        if len(bloques) > 0:
            candidato = _mejor_bloque(bloques)
            print(f"NAVEGAR_CALLE: pilar detectado en angulo={angulo_oscilacion} id={candidato.id}")
            return angulo_oscilacion, candidato.id

        # Seguridad de pared con el TFmini-S: ya esta mirando hacia
        # angulo_oscilacion en este instante, asi que si mide muy cerca,
        # sabemos de que lado esta la pared y corregimos alejandonos -
        # sobrescribe la direccion de rumbo de este ciclo concreto.
        distancia_tf = leer_tfmini()
        correccion_pared = False
        if distancia_tf is not None and distancia_tf < hardware.DISTANCIA_MINIMA_PARED_CM:
            correccion_pared = True
            if angulo_oscilacion < 0:
                hardware.servoDireccion.duty_u16(hardware.Dcha)  # pared a la izquierda -> corrige a la derecha
            elif angulo_oscilacion > 0:
                hardware.servoDireccion.duty_u16(hardware.Izda)  # pared a la derecha -> corrige a la izquierda

        print(f"NAVEGAR_CALLE: calle={hardware.calle_actual} rumbo_obj={rumbo_objetivo:.1f} "
              f"rumbo_act={rumbo_actual:.1f} error={error:.1f} angulo_cam={angulo_oscilacion} "
              f"tf={distancia_tf} correccion_pared={correccion_pared}")

        angulo_oscilacion += sentido * hardware.PASO_BARRIDO
        if angulo_oscilacion >= hardware.ANGULO_MAX_BARRIDO_CRUCERO or angulo_oscilacion <= -hardware.ANGULO_MAX_BARRIDO_CRUCERO:
            sentido *= -1

        _comprobar_lineas()

        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            return None, None

        time.sleep_ms(20)


def pulso_barrido(angulo_deg):
    """Convierte un angulo (positivo=derecha, negativo=izquierda) en pulso de SERVOcam."""
    return int(hardware.Cam_Centro - angulo_deg * hardware.GRADOS_A_PULSO)


def _mejor_bloque(bloques):
    """De una lista de bloques de la Huskylens, devuelve el mas cercano segun
    la coordenada Y (el eje vertical tiene el 0 arriba): el objeto mas lejano
    se proyecta mas arriba en la pantalla (Y menor), el mas cercano mas abajo
    (Y mayor) - geometria de perspectiva basica. Mas fiable que el area, que
    depende de la silueta exacta detectada y resulto ser ruidosa."""
    return max(bloques, key=lambda b: b.y_center)


def _obtener_bloques():
    """Consulta la Huskylens con un reintento: el I2C puede fallar de forma
    puntual (ya lo hemos visto con otros sensores) incluso con el bloque
    delante, y sin este margen una sola lectura vacia por mala suerte hace
    creer que no hay nada cuando si lo hay."""
    bloques = hardware.husky.get_blocks()
    if len(bloques) > 0:
        return bloques
    time.sleep_ms(15)
    return hardware.husky.get_blocks()


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
    la coordenada X de la Huskylens (reencuadrando la camara y dirigiendo el chasis
    proporcionalmente al angulo que le queda a la camara), hasta quedar a
    DISTANCIA_EVASION_CM del pilar segun el TFmini. De paso cuenta las lineas
    azules, igual que en el resto del programa.
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

        # Dirige el chasis proporcionalmente al angulo que le queda a la camara
        pulso_dir = hardware.Recto - (angulo_camara * hardware.GANANCIA_KP_VISUAL)
        pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
        hardware.servoDireccion.duty_u16(pulso_dir)

        # Distancia real al pilar con el TFmini (mismo eje que la camara).
        # Se lee ANTES de decidir la velocidad, porque ahora la velocidad
        # tambien depende de la distancia, no solo del angulo.
        distancia = leer_tfmini()

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

        if distancia is not None and distancia <= hardware.DISTANCIA_EVASION_CM:
            hardware.servoTraccion.duty_u16(hardware.Para)
            print(f"APROXIMARSE_A_PILAR: LLEGADA a {distancia}cm, id={color_id}")
            return color_id

        time.sleep_ms(20)


def _retroceder_hasta_distancia(lado_contrario, objetivo_cm):
    """Retrocede en linea recta (con el volante hacia lado_contrario) hasta
    que el TFmini mide objetivo_cm o mas, o hasta el timeout de seguridad.
    Sigue al pilar con la camara (mismo seguimiento visual que el resto del
    programa) para que el TFmini mida siempre al pilar y no a otra cosa,
    aunque el chasis vaya girando durante el retroceso. Vacia el bufer del
    TFmini antes de cada lectura, para que sea una medida fresca de verdad,
    no un dato atrasado del bufer.
    Devuelve la ultima distancia medida (o None si nunca hubo lectura)."""
    hardware.servoDireccion.duty_u16(lado_contrario)
    hardware.servoTraccion.duty_u16(hardware.Retrocede_lento)

    angulo_camara_retroceso = 0  # el pilar deberia estar mas o menos centrado al empezar
    ultima_distancia = None
    t0 = time.ticks_ms()

    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_MAX_RETROCESO_ESQUIVE_MS:
        bloques = _obtener_bloques()
        if len(bloques) > 0:
            objetivo = _mejor_bloque(bloques)
            error_px = objetivo.x_center - hardware.FRAME_CENTRO_X
            if abs(error_px) > hardware.DEADBAND_PX:
                correccion = error_px * hardware.PX_A_GRADOS_CAMARA
                correccion = max(-hardware.MAX_CORRECCION_CAMARA_DEG, min(correccion, hardware.MAX_CORRECCION_CAMARA_DEG))
                correccion *= hardware.FACTOR_SUAVIZADO_CAMARA
                angulo_camara_retroceso += correccion
                angulo_camara_retroceso = max(hardware.ANGULO_SERVO_MIN, min(angulo_camara_retroceso, hardware.ANGULO_SERVO_MAX))
                hardware.SERVOcam.duty_u16(pulso_barrido(angulo_camara_retroceso))

        while hardware.uart0.any():
            hardware.uart0.read(hardware.uart0.any())
        time.sleep_ms(5)
        distancia = leer_tfmini()

        if distancia is not None:
            ultima_distancia = distancia
            if distancia >= objetivo_cm:
                break

        time.sleep_ms(20)

    hardware.servoTraccion.duty_u16(hardware.Para)
    return ultima_distancia


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

        if volver_a_retroceder:
            continue  # vuelve al principio del while True: reintenta el retroceso

        break  # Fase 1 termino con normalidad (lateral cerca o Husky perdida) o se agotaron los intentos

    # === FASE 2: camara al frente, confirmacion por el lateral contrario ===
    hardware.SERVOcam.duty_u16(pulso_barrido(0))
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    t0 = time.ticks_ms()

    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIMEOUT_CONFIRMACION_ESQUIVE_MS:
        if usar_izquierdo:
            dist_mm = hardware.tof_izquierdo.read_distance_mm() if hardware.tof_izquierdo is not None else None
        else:
            dist_mm = leer_tof_derecho_mm()

        if dist_mm is not None:
            dist_cm = dist_mm / 10

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