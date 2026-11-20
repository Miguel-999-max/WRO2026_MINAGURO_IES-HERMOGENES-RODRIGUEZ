"""MISION3_CW.PY - Obstaculos, sentido CW. Navega por deteccion de pilares
(busca -> se aproxima -> esquiva -> confirma -> vuelve a buscar). Arranca
ya en la calle - el arranque comun a las 4 misiones lo hace main.py.

Lineas: la naranja (la primera de cada esquina en CW) cambia de calle y
cuenta vueltas (4 por vuelta x 3 vueltas = 12); main.py fija
hardware.color_esquina y hardware.color_conteo a 'NARANJA' antes de llamar.
La azul no la usamos: queda pegada a la calle siguiente y, al esquivar un
pilar cerca de la esquina, el sensor podia pisarla varias veces."""
import time
import math
import hardware
from funciones_comunes import navegar_calle_por_rumbo, leer_tfmini, leer_lateral_izquierdo_cm, leer_lateral_derecho_cm, diferencia_angular, pulso_barrido, _obtener_bloques, _mejor_bloque
from funciones_comunes1 import pilar_visible_ahora, buscar_pilar, buscar_direccion_mas_despejada, dirigirse_a_zona_despejada, aproximarse_a_pilar
from funciones_comunes2 import esquivar_pilar


# Color del pilar al que nos estabamos aproximando (None si a ninguno). Lo
# usamos en _aparcar(): si al contar la ultima linea ibamos hacia un pilar,
# casi seguro es el del principio de la calle 1.
_pilar_en_curso = None


def _buscar_objetivo():
    """Caso 1: encontrar el proximo pilar.
    0. Si ya se ve uno sin barrer (camara centrada), se usa directamente.
    1. Modo crucero por rumbo absoluto (magnetometro): mantiene el chasis
       alineado con la calle actual mientras vigila con un barrido de
       camara +-60, sin dejar de avanzar. Cambia de calle en la linea
       naranja (la primera que aparece en Mision 3), cuenta lineas azules
       de paso. Se usa TAMBIEN justo tras esquivar - antes habia una parada
       + barrido de 180 grados aparte, que arrastraba de cuando no habia
       magnetometro; se quito porque perdia demasiado tiempo por vuelta.
    2. Red de seguridad si el magnetometro no esta disponible: la escalada
       antigua de barridos (90 grados -> 180 grados -> zona mas despejada).
    Devuelve (angulo, color_id) listo para aproximarse_a_pilar(), o (None, None)
    si se completaron las vueltas sin encontrar mas pilares."""
    if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
        return None, None

    angulo, color = pilar_visible_ahora()
    if angulo is not None:
        return angulo, color

    if hardware.mag is not None:
        return navegar_calle_por_rumbo(lado_pared='izquierda')

    # --- Red de seguridad: solo si el magnetometro no esta disponible ---
    angulo, color = buscar_pilar()  # 90 grados (rango por defecto)
    if angulo is not None:
        return angulo, color

    angulo, color = buscar_pilar(hardware.ANGULO_BUSQUEDA_180_INICIO, hardware.ANGULO_BUSQUEDA_180_FIN)
    if angulo is not None:
        return angulo, color

    angulo_despejado = buscar_direccion_mas_despejada()
    encontro_pilar = dirigirse_a_zona_despejada(angulo_despejado)
    if encontro_pilar:
        return pilar_visible_ahora()

    return None, None


def _medir_frontal_hacia(cam):
    """Giramos la camara (con el TFmini frontal) al angulo cam respecto al
    chasis, esperamos a que llegue y devolvemos la media de 5 lecturas en cm,
    o None si no hay ninguna valida."""
    cam = max(hardware.ANGULO_SERVO_MIN, min(cam, hardware.ANGULO_SERVO_MAX))
    hardware.SERVOcam.duty_u16(pulso_barrido(cam))
    time.sleep_ms(350)
    lecturas = []
    for _ in range(5):
        d = leer_tfmini()
        if d is not None:
            lecturas.append(d)
        time.sleep_ms(15)
    return sum(lecturas) / len(lecturas) if lecturas else None


