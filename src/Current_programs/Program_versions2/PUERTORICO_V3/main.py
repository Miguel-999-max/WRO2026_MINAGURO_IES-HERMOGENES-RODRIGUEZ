#Descomponemos el programa en varios archivos para que sea más legible y mantenible.
#Retocamos la lectura de las líneas de suelo. Ahora va por color.
#Reforzamos la lectura de los sensores de distancia. Ahora se leen varias veces y se descartan lecturas erráticas.
#Cambiamos la forma de detectar misión 1 - misión 2. Ahora se hace por distancias laterales en lugar de por color de línea.
#Introducimos el magnetómetro 10 DOF
#Troceamos funciones_comunes.py en 3 archivos para manejarlos mejor
#Hemos podido completar la primera vuelta de la zona de obstáculos.Ahora vamos a hacer que el robot no confunda el parking con un bloque rojo.
#Decidimos cambiar estrategia. Eliminamos paredes aparcamiento.Implementamos misión 4.
#Cambiamos la forma de salir del parking y de discriminar entre misiones. REtocamos algoritmos de buscar pilares.
#Quitamos la parada+barrido de 180 tras esquivar (venia de cuando no habia magnetometro). Ahora tras esquivar, se va directo a navegar_calle_por_rumbo(). Objetivo: ganar tiempo por vuelta. Cambiamos la forma de discriminar entre misiones 3 y 4: ahora se hace por color de línea (naranja=misión3, azul=misión4) en lugar de por hueco a derecha/izquierda. Esto permite que el robot pueda hacer misiones 3 y 4 aunque no haya hueco a derecha/izquierda.
#PUERTO RICO
#Cambiamos 2xTOF400F por 2xTFmini-S.Sustituimos Huskylens por Huskylens 2. Aumentamos la relación de transmisión t, por tanto, la velocidad. Cambiamos el regulador 7805 por un conversor DC-DC step-down.
#Cambiamos de estrategia: en reto obstáculos salimos del aparcamiento. Si no se va a retirar el aparcamiento, nos aprovechamos de él.
#La husky daba problemas en el I2C. Le ponemos una R=5k1ohms pull-up en cada línea y comnectamos el TFminiS derecho a un puerto UART PIO (6,7).





"""MAIN.PY - Punto de entrada. Esperamos el boton y, sin movernos, medimos el
frente: menos de 30 cm es Reto Obstaculos (estamos en el aparcamiento); si
no, Reto Libre. En obstaculos comparamos derecha e izquierda con los dos
TFmini laterales: mas espacio a la derecha es Mision 3 y mas a la izquierda,
Mision 4; desaparcamos y lanzamos la mision. En Reto Libre avanzamos hasta ver la esquina (hueco
lateral) y lanzamos Mision 1 o 2, que hacen su propia incorporacion."""
import time
import hardware
from funciones_comunes import leer_lateral_izquierdo_cm, leer_lateral_derecho_cm, leer_tfmini, medir_rumbos_calles
from mision1_cw import ejecutar_mision_1_cw
from mision2_ccw import ejecutar_mision_2_ccw
from mision3_cw import ejecutar_mision_3_cw
from mision4_ccw import ejecutar_mision_4_ccw

# ==========================================
# FASE DE INICIO (ESPERA DE BOTON)
# ==========================================
print("--- Robot Unificado Inicializado ---")
hardware.servoTraccion.duty_u16(hardware.Para)
hardware.servoDireccion.duty_u16(hardware.Recto)
hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

while hardware.pinBoton.value() == 0:
    hardware.ledR.value(1)
    hardware.ledV.value(0)
    time.sleep_ms(100)
    hardware.ledR.value(0)
    hardware.ledV.value(1)
    time.sleep_ms(100)
#Boton pulsado, arrancamos

hardware.ledV.value(0)
hardware.ledR.value(0)
print("--- ¡ARRANQUE INTERNO! ---")

# Rumbo de referencia: se mide AQUI, antes de mover nada - el robot esta
# perfectamente paralelo a la calle de salida solo en este instante. Si se
# midiera mas tarde (por ejemplo tras esquivar el primer pilar en la rama
# de Mision 3/4), el robot ya habria girado y la referencia saldria mal.
rumbo_base_inicial = hardware.mag.heading() if hardware.mag is not None else None


# ==========================================
# DISCRIMINACION RETO LIBRE / OBSTACULOS Y MISION 3 / 4 (sin movernos)
# ==========================================
def leer_hasta_valor(funcion):
    """Repetimos la lectura hasta que el sensor nos da un valor valido (se usa
    con el TFmini frontal, que en el arranque siempre tiene una pared delante)."""
    valor = funcion()
    while valor is None:
        time.sleep_ms(20)
        valor = funcion()
    return valor


