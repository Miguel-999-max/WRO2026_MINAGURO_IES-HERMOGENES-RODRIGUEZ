from machine import Pin, UART, PWM, I2C
import time
from tcs34725 import TCS34725   # su libreria editada
from vl53l1x import VL53L1X     # driver del TOF400F #2 (modo I2C)
from huskylens import HuskyLens # driver de la Huskylens (modo I2C)

# ==========================================
# 1. CONFIGURACION DE PINES
# ==========================================
pinBoton = Pin(2, Pin.IN, Pin.PULL_DOWN)
ledV = Pin(10, Pin.OUT)
ledR = Pin(22, Pin.OUT)

# Comunicacion UART0 para el LiDAR TFmini-S (frontal)
uart0 = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

# Comunicacion UART1 para el TOF400F derecho (sigue en modo Modbus/Serie de fabrica)
uart1 = UART(1, baudrate=115200, tx=Pin(8), rx=Pin(9))

# Comunicacion I2C1 para el TOF400F #2 (reconfigurado a modo IIC) -> lateral IZQUIERDO
# y la Huskylens, que comparten el mismo bus fisico (direcciones distintas: 0x29 y 0x32).
i2c1 = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000, timeout=100000)
try:
    tof_izquierdo = VL53L1X(i2c1, address=0x29)
    print("TOF400F izquierdo (I2C) listo!")
except Exception as e:
    print("Error TOF400F izquierdo:", e)
    tof_izquierdo = None

husky = HuskyLens(i2c1)
husky_lista = False
for intento in range(5):
    if husky.knock():
        husky_lista = True
        break
    time.sleep_ms(300)  # la Huskylens puede tardar en terminar de arrancar

if husky_lista:
    print("Huskylens lista!")
else:
    print("Aviso: Huskylens no respondio al knock tras varios intentos (se seguira intentando usar)")

# Actuadores (PWM a 50Hz)
servoTraccion = PWM(Pin(13))    # Movido del pin 14 al 13 (14 ahora es SDA1)
servoDireccion = PWM(Pin(20))
SERVOcam = PWM(Pin(21))

servoTraccion.freq(50)
servoDireccion.freq(50)
SERVOcam.freq(50)

# ==========================================
# 2. CONSTANTES DE CALIBRACION REALES
# ==========================================
# Servo Direccion
Recto = 5000
Dcha = 3900
Izda = 6190

# Servo Camara / Lidar (Pin 21)
Cam_Centro = 4675
RADAR_FIJO_DERECHA = 1350
RADAR_FIJO_IZQUIERDA = 8000

# Servo Traccion (Rotacion continua)
Para = 5000
Avanza_tope = 3600
Retrocede_tope = 6250

# Parametros del algoritmo de seguimiento de pared
DISTANCIA_OBJETIVO = 15        # SetPoint a la pared (cm)
GANANCIA_KP = 85               # Sensibilidad de direccion (Reto Libre, pared unica)
GANANCIA_KP_VISUAL = 15        # AJUSTAR EN PISTA: sensibilidad de direccion durante la aproximacion visual
DISTANCIA_EVASION_CM = 12      # distancia al pilar a la que se inicia la maniobra de evasion
TIEMPO_ESQUIVE_MS = 600        # AJUSTAR EN PISTA: duracion del giro para rodear el pilar
TIEMPO_RECTO_TRAS_ESQUIVE_MS = 500  # AJUSTAR EN PISTA: avance recto tras el giro, para dejar el pilar atras

# Umbrales del sensor de color trasero
UMBRAL_BLANCO_A_COLOR = 500
PUNTO_CORTE_COLORES = 210

# Variables de carrera (cuenta solo AZULES: 4 por vuelta * 3 vueltas = 12)
TOTAL_LINEAS_META = 12
contadorLineas = 0
sobre_linea = False             # bandera para control de flanco

