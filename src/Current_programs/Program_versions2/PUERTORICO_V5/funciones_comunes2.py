"""
FUNCIONES_COMUNES2.PY - Maniobra de esquive: esquivar_pilar(), y la
recolocacion marcha atras que usamos cuando llegamos demasiado cerca de un
pilar (o de lado).
Tercera parte del troceo de funciones_comunes.py (ver ese archivo para el
resto de piezas). Usa "import hardware" y accede a pines/constantes con
hardware.X
"""
import time
import hardware
from funciones_comunes import pulso_barrido, leer_tfmini, diferencia_angular, _comprobar_lineas, _obtener_bloques, _bloque_seguido

def _recolocar_ante_pilar(color_id):
    """Nos recolocamos cuando hemos llegado demasiado cerca de un pilar (o de
    lado), antes de esquivarlo, sin volver a escanear:
      a. Camara al centro y fija: asi el error en pixeles del pilar mide
         directamente lo desalineado que esta el chasis.
      b. Marcha atras lenta con las ruedas giradas hacia el lado CONTRARIO al
         pilar, en proporcion al error (a tope con el pilar en el borde de la
         imagen), hasta que el pilar queda a menos de 40 px del centro. Marcha
         atras, con el pilar a la derecha y las ruedas a la izquierda, el morro
         gira a la derecha: hacia el pilar. Como la camara no se mueve, el giro
         se para solo en cuanto el pilar esta centrado.
      c. Marcha atras recta hasta que el TFmini (que ya apunta al pilar) mide
         17 cm o mas. Si ya estamos a esa distancia, nos lo saltamos.
    Topes de seguridad (no tenemos sensor trasero): 800 ms para el paso b y
    600 ms para el paso c; en el paso b cortamos tambien si perdemos el pilar
    5 veces seguidas. Pase lo que pase, despues esquivamos.
    Todo el retroceso va con hardware.marcha_atras = True: las lineas que
    crucemos se cuentan en negativo."""
    hardware.SERVOcam.duty_u16(pulso_barrido(0))
    hardware.servoTraccion.duty_u16(hardware.Para)
    time.sleep_ms(200)  # la camara llega al centro y la imagen se estabiliza

    hardware.marcha_atras = True

    # --- b. Centrar el pilar girando marcha atras ---
    hardware.servoTraccion.duty_u16(hardware.Retrocede_lento)
    x_previo = None
    fallos_seguidos = 0
    error_px = None
    motivo = 'tiempo agotado'
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 800:  # AJUSTAR EN PISTA: tope del paso b
        bloques = _obtener_bloques()
        objetivo = _bloque_seguido(bloques, x_previo, color_id) if len(bloques) > 0 else None  # solo nuestro pilar
        if objetivo is not None:
            fallos_seguidos = 0
            x_previo = objetivo.x_center
            error_px = objetivo.x_center - hardware.FRAME_CENTRO_X
            if abs(error_px) <= 40:  # AJUSTAR EN PISTA: tolerancia de centrado en px
                motivo = 'pilar centrado'
                break
            # Pilar a la derecha (error > 0) -> ruedas a la izquierda (pulso mayor que Recto)
            pulso_dir = hardware.Recto + error_px * 6  # AJUSTAR EN PISTA: a tope con ~200 px de error
            pulso_dir = int(max(hardware.Dcha, min(pulso_dir, hardware.Izda)))
            hardware.servoDireccion.duty_u16(pulso_dir)
        else:
            fallos_seguidos += 1
            if fallos_seguidos >= 5:
                motivo = 'pilar perdido'
                break
        _comprobar_lineas()
        time.sleep_ms(10)
    t_b = time.ticks_diff(time.ticks_ms(), t0)

    # --- c. Retroceso recto hasta 17 cm ---
    hardware.servoDireccion.duty_u16(hardware.Recto)
    distancia = leer_tfmini()
    t0 = time.ticks_ms()
    while (distancia is None or distancia < 17) and time.ticks_diff(time.ticks_ms(), t0) < 600:  # AJUSTAR EN PISTA: 17 cm y tope del paso c
        _comprobar_lineas()
        time.sleep_ms(10)
        distancia = leer_tfmini()
    t_c = time.ticks_diff(time.ticks_ms(), t0)

    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.marcha_atras = False
    print(f"RECOLOCAR: paso b fin por {motivo} en {t_b} ms (err={error_px}px), "
          f"paso c {t_c} ms, distancia={distancia}")


