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





"""MAIN.PY - Punto de entrada. Espera el boton y comprueba de inmediato si
hay un pilar visible: si lo hay, Mision 3/4 directa; si no, busqueda de
esquina clasica y Mision 1/2 (que hacen su propia incorporacion)."""
import time
import hardware
from funciones_comunes import leer_tfmini, leer_tof_derecho_mm, medir_rumbos_calles, pulso_barrido, _obtener_bloques, _mejor_bloque, clasificar_color
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

    # Retroceso a tope tras esquivar, antes de buscar la primera linea de
    # esquina. Ninguna linea vista durante todo este bloque (ni esta, ni la
    # de identificacion mas abajo) pasa por _comprobar_lineas() - no cuentan
    # como "Esquina detectada" ni afectan al conteo de vueltas, que solo
    # arranca de verdad cuando se lanza la mision al final.
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Retrocede_tope)
    time.sleep_ms(500)
    hardware.servoTraccion.duty_u16(hardware.Para)

    # Avanza hasta detectar la primera linea de esquina real: naranja =
    # Mision 3, azul = Mision 4. Exige 3 lecturas seguidas del mismo color
    # antes de aceptarlo, para no fiarse de una lectura aislada.
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    color_confirmado = None
    color_candidato = None
    repeticiones = 0
    while color_confirmado is None:
        r, g, b, claro = hardware.sensor_color.read_rgbc()
        color = clasificar_color(r, g, b)
        if color in ('NARANJA', 'AZUL'):
            if color == color_candidato:
                repeticiones += 1
            else:
                color_candidato = color
                repeticiones = 1
            if repeticiones >= 3:
                color_confirmado = color
        else:
            color_candidato = None
            repeticiones = 0
        time.sleep_ms(20)

    hardware.servoTraccion.duty_u16(hardware.Para)
    print(f"DISCRIMINACION 3/4: linea {color_confirmado} confirmada")

    es_mision_3 = (color_confirmado == 'NARANJA')
    if es_mision_3:
        print("DISCRIMINACION 3/4: MISION 3")
        hardware.ledV.value(1)
        hardware.ledR.value(0)
        hardware.color_esquina = 'NARANJA'
        if hardware.mag is not None:
            medir_rumbos_calles(hardware.GIRO_POR_ESQUINA_DEG, rumbo_base=rumbo_base_inicial)
    else:
        print("DISCRIMINACION 3/4: MISION 4")
        hardware.ledR.value(1)
        hardware.ledV.value(0)
        hardware.color_esquina = 'AZUL'
        hardware.color_conteo = 'NARANJA'
        if hardware.mag is not None:
            medir_rumbos_calles(-hardware.GIRO_POR_ESQUINA_DEG, rumbo_base=rumbo_base_inicial)

    # Sale de la linea (rapido, 300ms) antes de lanzar la mision - a partir
    # de aqui ya cuenta todo con normalidad (Esquina detectada, 12 lineas).
    hardware.servoTraccion.duty_u16(hardware.Retrocede_tope)
    time.sleep_ms(500)
    hardware.servoTraccion.duty_u16(hardware.Para)
    time.sleep_ms(200)

    # Reset explicito de todo el estado de conteo: el esquive del primer
    # pilar (y la propia identificacion de mision) pueden haber cruzado
    # lineas de verdad por el camino (se vio en pista) - sin este reset,
    # los flancos podian quedar "atascados" en True y bloquear tanto el
    # contador como la deteccion de esquina en el primer cruce real de la
    # mision.
    hardware.sobre_linea = False
    hardware.sobre_linea_esquina = False
    hardware.contadorLineas = 0
    hardware.ultimo_conteo_linea_ms = None
    time.sleep_ms(400)

    if es_mision_3:
        ejecutar_mision_3_cw()
    else:
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
        ejecutar_mision_3_cw()
    else:
        print("BUSQUEDA DE ESQUINA: hueco a la izquierda -> MISION 2")
        ejecutar_mision_4_ccw()