# --- Barrido frontal de deteccion de obstaculos (Misiones 3 y 4) ---
ANGULO_MAX_BARRIDO = 14         # grados a cada lado del centro (~15 aprox)
PASO_BARRIDO = 2                # grados por paso (aprox. ancho del haz del TFmini)
GRADOS_A_PULSO = (Cam_Centro - RADAR_FIJO_DERECHA) / 90   # pulsos de servo por grado
UMBRAL_OBSTACULO_CM = 60        # AJUSTAR EN PISTA: por debajo de esto, se marca posible obstaculo

# --- Busqueda y alineacion tras el desaparque (PASO 3.5, solo Mision 3 por ahora) ---
ANGULO_BUSQUEDA_INICIO = 45     # empieza mirando 45 grados a la derecha
ANGULO_BUSQUEDA_FIN = -45       # hasta mirar 45 grados a la izquierda (90 grados centrados en el frente)
PASO_BUSQUEDA = 10              # grados por paso (mas grueso que el barrido de crucero)
DISTANCIA_MAX_BUSQUEDA_CM = 80  # ignora objetos mas lejanos (probablemente pared, no pilar)
MS_POR_GRADO_GIRO = 15          # (ya no se usa: sustituido por alineacion visual con Huskylens)

# --- Alineacion visual con la Huskylens (bucle cerrado, sin IMU) ---
FRAME_ANCHO = 320                    # resolucion horizontal de la Huskylens (verificar en pista)
FRAME_CENTRO_X = FRAME_ANCHO // 2
TOLERANCIA_PX = 10                   # +-10px sobre el centro (rango 150-170 de 320)
PX_A_GRADOS_CAMARA = 0.15            # AJUSTAR EN PISTA: grados de camara por pixel de error
MAX_INTENTOS_CENTRADO_BUSQUEDA = 6   # intentos para centrar el bloque antes de fiarnos del TFmini

# --- Retardo de depuracion: pausa entre pasos para poder observar cada reaccion ---
RETARDO_DEBUG_MS = 4000  # ya no se usa en la Mision 3 (quitado); se conserva por si hace falta depurar de nuevo

# ==========================================
# 3. FUNCIONES AUXILIARES - SENSORES DE DISTANCIA
# ==========================================
def leer_tfmini():
    """Vacia el bufer de la UART0 buscando una lectura valida del LiDAR frontal (cm)."""
    if uart0.any():
        datos = uart0.read()
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
    while uart1.any():
        uart1.read(uart1.any())
    uart1.write(_CMD_LEER_DIST_DER)

    t0 = time.ticks_ms()
    while uart1.any() < 7:
        if time.ticks_diff(time.ticks_ms(), t0) > 30:
            return None
        time.sleep_ms(1)

    resp = uart1.read(7)
    if resp is None or len(resp) < 7:
        return None
    if resp[0] == 0x01 and resp[1] == 0x03 and resp[2] == 0x02:
        return (resp[3] << 8) | resp[4]
    return None


def pulso_barrido(angulo_deg):
    """Convierte un angulo (positivo=derecha, negativo=izquierda) en pulso de SERVOcam."""
    return int(Cam_Centro - angulo_deg * GRADOS_A_PULSO)


