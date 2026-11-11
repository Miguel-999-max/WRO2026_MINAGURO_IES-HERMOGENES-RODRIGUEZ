"""
FUNCIONES_COMUNES.PY - Funciones auxiliares de bajo nivel usadas por varias
misiones: lectura de sensores de distancia, clasificacion de color, deteccion
de zona, utilidades de rumbo (magnetometro) y navegacion por rumbo absoluto,
y las utilidades compartidas de la Huskylens.

Este modulo se trocea en tres por tamano:
  funciones_comunes.py  (este archivo) - sensores y utilidades de bajo nivel
  funciones_comunes1.py - busqueda y aproximacion a pilares
  funciones_comunes2.py - maniobra de esquive (esquivar_pilar)

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
                        if distancia <= 350:  # sanity: el campo mide 300x300cm, por encima de esto es dato sospechoso
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
        if distancia_mm <= 3500:  # sanity: el campo mide 300x300cm, por encima de esto es dato sospechoso
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
            hardware.sobre_linea = True
            hardware.ledR.value(1)
            ahora = time.ticks_ms()
            if hardware.ultimo_conteo_linea_ms is None or \
                    time.ticks_diff(ahora, hardware.ultimo_conteo_linea_ms) >= hardware.COOLDOWN_LINEA_MS:
                hardware.contadorLineas += 1
                hardware.ultimo_conteo_linea_ms = ahora
                print(f"¡LINEA AZUL DETECTADA! -> Total lineas: {hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META}")
            else:
                print("LINEA AZUL ignorada (cooldown)")
    else:
        if color == 'BLANCO':
            hardware.sobre_linea = False
            hardware.ledR.value(0)


def navegar_calle_por_rumbo(lado_pared='izquierda'):
    """Modo crucero: mientras no haya ningun pilar a la vista, corrige el
    rumbo del chasis (magnetometro, control proporcional continuo) hacia el
    rumbo absoluto de la calle actual, con la camara haciendo un barrido
    oscilante ancho (sin dejar de avanzar) para detectar pilares.

    Velocidad en tres niveles segun el error de rumbo: alineado -> crucero;
    error moderado -> lento; error GRANDE (tipico justo tras cortar una
    esquina) -> tambien lento (antes mas reducido, ya no hace falta desde
    que se lastro el robot y dejo de sobrevirar).

    Correccion de DERIVA hacia la pared lateral (lado_pared: 'izquierda' en
    Mision 3, 'derecha' en Mision 4): usa el TOF400F fijo de ese lado, leido
    en cada vuelta del bucle - no el TFmini panoramico, que al estar
    ocupado buscando pilares solo revisitaba cada extremo tras un barrido
    completo, dejando demasiada distancia recorrida entre medidas. Si la
    lectura decrece respecto a la anterior y baja de DISTANCIA_MINIMA_PARED_CM,
    se acumula un pequeño sesgo (con tope) que se suma al rumbo objetivo.

    Camara SUSPENDIDA (fija al frente) durante los primeros
    ANGULO_MINIMO_TRAS_ESQUINA_PARA_BARRER grados del giro de 90 tras cruzar
    una esquina: mirando de lado en pleno giro, la Huskylens a veces confunde
    la propia linea naranja de la esquina con un pilar rojo.

    Prioridad absoluta: en cuanto aparece un pilar, se devuelve su
    (angulo, color_id) de inmediato para que se vaya a por el.
    Devuelve (None, None) si contadorLineas llega a la meta antes de
    encontrar ningun pilar (fin de mision)."""
    angulo_oscilacion = -hardware.ANGULO_MAX_BARRIDO_CRUCERO
    sentido = 1

    calle_previa = hardware.calle_actual
    sesgo_pared = 0.0
    ultima_dist_pared = None
    rumbo_al_cruzar = None

    while True:
        _comprobar_lineas()
        if hardware.calle_actual != calle_previa:
            calle_previa = hardware.calle_actual
            sesgo_pared = 0.0
            ultima_dist_pared = None
            rumbo_al_cruzar = hardware.mag.heading()

        # La meta se comprueba ANTES de la deteccion de pilar, no despues:
        # un pilar lejano puede llevar varias vueltas de bucle a la vista, y
        # la deteccion de pilar tenia prioridad absoluta - la comprobacion
        # de meta, si estaba al final, nunca llegaba a ejecutarse mientras
        # hubiera algo que seguir viendo.
        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            return None, None

        rumbo_objetivo = (hardware.rumbo_calle[hardware.calle_actual] + sesgo_pared) % 360
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

        # Camara suspendida (fija al frente) hasta pasar 45 de los 90 grados
        # del giro de esquina - evita que el barrido ancho mire de lado
        # justo hacia la propia linea naranja recien cruzada.
        if rumbo_al_cruzar is not None:
            if abs(diferencia_angular(rumbo_actual, rumbo_al_cruzar)) >= hardware.ANGULO_MINIMO_TRAS_ESQUINA_PARA_BARRER:
                rumbo_al_cruzar = None
            else:
                hardware.SERVOcam.duty_u16(pulso_barrido(0))
                bloques = hardware.husky.get_blocks()
                if len(bloques) > 0:
                    candidato = _mejor_bloque(bloques)
                    print(f"NAVEGAR_CALLE: pilar detectado en angulo=0 id={candidato.id}")
                    return 0, candidato.id
                time.sleep_ms(20)
                continue

        # Camara: barrido oscilante ancho (+-90, 180 grados totales, limite fisico)
        # buscando pilares sin dejar de avanzar
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo_oscilacion))
        bloques = hardware.husky.get_blocks()
        if len(bloques) > 0:
            candidato = _mejor_bloque(bloques)
            print(f"NAVEGAR_CALLE: pilar detectado en angulo={angulo_oscilacion} id={candidato.id}")
            return angulo_oscilacion, candidato.id

        if lado_pared == 'izquierda':
            distancia_pared_mm = hardware.tof_izquierdo.read_distance_mm() if hardware.tof_izquierdo is not None else None
        else:
            distancia_pared_mm = leer_tof_derecho_mm()
        distancia_pared = distancia_pared_mm / 10 if distancia_pared_mm is not None else None

        if distancia_pared is not None:
            if ultima_dist_pared is not None and distancia_pared < ultima_dist_pared \
                    and distancia_pared < hardware.DISTANCIA_MINIMA_PARED_CM:
                incremento = hardware.SESGO_PARED_INCREMENTO_DEG if lado_pared == 'izquierda' else -hardware.SESGO_PARED_INCREMENTO_DEG
                sesgo_pared = max(-hardware.SESGO_PARED_MAX_DEG, min(sesgo_pared + incremento, hardware.SESGO_PARED_MAX_DEG))
                print(f"NAVEGAR_CALLE: acercandose a pared {lado_pared.upper()} "
                      f"({distancia_pared:.1f}cm < {ultima_dist_pared:.1f}cm) -> sesgo={sesgo_pared:.1f}")
            ultima_dist_pared = distancia_pared

        print(f"NAVEGAR_CALLE: calle={hardware.calle_actual} rumbo_obj={rumbo_objetivo:.1f} "
              f"rumbo_act={rumbo_actual:.1f} error={error:.1f} angulo_cam={angulo_oscilacion} "
              f"dist_pared={distancia_pared} sesgo_pared={sesgo_pared:.1f}")

        angulo_oscilacion += sentido * hardware.PASO_BARRIDO
        if angulo_oscilacion >= hardware.ANGULO_MAX_BARRIDO_CRUCERO or angulo_oscilacion <= -hardware.ANGULO_MAX_BARRIDO_CRUCERO:
            sentido *= -1

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