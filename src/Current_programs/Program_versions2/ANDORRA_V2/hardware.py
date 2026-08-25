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
from vl53l1x import VL53L1X
from huskylens import HuskyLens

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
for _intento in range(5):
    if husky.knock():
        husky_lista = True
        break
    time.sleep_ms(300)  # la Huskylens puede tardar en terminar de arrancar

if husky_lista:
    print("Huskylens lista!")
else:
    print("Aviso: Huskylens no respondio al knock tras varios intentos (se seguira intentando usar)")

# Inicializar bus I2C0 para el sensor de color
i2c0 = I2C(0, sda=Pin(4), scl=Pin(5))
try:
    sensor_color = TCS34725(i2c0)
    print("¡Sensor TCS34725 listo!")
except Exception as e:
    print("Error sensor color:", e)
    sensor_color = None

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
Para = 4900
Avanza_tope = 3200
Retrocede_tope = 6250

# Parametros del algoritmo de seguimiento de pared
DISTANCIA_OBJETIVO = 15        # SetPoint a la pared (cm)
GANANCIA_KP = 85               # Sensibilidad de direccion (Reto Libre, pared unica)
GANANCIA_KP_VISUAL = 15        # AJUSTAR EN PISTA: sensibilidad de direccion durante la aproximacion visual
DISTANCIA_EVASION_CM = 12      # distancia al pilar a la que se inicia la maniobra de evasion
TIEMPO_ESQUIVE_MS = 600        # AJUSTAR EN PISTA: duracion del giro para rodear el pilar
TIEMPO_RECTO_TRAS_ESQUIVE_MS = 500  # AJUSTAR EN PISTA: avance recto tras el giro, para dejar el pilar atras

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

contadorLineas = 0
sobre_linea = False             # bandera para control de flanco

# --- Barrido frontal de deteccion de obstaculos (Misiones 3 y 4) ---
ANGULO_MAX_BARRIDO = 14         # grados a cada lado del centro (~15 aprox)
PASO_BARRIDO = 2                # grados por paso (aprox. ancho del haz del TFmini)
GRADOS_A_PULSO = (Cam_Centro - RADAR_FIJO_DERECHA) / 90   # pulsos de servo por grado
UMBRAL_OBSTACULO_CM = 60        # AJUSTAR EN PISTA: por debajo de esto, se marca posible obstaculo

# --- Busqueda de pilares (Mision 3 por ahora) ---
ANGULO_BUSQUEDA_INICIO = 45     # empieza mirando 45 grados a la derecha
ANGULO_BUSQUEDA_FIN = -45       # hasta mirar 45 grados a la izquierda (90 grados centrados en el frente)
PASO_BUSQUEDA = 10              # grados por paso (mas grueso que el barrido de crucero)
DISTANCIA_MAX_BUSQUEDA_CM = 80  # ignora objetos mas lejanos (probablemente pared, no pilar)

# --- Alineacion visual con la Huskylens (bucle cerrado, sin IMU) ---
FRAME_ANCHO = 320                    # resolucion horizontal de la Huskylens (verificar en pista)
FRAME_CENTRO_X = FRAME_ANCHO // 2
TOLERANCIA_PX = 10                   # +-10px sobre el centro (rango 150-170 de 320)
PX_A_GRADOS_CAMARA = 0.15            # AJUSTAR EN PISTA: grados de camara por pixel de error
MAX_INTENTOS_CENTRADO_BUSQUEDA = 6   # intentos para centrar el bloque antes de fiarnos del TFmini

# --- Retardo de depuracion: pausa entre pasos para poder observar cada reaccion ---
RETARDO_DEBUG_MS = 4000  # no se usa por defecto; se conserva por si hace falta depurar de nuevo