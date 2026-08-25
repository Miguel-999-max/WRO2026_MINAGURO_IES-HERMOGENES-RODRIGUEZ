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


def centrar_camara_en_bloque(angulo_partida):
    """Ajusta finamente el angulo de la camara hasta que el bloque quede centrado
    en la pantalla de la Huskylens (X cerca de FRAME_CENTRO_X). El TFmini tiene un
    haz muy estrecho: si el bloque no esta centrado, el laser puede estar midiendo
    lo que hay detras (la pared) en vez del bloque. Solo cuando esta centrado nos
    podemos fiar de la distancia que da el TFmini.
    Devuelve (angulo_final, color_id), o (None, None) si pierde el bloque de vista."""
    angulo = angulo_partida
    color_id = None

    # El servo puede seguir en la ultima posicion del barrido, lejos del angulo
    # del candidato. Sin este movimiento, la primera lectura sale siempre vacia.
    hardware.SERVOcam.duty_u16(pulso_barrido(angulo))
    time.sleep_ms(150)

    fallos_seguidos = 0
    MAX_FALLOS_CENTRADO = 3  # tolera lecturas vacias puntuales antes de rendirse

    for _ in range(hardware.MAX_INTENTOS_CENTRADO_BUSQUEDA):
        bloques = hardware.husky.get_blocks()
        if len(bloques) == 0:
            fallos_seguidos += 1
            if fallos_seguidos >= MAX_FALLOS_CENTRADO:
                return None, None
            time.sleep_ms(20)
            continue

        fallos_seguidos = 0
        objetivo = bloques[0]
        color_id = objetivo.id
        error_px = objetivo.x_center - hardware.FRAME_CENTRO_X

        if abs(error_px) <= hardware.TOLERANCIA_PX:
            return angulo, color_id

        angulo += error_px * hardware.PX_A_GRADOS_CAMARA
        angulo = max(hardware.ANGULO_BUSQUEDA_FIN, min(angulo, hardware.ANGULO_BUSQUEDA_INICIO))
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo))
        time.sleep_ms(60)

    # No llego a la tolerancia exacta en los intentos disponibles, pero devolvemos
    # el mejor esfuerzo (mas centrado que el angulo de partida del barrido).
    return angulo, color_id