def centrar_camara_en_bloque(angulo_partida):
    """Ajusta finamente el angulo de la camara hasta que el bloque quede centrado
    en la pantalla de la Huskylens (X cerca de FRAME_CENTRO_X). El TFmini tiene un
    haz muy estrecho: si el bloque no esta centrado, el laser puede estar midiendo
    lo que hay detras (la pared) en vez del bloque. Solo cuando esta centrado nos
    podemos fiar de la distancia que da el TFmini.
    Devuelve (angulo_final, color_id), o (None, None) si pierde el bloque de vista."""
    angulo = angulo_partida
    color_id = None

    # Falta esto: el servo puede seguir en la ultima posicion del barrido (-90),
    # muy lejos del angulo del candidato. Sin este movimiento, la primera lectura
    # se hace mirando al sitio equivocado y siempre sale vacia.
    SERVOcam.duty_u16(pulso_barrido(angulo))
    time.sleep_ms(150)

    fallos_seguidos = 0
    MAX_FALLOS_CENTRADO = 3  # tolera lecturas vacias puntuales antes de rendirse

    for _ in range(MAX_INTENTOS_CENTRADO_BUSQUEDA):
        bloques = husky.get_blocks()
        if len(bloques) == 0:
            fallos_seguidos += 1
            if fallos_seguidos >= MAX_FALLOS_CENTRADO:
                return None, None
            time.sleep_ms(20)
            continue

        fallos_seguidos = 0
        objetivo = bloques[0]
        color_id = objetivo.id
        error_px = objetivo.x_center - FRAME_CENTRO_X

        if abs(error_px) <= TOLERANCIA_PX:
            return angulo, color_id

        angulo += error_px * PX_A_GRADOS_CAMARA
        angulo = max(ANGULO_BUSQUEDA_FIN, min(angulo, ANGULO_BUSQUEDA_INICIO))
        SERVOcam.duty_u16(pulso_barrido(angulo))
        time.sleep_ms(60)

    # No llego a la tolerancia exacta en los intentos disponibles, pero devolvemos
    # el mejor esfuerzo (mas centrado que el angulo de partida del barrido).
    return angulo, color_id