def _terminar_maniobra():
    """Dejamos el robot parado y recto, los LED apagados y el foco a tope
    (volvemos a escanear)."""
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.ledR.value(0)
    hardware.ledV.value(0)
    hardware.foco_brillo(1.0)


def esquivar_pilar(color_id, alineado=True, fase2=True, rumbo_fase2=None):
    """Maniobra de evasion segun el color del pilar (regla oficial WRO 2026):
    ROJO (id=1)  -> mantener el lado DERECHO del carril -> esquivar por la derecha.
    VERDE (id=2) -> mantener el lado IZQUIERDO del carril -> esquivar por la izquierda.

    DEMASIADO CERCA O SIN ENCARAR: si al empezar el TFmini mide
    DISTANCIA_RETROCESO_TRIGGER_CM o menos (o no da lectura), o si
    aproximarse_a_pilar nos dice que hemos llegado sin el chasis encarado al
    pilar (alineado=False), antes de esquivar nos recolocamos marcha atras
    (_recolocar_ante_pilar): centramos el pilar en la imagen girando hacia
    atras y retrocedemos recto hasta 17 cm. Despues esquivamos directamente,
    sin volver a escanear. Una vez empezado el giro (Fases 1 y 2) ya no
    vigilamos la distancia: el giro se completa siempre.

    Las dos fases del esquive se deciden con la BRUJULA, no con el pilar:
    FASE 1: giramos hacia el lado de evasion (a tope) hasta que el rumbo ha
    cambiado ANGULO_GIRO_ESQUIVE grados en el sentido esperado (rojo: rumbo
    aumenta / derecha; verde: rumbo disminuye / izquierda).
    FASE 2: giramos hacia el lado contrario (a tope) hasta recuperar el rumbo
    inicial, quedando otra vez paralelos a la calle pero ya al otro lado del
    pilar. Con fase2=False nos la saltamos (y su tramo recto final): tras el
    tramo recto entre fases terminamos y navegar_calle_por_rumbo() recupera el
    rumbo de la calle mientras busca el siguiente pilar. Lo usamos con el
    color que se esquiva por el lado hacia el que gira el circuito (rojo en
    Mision 3, verde en Mision 4): asi quedamos ya orientados hacia la esquina.

    rumbo_fase2: si lo damos, la Fase 2 no vuelve al rumbo inicial sino que
    gira hasta este rumbo (por ejemplo el de la calle 0, para quedar
    paralelos a ella al salir en M4 o al terminar en la fase final).

    Devolvemos siempre (None, None): el llamador hace una busqueda normal
    para el siguiente pilar."""

    lado_evasion = hardware.Dcha if color_id == 1 else hardware.Izda
    lado_contrario = hardware.Izda if color_id == 1 else hardware.Dcha
    signo_giro = 1 if color_id == 1 else -1  # rojo: rumbo aumenta (CW). verde: rumbo disminuye (CCW)

    if color_id == 1:  # ROJO
        hardware.ledR.value(1)
        hardware.ledV.value(0)
    else:  # VERDE (o cualquier otro id, por seguridad)
        hardware.ledV.value(1)
        hardware.ledR.value(0)

    # Mientras esquivamos, el foco va apagado (vuelve a tope al terminar).
    hardware.foco_apagar()

    # No vaciamos el bufer de la UART0: el TFmini frontal emite en continuo y
    # el driver ya se queda con la ultima trama recibida.
    time.sleep_ms(10)
    distancia_actual = leer_tfmini()
    print(f"ESQUIVAR_PILAR: id={color_id} distancia_inicial={distancia_actual} alineado={alineado}")

    # === DEMASIADO CERCA: nos recolocamos marcha atras y esquivamos ===
    # None (o 0) cuenta como demasiado cerca: por debajo de unos 10 cm el
    # TFmini-S no da una lectura fiable.
    if distancia_actual is None or distancia_actual <= hardware.DISTANCIA_RETROCESO_TRIGGER_CM or not alineado:
        print(f"ESQUIVAR_PILAR: demasiado cerca ({distancia_actual}cm) o sin encarar "
              f"(alineado={alineado}) -> nos recolocamos marcha atras")
        _recolocar_ante_pilar(color_id)

    # Camara al frente: las dos fases se deciden solo con la brujula.
    hardware.SERVOcam.duty_u16(pulso_barrido(0))

    # === FASE 1: giramos hacia lado_evasion hasta sumar/restar ANGULO_GIRO_ESQUIVE ===
    rumbo_inicial = hardware.mag.heading()
    hardware.servoDireccion.duty_u16(lado_evasion)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    while True:
        rumbo_actual = hardware.mag.heading()
        cambio = diferencia_angular(rumbo_actual, rumbo_inicial)

        if cambio * signo_giro >= hardware.ANGULO_GIRO_ESQUIVE:
            print(f"ESQUIVAR_PILAR Fase1: giro completado ({cambio:.1f} grados)")
            break

        _comprobar_lineas()
        time.sleep_ms(20)

    # === TRAMO RECTO entre Fase 1 y Fase 2 ===
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_RECTO_ENTRE_FASES_MS:
        _comprobar_lineas()
        time.sleep_ms(20)

    if not fase2:
        _terminar_maniobra()
        print("ESQUIVAR_PILAR: maniobra completada sin Fase 2")
        return None, None

    # === FASE 2: giramos hacia lado_contrario hasta recuperar el rumbo inicial
    # (o hasta rumbo_fase2, si nos lo han dado) ===
    rumbo_objetivo_fase2 = rumbo_inicial if rumbo_fase2 is None else rumbo_fase2
    hardware.servoDireccion.duty_u16(lado_contrario)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    while True:
        rumbo_actual = hardware.mag.heading()
        cambio = diferencia_angular(rumbo_actual, rumbo_objetivo_fase2)

        if cambio * signo_giro <= 0:
            print(f"ESQUIVAR_PILAR Fase2: rumbo recuperado ({cambio:.1f} grados)")
            break

        _comprobar_lineas()
        time.sleep_ms(20)

    # === TRAMO RECTO tras Fase 2 ===
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.servoTraccion.duty_u16(hardware.Avanza_lento)

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < hardware.TIEMPO_RECTO_TRAS_FASE2_MS:
        _comprobar_lineas()
        time.sleep_ms(20)

    _terminar_maniobra()
    print("ESQUIVAR_PILAR: maniobra completada")
    return None, None


