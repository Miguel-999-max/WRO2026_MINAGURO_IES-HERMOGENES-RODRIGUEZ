"""
HARDWARE.PY - Configuracion centralizada del robot.
Pines, actuadores, sensores, constantes de calibracion y estado compartido
entre misiones (contadorLineas, sobre_linea).

Todos los demas modulos (funciones_comunes.py, mision1_cw.py, etc.) importan
este archivo con "import hardware" y acceden a todo con el prefijo hardware.,
por ejemplo hardware.uart0, hardware.Recto, hardware.contadorLineas.

Esto es necesario porque las variables de estado (contadorLineas, sobre_linea)
se modifican desde varios modulos - "from hardware import contadorLineas"
NO funcionaria para eso, porque crearia una copia local en vez de modificar
el original. Con "import hardware" y "hardware.contadorLineas = ...", todos
los modulos comparten el mismo valor real.
"""
from machine import Pin, UART, PWM, I2C
import time
from tcs34725 import TCS34725
from tfmini import TFminiI2C, TFminiUART, TFminiUARTContinuo
from huskylens2 import HuskyLensV2, ALGORITHM_COLOR_RECOGNITION
from lsm303_mag import LSM303Mag

# ==========================================
# 1. CONFIGURACION DE PINES
# ==========================================
pinBoton = Pin(2, Pin.IN, Pin.PULL_DOWN)
ledV = Pin(10, Pin.OUT)
ledR = Pin(22, Pin.OUT)

# ==========================================
# 1b. ACTUADORES: lo primero que hacemos, antes de esperar a ningun sensor.
# Con la alimentacion nueva (un solo pulsador y un rele que enciende la
# primera fuente), la Pico arranca antes que la Huskylens 2: dejamos los
# servos parados y centrados desde el primer instante.
# ==========================================
# Servo Direccion
Recto = 5300
Dcha = 4200
Izda = 6490

def dir_desde_recto(desplazamiento):
    """Pulso de direccion como desplazamiento respecto a Recto (negativo =
    derecha, positivo = izquierda), limitado a los topes Dcha/Izda. Asi, si
    recalibramos Recto, las maniobras se mueven con el."""
    return max(Dcha, min(Recto + desplazamiento, Izda))


# Servo Camara / Lidar (Pin 21)
Cam_Centro = 4675
RADAR_FIJO_DERECHA = 1350
RADAR_FIJO_IZQUIERDA = 8000

# Servo Traccion (Rotacion continua)
Para = 4900
Avanza_tope = 3200
Avanza_tope_pilares = 3471    # AJUSTAR EN PISTA: avance rapido SOLO en misiones 3 y 4 (3200 / 1.19); misiones 1 y 2 siguen con Avanza_tope
Avanza_lento = 4312           # AJUSTAR EN PISTA: velocidad reducida mientras se alinea con el objetivo
Avanza_crucero = 3892         # AJUSTAR EN PISTA: velocidad durante navegar_calle_por_rumbo ya alineado - mas lenta que Avanza_tope para no adelantar al barrido ancho
Avanza_giro_cerrado = 4600     # AJUSTAR EN PISTA: navegar_calle_por_rumbo con error de rumbo grande o pared muy cerca - casi un giro sobre el sitio, nunca se para del todo
Retrocede_tope = 6250
Retrocede_lento = 5572         # AJUSTAR EN PISTA: velocidad reducida para el retroceso previo al esquive (no a tope, mas control)
TIEMPO_RETROCESO_INICIAL_MS = 2000  # AJUSTAR EN PISTA: retroceso inicial comun a las 4 misiones, antes de decidir cual toca


# Actuadores (PWM a 50Hz)
servoTraccion = PWM(Pin(13))    # Movido del pin 14 al 13 (14 ahora es SDA1)
servoDireccion = PWM(Pin(20))
SERVOcam = PWM(Pin(21))

servoTraccion.freq(50)
servoDireccion.freq(50)
SERVOcam.freq(50)

servoTraccion.duty_u16(Para)
servoDireccion.duty_u16(Recto)
SERVOcam.duty_u16(Cam_Centro)


# --- Foco delantero (GPIO17, PWM a traves del MOSFET) ---
# Solo se usa en Mision 3 y 4: main.py pone foco_habilitado = True al lanzarlas.
# Frecuencia de 20 kHz: muy por encima de lo que ve la camara (a 1 kHz podia
# producir bandas en la imagen que confundieran el color).
foco_pwm = PWM(Pin(17))
foco_pwm.freq(20000)
foco_pwm.duty_u16(0)
foco_habilitado = False
foco_nivel = 0.0