def buscar_pilar():
    """FASE 1 (deteccion): barre el servo por ANGULO_BUSQUEDA_INICIO..FIN anotando
    en que angulos la Huskylens ve un bloque (normalmente 1 o 2 candidatos, ya
    que el mismo bloque suele aparecer en varios pasos consecutivos del barrido
    - esos se agrupan como un unico candidato).
    FASE 2 (medicion): para cada candidato, vuelve a su angulo, centra la camara
    sobre el (X entre 150 y 170) y SOLO ENTONCES lanza el TFmini - si no esta
    centrado, el laser mide lo que hay detras del bloque, no el bloque.
    FASE 3 (decision): de todos los candidatos medidos, se queda con el mas cercano.
    Devuelve (angulo, color_id) del pilar mas cercano, o (None, None) si no vio nada."""
    hardware.ledR.value(0)
    hardware.ledV.value(0)

    # --- FASE 1: barrido de deteccion (sin TFmini todavia) ---
    candidatos = []  # lista de (angulo, color_id), un elemento por bloque distinto

    angulo = hardware.ANGULO_BUSQUEDA_INICIO
    while angulo >= hardware.ANGULO_BUSQUEDA_FIN:
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo))
        time.sleep_ms(80)  # paso grande: el servo necesita mas asentamiento que en la aproximacion

        bloques = hardware.husky.get_blocks()

        if len(bloques) > 0:
            color_visto = bloques[0].id
            # Testigo LED: se enciende en cuanto la Huskylens identifica algo.
            if color_visto == 1:
                hardware.ledR.value(1)
                hardware.ledV.value(0)
            else:
                hardware.ledV.value(1)
                hardware.ledR.value(0)

            # Si el candidato anterior es del mismo color y esta a un paso de
            # distancia, es casi seguro el mismo bloque visto en el paso previo
            # del barrido - no lo contamos como uno nuevo.
            mismo_que_anterior = (
                len(candidatos) > 0
                and candidatos[-1][1] == color_visto
                and abs(candidatos[-1][0] - angulo) <= hardware.PASO_BUSQUEDA * 1.5
            )
            if not mismo_que_anterior:
                candidatos.append((angulo, color_visto))
                print(f"BUSCANDO [{angulo}]: nuevo candidato detectado, id={color_visto}")
        else:
            hardware.ledR.value(0)
            hardware.ledV.value(0)

        angulo -= hardware.PASO_BUSQUEDA

    if len(candidatos) == 0:
        return None, None

    # --- FASE 2: medir la distancia real de cada candidato (centrando primero) ---
    mejor_angulo = None
    mejor_distancia = None
    mejor_id = None

    for angulo_candidato, color_candidato in candidatos:
        angulo_centrado, color_centrado = centrar_camara_en_bloque(angulo_candidato)

        if angulo_centrado is None:
            print(f"MEDICION [{angulo_candidato}]: candidato perdido al intentar centrar, se descarta.")
            continue

        while hardware.uart0.any():
            hardware.uart0.read(hardware.uart0.any())
        time.sleep_ms(10)

        distancia = None
        t0 = time.ticks_ms()
        while distancia is None and time.ticks_diff(time.ticks_ms(), t0) < 50:
            distancia = leer_tfmini()

        print(f"MEDICION [{angulo_candidato}->{angulo_centrado:.1f}]: id={color_centrado} distancia={distancia}")

        if distancia is not None and distancia < hardware.DISTANCIA_MAX_BUSQUEDA_CM:
            if mejor_distancia is None or distancia < mejor_distancia:
                mejor_distancia = distancia
                mejor_angulo = angulo_centrado
                mejor_id = color_centrado

    # --- FASE 3: decision ---
    if mejor_angulo is not None:
        print(f"DECISION: pilar mas cercano -> angulo={mejor_angulo:.1f} id={mejor_id} distancia={mejor_distancia}cm")

    return mejor_angulo, mejor_id


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
            print(f"APROXIMACION: sin bloque en esta lectura ({fallos_seguidos}/{MAX_FALLOS_SEGUIDOS})")
            if fallos_seguidos >= MAX_FALLOS_SEGUIDOS:
                hardware.servoTraccion.duty_u16(hardware.Para)
                print("APROXIMACION: pilar perdido de vista.")
                return None
            time.sleep_ms(20)
            continue

        fallos_seguidos = 0
        objetivo = bloques[0]
        color_id = objetivo.id
        error_px = objetivo.x_center - hardware.FRAME_CENTRO_X

        # Reencuadra la camara sobre el pilar
        angulo_camara += error_px * hardware.PX_A_GRADOS_CAMARA
        angulo_camara = max(hardware.ANGULO_BUSQUEDA_FIN, min(angulo_camara, hardware.ANGULO_BUSQUEDA_INICIO))
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo_camara))

        # Dirige el chasis proporcionalmente al angulo que le queda a la camara
        pulso_dir = hardware.Recto - (angulo_camara * hardware.GANANCIA_KP_VISUAL)
        pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
        hardware.servoDireccion.duty_u16(pulso_dir)
        hardware.servoTraccion.duty_u16(hardware.Avanza_tope)

        # Distancia real al pilar con el TFmini (mismo eje que la camara)
        distancia = leer_tfmini()

        # Conteo de lineas azules mientras nos aproximamos (igual que en el resto del programa)
        if hardware.sensor_color is None:
            claro = 0
            color = 'BLANCO'
        else:
            r_c, g_c, b_c, claro = hardware.sensor_color.read_rgbc()
            color = clasificar_color(r_c, g_c, b_c)

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

        if distancia is not None and distancia <= hardware.DISTANCIA_EVASION_CM:
            hardware.servoTraccion.duty_u16(hardware.Para)
            print(f"APROXIMACION: pilar alcanzado a {distancia}cm (id={color_id})")
            return color_id

        time.sleep_ms(20)


def esquivar_pilar(color_id):
    """Maniobra de evasion segun el color del pilar (regla oficial WRO 2026):
    ROJO (id=1)  -> mantener el lado DERECHO del carril -> esquivar por la derecha.
    VERDE (id=2) -> mantener el lado IZQUIERDO del carril -> esquivar por la izquierda."""
    lado = "DERECHA" if color_id == 1 else "IZQUIERDA"
    print(f"EVASION: pilar id={color_id} -> esquivando por la {lado}")

    if color_id == 1:  # ROJO
        hardware.servoDireccion.duty_u16(hardware.Dcha)
    else:  # VERDE (o cualquier otro id, por seguridad)
        hardware.servoDireccion.duty_u16(hardware.Izda)

    hardware.servoTraccion.duty_u16(hardware.Avanza_tope)
    time.sleep_ms(hardware.TIEMPO_ESQUIVE_MS)

    hardware.servoDireccion.duty_u16(hardware.Recto)
    time.sleep_ms(hardware.TIEMPO_RECTO_TRAS_ESQUIVE_MS)

    hardware.servoTraccion.duty_u16(hardware.Para)