def buscar_pilar():
    """FASE 1 (deteccion): barre el servo de frente hacia la izquierda anotando
    en que angulos la Huskylens ve un bloque (normalmente 1 o 2 candidatos, ya
    que el mismo bloque suele aparecer en varios pasos consecutivos del barrido
    - esos se agrupan como un unico candidato).
    FASE 2 (medicion): para cada candidato, vuelve a su angulo, centra la camara
    sobre el (X entre 150 y 170) y SOLO ENTONCES lanza el TFmini - si no esta
    centrado, el laser mide lo que hay detras del bloque, no el bloque.
    FASE 3 (decision): de todos los candidatos medidos, se queda con el mas cercano.
    Devuelve (angulo, color_id) del pilar mas cercano, o (None, None) si no vio nada."""
    ledR.value(0)
    ledV.value(0)

    # --- FASE 1: barrido de deteccion (sin TFmini todavia) ---
    candidatos = []  # lista de (angulo, color_id), un elemento por bloque distinto

    angulo = ANGULO_BUSQUEDA_INICIO
    while angulo >= ANGULO_BUSQUEDA_FIN:
        SERVOcam.duty_u16(pulso_barrido(angulo))
        time.sleep_ms(80)  # paso grande: el servo necesita mas asentamiento que en la aproximacion

        bloques = husky.get_blocks()

        if len(bloques) > 0:
            color_visto = bloques[0].id
            # Testigo LED: se enciende en cuanto la Huskylens identifica algo.
            if color_visto == 1:
                ledR.value(1)
                ledV.value(0)
            else:
                ledV.value(1)
                ledR.value(0)

            # Si el candidato anterior es del mismo color y esta a un paso de
            # distancia, es casi seguro el mismo bloque visto en el paso previo
            # del barrido - no lo contamos como uno nuevo.
            mismo_que_anterior = (
                len(candidatos) > 0
                and candidatos[-1][1] == color_visto
                and abs(candidatos[-1][0] - angulo) <= PASO_BUSQUEDA * 1.5
            )
            if not mismo_que_anterior:
                candidatos.append((angulo, color_visto))
                print(f"BUSCANDO [{angulo}]: nuevo candidato detectado, id={color_visto}")
        else:
            ledR.value(0)
            ledV.value(0)

        angulo -= PASO_BUSQUEDA

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

        while uart0.any():
            uart0.read(uart0.any())
        time.sleep_ms(10)

        distancia = None
        t0 = time.ticks_ms()
        while distancia is None and time.ticks_diff(time.ticks_ms(), t0) < 50:
            distancia = leer_tfmini()

        print(f"MEDICION [{angulo_candidato}->{angulo_centrado:.1f}]: id={color_centrado} distancia={distancia}")

        if distancia is not None and distancia < DISTANCIA_MAX_BUSQUEDA_CM:
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
    global contadorLineas, sobre_linea

    angulo_camara = angulo_inicial
    SERVOcam.duty_u16(pulso_barrido(angulo_camara))
    time.sleep_ms(250)  # el salto desde el ultimo angulo del barrido puede ser grande

    fallos_seguidos = 0
    MAX_FALLOS_SEGUIDOS = 5  # tolera lecturas vacias puntuales antes de dar el pilar por perdido

    while True:
        bloques = husky.get_blocks()

        if len(bloques) == 0:
            fallos_seguidos += 1
            print(f"APROXIMACION: sin bloque en esta lectura ({fallos_seguidos}/{MAX_FALLOS_SEGUIDOS})")
            if fallos_seguidos >= MAX_FALLOS_SEGUIDOS:
                servoTraccion.duty_u16(Para)
                print("APROXIMACION: pilar perdido de vista.")
                return None
            time.sleep_ms(20)
            continue

        fallos_seguidos = 0
        objetivo = bloques[0]
        color_id = objetivo.id
        error_px = objetivo.x_center - FRAME_CENTRO_X

        # Reencuadra la camara sobre el pilar
        angulo_camara += error_px * PX_A_GRADOS_CAMARA
        angulo_camara = max(ANGULO_BUSQUEDA_FIN, min(angulo_camara, ANGULO_BUSQUEDA_INICIO))
        SERVOcam.duty_u16(pulso_barrido(angulo_camara))

        # Dirige el chasis proporcionalmente al angulo que le queda a la camara
        pulso_dir = Recto - (angulo_camara * GANANCIA_KP_VISUAL)
        pulso_dir = int(max(Dcha, min(pulso_dir, Izda)))
        servoDireccion.duty_u16(pulso_dir)
        servoTraccion.duty_u16(Avanza_tope)

        # Distancia real al pilar con el TFmini (mismo eje que la camara)
        distancia = leer_tfmini()

        # Conteo de lineas azules mientras nos aproximamos (igual que en el resto del programa)
        if sensor_color is None:
            claro = 0
        else:
            r, g, b, claro = sensor_color.read_rgbc()

        if not sobre_linea:
            if claro < PUNTO_CORTE_COLORES:
                contadorLineas += 1
                sobre_linea = True
                ledR.value(1)
                print(f"¡LINEA AZUL DETECTADA! -> Total lineas: {contadorLineas}/12")
        else:
            if claro >= UMBRAL_BLANCO_A_COLOR:
                sobre_linea = False
                ledR.value(0)

        if distancia is not None and distancia <= DISTANCIA_EVASION_CM:
            servoTraccion.duty_u16(Para)
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
        servoDireccion.duty_u16(Dcha)
    else:  # VERDE (o cualquier otro id, por seguridad)
        servoDireccion.duty_u16(Izda)

    servoTraccion.duty_u16(Avanza_tope)
    time.sleep_ms(TIEMPO_ESQUIVE_MS)

    servoDireccion.duty_u16(Recto)
    time.sleep_ms(TIEMPO_RECTO_TRAS_ESQUIVE_MS)

    servoTraccion.duty_u16(Para)