def foco_brillo(nivel):
    """Ponemos el foco al nivel indicado (0.0 apagado, 1.0 a tope). No hace
    nada mientras foco_habilitado sea False (Mision 1 y 2)."""
    global foco_nivel
    if not foco_habilitado:
        return
    nivel = max(0.0, min(1.0, nivel))
    foco_nivel = nivel
    foco_pwm.duty_u16(int(nivel * 65535))


def foco_apagar():
    """Apagamos el foco del todo."""
    foco_brillo(0.0)


def foco_hacia(nivel_objetivo, paso=0.05):
    """Acercamos el foco al nivel objetivo como mucho 'paso' por llamada, para
    que la intensidad suba o baje poco a poco y no a saltos."""
    nivel = foco_nivel
    if nivel_objetivo > nivel:
        nivel = min(nivel + paso, nivel_objetivo)
    else:
        nivel = max(nivel - paso, nivel_objetivo)
    foco_brillo(nivel)


# UART0: TFmini-S frontal (GPIO0/GPIO1), en CONTINUO a 100 Hz. Lo configuramos
# con config_tfmini_uart_continuo.py y lo leemos sin esperar, quedandonos con
# la ultima trama, como hacemos en Andorra.
# UART1: TFmini-S lateral izquierdo (GPIO8/GPIO9), a demanda. Lo configuramos
# con config_tfmini_uart_demanda.py (frame rate 0): solo mide cuando se lo
# pedimos.
uart0 = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
uart1 = UART(1, baudrate=115200, tx=Pin(8), rx=Pin(9))
tfmini_frontal = TFminiUARTContinuo(uart0)
tfmini_izquierdo = TFminiUART(uart1)

# I2C1: el TFmini-S lateral derecho (0x10, a demanda, configurado con
# config_tfmini_i2c_demanda.py) y la Huskylens 2 (0x50) comparten el mismo bus fisico.
# A demanda para no interferir con el frontal cuando mira a la derecha.
i2c1 = I2C(1, sda=Pin(14), scl=Pin(15), freq=100000, timeout=100000)
tfmini_derecho = TFminiI2C(i2c1, 0x10)

husky = HuskyLensV2(i2c1, address=0x50)
husky_lista = False

# Al encender con el pulsador, la Pico arranca al instante y la Huskylens 2
# (que cuelga de la primera fuente, conectada por el rele) tarda varios
# segundos en estar lista. Esperamos hasta 60 s reintentando el knock, con los
# dos LED parpadeando a la vez (distinto de la espera del boton, que los
# alterna). Un error de I2C mientras arranca no nos tumba el programa.
t_espera_ms = time.ticks_ms()
estado_led = 0
while time.ticks_diff(time.ticks_ms(), t_espera_ms) < 60000:
    try:
        husky.vaciar()  # por si quedaron tramas de una ejecucion anterior
        if husky.knock():
            husky_lista = True
            break
    except OSError:
        pass  # la Huskylens 2 aun no atiende el bus
    estado_led = 1 - estado_led
    ledV.value(estado_led)
    ledR.value(estado_led)
    time.sleep_ms(300)
ledV.value(0)
ledR.value(0)

if husky_lista:
    print("Huskylens 2 lista!")
    # Le pedimos el modo reconocimiento de color (pilares aprendidos: id 1 = rojo, id 2 = verde)
    try:
        if husky.switch_algorithm(ALGORITHM_COLOR_RECOGNITION):
            print("Huskylens 2 en modo reconocimiento de color")
        else:
            print("Huskylens 2 sin confirmacion del cambio de modo: es normal si ya estaba en reconocimiento de color (comprobamos en su pantalla que lo esta)")
    except OSError:
        print("Aviso: error de bus al pedir el modo de color a la Huskylens 2")
else:
    print("Aviso: Huskylens 2 no respondio al knock en 60 s (se seguira intentando usar)")

# Inicializar bus I2C0 para el sensor de color y el magnetometro
i2c0 = I2C(0, sda=Pin(4), scl=Pin(5))
try:
    sensor_color = TCS34725(i2c0)
    print("¡Sensor TCS34725 listo!")
except Exception as e:
    print("Error sensor color:", e)
    sensor_color = None

try:
    mag = LSM303Mag(i2c0)
    print("Magnetometro listo!")
except Exception as e:
    print("Error magnetometro:", e)
    mag = None