def leer_lateral_o_pegado(funcion):
    """Leemos un TFmini hasta 10 veces. Si no da valor, lo damos por pegado a
    la pared (0 cm): el TFmini-S no mide por debajo de unos 10 cm y, como el
    campo mide 300 cm, un sensor sin lectura valida solo puede ser eso. Asi el
    lado con mas espacio es siempre el que si responde. Pasamos un techo de
    1200 cm para no descartar un lado abierto."""
    for _ in range(10):
        valor = funcion(1200)
        if valor is not None:
            return valor
        time.sleep_ms(20)
    return 0


def medir_laterales():
    """Medimos los dos lados con los dos TFmini laterales (el derecho por la
    UART hecha con PIO y el izquierdo por la UART1), sin mover la camara: el
    frontal se queda mirando al frente. En el aparcamiento uno de los dos
    lados tiene la pared muy cerca y puede no dar lectura (por debajo de unos
    10 cm): leer_lateral_o_pegado lo cuenta como 0 cm. Devuelve
    (derecha, izquierda) en cm."""
    derecha = leer_lateral_o_pegado(leer_lateral_derecho_cm)
    izquierda = leer_lateral_o_pegado(leer_lateral_izquierdo_cm)
    return derecha, izquierda


def _rumbo_actual():
    """Rumbo del magnetometro (o None si no lo tenemos), para ajustar las maniobras en pista."""
    return hardware.mag.heading() if hardware.mag is not None else None


def desaparca_mision_3():
    """Salimos del aparcamiento en Mision 3 como un coche de un aparcamiento
    en linea: 1) marcha atras, recta y a la velocidad mas lenta, mientras el
    frente este a menos de 15 cm de la pared; 2) paramos; 3) volante a tope a
    la derecha y adelante lento durante 2000 ms; 4) paramos y enderezamos.
    Imprimimos el rumbo antes y despues para ajustar los tiempos en pista."""
    print(f"DESAPARCA M3: rumbo inicial {_rumbo_actual()} (calle 0 = {hardware.rumbo_calle[0]})")
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Retrocede_lento)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 3000:  # tope de seguridad: no hay sensor trasero
        d = leer_tfmini()
        if d is not None and d >= 15:
            break
        time.sleep_ms(10)
    hardware.servoTraccion.duty_u16(hardware.Para)
    time.sleep_ms(500)

    hardware.servoDireccion.duty_u16(hardware.Dcha)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)
    time.sleep_ms(2000)

    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    time.sleep_ms(300)
    print(f"DESAPARCA M3: rumbo final {_rumbo_actual()} (calle 0 = {hardware.rumbo_calle[0]})")


def desaparca_mision_4():
    """Salimos del aparcamiento en Mision 4: igual que en Mision 3 pero con el
    volante a tope a la izquierda. Mantenemos la funcion aparte para ajustar
    sus tiempos y anadir acciones propias sin tocar las de la Mision 3."""
    print(f"DESAPARCA M4: rumbo inicial {_rumbo_actual()} (calle 0 = {hardware.rumbo_calle[0]})")
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Retrocede_lento)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 3000:  # tope de seguridad: no hay sensor trasero
        d = leer_tfmini()
        if d is not None and d >= 15:
            break
        time.sleep_ms(10)
    hardware.servoTraccion.duty_u16(hardware.Para)
    time.sleep_ms(500)

    hardware.servoDireccion.duty_u16(hardware.Izda)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)
    time.sleep_ms(1400)

    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    time.sleep_ms(300)
    print(f"DESAPARCA M4: rumbo final {_rumbo_actual()} (calle 0 = {hardware.rumbo_calle[0]})")


import sys


def parada_de_emergencia(e):
    """Si algo falla durante la carrera, dejamos el robot parado y seguro, y
    guardamos el error en error.log (en la Pico) para poder leerlo despues aunque
    no hubiera cable: print(open('error.log').read()) desde la consola."""
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.foco_apagar()
    print("ERROR:", repr(e))
    sys.print_exception(e)
    try:
        with open('error.log', 'w') as f:
            sys.print_exception(e, f)
    except Exception:
        pass
    while True:  # LED rojo parpadeando rapido: el programa se ha parado por un error
        hardware.ledR.value(1)
        time.sleep_ms(150)
        hardware.ledR.value(0)
        time.sleep_ms(150)


