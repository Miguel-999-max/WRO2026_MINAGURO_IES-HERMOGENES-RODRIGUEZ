"""MISION1_CW.PY - Reto Libre, giro a derechas (CW)."""
import time
import hardware
from funciones_comunes import leer_tfmini, clasificar_color, parar_en_salida_libre


def ejecutar_mision_1_cw():
    """MISION 1: Giro a derechas siguiendo pared con filtro estricto de lineas AZULES."""
    print("--- EJECUTANDO MISION 1 CW (GIRO A DERECHAS) ---")

    # Seguimos la pared con el TFmini frontal (I2C), girado hacia la derecha
    # con el servo de la camara. Lo orientamos ya, antes de las maniobras.
    hardware.SERVOcam.duty_u16(hardware.RADAR_FIJO_DERECHA)

    # Maniobras iniciales. La direccion va como desplazamiento respecto a
    # hardware.Recto (negativo = derecha, positivo = izquierda), asi sigue al
    # centro si lo recalibramos. dir_desde_recto() solo limita a Dcha/Izda.



    print("Movimiento Inicial 1: Avanzando a la derecha...")
    hardware.servoDireccion.duty_u16(hardware.dir_desde_recto(-1200))
    hardware.servoTraccion.duty_u16(4000)
    time.sleep_ms(1500)

    print("Movimiento Inicial 2: Avanzando a la derecha pero menos...")
    hardware.servoDireccion.duty_u16(hardware.dir_desde_recto(-150))
    hardware.servoTraccion.duty_u16(3800)
    time.sleep_ms(1500)

    

    print("Salida completada. Entrando en bucle de carrera...")
    distancia_actual = hardware.DISTANCIA_OBJETIVO

    # === FASE 1: sigue pared, termina por CONTEO DE VUELTAS (sin tocar) ===
    while True:
        hardware.servoTraccion.duty_u16(hardware.Avanza_tope)

        nueva_distancia = leer_tfmini()
        if nueva_distancia is not None:
            distancia_actual = nueva_distancia

        error = distancia_actual - hardware.DISTANCIA_OBJETIVO
        pulso_dir = hardware.Recto - (error * hardware.GANANCIA_KP)
        pulso_dir = max(hardware.Dcha, min(pulso_dir, hardware.Izda))
        hardware.servoDireccion.duty_u16(pulso_dir)

        if hardware.sensor_color is None:
            r = g = b = claro = 0
        else:
            r, g, b, claro = hardware.sensor_color.read_rgbc()

        color = clasificar_color(r, g, b)

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

        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            print("¡Lineas completadas! Pasando a la fase final por distancia...")
            break

        time.sleep_ms(20)

    # === FASE 2: seguimos la isla con el TFmini lateral y paramos a 160 cm
    # de la pared del fondo (antes: 2000 ms por tiempo). Ver
    # parar_en_salida_libre en funciones_comunes.py ===
    parar_en_salida_libre('derecha', distancia_actual)

    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    print("--- CARRERA COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)