# ==========================================
# 2. CONSTANTES DE CALIBRACION REALES
# ==========================================
# Parametros del algoritmo de seguimiento de pared
DISTANCIA_OBJETIVO = 15        # SetPoint a la pared (cm)
GANANCIA_KP = 85               # Sensibilidad de direccion (Reto Libre, pared unica)
GANANCIA_KP_VISUAL = 15        # AJUSTAR EN PISTA: sensibilidad de direccion en dirigirse_a_zona_despejada
GANANCIA_KP_VISUAL_APROX = 30  # AJUSTAR EN PISTA: sensibilidad de direccion en aproximarse_a_pilar - mas alta que la de zona despejada, para alinear mas rapido que el proporcional original sin llegar al salto brusco de todo/nada
DISTANCIA_EVASION_CM = 15      # distancia al pilar a la que se inicia la maniobra de evasion (igualada al objetivo de esquive)
DISTANCIA_EMERGENCIA_APROX_CM = 8  # AJUSTAR EN PISTA: llegada sin alinear si baja de esto (< DISTANCIA_RETROCESO_TRIGGER_CM)
MARGEN_FRENADO_APROX_CM = 15   # AJUSTAR EN PISTA: empieza a frenar por distancia esta cantidad antes del punto de parada, para no pasarse por inercia
DISTANCIA_OBJETIVO_ESQUIVE_CM = 15  # AJUSTAR EN PISTA: distancia de seguridad a mantener durante el giro de evasion
DISTANCIA_RETROCESO_OBJETIVO_CM = 22  # AJUSTAR EN PISTA: a esta distancia retrocede si empieza demasiado cerca - mas colchon lateral antes de girar (debe quedar por debajo de DISTANCIA_RETROCESO_LECTURA_MAXIMA_CM)
DISTANCIA_MINIMA_SIGUIENTE_PILAR_CM = 30  # AJUSTAR EN PISTA: en el tramo entre fases, por debajo de esto se asume que es el mismo pilar recien esquivado, no uno nuevo
DISTANCIA_RETROCESO_TRIGGER_CM = 12   # AJUSTAR EN PISTA: por debajo de esto (no en DISTANCIA_EVASION_CM, que es la llegada normal) hace falta retroceder de verdad
MAX_INTENTOS_RETROCESO = 3      # cuantas veces se permite retroceder+reintentar el giro antes de rendirse
INTENSIDAD_GIRO_BASE = 0.5          # AJUSTAR EN PISTA: giro minimo incluso ya a salvo (VERDE), para poder rodear el pilar
INTENSIDAD_GIRO_BASE_ROJO = 0.65    # AJUSTAR EN PISTA: mas alto que el verde - el giro a la derecha (rojo) parece necesitar mas angulo real para la misma separacion lateral

# Correccion geometrica: el TFmini-S va montado en el centro del robot, no
# en el borde lateral como los TOF400F. Mirando de lado, esta 2,5cm mas
# metido hacia el centro que el borde del chasis, asi que sus lecturas
# laterales dan 2,5cm MAS de lo que hay realmente hasta el borde del robot.
OFFSET_TFMINI_LATERAL_CM = 2.5
TIEMPO_MAX_RETROCESO_ESQUIVE_MS = 800  # AJUSTAR EN PISTA: techo de seguridad para el retroceso previo si se empieza muy cerca (bajado de 2000: retrocedia hasta 50 cm cuando la lectura del TFmini no confirmaba el objetivo)
MAX_FALLOS_SEGUIDOS_RETROCESO = 5  # si la Huskylens pierde el pilar tantas veces seguidas durante el retroceso, se corta
CONFIRMACION_OBJETIVO_RETROCESO = 2  # AJUSTAR EN PISTA: lecturas seguidas por encima del objetivo antes de dar el retroceso por completado
DISTANCIA_RETROCESO_LECTURA_MAXIMA_CM = 25  # AJUSTAR EN PISTA: por encima de esto, la lectura no puede ser el pilar en este contexto - se descarta
DISTANCIA_EMERGENCIA_GIRO_CM = 7  # AJUSTAR EN PISTA: red de seguridad durante el giro de las Fases 1 y 2 - por debajo de esto, se corta el giro y se reintenta el retroceso
TIEMPO_ESQUIVE_MS = 1500       # AJUSTAR EN PISTA: techo de tiempo para completar el giro de ANGULO_GIRO_ESQUIVE grados (subido de 600 a 1500: el valor antiguo era del diseno anterior, con giro proporcional que se intensificaba solo al final)

