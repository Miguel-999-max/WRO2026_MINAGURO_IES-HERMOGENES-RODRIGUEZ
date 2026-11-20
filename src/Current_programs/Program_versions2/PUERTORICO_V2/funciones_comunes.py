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
    """Clasificamos una lectura del sensor de color combinando proporcion (que
    color domina, con un MARGEN minimo) con el nivel total de luz (para
    distinguir una linea de color real del blanco). Devolvemos 'AZUL',
    'NARANJA' o 'BLANCO'.

    Calibrado en la pista de Puerto Rico (sensor pegado al suelo con falda de
    goma-eva, integracion de 24 ms, ganancia 1x):
      Blanco:  total 764  r%=0.37  b%=0.26  (r%-b% = +0.12)
      Naranja: total 324  r%=0.60  b%=0.15  (r%-b% = +0.45)
      Azul:    total 110  r%=0.20  b%=0.46  (r%-b% = -0.27)
    El margen de 0.19 queda a medio camino entre el blanco (0.12) y el color
    mas flojo (0.26). El filtro de luz de 550 deja fuera el blanco (764),
    incluso con alguna mancha en el tapete, y admite las lecturas mezcladas
    de cuando el sensor cruza una linea a velocidad y la ve solo en parte."""
    total = r + g + b
    if total == 0:
        return 'BLANCO'

    pr = r / total
    pb = b / total
    MARGEN = 0.19  # AJUSTAR EN PISTA: entre el 0.12 del blanco y el 0.26 del color mas flojo

    if pb > pr + MARGEN and total < 550:
        return 'AZUL'
    if pr > pb + MARGEN and total < 550:
        return 'NARANJA'
    return 'BLANCO'


def leer_tfmini(max_cm=350):
    """Leemos el TFmini-S frontal (UART0, continuo a 100 Hz): sin esperar,
    la ultima trama recibida. Devolvemos la distancia en cm, o None si no
    tenemos una lectura fiable. Por defecto descartamos lo que pase de 350 cm;
    para detectar el hueco de la esquina pasamos un max_cm mayor."""
    return hardware.tfmini_frontal.leer(max_cm)


def leer_lateral_izquierdo_cm(max_cm=350):
    """Pedimos una medida al TFmini-S lateral izquierdo (UART1). cm o None.
    Por defecto descartamos lo que pase de 350 cm (el campo mide 300x300);
    para detectar el hueco de la esquina pasamos un max_cm mayor."""
    return hardware.tfmini_izquierdo.leer(max_cm)


def leer_lateral_derecho_cm(max_cm=350):
    """Pedimos una medida al TFmini-S lateral derecho (I2C1, a demanda). cm o None.
    Igual que el izquierdo: max_cm sube el techo de lectura valida."""
    return hardware.tfmini_derecho.leer(max_cm)


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

        # --- Metodo 2: laterales (izquierdo por UART1, derecho por I2C1) ---
        dist_der = None
        for _ in range(10):
            lectura = leer_lateral_derecho_cm()
            if lectura is not None:
                dist_der = lectura
                break
            time.sleep_ms(20)

        dist_izq = None
        for _ in range(10):
            lectura = leer_lateral_izquierdo_cm()
            if lectura is not None:
                dist_izq = lectura
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