# ==========================================
# SALIDA Y FINAL DE LAS MISIONES 3 Y 4
# ==========================================
def bloques_tras_mover():
    """Bloques de la Huskylens despues de mover la camara (con el robot
    parado). La primera lectura puede traer todavia una imagen de ANTES del
    movimiento (la Huskylens va con retraso) y nos haria creer que un pilar
    esta en otra direccion: la tiramos y nos quedamos con la siguiente."""
    _obtener_bloques()
    time.sleep_ms(50)
    return _obtener_bloques()


def mover_camara(destino, actual):
    """Movemos la camara (robot parado) y esperamos segun lo que tiene que
    girar el servo, para que la imagen siguiente sea ya la de la posicion
    nueva. Devolvemos el angulo al que la hemos dejado."""
    hardware.SERVOcam.duty_u16(pulso_barrido(destino))
    time.sleep_ms(200 + 3 * int(abs(destino - actual)))  # AJUSTAR EN PISTA
    return destino


def centrar_pilar(cam, bloque, intentos=4):
    """Con el robot parado, movemos la camara poco a poco hasta tener el
    bloque en el centro de la imagen. Devolvemos (angulo de la camara,
    bloque, error en px) al terminar; si el bloque desaparece, el ultimo que
    vimos."""
    for _ in range(intentos):
        error_px = bloque.x_center - hardware.FRAME_CENTRO_X
        if abs(error_px) <= 20:
            break
        nuevo_cam = max(hardware.ANGULO_SERVO_MIN, min(cam + error_px * hardware.PX_A_GRADOS_CAMARA, hardware.ANGULO_SERVO_MAX))
        if abs(nuevo_cam - cam) < 0.5:
            # En el tope del servo: no podemos girar mas. Releemos una vez por
            # si la imagen era de antes de que la camara llegase al tope.
            time.sleep_ms(150)
            mismos = [b for b in bloques_tras_mover() if b.id == bloque.id]
            if mismos:
                bloque = min(mismos, key=lambda b: abs(b.x_center - hardware.FRAME_CENTRO_X))
            break
        cam = nuevo_cam
        hardware.SERVOcam.duty_u16(pulso_barrido(cam))
        time.sleep_ms(200)
        mismos = [b for b in bloques_tras_mover() if b.id == bloque.id]
        if not mismos:
            break
        bloque = min(mismos, key=lambda b: abs(b.x_center - hardware.FRAME_CENTRO_X))
    return cam, bloque, bloque.x_center - hardware.FRAME_CENTRO_X