def _aparcar():
    """Aparcamiento final de la Mision 3 - FASE DE TOMA DE DATOS. Todavia no
    movemos el robot: medimos donde se ha parado al contar la ultima linea
    naranja y donde estan los pilares de la calle 1, e imprimimos todo para
    decidir la maniobra con datos reales.

    Plano de la esquina (M3, CW), en cm, campo de 300 x 300 de muro a muro:
      "norte" = la direccion de la calle 4 (rumbo_calle de la calle 4).
      x = distancia al muro exterior de la izquierda (el oeste), que cierra
          la calle 1: es la posicion A LO LARGO de la calle 1. La esquina
          va de 0 a 100, la calle 1 de 100 a 200 (asientos de pilar en unos
          100, 150 y 200).
      y = distancia al muro exterior del norte: posicion A LO ANCHO de la
          calle 1. Fila exterior de pilares a 40, fila interior a 60, muro
          interior a 100 (el aparcamiento ocupa de 0 a 20).
    theta = cuanto estamos girados respecto al norte (brujula; positivo a la
    derecha). Usamos el TFmini frontal, que va en el servo de la camara, como
    un radar que apunta a direcciones absolutas:
      - Al norte: camara a -theta -> y del robot.
      - Al este, a lo largo de la calle 1: camara a 90 - theta -> distancia
        al muro del fondo. Si y < 100 el haz recorre la calle 1 y llega al
        muro exterior del este (x = 300 - d); si y > 100 todavia estamos a la
        altura de la calle 4 y el haz choca con el muro interior (x = 100 - d).
      - De comprobacion, el lateral izquierdo: con theta pequeno mira al
        oeste (x = lateral x cos theta).
    Para cada pilar: direccion respecto al norte = theta + angulo de la
    camara (tras centrarlo en la imagen), y con la distancia del TFmini
      x_pilar = x_robot + d x sin(direccion)
      y_pilar = y_robot - d x cos(direccion)
    No tenemos en cuenta donde van montados los sensores en el chasis (unos
    pocos cm de error). Imprimimos tambien las lecturas en bruto."""
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    time.sleep_ms(300)  # robot parado

    rumbo_norte = hardware.rumbo_calle[(hardware.calle_actual - 1) % 4]  # rumbo de la calle 4
    theta = diferencia_angular(hardware.mag.heading(), rumbo_norte)  # positivo = girados a la derecha

    print("========== APARCAR M3: TOMA DE DATOS ==========")
    print(f"Pilar que estabamos aproximando al parar: {_pilar_en_curso} (1 = rojo, 2 = verde, None = ninguno)")
    print(f"theta (giro respecto a la calle 4) = {theta:.1f} grados")

    # --- Posicion del robot ---
    cam_norte = -theta
    cam_este = 90 - theta
    d_norte = _medir_frontal_hacia(cam_norte) if abs(cam_norte) <= 90 else None
    d_este = _medir_frontal_hacia(cam_este) if abs(cam_este) <= 90 else None
    lateral_izq = leer_lateral_izquierdo_cm()

    y_robot = d_norte
    x_robot = None
    origen_x = '-'
    if d_este is not None and y_robot is not None:
        if y_robot < 100:
            x_robot = 300 - d_este
            origen_x = 'muro exterior del este'
        else:
            x_robot = 100 - d_este
            origen_x = 'muro interior'
    x_lateral = lateral_izq * math.cos(math.radians(theta)) if (lateral_izq is not None and abs(theta) <= 30) else None
    if x_robot is None and x_lateral is not None:
        x_robot = x_lateral
        origen_x = 'lateral izquierdo'

    print(f"En bruto: al norte (cam {cam_norte:.0f}) = {d_norte} cm, al este (cam {cam_este:.0f}) = {d_este} cm, "
          f"lateral izq = {lateral_izq} cm (x por el lateral = {x_lateral})")
    print(f"Robot: x = {x_robot if x_robot is None else round(x_robot)} cm (a lo largo de la calle 1, por {origen_x}), "
          f"y = {y_robot if y_robot is None else round(y_robot)} cm (a lo ancho)")

    # --- Pilares: barrido de la camara de -20 a +90 grados ---
    medidos = []   # direcciones respecto al norte de los pilares ya medidos
    angulo = -20
    while angulo <= 90 and len(medidos) < 6:
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo))
        time.sleep_ms(200)  # robot parado: dejamos que la imagen se ponga al dia
        bloques = _obtener_bloques()
        nuevo = None
        for b in bloques:
            direccion_aprox = theta + angulo + (b.x_center - hardware.FRAME_CENTRO_X) * hardware.PX_A_GRADOS_CAMARA
            if all(abs(direccion_aprox - m) > 6 for m in medidos):  # AJUSTAR EN PISTA: grados entre pilares distintos
                nuevo = b
                break
        if nuevo is None:
            angulo += 5
            continue

        # Centramos el pilar nuevo en la imagen (como mucho 6 correcciones)
        objetivo = nuevo
        cam = angulo
        for _ in range(6):
            error_px = objetivo.x_center - hardware.FRAME_CENTRO_X
            if abs(error_px) <= 20:
                break
            cam = max(hardware.ANGULO_SERVO_MIN, min(cam + error_px * hardware.PX_A_GRADOS_CAMARA, hardware.ANGULO_SERVO_MAX))
            hardware.SERVOcam.duty_u16(pulso_barrido(cam))
            time.sleep_ms(250)
            mismos = [b for b in _obtener_bloques() if b.id == objetivo.id]
            if not mismos:
                break
            objetivo = min(mismos, key=lambda b: abs(b.x_center - hardware.FRAME_CENTRO_X))
        error_px = objetivo.x_center - hardware.FRAME_CENTRO_X
        if abs(error_px) > 60:  # AJUSTAR EN PISTA: px
            # No hemos podido centrarlo (por ejemplo, con la camara al tope de
            # 90 grados): el TFmini no le apunta, asi que no lo usamos
            print(f"PILAR descartado: id={objetivo.id} cam={cam:.1f} err={error_px}px (no se ha podido centrar)")
            medidos.append(theta + cam + error_px * hardware.PX_A_GRADOS_CAMARA)  # para no volver a mirarlo
            angulo = int(cam) + 10
            continue
        lecturas = [d for d in (leer_tfmini() for _ in range(5)) if d is not None]
        d = sum(lecturas) / len(lecturas) if lecturas else None

        direccion = theta + cam + error_px * hardware.PX_A_GRADOS_CAMARA
        medidos.append(direccion)
        base = objetivo.y_center + objetivo.height // 2
        print(f"PILAR {len(medidos)}: id={objetivo.id} cam={cam:.1f} err={error_px}px base={base} "
              f"dist={d} -> direccion respecto al norte={direccion:.1f} grados")
        if d is not None and x_robot is not None and y_robot is not None:
            r = math.radians(direccion)
            x_p = x_robot + d * math.sin(r)
            y_p = y_robot - d * math.cos(r)
            posicion = 'PRINCIPIO' if x_p < 125 else ('CENTRO' if x_p < 175 else 'FINAL')
            fila = 'interior' if y_p >= 50 else 'exterior'
            print(f"         x_pilar = {x_p:.0f} cm, y_pilar = {y_p:.0f} cm -> parece {posicion}, fila {fila}")
        angulo = int(cam) + 10  # seguimos barriendo mas alla de este pilar

    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    print(f"========== FIN DE LA TOMA DE DATOS ({len(medidos)} pilares) ==========")