def medir_rumbos_calles(giro_por_esquina_deg, rumbo_base=None):
    """Calcula, a partir de un rumbo de referencia, UNA SOLA VEZ, el rumbo
    absoluto de las 4 calles del circuito cuadrado. Esto NO es una
    calibracion del magnetometro (los offsets de hierro duro ya estan
    resueltos en lsm303_mag.py) - es solo la referencia de partida de esta
    carrera concreta.
    giro_por_esquina_deg: positivo para Mision 3 (CW, giros a la derecha),
    negativo para Mision 4 (CCW, giros a la izquierda).
    rumbo_base: si se pasa, se usa como rumbo de la calle 0 en vez de leer
    el magnetometro en este instante - para medir el rumbo justo al pulsar
    el boton (antes de cualquier movimiento) y calcular las 4 calles mas
    tarde, una vez se sabe si toca Mision 3 o Mision 4."""
    if rumbo_base is None:
        rumbo_base = hardware.mag.heading()
    hardware.rumbo_calle[0] = rumbo_base
    for i in range(1, 4):
        hardware.rumbo_calle[i] = (hardware.rumbo_calle[0] + giro_por_esquina_deg * i) % 360
    hardware.calle_actual = 0
    print(f"MEDIR_RUMBOS_CALLES: {[f'{r:.1f}' for r in hardware.rumbo_calle]}")


# --- DIAGNOSTICO TEMPORAL de la lectura de lineas (quitar cuando lo tengamos claro) ---
# Medimos cada cuanto llamamos a _comprobar_lineas(): si pasan mas de ~40 ms entre
# dos lecturas, a 22 cm/s el robot avanza casi 1 cm y puede saltarse una linea de 2 cm.
_diag_ultima_ms = None
_diag_muestras = 0
_diag_suma_ms = 0
_diag_maximo_ms = 0
_diag_color = 'BLANCO'


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

    # --- DIAGNOSTICO TEMPORAL ---
    global _diag_ultima_ms, _diag_muestras, _diag_suma_ms, _diag_maximo_ms, _diag_color
    ahora_diag = time.ticks_ms()
    hueco_ms = None
    if _diag_ultima_ms is not None:
        hueco_ms = time.ticks_diff(ahora_diag, _diag_ultima_ms)
        _diag_muestras += 1
        _diag_suma_ms += hueco_ms
        if hueco_ms > _diag_maximo_ms:
            _diag_maximo_ms = hueco_ms
        if _diag_muestras >= 50:
            print(f"LINEAS_DIAG: periodo medio {_diag_suma_ms / _diag_muestras:.0f} ms, maximo {_diag_maximo_ms} ms (50 lecturas)")
            _diag_muestras = 0
            _diag_suma_ms = 0
            _diag_maximo_ms = 0
    _diag_ultima_ms = ahora_diag
    if color != _diag_color:
        print(f"LINEAS_DIAG: color {color} (r={r} g={g} b={b} total={r + g + b}) tras {hueco_ms} ms desde la lectura anterior")
        _diag_color = color
    # --- fin del diagnostico ---

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
        color_conteo = getattr(hardware, 'color_conteo', 'AZUL')
        if color == color_conteo:
            hardware.sobre_linea = True
            hardware.ledR.value(1)
            ahora = time.ticks_ms()
            if hardware.ultimo_conteo_linea_ms is None or \
                    time.ticks_diff(ahora, hardware.ultimo_conteo_linea_ms) >= hardware.COOLDOWN_LINEA_MS:
                hardware.contadorLineas += 1
                hardware.ultimo_conteo_linea_ms = ahora
                print(f"¡LINEA {color_conteo} DETECTADA! -> Total lineas: {hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META}")
            else:
                print(f"LINEA {color_conteo} ignorada (cooldown)")
    else:
        if color == 'BLANCO':
            hardware.sobre_linea = False
            hardware.ledR.value(0)