def escanear_calle_0(miradas):
    """Justo despues de desaparcar: que pilares hay en la calle 0. El robot se
    para siempre en el mismo sitio, mirando al muro interior, y en la calle
    de salida todos los pilares van en la fila interior: asientos a, b, c
    (a = el primero en el sentido de la marcha). Cada asiento se ve siempre
    en la misma direccion y a la misma distancia, distinta en M3 y en M4:
    las miradas las pasa cada mision (ver MIRADAS_CALLE_0 en mision3_cw.py y
    mision4_ccw.py), con el formato
        (asiento, camara, direccion min, max, distancia TFmini min, max, base min, max)
    Hacemos TRES miradas con el foco apagado. Si en
    una aparece un pilar cercano (base de 100 o mas), lo centramos moviendo
    un poco la camara y medimos su distancia con el TFmini: asi la direccion
    y la distancia son precisas aunque el robot haya quedado un poco
    distinto al desaparcar (por ejemplo, con las baterias mas bajas). Si no
    podemos centrarlo (el asiento a queda mas alla del tope del servo) o el
    TFmini no da lectura, usamos la BASE del bloque como medida de la
    distancia. Lo que sale mas lejos (pilares de otras calles, o vistos por
    encima del muro interior) lo ignoramos.
    Guardamos el resultado en hardware.pilares_calle0, por ejemplo
    {'a': 'R', 'b': None, 'c': 'V'}, para el aparcamiento."""
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.foco_apagar()  # de cerca y de frente, el reflejo del foco nos haria perder algun pilar
    time.sleep_ms(300)      # robot parado
    theta0 = diferencia_angular(hardware.mag.heading(), hardware.rumbo_calle[0])
    t0 = time.ticks_ms()
    print("========== ESCANEO CALLE 0 ==========")
    print(f"Rumbo del robot respecto a la calle 0 = {theta0:.1f} grados (positivo a la derecha)")

    resultado = {'a': None, 'b': None, 'c': None}
    direcciones = {}  # direccion (respecto al frente del robot) de cada pilar clasificado
    vistos = []     # direcciones de los pilares ya centrados (para no repetirlos)
    cam_actual = 0  # la camara viene del centro
    for asiento, cam_mirada, dir_min, dir_max, d_min, d_max, base_min, base_max in miradas:
        # Hasta 3 pilares por mirada. Antes de cada uno volvemos a la mirada y
        # pedimos una imagen NUEVA: si usaramos la lista de bloques de antes
        # de centrar el anterior, sus posiciones ya no corresponderian a donde
        # esta la camara y saldrian pilares fantasma.
        for _ in range(3):
            if resultado[asiento] is not None:
                break  # este asiento ya lo tenemos (quiza visto desde otra mirada)
            cam_actual = mover_camara(cam_mirada, cam_actual)
            candidato = None
            # Primero los mas cercanos (base mas abajo en la imagen). Ignoramos
            # los que asoman por el borde de la imagen (a mas de 260 px del
            # centro): su caja sale cortada, su direccion aproximada no es
            # fiable y casi siempre son pilares que ya hemos medido desde otra
            # mirada. Y un pilar a menos de 10 grados de uno ya medido es el
            # mismo.
            for b in sorted(bloques_tras_mover(), key=lambda b: -(b.y_center + b.height // 2)):
                base = b.y_center + b.height // 2
                direccion_aprox = cam_mirada + (b.x_center - hardware.FRAME_CENTRO_X) * hardware.PX_A_GRADOS_CAMARA
                if b.id in (1, 2) and base >= 100 and abs(b.x_center - hardware.FRAME_CENTRO_X) <= 260 \
                        and all(abs(direccion_aprox - v) > 10 for v in vistos):
                    candidato = b
                    break
            if candidato is None:
                break
            color = 'R' if candidato.id == 1 else 'V'
            cam, b, error_px = centrar_pilar(cam_mirada, candidato)
            cam_actual = cam
            base = b.y_center + b.height // 2
            direccion = cam + error_px * hardware.PX_A_GRADOS_CAMARA
            if any(abs(direccion - v) <= 10 for v in vistos):
                vistos.append(direccion)
                continue  # ya centrado, resulta ser uno que ya teniamos
            vistos.append(direccion)
            d = None
            if abs(error_px) <= 40:
                lecturas = [x for x in (leer_tfmini() for _ in range(5)) if x is not None]
                d = sum(lecturas) / len(lecturas) if lecturas else None
            # Lo comparamos con los TRES asientos, no solo con el de esta
            # mirada: si el robot ha quedado algo mas girado al desaparcar, un
            # pilar puede aparecer en la mirada de otro asiento
            if d is not None:
                medida = f"TFmini {d:.0f} cm"
            else:
                medida = f"base {base} (sin centrar o sin TFmini)"
            encontrado = None
            for (asiento_m, _c, dmin, dmax, dist_min, dist_max, bmin, bmax) in miradas:
                if resultado[asiento_m] is not None or not (dmin <= direccion <= dmax):
                    continue
                if (d is not None and dist_min <= d <= dist_max) or (d is None and bmin <= base <= bmax):
                    encontrado = asiento_m
                    break
            print(f"  mirada {asiento} (cam {cam_mirada}): {color} centrado en cam {cam:.1f} err={error_px}px "
                  f"direccion={direccion:.1f} {medida} -> {'ASIENTO ' + encontrado if encontrado else 'no es de la calle 0'}")
            if encontrado:
                resultado[encontrado] = color
                direcciones[encontrado] = direccion
    # Camara al centro y esperamos a que llegue (viene de 90 grados) antes de
    # seguir: si no, el primer vistazo de la mision recibe una imagen de
    # cuando la camara miraba al asiento a y cree tener un pilar delante
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    time.sleep_ms(200 + 3 * int(abs(cam_actual)))
    bloques_tras_mover()  # tiramos la imagen vieja
    hardware.pilares_calle0 = resultado
    hardware.direcciones_calle0 = direcciones
    hardware.foco_brillo(1.0)  # volvemos a buscar con el foco a tope
    print(f"PILARES CALLE 0: a={resultado['a']} b={resultado['b']} c={resultado['c']} "
          f"({time.ticks_diff(time.ticks_ms(), t0)} ms)")
    print("========== FIN DEL ESCANEO CALLE 0 ==========")


def escanear_calle_0_datos(desde=-90, hasta=60, paso=20):
    """TOMA DE DATOS del escaneo de la calle 0 (para una mision cuyos
    angulos aun no conocemos, como M4). Con el robot parado tras desaparcar
    y el foco apagado, barremos la camara de 'desde' a 'hasta' y, para cada
    pilar cercano (base de 100 o mas), lo centramos, medimos su distancia con
    el TFmini e imprimimos su direccion respecto al frente del robot, su
    distancia y su base. Dos pilares a menos de 6 grados los tomamos por el
    mismo. No clasificamos nada: hardware.pilares_calle0 queda en None (en la
    fase final aceptaremos entonces el primer pilar que veamos)."""
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.foco_apagar()
    time.sleep_ms(300)
    theta0 = diferencia_angular(hardware.mag.heading(), hardware.rumbo_calle[0])
    t0 = time.ticks_ms()
    print("========== ESCANEO CALLE 0: TOMA DE DATOS ==========")
    print(f"Rumbo del robot respecto a la calle 0 = {theta0:.1f} grados (positivo a la derecha)")
    medidos = []
    cam_actual = 0
    cam_mirada = desde
    while cam_mirada <= hasta:
        # Hasta 3 pilares por mirada; antes de cada uno, volvemos a la mirada
        # y pedimos una imagen nueva (ver escanear_calle_0)
        for _ in range(3):
            cam_actual = mover_camara(cam_mirada, cam_actual)
            candidato = None
            for b in sorted(bloques_tras_mover(), key=lambda b: -(b.y_center + b.height // 2)):
                base = b.y_center + b.height // 2
                direccion_aprox = cam_mirada + (b.x_center - hardware.FRAME_CENTRO_X) * hardware.PX_A_GRADOS_CAMARA
                if b.id in (1, 2) and base >= 100 and all(abs(direccion_aprox - m) > 6 for m in medidos):
                    candidato = b
                    break
            if candidato is None:
                break
            cam, b, error_px = centrar_pilar(cam_mirada, candidato)
            cam_actual = cam
            base = b.y_center + b.height // 2
            direccion = cam + error_px * hardware.PX_A_GRADOS_CAMARA
            medidos.append(direccion)
            if sum(1 for m in medidos if abs(direccion - m) <= 6) > 1:
                continue  # ya lo teniamos
            d = None
            if abs(error_px) <= 40:
                lecturas = [x for x in (leer_tfmini() for _ in range(5)) if x is not None]
                d = sum(lecturas) / len(lecturas) if lecturas else None
            color = 'ROJO' if b.id == 1 else 'VERDE'
            dist_txt = 'sin medida' if d is None else '{:.0f} cm'.format(d)
            print(f"  PILAR {color}: cam {cam:.1f} err={error_px}px direccion={direccion:.1f} "
                  f"dist={dist_txt} base={base}")
        cam_mirada += paso
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    time.sleep_ms(200 + 3 * int(abs(cam_actual)))
    bloques_tras_mover()  # tiramos la imagen vieja
    hardware.pilares_calle0 = None
    hardware.foco_brillo(1.0)
    print(f"========== FIN DEL ESCANEO CALLE 0 ({len(medidos)} pilares, "
          f"{time.ticks_diff(time.ticks_ms(), t0)} ms) ==========")


def fase_final_si_toca():
    """(Mision 3 y Mision 4) Al contar la ultima linea no nos paramos: pasamos a la FASE FINAL y
    seguimos con el bucle de siempre (terminamos de girar la esquina, nos
    alineamos con la calle 0 y, si hay pilar en el asiento a, lo esquivamos
    como en cualquier vuelta; solo esos: hardware.final_pendientes). NAVEGAR_CALLE se para a hardware.distancia_parada_final de la pared
    del fondo (hardware.parados_en_salida). Para que las funciones de siempre
    no se detengan por la meta, la subimos. Seguridad: si aun asi contamos
    una linea mas (la de la esquina siguiente), nos paramos.
    Devolvemos True si hay que terminar ya."""
    if getattr(hardware, 'parados_en_salida', False):
        return True
    if not getattr(hardware, 'fase_final', False):
        if hardware.contadorLineas >= hardware.TOTAL_LINEAS_META:
            hardware.fase_final = True
            hardware.meta_original = hardware.TOTAL_LINEAS_META
            hardware.TOTAL_LINEAS_META = 99
            # Lo unico que nos queda por esquivar es el pilar del asiento a (el
            # escaneo de la salida nos dice si esta y de que color); cualquier
            # otro pilar (b, c, de otras calles) lo ignoramos
            # Los asientos que pasamos antes de pararnos los fija cada mision
            # en hardware.asientos_finales: en M3 solo el a; en M4 el a y el b
            pilares = getattr(hardware, 'pilares_calle0', None)
            asientos = getattr(hardware, 'asientos_finales', ('a',))
            if pilares is None:
                # Escaneo solo de toma de datos: no sabemos que hay en esos
                # asientos, asi que aceptamos el primer pilar que veamos
                texto = 'desconocido'
                hardware.final_pendientes = [0]
            else:
                texto = ', '.join(f"{x}={pilares.get(x)}" for x in asientos)
                hardware.final_pendientes = [1 if pilares.get(x) == 'R' else 2
                                             for x in asientos if pilares.get(x) in ('R', 'V')]
            hardware.final_color_pendiente = hardware.final_pendientes[0] if hardware.final_pendientes else None
            parada = getattr(hardware, 'distancia_parada_final', 160)
            print(f"--- ULTIMA LINEA: FASE FINAL (asientos por esquivar: {texto}), "
                  f"seguimos hasta {parada} cm de la pared del fondo de la calle 0 ---")
        return False
    if hardware.contadorLineas > hardware.meta_original:
        print("--- FASE FINAL: hemos contado otra linea sin pararnos -> paramos aqui ---")
        hardware.parados_en_salida = True
        return True
    return False


def final_pilar_esquivado():
    """Fase final: acabamos de esquivar uno de los pilares que teniamos
    pendientes en la calle 0. Pasamos al siguiente (o a ninguno)."""
    pendientes = getattr(hardware, 'final_pendientes', [])
    if pendientes:
        pendientes.pop(0)
    hardware.final_color_pendiente = pendientes[0] if pendientes else None
    print(f"--- FASE FINAL: pilar esquivado; pendientes ahora: {pendientes} ---")