# ==========================================
# 4. FUNCIONES DE LAS MISIONES (DESAFIO ABIERTO)
# ==========================================
def ejecutar_mision_1_cw():
    """MISION 1: Giro a derechas siguiendo pared con filtro estricto de lineas AZULES."""
    global contadorLineas, sobre_linea
    print("--- EJECUTANDO MISION 1 CW (GIRO A DERECHAS) ---")

    SERVOcam.duty_u16(RADAR_FIJO_DERECHA)

    print("Movimiento Inicial 1: Avanzando a la derecha...")
    servoDireccion.duty_u16(4400)
    servoTraccion.duty_u16(4000)
    time.sleep_ms(2500)

    print("Movimiento Inicial 2: Avanzando a la izquierda...")
    servoDireccion.duty_u16(5600)
    servoTraccion.duty_u16(4000)
    time.sleep_ms(2400)

    print("Salida completada. Entrando en bucle de carrera...")
    distancia_actual = DISTANCIA_OBJETIVO

    while True:
        servoTraccion.duty_u16(Avanza_tope)

        nueva_distancia = leer_tfmini()
        if nueva_distancia is not None:
            distancia_actual = nueva_distancia

        error = distancia_actual - DISTANCIA_OBJETIVO
        pulso_dir = Recto - (error * GANANCIA_KP)
        pulso_dir = max(Dcha, min(pulso_dir, Izda))
        servoDireccion.duty_u16(pulso_dir)

        if sensor_color is None:
            r = g = b = claro = 0
        else:
            r, g, b, claro = sensor_color.read_rgbc()

        if not sobre_linea:
            if claro < PUNTO_CORTE_COLORES:
                contadorLineas += 1
                sobre_linea = True
                ledR.value(1)
                print(f"¡LINEA AZUL DETECTADA! -> Total lineas: {contadorLineas}/12")
        else:
            if claro >= UMBRAL_BLANCO_A_COLOR:
                sobre_linea = False
                ledR.value(0)

        if contadorLineas >= TOTAL_LINEAS_META:
            print("¡12 lineas azules completadas! Esperando para clavar la meta...")
            time.sleep_ms(1500)
            servoTraccion.duty_u16(Para)
            servoDireccion.duty_u16(Recto)
            print("--- CARRERA COMPLETADA CON EXITO ---")
            while True:
                ledR.value(1)
                ledV.value(1)
                time.sleep_ms(500)

        time.sleep_ms(20)


def ejecutar_mision_2_ccw():
    """MISION 2: Giro a izquierdas siguiendo pared con filtro estricto de lineas AZULES."""
    global contadorLineas, sobre_linea
    print("--- EJECUTANDO MISION 2 CCW (GIRO A IZQUIERDAS) ---")

    SERVOcam.duty_u16(RADAR_FIJO_IZQUIERDA)

    print("Movimiento Inicial 1: Avanzando a la izquierda...")
    servoDireccion.duty_u16(5600)
    servoTraccion.duty_u16(4000)
    time.sleep_ms(2500)

    print("Movimiento Inicial 2: Avanzando a la derecha...")
    servoDireccion.duty_u16(4400)
    servoTraccion.duty_u16(4000)
    time.sleep_ms(2400)

    print("Salida completada. Entrando en bucle de carrera izquierda...")
    distancia_actual = DISTANCIA_OBJETIVO

    while True:
        servoTraccion.duty_u16(Avanza_tope)

        nueva_distancia = leer_tfmini()
        if nueva_distancia is not None:
            distancia_actual = nueva_distancia

        error = distancia_actual - DISTANCIA_OBJETIVO
        pulso_dir = Recto + (error * GANANCIA_KP)
        pulso_dir = max(Dcha, min(pulso_dir, Izda))
        servoDireccion.duty_u16(pulso_dir)

        if sensor_color is None:
            r = g = b = claro = 0
        else:
            r, g, b, claro = sensor_color.read_rgbc()

        if not sobre_linea:
            if claro < PUNTO_CORTE_COLORES:
                contadorLineas += 1
                sobre_linea = True
                ledR.value(1)
                print(f"¡LINEA AZUL DETECTADA! -> Total lineas: {contadorLineas}/12")
        else:
            if claro >= UMBRAL_BLANCO_A_COLOR:
                sobre_linea = False
                ledR.value(0)

        if contadorLineas >= TOTAL_LINEAS_META:
            print("¡12 lineas azules completadas! Esperando para clavar la meta...")
            time.sleep_ms(1500)
            servoTraccion.duty_u16(Para)
            servoDireccion.duty_u16(Recto)
            print("--- CARRERA COMPLETADA CON EXITO ---")
            while True:
                ledR.value(1)
                ledV.value(1)
                time.sleep_ms(500)

        time.sleep_ms(20)