def programa_principal():
    distancia_frontal = leer_hasta_valor(leer_tfmini)
    print(f"ARRANQUE: distancia frontal {distancia_frontal} cm")

    if distancia_frontal < 30:
        # ==========================================
        # RETO OBSTACULOS: estamos en el aparcamiento, pegados a la pared frontal
        # ==========================================
        dist_der, dist_izq = medir_laterales()
        while dist_der == dist_izq:  # los dos sin lectura (o iguales): no podemos decidir, repetimos
            print(f"ARRANQUE: derecha {dist_der} cm, izquierda {dist_izq} cm: igual, repetimos")
            time.sleep_ms(200)
            dist_der, dist_izq = medir_laterales()
        print(f"ARRANQUE: derecha {dist_der} cm, izquierda {dist_izq} cm (0 = pegado, sin lectura)")

        es_mision_3 = dist_der > dist_izq
        if es_mision_3:
            print("DISCRIMINACION 3/4: MISION 3")
            hardware.ledV.value(1)
            hardware.ledR.value(0)
            # La primera linea de cada esquina (naranja en CW) cambia de calle y
            # cuenta vueltas: es la mas alejada de los pilares de la calle
            # siguiente, asi que no la repisamos al esquivarlos.
            hardware.color_esquina = 'NARANJA'
            hardware.color_conteo = 'NARANJA'
            if hardware.mag is not None:
                medir_rumbos_calles(hardware.GIRO_POR_ESQUINA_DEG, rumbo_base=rumbo_base_inicial)
            desaparca_mision_3()
        else:
            print("DISCRIMINACION 3/4: MISION 4")
            hardware.ledR.value(1)
            hardware.ledV.value(0)
            # La primera linea de cada esquina (azul en CCW) cambia de calle y
            # cuenta vueltas, igual que en la Mision 3.
            hardware.color_esquina = 'AZUL'
            hardware.color_conteo = 'AZUL'
            if hardware.mag is not None:
                medir_rumbos_calles(-hardware.GIRO_POR_ESQUINA_DEG, rumbo_base=rumbo_base_inicial)
            desaparca_mision_4()

        # Estado de conteo limpio: salimos con el contador de lineas a 0 y la
        # primera linea de esquina sera la que ya conocemos (naranja en Mision 3,
        # azul en Mision 4), que es tambien la que cuenta las vueltas.
        hardware.sobre_linea = False
        hardware.sobre_linea_esquina = False
        hardware.contadorLineas = 0
        hardware.ultimo_conteo_linea_ms = None

        # El foco solo se usa en Mision 3 y 4: a tope mientras escaneamos.
        hardware.foco_habilitado = True
        hardware.foco_brillo(1.0)

        if es_mision_3:
            ejecutar_mision_3_cw()
        else:
            ejecutar_mision_4_ccw()

    else:
        # ==========================================
        # RETO LIBRE (frente despejado): igual que el antiguo Reto
        # Libre - avanzamos leyendo el TFmini lateral izquierdo y el TFmini
        # frontal girado a la derecha con el servo de la camara (lecturas
        # simetricas) hasta ver el hueco. El lateral derecho no se usa aqui: asi
        # no interfiere con el frontal, que mira a la misma pared.
        # ==========================================
        hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_DERECHA)
        time.sleep_ms(500)  # esperamos a que el servo llegue
        hardware.servoDireccion.duty_u16(hardware.Recto)
        hardware.servoTraccion.duty_u16(hardware.Avanza_tope)

        lado_hueco = None
        while lado_hueco is None:
            # Techo de 1200 cm: un hueco abierto puede dar mas de 350 cm y no
            # queremos descartarlo como lectura sospechosa.
            dist_der_cm = leer_tfmini(1200)  # frontal girado a la derecha
            dist_izq_cm = leer_lateral_izquierdo_cm(1200)

            if dist_der_cm is not None and dist_der_cm > hardware.DISTANCIA_HUECO_CM:
                lado_hueco = 'derecha'
            elif dist_izq_cm is not None and dist_izq_cm > hardware.DISTANCIA_HUECO_CM:
                lado_hueco = 'izquierda'

            time.sleep_ms(5)  # la lectura del izquierdo ya tarda ~12 ms, no hace falta mas pausa

        hardware.contadorLineas = 1  # primera esquina ya contada, igual que antes

        if lado_hueco == 'derecha':
            print("BUSQUEDA DE ESQUINA: hueco a la derecha -> MISION 1")
            ejecutar_mision_1_cw()
        else:
            print("BUSQUEDA DE ESQUINA: hueco a la izquierda -> MISION 2")
            ejecutar_mision_2_ccw()


try:
    programa_principal()
except Exception as e:
    parada_de_emergencia(e)