def ejecutar_mision_3_cw(angulo_inicial=None, color_inicial=None):
    """MISION 3 (CW): navega por deteccion de pilares (no por pared): busca el
    pilar mas cercano, se aproxima manteniendolo centrado con la Huskylens, lo
    esquiva por el lado que marca su color (regla oficial: ROJO=derecha,
    VERDE=izquierda), y vuelve a buscar el siguiente.
    angulo_inicial/color_inicial: si main.py ya localizo el primer pilar, se
    va directo a aproximarse_a_pilar() sin barrer de nuevo. rumbo_calle,
    color_esquina y color_conteo los prepara main.py antes de llamar."""
    global _pilar_en_curso
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

    angulo_pendiente = angulo_inicial
    color_pendiente = color_inicial

    while True:
        if angulo_pendiente is not None:
            # esquivar_pilar() ya localizo el siguiente pilar mirando al
            # frente en su propio tramo entre fases - nos ahorramos volver a
            # barrear desde cero.
            angulo_encontrado, color_encontrado = angulo_pendiente, color_pendiente
            angulo_pendiente = None
            color_pendiente = None
            print(f"--- pilar ya localizado al esquivar el anterior: angulo={angulo_encontrado} color={color_encontrado} ---")
        else:
            print("--- _buscar_objetivo() ---")
            angulo_encontrado, color_encontrado = _buscar_objetivo()
            print(f"--- _buscar_objetivo() resultado: angulo={angulo_encontrado} color={color_encontrado} ---")

        if angulo_encontrado is None:
            print("--- nada encontrado, se reintenta ---")
            if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
                break
            continue

        print("--- aproximarse_a_pilar() ---")
        _pilar_en_curso = color_encontrado
        color_real, alineado = aproximarse_a_pilar(angulo_encontrado, color_encontrado)
        if hardware.contadorLineas < hardware.TOTAL_LINEAS_META:
            _pilar_en_curso = None  # si hemos parado por la ultima linea, lo conservamos para _aparcar()

        if color_real is None:
            print("--- pilar perdido durante la aproximacion, se reintenta ---")
            continue

        print(f"--- esquivar_pilar(color={color_real}) ---")
        # Sin Fase 2 para el ROJO: lo esquivamos por el lado hacia el que gira el
        # circuito y asi quedamos ya orientados hacia la esquina
        angulo_siguiente, color_siguiente = esquivar_pilar(color_real, alineado, fase2=(color_real != 1))
        hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
        print(f"--- ciclo completado, contadorLineas={hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META} ---")

        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            break

        if angulo_siguiente is not None:
            angulo_pendiente = angulo_siguiente
            color_pendiente = color_siguiente

    # Ultima linea contada: paramos en seco y aparcamos
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    print("¡Lineas completadas! Paramos y aparcamos")
    _aparcar()
    print("--- MISION 3 COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)