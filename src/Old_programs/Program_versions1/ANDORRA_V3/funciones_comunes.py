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
    color domina) con el nivel total de luz (para distinguir una linea de
    color real del blanco, que tambien puede tener un canal ligeramente
    dominante). Devuelve 'AZUL', 'NARANJA' o 'BLANCO'.
    Validado en pista en Misiones 1 y 2."""
    total = r + g + b
    if total == 0:
        return 'BLANCO'

    pr = r / total
    pb = b / total

    if pb > pr and total < 400:
        return 'AZUL'
    if pr > pb and total < 400:
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
        return (resp[3] << 8) | resp[4]
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


def pulso_barrido(angulo_deg):
    """Convierte un angulo (positivo=derecha, negativo=izquierda) en pulso de SERVOcam."""
    return int(hardware.Cam_Centro - angulo_deg * hardware.GRADOS_A_PULSO)


def _mejor_bloque(bloques):
    """De una lista de bloques de la Huskylens, devuelve el de mayor area
    (ancho x alto) - el area es un proxy fiable de cercania real sin
    necesitar centrar ni medir con el TFmini."""
    return max(bloques, key=lambda b: b.width * b.height)


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
        return None, None

    candidato = _mejor_bloque(bloques)
    return 0, candidato.id


def buscar_pilar(angulo_inicio=None, angulo_fin=None):
    """Barre el rango indicado (por defecto ANGULO_BUSQUEDA_INICIO..FIN, 90
    grados centrados) buscando pilares con la Huskylens. Si en una misma
    lectura ve varios bloques a la vez (su propio campo de vision es ancho),
    se queda con el de mayor area (Caso 3) - sin necesitar centrar ni medir
    con el TFmini para elegir. El mismo bloque visto en varios pasos del
    barrido se resuelve solo, porque siempre gana el area mayor vista hasta
    el momento, sin necesidad de agrupar detecciones.
    Devuelve (angulo, color_id) del pilar mas cercano, o (None, None)."""
    if angulo_inicio is None:
        angulo_inicio = hardware.ANGULO_BUSQUEDA_INICIO
    if angulo_fin is None:
        angulo_fin = hardware.ANGULO_BUSQUEDA_FIN

    hardware.ledR.value(0)
    hardware.ledV.value(0)

    mejor_angulo = None
    mejor_area = -1
    mejor_id = None

    angulo = angulo_inicio
    while angulo >= angulo_fin:
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo))
        time.sleep_ms(80)  # paso grande: el servo necesita mas asentamiento que en la aproximacion

        bloques = _obtener_bloques()

        if len(bloques) > 0:
            candidato = _mejor_bloque(bloques)
            area = candidato.width * candidato.height

            if candidato.id == 1:
                hardware.ledR.value(1)
                hardware.ledV.value(0)
            else:
                hardware.ledV.value(1)
                hardware.ledR.value(0)

            if area > mejor_area:
                mejor_area = area
                mejor_angulo = angulo
                mejor_id = candidato.id
        else:
            hardware.ledR.value(0)
            hardware.ledV.value(0)

        angulo -= hardware.PASO_BUSQUEDA

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

    fallos_seguidos = 0
    MAX_FALLOS_SEGUIDOS = 5  # tolera lecturas vacias puntuales antes de dar el pilar por perdido

    while True:
        bloques = hardware.husky.get_blocks()

        if len(bloques) == 0:
            fallos_seguidos += 1
            if fallos_seguidos >= MAX_FALLOS_SEGUIDOS:
                hardware.servoTraccion.duty_u16(hardware.Para)
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

        # Mientras la camara siga muy desviada, el chasis todavia no esta
        # alineado con el pilar - avanzamos despacio para darle tiempo a girar
        # antes de que la distancia se cierre (el paralaje se dispara si nos
        # acercamos sin apuntar bien). Solo aceleramos a tope ya alineados.
        if abs(angulo_camara) <= hardware.UMBRAL_ALINEACION_APROX:
            hardware.servoTraccion.duty_u16(hardware.Avanza_tope)
        else:
            hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

        # Distancia real al pilar con el TFmini (mismo eje que la camara)
        distancia = leer_tfmini()

        # Conteo de lineas azules mientras nos aproximamos (igual que en el resto del programa)
        if hardware.sensor_color is None:
            color = 'BLANCO'
        else:
            r_c, g_c, b_c, claro = hardware.sensor_color.read_rgbc()
            color = clasificar_color(r_c, g_c, b_c)

        if not hardware.sobre_linea:
            if color == 'AZUL':
                hardware.contadorLineas += 1
                hardware.sobre_linea = True
                hardware.ledR.value(1)
        else:
            if color == 'BLANCO':
                hardware.sobre_linea = False
                hardware.ledR.value(0)

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
            return color_id

        time.sleep_ms(20)


def esquivar_pilar(color_id):
    """Maniobra de evasion segun el color del pilar (regla oficial WRO 2026):
    ROJO (id=1)  -> mantener el lado DERECHO del carril -> esquivar por la derecha.
    VERDE (id=2) -> mantener el lado IZQUIERDO del carril -> esquivar por la izquierda.

    PASO PREVIO: si al empezar la distancia real al pilar es menor que
    DISTANCIA_EVASION_CM, retrocede en linea recta hasta alcanzar
    DISTANCIA_OBJETIVO_ESQUIVE_CM antes de iniciar el giro - evita arrancar
    la maniobra desde una posicion ya demasiado cerca para poder evitarlo.

    FASE 1 (giro proporcional a la distancia real, con seguimiento visual):
    la camara sigue apuntando al pilar (igual que en aproximarse_a_pilar)
    para que el TFmini de una distancia real fiable en todo momento. En vez
    de un angulo y velocidad fijos, ambos se calculan de forma CONTINUA segun
    lo lejos que este la distancia actual de DISTANCIA_OBJETIVO_ESQUIVE_CM:
    cuanto mas cerca del pilar, giro mas cerrado y mas velocidad; cuanto mas
    lejos (ya a salvo), giro suave y velocidad de crucero. El robot NUNCA se
    para del todo. Termina cuando ocurre cualquiera de estas dos cosas (lo
    que pase antes): la Huskylens pierde el pilar de vista (la camara ha
    llegado al limite fisico del servo), o el sensor lateral contrario ya lo
    ve cerca.

    FASE 2 (confirmacion): camara al frente, sigue recto vigilando el lateral
    contrario hasta confirmar el patron cerca->lejos (pilar superado), con
    timeout de seguridad por si nunca se completa."""
    usar_izquierdo = (color_id == 1)  # ROJO esquivado por la derecha -> pilar queda a la izquierda
    lado_evasion = hardware.Dcha if color_id == 1 else hardware.Izda

    if color_id == 1:  # ROJO
        hardware.ledR.value(1)
        hardware.ledV.value(0)
    else:  # VERDE (o cualquier otro id, por seguridad)
        hardware.ledV.value(1)
        hardware.ledR.value(0)

    # === PASO PREVIO: retroceder si se empieza demasiado cerca ===
    distancia_inicial = leer_tfmini()
    if distancia_inicial is not None and distancia_inicial < hardware.DISTANCIA_EVASION_CM:
        hardware.servoDireccion.duty_u16(hardware.Recto)
        hardware.servoTraccion.duty_u16(hardware.Retrocede_tope)

        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_MAX_RETROCESO_ESQUIVE_MS:
            distancia = leer_tfmini()
            if distancia is not None and distancia >= hardware.DISTANCIA_OBJETIVO_ESQUIVE_CM:
                break
            time.sleep_ms(20)

    # === FASE 1: giro proporcional a la distancia real + seguimiento visual ===
    angulo_camara = 0  # el pilar deberia estar mas o menos centrado al empezar
    detectado_cerca = False
    distancia_frontal = hardware.DISTANCIA_OBJETIVO_ESQUIVE_CM  # valor de partida conservador
    t0 = time.ticks_ms()

    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_ESQUIVE_MS:
        # Sensor lateral contrario: si ya ve el pilar cerca, la evasion ha
        # llegado a su punto critico - pasamos a la Fase 2 de inmediato.
        dist_lateral_mm = (hardware.tof_izquierdo.read_distance_mm() if usar_izquierdo and hardware.tof_izquierdo is not None
                            else (None if usar_izquierdo else leer_tof_derecho_mm()))
        if dist_lateral_mm is not None and (dist_lateral_mm / 10) < hardware.DISTANCIA_LATERAL_CERCA_CM:
            detectado_cerca = True
            break

        bloques = _obtener_bloques()
        if len(bloques) == 0:
            # La Huskylens ha perdido el pilar (limite fisico del servo) - salimos.
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
            distancia_frontal = nueva_distancia

        # Control proporcional continuo: INTENSIDAD_GIRO_BASE = giro minimo
        # que se mantiene siempre (para poder rodear el pilar aunque ya
        # estemos a la distancia de seguridad); por encima de eso, cuanto mas
        # cerca del pilar, mas se intensifica el giro y la velocidad, hasta
        # el maximo si estamos pegados. Sin ningun escalon ni parada.
        cercania = (hardware.DISTANCIA_OBJETIVO_ESQUIVE_CM - distancia_frontal) / hardware.DISTANCIA_OBJETIVO_ESQUIVE_CM
        cercania = max(0, min(1, cercania))
        intensidad = hardware.INTENSIDAD_GIRO_BASE + (1 - hardware.INTENSIDAD_GIRO_BASE) * cercania

        pulso_dir = hardware.Recto + intensidad * (lado_evasion - hardware.Recto)
        hardware.servoDireccion.duty_u16(int(pulso_dir))

        velocidad = hardware.Avanza_lento + intensidad * (hardware.Avanza_tope - hardware.Avanza_lento)
        hardware.servoTraccion.duty_u16(int(velocidad))

        time.sleep_ms(20)

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
                    break  # confirmado: pilar superado

        time.sleep_ms(20)

    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.ledR.value(0)
    hardware.ledV.value(0)