# ==========================================
# 5. FUNCIONES DE LAS MISIONES (DESAFIO OBSTACULOS)
# ==========================================
def ejecutar_mision_3_cw():
    """MISION 3 (CW): Desaparca y despues navega por deteccion de pilares (no por
    pared, que de momento no es fiable con el chasis desalineado tras aparcar):
    busca el pilar mas cercano, se aproxima hasta 12cm mantenendolo centrado con
    la Huskylens, lo esquiva por el lado que marca su color (regla oficial:
    ROJO=derecha, VERDE=izquierda) y vuelve a buscar el siguiente."""
    global contadorLineas, sobre_linea

    DISTANCIA_FRENO_ATRAS = 19  # cm, frenar la marcha atras al llegar a esta distancia

    SERVOcam.duty_u16(Cam_Centro)
    time.sleep_ms(300)

    # === PASO 1: MARCHA ATRAS CONTROLADA POR LIDAR FRONTAL ===
    print("PASO 1: Marcha atras controlada por LiDAR...")
    servoDireccion.duty_u16(Recto)
    servoTraccion.duty_u16(5500)
    time.sleep_ms(200)

    while uart0.any():
        uart0.read(uart0.any())
    time.sleep_ms(10)

    distancia_frontal = 0
    while distancia_frontal < DISTANCIA_FRENO_ATRAS:
        lectura = leer_tfmini()
        if lectura is not None:
            distancia_frontal = lectura
        time.sleep_ms(5)

    servoTraccion.duty_u16(Para)
    print(f"PASO 1: completado, distancia frontal final = {distancia_frontal}cm")

    # === PASO 2: GIRO DELANTERO HACIA EL INTERIOR (derecha) ===
    print("PASO 2: Giro delantero hacia el interior...")
    servoDireccion.duty_u16(Dcha)
    servoTraccion.duty_u16(4000)
    time.sleep_ms(1500)
    servoTraccion.duty_u16(Para)
    print("PASO 2: completado.")

    # === PASO 3: INCORPORACION AL PASILLO ===
    print("PASO 3: Enderezando en el pasillo...")
    servoDireccion.duty_u16(Recto)
    servoTraccion.duty_u16(Para)
    print("PASO 3: completado.")

    # === PASO 4: BUCLE BUSCAR -> APROXIMAR -> ESQUIVAR ===
    print("Entrando en bucle de obstaculos Mision 3 (CW)...")
    SERVOcam.duty_u16(Cam_Centro)

    while True:
        print("BUSCANDO: escaneando en busca de pilar...")
        angulo_encontrado, color_encontrado = buscar_pilar()
        print(f"BUSCANDO: resultado -> angulo={angulo_encontrado} color={color_encontrado}")

        if angulo_encontrado is None:
            print("BUSCANDO: no se encontro ningun pilar, se reintenta.")
            if contadorLineas >= TOTAL_LINEAS_META:
                break
            continue

        color_real = aproximarse_a_pilar(angulo_encontrado)

        if color_real is None:
            print("Pilar perdido durante la aproximacion, se vuelve a buscar.")
            continue

        esquivar_pilar(color_real)
        SERVOcam.duty_u16(Cam_Centro)
        print("EVASION: completada.")

        if contadorLineas >= TOTAL_LINEAS_META:
            break

    print("¡12 lineas azules completadas! Esperando para clavar la meta...")
    time.sleep_ms(1500)
    servoTraccion.duty_u16(Para)
    servoDireccion.duty_u16(Recto)
    print("--- MISION 3 COMPLETADA CON EXITO ---")
    while True:
        ledR.value(1)
        ledV.value(1)
        time.sleep_ms(500)


