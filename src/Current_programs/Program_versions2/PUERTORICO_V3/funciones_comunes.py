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
    """Pedimos una medida al TFmini-S lateral derecho (UART por PIO en
    GPIO6/7, a demanda). cm o None. Igual que el izquierdo: max_cm sube el
    techo de lectura valida."""
    return hardware.tfmini_derecho.leer(max_cm)


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


# Cooldown del cambio de calle (como el del conteo, pero solo lo usa
# _comprobar_lineas): instante y sentido del ultimo cambio de calle.
_ultima_esquina_ms = None
_ultimo_signo_esquina = 0


def _comprobar_lineas():
    """Leemos el sensor de color UNA VEZ y actualizamos a la vez el conteo de
    lineas (vueltas, color en hardware.color_conteo) y el cambio de calle
    (linea de esquina de esta mision, en hardware.color_esquina). La
    llamamos desde CUALQUIER bucle en el que el robot se mueva
    (navegar_calle_por_rumbo, aproximarse_a_pilar, esquivar_pilar y su
    retroceso corto), para no perder ninguno de los dos eventos.

    Contamos CON SIGNO: marcha adelante (hardware.marcha_atras False) las
    lineas suman y marcha atras restan. Contamos al ENTRAR en la linea, con
    el signo de la marcha (asi el cambio de rumbo en la esquina es
    inmediato), y al SALIR comprobamos el sentido: si salimos en sentido
    contrario al de entrada, no la hemos cruzado (por ejemplo, entramos
    hacia delante, paramos encima y retrocedemos) y deshacemos la cuenta:
      entra adelante (+1), sale adelante -> +1 (la hemos cruzado)
      entra adelante (+1), sale atras    ->  0 (no la hemos cruzado)
      entra atras    (-1), sale atras    -> -1 (la hemos cruzado de vuelta)
      entra atras    (-1), sale adelante ->  0 (no la hemos cruzado)
    En las Misiones 3 y 4 las dos cosas usan la MISMA linea: la primera de
    cada esquina (naranja en CW, azul en CCW), la mas alejada de los pilares
    de la calle siguiente. Las dos llevan el mismo cooldown
    (COOLDOWN_LINEA_MS): tras contar, ignoramos nuevas entradas en el MISMO
    sentido durante ese tiempo, por si al esquivar un pilar cerca de la
    esquina el sensor vuelve a pisar la linea. En sentido contrario no lo
    aplicamos, para no estorbar al conteo marcha atras."""
    if hardware.sensor_color is None:
        return

    r, g, b, claro = hardware.sensor_color.read_rgbc()
    color = clasificar_color(r, g, b)

    signo = -1 if hardware.marcha_atras else 1

    global _ultima_esquina_ms, _ultimo_signo_esquina

    # --- Linea de esquina: cambio de calle ---
    if not hardware.sobre_linea_esquina:
        if color == hardware.color_esquina:
            hardware.sobre_linea_esquina = True
            ahora = time.ticks_ms()
            repetida = (_ultima_esquina_ms is not None
                        and signo == _ultimo_signo_esquina
                        and time.ticks_diff(ahora, _ultima_esquina_ms) < hardware.COOLDOWN_LINEA_MS)
            if repetida:
                hardware.signo_entrada_esquina = 0  # no contada: al salir no hay nada que deshacer
                print(f"ESQUINA ignorada (cooldown)")
            else:
                hardware.signo_entrada_esquina = signo
                _ultimo_signo_esquina = signo
                _ultima_esquina_ms = ahora
                hardware.calle_actual = (hardware.calle_actual + signo) % 4
                print(f"ESQUINA {'adelante' if signo > 0 else 'ATRAS'} (r={r} g={g} b={b}) -> calle {hardware.calle_actual}, "
                      f"rumbo {hardware.rumbo_calle[hardware.calle_actual]:.1f}")
    else:
        if color == 'BLANCO':
            hardware.sobre_linea_esquina = False
            if hardware.signo_entrada_esquina != 0 and signo != hardware.signo_entrada_esquina:
                # Salimos por el mismo lado por el que entramos: deshacemos el cambio
                # de calle y anulamos el cooldown, para contar bien la proxima entrada
                hardware.calle_actual = (hardware.calle_actual - hardware.signo_entrada_esquina) % 4
                _ultima_esquina_ms = None
                print(f"ESQUINA deshecha (salimos en sentido contrario) -> calle {hardware.calle_actual}, "
                      f"rumbo {hardware.rumbo_calle[hardware.calle_actual]:.1f}")
            hardware.signo_entrada_esquina = 0

    # --- Linea de conteo: vueltas ---
    color_conteo = getattr(hardware, 'color_conteo', 'AZUL')
    if not hardware.sobre_linea:
        if color == color_conteo:
            hardware.sobre_linea = True
            hardware.ledR.value(1)
            ahora = time.ticks_ms()
            repetida = (hardware.ultimo_conteo_linea_ms is not None
                        and signo == hardware.ultimo_signo_conteo
                        and time.ticks_diff(ahora, hardware.ultimo_conteo_linea_ms) < hardware.COOLDOWN_LINEA_MS)
            if repetida:
                hardware.signo_entrada_conteo = 0  # no contada: al salir no hay nada que deshacer
                print(f"LINEA {color_conteo} ignorada (cooldown)")
            else:
                hardware.contadorLineas += signo
                hardware.signo_entrada_conteo = signo
                hardware.ultimo_signo_conteo = signo
                hardware.ultimo_conteo_linea_ms = ahora
                print(f"¡LINEA {color_conteo} {'adelante' if signo > 0 else 'ATRAS'}! -> Total lineas: "
                      f"{hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META}")
    else:
        if color == 'BLANCO':
            hardware.sobre_linea = False
            hardware.ledR.value(0)
            if hardware.signo_entrada_conteo != 0 and signo != hardware.signo_entrada_conteo:
                # Salimos por el mismo lado por el que entramos: deshacemos la cuenta
                # y anulamos el cooldown, para contar bien la proxima entrada
                hardware.contadorLineas -= hardware.signo_entrada_conteo
                hardware.ultimo_conteo_linea_ms = None
                print(f"LINEA {color_conteo} deshecha (salimos en sentido contrario) -> Total lineas: "
                      f"{hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META}")
            hardware.signo_entrada_conteo = 0