# Clasificacion de color por PROPORCIONES RGB (no por "claro" absoluto), para
# que los baches del tapete no den falsos positivos - las proporciones se
# mantienen aunque el brillo baje por un bache, la magnitud absoluta no.
# Calibrado con lecturas reales:
#   Blanco:  r%=36 g%=38 b%=27  (ningun canal domina claramente)
#   Naranja: r%=59 g%=25 b%=16  (rojo domina)
#   Azul:    r%=19 g%=33 b%=48  (azul domina)

# Solo para detectar "hemos dejado el blanco" al buscar la linea de salida
# marcha atras (rapido y sensible). El COLOR (azul/naranja) se decide despues,
# ya parado, con clasificar_color() por proporciones - eso no cambia.
UMBRAL_BLANCO_A_COLOR = 500

# Variables de carrera (cuenta solo AZULES: 4 por vuelta * 3 vueltas = 12)
TOTAL_LINEAS_META = 12

# --- Deteccion de zona redundante (frontal + lateral), para evitar decisiones
# erroneas por una lectura puntual mala del TFmini frontal ---
DISTANCIA_ZONA_ABIERTA_CM = 40       # frontal > esto -> Libre (metodo original)
DIFERENCIA_LATERAL_LIBRE_CM = 20     # |derecha-izquierda| < esto -> Libre (metodo nuevo)

# --- Reto Libre: deteccion del hueco de la primera esquina, avanzando con
# los dos TOF400F laterales (sustituye al retroceso buscando linea de color) ---
DISTANCIA_HUECO_CM = 100             # por encima de esto en un lateral = hueco de la esquina real

contadorLineas = 0
sobre_linea = False             # bandera para control de flanco (linea AZUL, conteo de vueltas)
ultimo_conteo_linea_ms = None   # instante del ultimo conteo real, para el cooldown
COOLDOWN_LINEA_MS = 4000        # AJUSTAR EN PISTA: tras contar una linea azul, ignora nuevas cuentas durante este tiempo (bajado de 8000: con pilares entre esquinas, 8 s se quedaba largo y se ignoro una azul real)
sobre_linea_esquina = False     # bandera para control de flanco (linea de esquina que cambia de calle)

# --- Navegacion por rumbo absoluto de calle (magnetometro) ---
# Se mide UNA VEZ, antes de desaparcar (el robot esta perfectamente paralelo
# a la calle de salida en ese momento). NO es una calibracion del sensor
# (offsets de hierro duro, eso ya esta resuelto en lsm303_mag.py) - es solo
# la referencia de partida de esta carrera concreta, para poder calcular el
# rumbo absoluto de las otras 3 calles del circuito cuadrado.
GIRO_POR_ESQUINA_DEG = 90       # Mision 3 (CW): positivo. Mision 4 (CCW): negativo.
ANGULO_MINIMO_TRAS_ESQUINA_PARA_BARRER = 45  # AJUSTAR EN PISTA: grados girados tras la esquina antes de reanudar el barrido ancho
ANGULO_GIRO_ESQUIVE = 37        # AJUSTAR EN PISTA: grados que gira la Fase 1 de esquivar_pilar antes de que la Fase 2 los deshaga
TIEMPO_RECTO_ENTRE_FASES_MS = 600  # AJUSTAR EN PISTA: tramo recto entre la Fase 1 y la Fase 2 de esquivar_pilar
TIEMPO_RECTO_TRAS_FASE2_MS = 400   # AJUSTAR EN PISTA: tramo recto tras la Fase 2 de esquivar_pilar, antes de parar
GANANCIA_RUMBO = 15             # AJUSTAR EN PISTA: sensibilidad de direccion por rumbo
DEADBAND_RUMBO_DEG = 2          # AJUSTAR EN PISTA: por debajo de esto, no corrige (evita temblor)
UMBRAL_ALINEACION_RUMBO = 15    # AJUSTAR EN PISTA: grados; por debajo -> velocidad de crucero
UMBRAL_ERROR_GRANDE_RUMBO = 45  # AJUSTAR EN PISTA: grados; por encima -> giro casi sobre el sitio (Avanza_giro_cerrado)
ANGULO_MAX_BARRIDO_CRUCERO = 60  # AJUSTAR EN PISTA: barrido oscilante propio de navegar_calle_por_rumbo (120 grados totales, antes 180 - reducido para evitar el falso positivo de la linea naranja en los extremos)
DISTANCIA_MINIMA_PARED_CM = 30  # AJUSTAR EN PISTA: umbral de deriva - por debajo de esto Y decreciendo, se considera acercamiento real a esa pared
SESGO_PARED_INCREMENTO_DEG = 4  # AJUSTAR EN PISTA: grados que se suman al rumbo objetivo cada vez que se detecta acercamiento
SESGO_PARED_MAX_DEG = 20        # AJUSTAR EN PISTA: tope maximo del sesgo acumulado
PASO_BUSQUEDA_ESQUINA = 20      # grados por paso del escaneo obligatorio tras esquivar un pilar