def ejecutar_mision_4_ccw():
    """MISION 4 (CCW): version simetrica de la Mision 3. Desaparca, sigue la pared
    IZQUIERDA con el TOF400F #2 (I2C) y barre el frente con el TFmini.
    Igual que en Mision 3, de momento solo detecta y señaliza, sin evasion todavia."""
    global contadorLineas, sobre_linea

    DISTANCIA_FRENO_ATRAS = 19

    SERVOcam.duty_u16(Cam_Centro)
    time.sleep_ms(300)

    # === PASO 1: MARCHA ATRAS CONTROLADA POR LIDAR FRONTAL ===
    servoDireccion.duty_u16(Recto)
    servoTraccion.duty_u16(5500)
    time.sleep_ms(200)

    while uart0.any():
        uart0.read(uart0.any())
    time.sleep_ms(10)

    distancia_frontal = 0
    while distancia_frontal < DISTANCIA_FRENO_ATRAS:
        lectura = leer_tfmini()
        if lectura is not None:
            distancia_frontal = lectura
        time.sleep_ms(5)

    servoTraccion.duty_u16(Para)
    time.sleep_ms(100)

    # === PASO 2: GIRO DELANTERO HACIA EL INTERIOR (izquierda) ===
    servoDireccion.duty_u16(Izda)
    servoTraccion.duty_u16(4000)
    time.sleep_ms(1500)

    # === PASO 3: INCORPORACION AL PASILLO ===
    print("Desaparca Paso 3: Enderezando en el pasillo...")
    servoDireccion.duty_u16(Recto)
    servoTraccion.duty_u16(Para)
    time.sleep_ms(300)

    # === PASO 4: BUCLE DE CARRERA (pared izquierda + barrido frontal) ===
    print("Entrando en bucle de carrera Mision 4 (CCW)...")
    distancia_pared_mm = DISTANCIA_OBJETIVO * 10
    angulo_barrido = -ANGULO_MAX_BARRIDO
    sentido_barrido = 1

    while True:
        servoTraccion.duty_u16(Avanza_tope)

        # --- Seguimiento de pared con el TOF400F izquierdo (I2C) ---
        if tof_izquierdo is not None:
            nueva_dist_mm = tof_izquierdo.read_distance_mm()
            if nueva_dist_mm is not None:
                distancia_pared_mm = nueva_dist_mm

        error = (distancia_pared_mm / 10) - DISTANCIA_OBJETIVO
        pulso_dir = Recto + (error * GANANCIA_KP)
        pulso_dir = int(max(Dcha, min(pulso_dir, Izda)))
        servoDireccion.duty_u16(pulso_dir)

        # --- Barrido frontal incremental (un paso por vuelta de bucle, no bloqueante) ---
        SERVOcam.duty_u16(pulso_barrido(angulo_barrido))
        dist_frontal = leer_tfmini()
        if dist_frontal is not None and dist_frontal < UMBRAL_OBSTACULO_CM:
            ledV.value(1)
        else:
            ledV.value(0)

        angulo_barrido += sentido_barrido * PASO_BARRIDO
        if angulo_barrido >= ANGULO_MAX_BARRIDO or angulo_barrido <= -ANGULO_MAX_BARRIDO:
            sentido_barrido *= -1

        # --- Conteo de lineas azules (igual que en Reto Libre) ---
        if sensor_color is None:
            claro = 0
        else:
            r, g, b, claro = sensor_color.read_rgbc()

        if not sobre_linea:
            if claro < PUNTO_CORTE_COLORES:
                contadorLineas += 1
                sobre_linea = True
                ledR.value(1)
                print(f"¡LINEA AZUL DETECTADA! -> Total lineas: {contadorLineas}/12")
        else:
            if claro >= UMBRAL_BLANCO_A_COLOR:
                sobre_linea = False
                ledR.value(0)

        if contadorLineas >= TOTAL_LINEAS_META:
            print("¡12 lineas azules completadas! Esperando para clavar la meta...")
            time.sleep_ms(1500)
            servoTraccion.duty_u16(Para)
            servoDireccion.duty_u16(Recto)
            print("--- MISION 4 COMPLETADA CON EXITO ---")
            while True:
                ledR.value(1)
                ledV.value(1)
                time.sleep_ms(500)

        time.sleep_ms(20)