def navegar_calle_por_rumbo(lado_pared='izquierda'):
    """Modo crucero: mientras no haya ningun pilar a la vista, corrige el
    rumbo del chasis (magnetometro, control proporcional continuo) hacia el
    rumbo absoluto de la calle actual, con la camara haciendo un barrido
    oscilante ancho (sin dejar de avanzar) para detectar pilares.

    El barrido arranca en el CENTRO y va primero hacia el lado hacia el que
    gira el robot (es por donde antes aparecen los pilares): en Mision 3 (CW,
    lado_pared='izquierda') hacia +60 grados (derecha); en Mision 4 (CCW,
    lado_pared='derecha') hacia -60 grados (izquierda). Al llegar al extremo,
    la camara vuelve de golpe al centro y barre hacia el extremo contrario, y
    otra vez al centro: centro -> extremo -> centro -> otro extremo -> centro.
    Asi miramos primero lo que tenemos delante, y si acabamos de barrer un
    lado sin ver nada pasamos cuanto antes al otro. Tras cada salto al centro
    ignoramos unos ciclos las detecciones, porque el servo aun esta en
    camino y el angulo que anotariamos no seria el real.

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

    Prioridad absoluta: en cuanto aparece un pilar, se devuelve su
    (angulo, color_id) de inmediato para que se vaya a por el.
    Devuelve (None, None) si contadorLineas llega a la meta antes de
    encontrar ningun pilar (fin de mision)."""
    # Punto de partida del barrido: el centro, y primero hacia el lado hacia
    # el que gira el robot
    angulo_oscilacion = 0
    sentido = 1 if lado_pared == 'izquierda' else -1
    ciclos_sin_detectar = 4  # el servo viene de donde estuviera

    calle_previa = hardware.calle_actual
    sesgo_pared = 0.0
    ultima_dist_pared = None

    while True:
        _comprobar_lineas()
        if hardware.calle_actual != calle_previa:
            calle_previa = hardware.calle_actual
            sesgo_pared = 0.0
            ultima_dist_pared = None

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

        # Camara: barrido oscilante ancho (+-60, 120 grados totales)
        # buscando pilares sin dejar de avanzar
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo_oscilacion))
        bloques = hardware.husky.get_blocks()
        if ciclos_sin_detectar > 0:
            ciclos_sin_detectar -= 1
            bloques = []
        if len(bloques) > 0:
            candidato = _mejor_bloque(bloques)
            print(f"NAVEGAR_CALLE: pilar detectado en angulo={angulo_oscilacion} id={candidato.id}")
            return angulo_oscilacion, candidato.id

        if lado_pared == 'izquierda':
            distancia_pared = leer_lateral_izquierdo_cm()
        else:
            distancia_pared = leer_lateral_derecho_cm()

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

        if ciclos_sin_detectar == 0:
            angulo_oscilacion += sentido * hardware.PASO_BARRIDO
            if abs(angulo_oscilacion) >= hardware.ANGULO_MAX_BARRIDO_CRUCERO:
                # Extremo alcanzado: volvemos de golpe al centro y barremos el otro lado
                angulo_oscilacion = 0
                sentido *= -1
                ciclos_sin_detectar = 4

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


def _bloque_seguido(bloques, x_previo):
    """Elegimos el bloque que seguimos en una aproximacion o un retroceso.
    Si ya seguiamos uno (x_previo), nos quedamos con el mas cercano en X a
    donde estaba, para no saltar de un pilar a otro cuando hay dos a la vista
    con una Y parecida. Si no hay x_previo, o el mas cercano esta a mas de
    160 px (el pilar seguido ha desaparecido y lo que vemos es otro), usamos
    _mejor_bloque, el mas cercano segun la Y."""
    if x_previo is None:
        return _mejor_bloque(bloques)
    candidato = min(bloques, key=lambda b: abs(b.x_center - x_previo))
    if abs(candidato.x_center - x_previo) > 160:
        return _mejor_bloque(bloques)
    return candidato


def _obtener_bloques():
    """Consulta la Huskylens con un reintento: el I2C puede fallar de forma
    puntual (ya lo hemos visto con otros sensores) incluso con el bloque
    delante, y sin este margen una sola lectura vacia por mala suerte hace
    creer que no hay nada cuando si lo hay."""
    bloques = hardware.husky.get_blocks()
    if len(bloques) > 0:
        return bloques
    _comprobar_lineas()  # no dejamos de vigilar las lineas mientras esperamos el reintento
    time.sleep_ms(15)
    return hardware.husky.get_blocks()