rumbo_calle = [0, 0, 0, 0]
calle_actual = 0
color_esquina = 'NARANJA'  # que color de linea dispara el cambio de calle - lo fija cada mision al empezar

# --- Barrido frontal de deteccion de obstaculos (Misiones 3 y 4) ---
ANGULO_MAX_BARRIDO = 14         # grados a cada lado del centro (~15 aprox)
ANGULO_BUSQUEDA_TRANSICION = 30  # AJUSTAR EN PISTA: barrido estrecho en el tramo entre fases de esquivar_pilar (grados a cada lado)
PASO_BARRIDO = 2                # grados por paso (aprox. ancho del haz del TFmini)
GRADOS_A_PULSO = (Cam_Centro - RADAR_FIJO_DERECHA) / 90   # pulsos de servo por grado
UMBRAL_OBSTACULO_CM = 60        # AJUSTAR EN PISTA: por debajo de esto, se marca posible obstaculo

# --- Busqueda de pilares (Mision 3 por ahora) ---
ANGULO_BUSQUEDA_INICIO = 45     # empieza mirando 45 grados a la derecha
ANGULO_BUSQUEDA_FIN = -45       # hasta mirar 45 grados a la izquierda (90 grados centrados en el frente)
ANGULO_BUSQUEDA_180_INICIO = 90   # escaneo amplio (Caso 1, nivel 2): 180 grados centrados
ANGULO_BUSQUEDA_180_FIN = -90
PASO_BUSQUEDA = 10              # grados por paso (mas grueso que el barrido de crucero)

# Limite fisico real del servo de camara (coincide con RADAR_FIJO_DERECHA/IZQUIERDA)
ANGULO_SERVO_MIN = -90
ANGULO_SERVO_MAX = 90

# --- Caso 1, nivel 3: dirigirse a la zona mas despejada (TFmini puro) ---
TIEMPO_MANIOBRA_DESPEJADA_MS = 1500  # AJUSTAR EN PISTA: duracion de la maniobra
DISTANCIA_SEGURIDAD_CM = 20          # AJUSTAR EN PISTA: frena si algo se acerca mas que esto durante la maniobra

# --- Caso 2: confirmacion de evasion por el sensor lateral contrario ---
DISTANCIA_LATERAL_LEJOS_CM = 30      # por encima de esto: "sin pilar cerca" (antes y despues)
DISTANCIA_LATERAL_CERCA_CM = 10      # por debajo de esto: "a la altura del pilar"
TIMEOUT_CONFIRMACION_ESQUIVE_MS = 3000  # AJUSTAR EN PISTA: por si el patron nunca se completa

# --- Alineacion visual con la Huskylens (bucle cerrado, sin IMU) ---
FRAME_ANCHO = 640                    # resolucion horizontal de la Huskylens 2 (verificada: x_center llega a ~636)
FRAME_CENTRO_X = FRAME_ANCHO // 2
PX_A_GRADOS_CAMARA = 0.075           # AJUSTAR EN PISTA: grados de camara por pixel de error (mitad que con 320 px: mismo angulo de vision)
MAX_CORRECCION_CAMARA_DEG = 8        # limite de correccion de camara por ciclo, evita saltos bruscos
DEADBAND_PX = 16                     # AJUSTAR EN PISTA: si el error esta dentro de esto, no corrige (evita temblor cerca del centro)
FACTOR_SUAVIZADO_CAMARA = 0.25       # AJUSTAR EN PISTA: 0-1, que fraccion de la correccion se aplica cada ciclo (menor = mas suave)
UMBRAL_ALINEACION_APROX = 20         # grados: por debajo de esto, avanza a tope; si no, avanza despacio

# --- Retardo de depuracion: pausa entre pasos para poder observar cada reaccion ---
RETARDO_DEBUG_MS = 4000  # no se usa por defecto; se conserva por si hace falta depurar de nuevo