#Descomponemos el programa en varios archivos para que sea más legible y mantenible.
#Retocamos la lectura de las líneas de suelo. Ahora va por color.
#Reforzamos la lectura de los sensores de distancia. Ahora se leen varias veces y se descartan lecturas erráticas.
#Cambiamos la forma de detectar misión 1 - misión 2. Ahora se hace por distancias laterales en lugar de por color de línea.
#Introducimos el magnetómetro 10 DOF
#Troceamos funciones_comunes.py en 3 archivos para manejarlos mejor
#Hemos podido completar la primera vuelta de la zona de obstáculos.Ahora vamos a hacer que el robot no confunda el parking con un bloque rojo.
#Decidimos cambiar estrategia. Eliminamos paredes aparcamiento.Implementamos misión 4.
#Cambiamos la forma de salir del parking y de discriminar entre misiones. REtocamos algoritmos de buscar pilares.



"""MAIN.PY - Punto de entrada. Espera el boton y comprueba de inmediato si
hay un pilar visible: si lo hay, Mision 3/4 directa; si no, busqueda de
esquina clasica y Mision 1/2 (que hacen su propia incorporacion)."""
import time
import hardware
from funciones_comunes import leer_tfmini, leer_tof_derecho_mm, medir_rumbos_calles, pulso_barrido, _obtener_bloques, _mejor_bloque
from funciones_comunes1 import aproximarse_a_pilar
from funciones_comunes2 import esquivar_pilar
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

hardware.ledV.value(0)
hardware.ledR.value(0)
print("--- ¡ARRANQUE INTERNO! ---")

# ==========================================
# COMPROBACION 1: pilar visible de frente -> esquivar y discriminar Mision 3/4
# ==========================================
hardware.SERVOcam.duty_u16(pulso_barrido(0))
time.sleep_ms(300)
bloques = _obtener_bloques()

if len(bloques) > 0:
    objetivo = _mejor_bloque(bloques)
    print(f"COMPROBACION 1: pilar visible (id={objetivo.id}) -> aproximando antes de esquivar")

    color_real = aproximarse_a_pilar(0)
    while color_real is None:
        print("COMPROBACION 1: pilar perdido durante la aproximacion, se reintenta")
        hardware.SERVOcam.duty_u16(pulso_barrido(0))
        time.sleep_ms(200)
        bloques = _obtener_bloques()
        if len(bloques) > 0:
            color_real = aproximarse_a_pilar(0)
        else:
            time.sleep_ms(200)

    esquivar_pilar(color_real)

    # Separacion de la esquina antes de medir: sin esto, la medicion salia
    # a veces erronea por estar demasiado cerca de la esquina que se acaba
    # de dejar atras.
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)
    time.sleep_ms(500)
    hardware.servoTraccion.duty_u16(hardware.Para)

    # Robot parado: mide distancia a cada lado, igual que para discriminar
    # Mision 1/2 pero sin avanzar. Asentamiento del servo antes de fiarse
    # de la lectura del TFmini. Con reintentos: una lectura fallida puntual
    # de un solo sensor no debe decidir la mision por defecto.
    hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_IZQUIERDA)
    time.sleep_ms(300)
    while hardware.uart0.any():
        hardware.uart0.read(hardware.uart0.any())
    time.sleep_ms(10)

    dist_izq_cm = None
    for _ in range(10):
        dist_izq_cm = leer_tfmini()
        if dist_izq_cm is not None:
            break
        time.sleep_ms(20)

    dist_der_cm = None
    for _ in range(10):
        dist_der_mm = leer_tof_derecho_mm()
        if dist_der_mm is not None:
            dist_der_cm = dist_der_mm / 10
            break
        time.sleep_ms(20)

    print(f"DISCRIMINACION 3/4: dist_izq={dist_izq_cm} dist_der={dist_der_cm}")
    if dist_izq_cm is None or dist_der_cm is None:
        print("DISCRIMINACION 3/4: AVISO - algun sensor no dio lectura valida tras los reintentos")

    if dist_der_cm is not None and dist_izq_cm is not None and dist_der_cm > dist_izq_cm:
        print("DISCRIMINACION 3/4: MISION 3 (derecha mas despejada)")
        hardware.ledV.value(1)
        hardware.ledR.value(0)
        es_mision_3 = True
    else:
        print("DISCRIMINACION 3/4: MISION 4 (izquierda mas despejada)")
        hardware.ledR.value(1)
        hardware.ledV.value(0)
        es_mision_3 = False

    # Reposicionamiento: retrocede para quedar detras de la primera linea
    # (naranja en Mision 3, azul en Mision 4), asi el conteo de lineas de
    # la mision arranca limpio.
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Retrocede_lento)
    time.sleep_ms(800)
    hardware.servoTraccion.duty_u16(hardware.Para)

    # Todavia en la calle de salida (calle del aparcamiento) - se lanza la
    # mision sin ningun movimiento previo mas.
    if es_mision_3:
        hardware.color_esquina = 'NARANJA'
        if hardware.mag is not None:
            medir_rumbos_calles(hardware.GIRO_POR_ESQUINA_DEG)
        ejecutar_mision_3_cw()
    else:
        hardware.color_esquina = 'AZUL'
        if hardware.mag is not None:
            medir_rumbos_calles(-hardware.GIRO_POR_ESQUINA_DEG)
        ejecutar_mision_4_ccw()

else:
    # ==========================================
    # BUSQUEDA DE ESQUINA (sin pilar de frente): igual que el antiguo Reto
    # Libre - avanza leyendo TOF derecho + TFmini izquierdo hasta ver el hueco.
    # ==========================================
    hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_IZQUIERDA)
    time.sleep_ms(300)

    while hardware.uart0.any():
        hardware.uart0.read(hardware.uart0.any())
    time.sleep_ms(10)

    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_tope)

    lado_hueco = None
    while lado_hueco is None:
        dist_der_mm = leer_tof_derecho_mm()
        dist_izq_cm = leer_tfmini()

        if dist_der_mm is not None and (dist_der_mm / 10) > hardware.DISTANCIA_HUECO_CM:
            lado_hueco = 'derecha'
        elif dist_izq_cm is not None and dist_izq_cm > hardware.DISTANCIA_HUECO_CM:
            lado_hueco = 'izquierda'

        time.sleep_ms(20)

    hardware.contadorLineas = 1  # primera esquina ya contada, igual que antes

    if lado_hueco == 'derecha':
        print("BUSQUEDA DE ESQUINA: hueco a la derecha -> MISION 1")
        ejecutar_mision_1_cw()
    else:
        print("BUSQUEDA DE ESQUINA: hueco a la izquierda -> MISION 2")
        ejecutar_mision_2_ccw()