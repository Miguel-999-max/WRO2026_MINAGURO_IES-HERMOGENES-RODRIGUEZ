#Descomponemos el programa en varios archivos para que sea más legible y mantenible.
#Retocamos la lectura de las líneas de suelo. Ahora va por color.
#Reforzamos la lectura de los sensores de distancia. Ahora se leen varias veces y se descartan lecturas erráticas.
#Cambiamos la forma de detectar misión 1 - misión 2. Ahora se hace por distancias laterales en lugar de por color de línea.
#Introducimos el magnetómetro 10 DOF
#Troceamos funciones_comunes.py en 3 archivos para manejarlos mejor
#Hemos podido completar la primera vuelta de la zona de obstáculos.Ahora vamos a hacer que el robot no confunda el parking con un bloque rojo.
#Decidimos cambiar estrategia. Eliminamos paredes aparcamiento.Implementamos misión 4.



"""MAIN.PY - Punto de entrada. Arranque unificado para las 4 misiones: ya no
hay dos zonas de salida distintas, las cuatro empiezan igual (retroceso +
comprobacion de pilar de frente + busqueda de esquina si no hay pilar)."""
import time
import hardware
from funciones_comunes import leer_tfmini, leer_tof_derecho_mm, medir_rumbos_calles, pulso_barrido, _obtener_bloques, _mejor_bloque
from funciones_comunes1 import buscar_pilar
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
# RETROCESO INICIAL (sale del hueco de salida, comun a las 4 misiones)
# ==========================================
hardware.servoDireccion.duty_u16(hardware.Recto)
hardware.servoTraccion.duty_u16(hardware.Retrocede_lento)
time.sleep_ms(hardware.TIEMPO_RETROCESO_INICIAL_MS)
hardware.servoTraccion.duty_u16(hardware.Para)

# ==========================================
# COMPROBACION 1: pilar visible de frente -> Mision 3/4 directa
# ==========================================
hardware.SERVOcam.duty_u16(pulso_barrido(0))
time.sleep_ms(300)
bloques = _obtener_bloques()

if len(bloques) > 0:
    objetivo = _mejor_bloque(bloques)

    if objetivo.x_center > hardware.FRAME_CENTRO_X:
        print("COMPROBACION 1: pilar a la derecha -> MISION 3 directa")
        hardware.color_esquina = 'NARANJA'
        if hardware.mag is not None:
            medir_rumbos_calles(hardware.GIRO_POR_ESQUINA_DEG)
        ejecutar_mision_3_cw(angulo_inicial=0, color_inicial=objetivo.id)
    else:
        print("COMPROBACION 1: pilar a la izquierda -> MISION 4 directa")
        hardware.color_esquina = 'AZUL'
        if hardware.mag is not None:
            medir_rumbos_calles(-hardware.GIRO_POR_ESQUINA_DEG)
        ejecutar_mision_4_ccw(angulo_inicial=0, color_inicial=objetivo.id)

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

    if hardware.mag is not None:
        signo = hardware.GIRO_POR_ESQUINA_DEG if lado_hueco == 'derecha' else -hardware.GIRO_POR_ESQUINA_DEG
        medir_rumbos_calles(signo)

    if lado_hueco == 'derecha':
        hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_DERECHA)
        print("Movimiento Inicial 1: Avanzando a la derecha...")
        hardware.servoDireccion.duty_u16(3900)
        hardware.servoTraccion.duty_u16(4000)
        time.sleep_ms(2100)
        hardware.servoTraccion.duty_u16(hardware.Para)

        angulo, color = buscar_pilar(hardware.ANGULO_BUSQUEDA_TRANSICION, -hardware.ANGULO_BUSQUEDA_TRANSICION,
                                      paso=hardware.PASO_BARRIDO)
        if angulo is not None:
            print("BARRIDO ESTRECHO: pilar encontrado -> MISION 3")
            hardware.color_esquina = 'NARANJA'
            ejecutar_mision_3_cw(angulo_inicial=angulo, color_inicial=color)
        else:
            print("BARRIDO ESTRECHO: nada -> MISION 1")
            ejecutar_mision_1_cw(saltar_movimiento_1=True)
    else:
        hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_IZQUIERDA)
        print("Movimiento Inicial 1: Avanzando a la izquierda...")
        hardware.servoDireccion.duty_u16(6190)
        hardware.servoTraccion.duty_u16(4000)
        time.sleep_ms(1200)
        hardware.servoTraccion.duty_u16(hardware.Para)

        angulo, color = buscar_pilar(hardware.ANGULO_BUSQUEDA_TRANSICION, -hardware.ANGULO_BUSQUEDA_TRANSICION,
                                      paso=hardware.PASO_BARRIDO)
        if angulo is not None:
            print("BARRIDO ESTRECHO: pilar encontrado -> MISION 4")
            hardware.color_esquina = 'AZUL'
            ejecutar_mision_4_ccw(angulo_inicial=angulo, color_inicial=color)
        else:
            print("BARRIDO ESTRECHO: nada -> MISION 2")
            ejecutar_mision_2_ccw(saltar_movimiento_1=True)