# ==========================================
# 6. FASE DE INICIO (ESPERA DE BOTON)
# ==========================================
print("--- Robot Unificado Inicializado ---")
servoTraccion.duty_u16(Para)
servoDireccion.duty_u16(Recto)
SERVOcam.duty_u16(Cam_Centro)

# Inicializar bus I2C0 para el sensor de color
i2c0 = I2C(0, sda=Pin(4), scl=Pin(5))
try:
    sensor_color = TCS34725(i2c0)
    print("¡Sensor TCS34725 listo!")
except Exception as e:
    print("Error sensor color:", e)
    sensor_color = None

# Espera de boton parpadeando led
while pinBoton.value() == 0:
    ledR.value(1)
    ledV.value(0)
    time.sleep_ms(100)
    ledR.value(0)
    ledV.value(1)
    time.sleep_ms(100)

ledV.value(0)
ledR.value(0)
print("--- ¡ARRANQUE INTERNO! ---")

# ==========================================
# 7. SCAN 1 Y DECISION INICIAL
# ==========================================
distFR = 110
while True:
    lectura = leer_tfmini()
    if lectura is not None:
        distFR = lectura
        break
    time.sleep_ms(100)

if distFR > 40:
    # --- ZONA ABIERTA (DESAFIO RETO LIBRE) ---
    ledV.value(1)
    time.sleep_ms(2000)
    ledV.value(0)

    servoDireccion.duty_u16(Recto)
    servoTraccion.duty_u16(Retrocede_tope)

    linea_detectada = False
    luz_ambiente_final = 700

    while not linea_detectada and sensor_color is not None:
        r, g, b, claro = sensor_color.read_rgbc()
        if claro < UMBRAL_BLANCO_A_COLOR:
            time.sleep_ms(25)
            servoTraccion.duty_u16(Para)
            time.sleep_ms(10)
            r, g, b, claro = sensor_color.read_rgbc()
            luz_ambiente_final = claro
            linea_detectada = True
        time.sleep_ms(5)

    if luz_ambiente_final < PUNTO_CORTE_COLORES:
        ledV.value(1)
        time.sleep_ms(2000)
        ledV.value(0)
        ejecutar_mision_1_cw()
    else:
        ledR.value(1)
        time.sleep_ms(2000)
        ledR.value(0)
        ejecutar_mision_2_ccw()
else:
    # --- ZONA DE OBSTACULOS (APARCAMIENTO) ---
    ledR.value(1)
    time.sleep_ms(2000)
    ledR.value(0)

    # Lectura directa del TOF400F derecho (fijo, UART1/Modbus) - sin mover ningun servo
    dist_derecha = 100  # valor por defecto conservador si no hay lectura
    for _ in range(10):
        lectura_mm = leer_tof_derecho_mm()
        if lectura_mm is not None:
            dist_derecha = lectura_mm / 10
            break
        time.sleep_ms(20)

    if dist_derecha > 30:
        for _ in range(3):
            ledV.value(1)
            time.sleep_ms(150)
            ledV.value(0)
            time.sleep_ms(150)
        ejecutar_mision_3_cw()
    else:
        for _ in range(3):
            ledR.value(1)
            time.sleep_ms(150)
            ledR.value(0)
            time.sleep_ms(150)
        ejecutar_mision_4_ccw()