def navegar_calle_por_rumbo(lado_pared='izquierda', tiempo_max_ms=None, primero_derecha=False):
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
    (y al empezar) esperamos 200 ms sin consultar la Huskylens: el servo aun
    esta en camino y la imagen tarda en reflejar el movimiento, asi que el
    angulo que anotariamos no seria el real.

    Para que el barrido sea rapido, cada vuelta del bucle hace lo minimo: el
    lateral lo leemos solo una de cada 4 vueltas (cada lectura a demanda
    cuesta 11-12 ms y para la deriva basta con una cada 100-150 ms), la
    pausa es de 5 ms y no imprimimos nada salvo los eventos (pilar detectado,
    acercamiento a la pared).

    Velocidad en tres niveles segun el error de rumbo: alineado -> crucero;
    error moderado -> lento; error GRANDE (tipico justo tras cortar una
    esquina) -> tambien lento (antes mas reducido, ya no hace falta desde
    que se lastro el robot y dejo de sobrevirar).

    Correccion de DERIVA hacia la pared lateral (lado_pared: 'izquierda' en
    Mision 3, 'derecha' en Mision 4): usa el TFmini lateral fijo de ese lado,
    leido una de cada 4 vueltas del bucle - no el TFmini frontal, que al estar
    ocupado buscando pilares solo revisitaba cada extremo tras un barrido
    completo, dejando demasiada distancia recorrida entre medidas. Si la
    lectura decrece respecto a la anterior y baja de DISTANCIA_MINIMA_PARED_CM,
    se acumula un pequeño sesgo (con tope) que se suma al rumbo objetivo.

    Prioridad absoluta: en cuanto aparece un pilar, se devuelve su
    (angulo, color_id) de inmediato para que se vaya a por el. Solo cuentan
    los pilares cercanos (ver _bloques_cercanos): los lejanos y los objetos
    de fuera del campo los ignoramos hasta que, al acercarnos, bajan en la
    imagen.
    Devuelve (None, None) si contadorLineas llega a la meta antes de
    encontrar ningun pilar (fin de mision).

    primero_derecha: si es True, el primer barrido va hacia la derecha (+60)
    sea cual sea la mision. Lo usa la Mision 4 tras esquivar un pilar verde
    justo al desaparcar: el robot queda mirando hacia el muro interior y la
    calle siguiente aparece a su derecha.

    tiempo_max_ms: lo usamos en el tramo final, despues de la ultima linea.
    Con el, no salimos por la meta (ya la hemos alcanzado) sino cuando han
    pasado tiempo_max_ms sin encontrar ningun pilar: entonces devolvemos
    (None, None)."""
    # Punto de partida del barrido: el centro, y primero hacia el lado hacia
    # el que gira el robot
    angulo_oscilacion = 0
    sentido = 1 if (lado_pared == 'izquierda' or primero_derecha) else -1
    # El servo viene de donde estuviera: esperamos 200 ms antes de fiarnos de la imagen
    t_mirar_desde = time.ticks_add(time.ticks_ms(), 200)
    vueltas = 0  # para leer el lateral solo una de cada 4 vueltas

    calle_previa = hardware.calle_actual
    sesgo_pared = 0.0
    ultima_dist_pared = None
    t_inicio_ms = time.ticks_ms()

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
        if tiempo_max_ms is None:
            if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
                return None, None
        elif time.ticks_diff(time.ticks_ms(), t_inicio_ms) >= tiempo_max_ms:
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
        esperando_servo = time.ticks_diff(time.ticks_ms(), t_mirar_desde) < 0
        if esperando_servo:
            bloques = []  # ni consultamos la Huskylens: la imagen aun no es la buena
        else:
            bloques = _bloques_cercanos(hardware.husky.get_blocks())
        if len(bloques) > 0:
            candidato = _mejor_bloque(bloques)
            print(f"NAVEGAR_CALLE: pilar detectado en angulo={angulo_oscilacion} id={candidato.id} "
                  f"base={candidato.y_center + candidato.height // 2}")
            return angulo_oscilacion, candidato.id

        vueltas += 1
        distancia_pared = None
        if vueltas % 4 == 0:
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

        if not esperando_servo:
            angulo_oscilacion += sentido * hardware.PASO_BARRIDO
            if abs(angulo_oscilacion) >= hardware.ANGULO_MAX_BARRIDO_CRUCERO:
                # Extremo alcanzado: volvemos de golpe al centro y barremos el otro lado
                angulo_oscilacion = 0
                sentido *= -1
                t_mirar_desde = time.ticks_add(time.ticks_ms(), 200)  # AJUSTAR EN PISTA: espera tras el salto al centro

        time.sleep_ms(5)


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


def _bloques_cercanos(bloques):
    """Nos quedamos solo con los bloques cuya BASE (borde inferior de la
    caja, y_center + height/2, donde el pilar toca el suelo) esta por debajo
    de una linea de la imagen (Y mayor, con el 0 arriba). Asi ignoramos los
    pilares lejanos (su base sale mas arriba en la imagen) y los objetos de
    color de fuera del campo que la camara ve por encima del muro (su base
    siempre queda por encima del muro). Como la camara solo gira en
    horizontal, la misma linea vale para todo el barrido.
    Solo la usamos para DETECTAR (navegar_calle_por_rumbo, pilar_visible_ahora,
    buscar_pilar, dirigirse_a_zona_despejada), no en aproximarse_a_pilar: una
    vez elegido, el pilar solo puede bajar en la imagen al acercarnos.
    El umbral lo medimos en pista con test_base_pilar.py."""
    return [b for b in bloques if b.y_center + b.height // 2 >= 100]  # AJUSTAR EN PISTA: base minima en px


def _bloque_seguido(bloques, x_previo, id_seguido=None):
    """Elegimos el bloque que seguimos en una aproximacion o una recolocacion,
    SIN CAMBIAR NUNCA DE PILAR:
      - Si sabemos el color que seguimos (id_seguido), solo miramos los
        bloques de ese color.
      - Si ya seguiamos uno (x_previo), nos quedamos con el mas cercano en X a
        donde estaba. Si ese salta mas de 160 px, no es el nuestro (el que
        seguiamos ha desaparecido y lo que vemos es otro pilar del mismo
        color): devolvemos None, como si no lo vieramos.
      - Si aun no seguiamos ninguno, el mas cercano segun la Y.
    Devolvemos el bloque, o None si en esta imagen no esta el nuestro. El
    llamador cuenta los None como lecturas fallidas: tras varias seguidas da
    el pilar por perdido y volvemos a escanear (que ya elige el mas cercano)."""
    if id_seguido is not None:
        bloques = [b for b in bloques if b.id == id_seguido]
    if len(bloques) == 0:
        return None
    if x_previo is None:
        return _mejor_bloque(bloques)
    candidato = min(bloques, key=lambda b: abs(b.x_center - x_previo))
    if abs(candidato.x_center - x_previo) > 160:
        return None
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