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

    # En la fase final no miramos al frente sin mas: NAVEGAR_CALLE filtra los
    # pilares (solo el del asiento a) y se para a 160 cm de la pared del fondo
    if not getattr(hardware, 'fase_final', False):
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


def _bloques_tras_mover():
    """Bloques de la Huskylens despues de mover la camara (con el robot
    parado). La primera lectura puede traer todavia una imagen de ANTES del
    movimiento (la Huskylens va con retraso) y nos haria creer que un pilar
    esta en otra direccion: la tiramos y nos quedamos con la siguiente."""
    _obtener_bloques()
    time.sleep_ms(50)
    return _obtener_bloques()


def _barrer_pilares(angulo_desde, angulo_hasta, direccion_base, paso=5):
    """Con el robot PARADO, barremos la camara de angulo_desde a angulo_hasta
    y medimos cada pilar que aparece: lo centramos en la imagen (como mucho 6
    correcciones) y leemos el TFmini frontal, que va en el mismo servo.
    direccion_base: lo que sumamos al angulo de la camara para dar la
    direccion de cada pilar (theta respecto al norte en _aparcar, 0 si la
    queremos respecto al frente del robot). Dos pilares a menos de 6 grados
    los tomamos por el mismo. Devolvemos una lista de diccionarios con id,
    cam, err, base, d (cm, None sin lectura o 'descartado' si no se ha podido
    centrar) y direccion."""
    pilares = []
    medidos = []   # direcciones de los pilares ya medidos
    angulo = angulo_desde
    while angulo <= angulo_hasta and len(medidos) < 6:
        hardware.SERVOcam.duty_u16(pulso_barrido(angulo))
        time.sleep_ms(200)  # robot parado: dejamos que la imagen se ponga al dia
        bloques = _bloques_tras_mover()
        nuevo = None
        for b in bloques:
            direccion_aprox = direccion_base + angulo + (b.x_center - hardware.FRAME_CENTRO_X) * hardware.PX_A_GRADOS_CAMARA
            if all(abs(direccion_aprox - m) > 6 for m in medidos):  # AJUSTAR EN PISTA: grados entre pilares distintos
                nuevo = b
                break
        if nuevo is None:
            angulo += paso
            continue

        # Centramos el pilar nuevo en la imagen
        objetivo = nuevo
        cam = angulo
        for _ in range(6):
            error_px = objetivo.x_center - hardware.FRAME_CENTRO_X
            if abs(error_px) <= 20:
                break
            cam = max(hardware.ANGULO_SERVO_MIN, min(cam + error_px * hardware.PX_A_GRADOS_CAMARA, hardware.ANGULO_SERVO_MAX))
            hardware.SERVOcam.duty_u16(pulso_barrido(cam))
            time.sleep_ms(250)
            mismos = [b for b in _bloques_tras_mover() if b.id == objetivo.id]
            if not mismos:
                break
            objetivo = min(mismos, key=lambda b: abs(b.x_center - hardware.FRAME_CENTRO_X))
        error_px = objetivo.x_center - hardware.FRAME_CENTRO_X
        direccion = direccion_base + cam + error_px * hardware.PX_A_GRADOS_CAMARA
        # Seguimos barriendo mas alla de este pilar, y nunca hacia atras
        siguiente = max(angulo + paso, int(cam) + 10)
        if any(abs(direccion - m) <= 6 for m in medidos):
            # Ya centrado, resulta ser uno que ya teniamos: la Huskylens nos
            # dio una imagen de antes de mover la camara y el pilar parecia
            # estar en otra direccion. No lo contamos dos veces.
            angulo = siguiente
            continue
        medidos.append(direccion)
        base = objetivo.y_center + objetivo.height // 2
        if abs(error_px) > 60:  # AJUSTAR EN PISTA: px
            # No hemos podido centrarlo (por ejemplo, con la camara al tope de
            # 90 grados): el TFmini no le apunta, asi que no lo usamos
            d = 'descartado'
        else:
            lecturas = [x for x in (leer_tfmini() for _ in range(5)) if x is not None]
            d = sum(lecturas) / len(lecturas) if lecturas else None
        pilares.append({'id': objetivo.id, 'cam': cam, 'err': error_px, 'base': base, 'd': d, 'direccion': direccion})
        angulo = siguiente
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    return pilares


def _centrar_pilar(cam, bloque, intentos=4):
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
            mismos = [b for b in _bloques_tras_mover() if b.id == bloque.id]
            if mismos:
                bloque = min(mismos, key=lambda b: abs(b.x_center - hardware.FRAME_CENTRO_X))
            break
        cam = nuevo_cam
        hardware.SERVOcam.duty_u16(pulso_barrido(cam))
        time.sleep_ms(200)
        mismos = [b for b in _bloques_tras_mover() if b.id == bloque.id]
        if not mismos:
            break
        bloque = min(mismos, key=lambda b: abs(b.x_center - hardware.FRAME_CENTRO_X))
    return cam, bloque, bloque.x_center - hardware.FRAME_CENTRO_X


def _escanear_calle_0():
    """Justo despues de desaparcar: que pilares hay en la calle 0. El robot se
    para siempre en el mismo sitio, mirando al muro interior (girado unos
    57-60 grados respecto a la calle 0), y en la calle de salida todos los
    pilares van en la fila interior: asientos a, b, c. Medido en pista (M3):
        a: +92 grados (tope del servo, a la derecha), 42 cm, base ~210
        b:   0 a +6 grados (justo delante),           27 cm, base ~310-325
        c: -35 grados (a la izquierda),               65 cm, base ~156
    Hacemos TRES miradas (camara a 0, -35 y 90) con el foco apagado. Si en
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

    # AJUSTAR EN PISTA si la camara cambia de inclinacion o el robot de sitio al desaparcar.
    # (asiento, camara, direccion min, max, distancia TFmini min, max, base min, max)
    miradas = (
        ('b', 0, -20, 20, 15, 40, 250, 480),
        ('c', -35, -55, -15, 45, 85, 110, 230),
        ('a', 90, 60, 120, 25, 60, 150, 330),
    )
    resultado = {'a': None, 'b': None, 'c': None}
    cam_actual = 0  # la camara viene del centro
    for asiento, cam_mirada, dir_min, dir_max, d_min, d_max, base_min, base_max in miradas:
        hardware.SERVOcam.duty_u16(pulso_barrido(cam_mirada))
        # Esperamos segun lo que tiene que girar el servo: de -35 a 90 grados
        # tarda bastante mas que de 0 a -35, y una imagen tomada con la camara
        # aun en camino da una direccion equivocada
        time.sleep_ms(150 + 3 * int(abs(cam_mirada - cam_actual)))
        cam_actual = cam_mirada
        bloques = _bloques_tras_mover()
        # Primero los mas cercanos (base mas abajo en la imagen)
        for b in sorted(bloques, key=lambda b: -(b.y_center + b.height // 2)):
            color = 'R' if b.id == 1 else 'V' if b.id == 2 else f"id{b.id}"
            base = b.y_center + b.height // 2
            if resultado[asiento] is not None or b.id not in (1, 2) or base < 100:
                print(f"  mirada {asiento} (cam {cam_mirada}): {color} x={b.x_center} base={base} -> lejos o sobra, no lo miramos")
                continue
            cam, b, error_px = _centrar_pilar(cam_mirada, b)
            base = b.y_center + b.height // 2
            direccion = cam + error_px * hardware.PX_A_GRADOS_CAMARA
            d = None
            if abs(error_px) <= 40:
                lecturas = [x for x in (leer_tfmini() for _ in range(5)) if x is not None]
                d = sum(lecturas) / len(lecturas) if lecturas else None
            if d is not None:
                vale = dir_min <= direccion <= dir_max and d_min <= d <= d_max
                medida = f"TFmini {d:.0f} cm"
            else:
                vale = dir_min <= direccion <= dir_max and base_min <= base <= base_max
                medida = f"base {base} (sin centrar o sin TFmini)"
            print(f"  mirada {asiento} (cam {cam_mirada}): {color} centrado en cam {cam:.1f} err={error_px}px "
                  f"direccion={direccion:.1f} {medida} -> {'ASIENTO ' + asiento if vale else 'no es de la calle 0'}")
            if vale:
                resultado[asiento] = color
            hardware.SERVOcam.duty_u16(pulso_barrido(cam_mirada))  # volvemos a la mirada por si hay otro bloque
    # Camara al centro y esperamos a que llegue (viene de 90 grados) antes de
    # seguir: si no, el primer vistazo de la mision recibe una imagen de
    # cuando la camara miraba al asiento a y cree tener un pilar delante
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    time.sleep_ms(150 + 3 * int(abs(cam_actual)))
    _bloques_tras_mover()  # tiramos la imagen vieja
    hardware.pilares_calle0 = resultado
    hardware.foco_brillo(1.0)  # volvemos a buscar con el foco a tope
    print(f"PILARES CALLE 0: a={resultado['a']} b={resultado['b']} c={resultado['c']} "
          f"({time.ticks_diff(time.ticks_ms(), t0)} ms)")
    print("========== FIN DEL ESCANEO CALLE 0 ==========")


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
    pilares = _barrer_pilares(-20, 90, theta)
    for n, p in enumerate(pilares, 1):
        if p['d'] == 'descartado':
            print(f"PILAR descartado: id={p['id']} cam={p['cam']:.1f} err={p['err']}px (no se ha podido centrar)")
            continue
        print(f"PILAR {n}: id={p['id']} cam={p['cam']:.1f} err={p['err']}px base={p['base']} "
              f"dist={p['d']} -> direccion respecto al norte={p['direccion']:.1f} grados")
        if p['d'] is not None and x_robot is not None and y_robot is not None:
            r = math.radians(p['direccion'])
            x_p = x_robot + p['d'] * math.sin(r)
            y_p = y_robot - p['d'] * math.cos(r)
            posicion = 'PRINCIPIO' if x_p < 125 else ('CENTRO' if x_p < 175 else 'FINAL')
            fila = 'interior' if y_p >= 50 else 'exterior'
            print(f"         x_pilar = {x_p:.0f} cm, y_pilar = {y_p:.0f} cm -> parece {posicion}, fila {fila}")
    print(f"========== FIN DE LA TOMA DE DATOS ({len(pilares)} pilares) ==========")


def _fase_final_si_toca():
    """Al contar la ultima linea no nos paramos: pasamos a la FASE FINAL y
    seguimos con el bucle de siempre (terminamos de girar la esquina, nos
    alineamos con la calle 0 y, si hay pilar en el asiento a, lo esquivamos
    como en cualquier vuelta; solo ese: hardware.final_color_pendiente). NAVEGAR_CALLE se para a 160 cm de la pared
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
            pilar_a = (getattr(hardware, 'pilares_calle0', None) or {}).get('a')
            hardware.final_color_pendiente = 1 if pilar_a == 'R' else 2 if pilar_a == 'V' else None
            print(f"--- ULTIMA LINEA: FASE FINAL (pilar en el asiento a: {pilar_a}), "
                  f"seguimos hasta 160 cm de la pared del fondo de la calle 0 ---")
        return False
    if hardware.contadorLineas > hardware.meta_original:
        print("--- FASE FINAL: hemos contado otra linea sin pararnos -> paramos aqui ---")
        hardware.parados_en_salida = True
        return True
    return False


def ejecutar_mision_3_cw(angulo_inicial=None, color_inicial=None):
    """MISION 3 (CW): navega por deteccion de pilares (no por pared): busca el
    pilar mas cercano, se aproxima manteniendolo centrado con la Huskylens, lo
    esquiva por el lado que marca su color (regla oficial: ROJO=derecha,
    VERDE=izquierda), y vuelve a buscar el siguiente.
    angulo_inicial/color_inicial: si main.py ya localizo el primer pilar, se
    va directo a aproximarse_a_pilar() sin barrer de nuevo. rumbo_calle,
    color_esquina y color_conteo los prepara main.py antes de llamar."""
    global _pilar_en_curso
    _escanear_calle_0()  # recien desaparcados: miramos que pilares hay en la calle 0
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
            if _fase_final_si_toca():
                break
            print("--- nada encontrado, se reintenta ---")
            continue

        print("--- aproximarse_a_pilar() ---")
        _pilar_en_curso = color_encontrado
        color_real, alineado = aproximarse_a_pilar(angulo_encontrado, color_encontrado)
        if hardware.contadorLineas < hardware.TOTAL_LINEAS_META:
            _pilar_en_curso = None  # si hemos parado por la ultima linea, lo conservamos para _aparcar()

        if color_real is None:
            if _fase_final_si_toca():
                break
            print("--- pilar perdido durante la aproximacion, se reintenta ---")
            continue

        print(f"--- esquivar_pilar(color={color_real}) ---")
        if getattr(hardware, 'fase_final', False):
            hardware.final_color_pendiente = None  # ya esquivado el del asiento a: no buscamos mas pilares
        # Sin Fase 2 para el ROJO: lo esquivamos por el lado hacia el que gira el
        # circuito y asi quedamos ya orientados hacia la esquina
        angulo_siguiente, color_siguiente = esquivar_pilar(color_real, alineado, fase2=(color_real != 1))
        hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
        print(f"--- ciclo completado, contadorLineas={hardware.contadorLineas}/{hardware.TOTAL_LINEAS_META} ---")

        if _fase_final_si_toca():
            break

        if angulo_siguiente is not None and not getattr(hardware, 'fase_final', False):
            angulo_pendiente = angulo_siguiente
            color_pendiente = color_siguiente

    # Parados en la zona de salida (_aparcar(), la toma de datos del
    # aparcamiento, queda para mas adelante): medimos donde nos hemos quedado
    hardware.servoTraccion.duty_u16(hardware.Para)
    hardware.servoDireccion.duty_u16(hardware.Recto)
    hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
    time.sleep_ms(500)
    lecturas = [d for d in (leer_tfmini() for _ in range(5)) if d is not None]
    final = sum(lecturas) / len(lecturas) if lecturas else None
    print(f"ZONA DE SALIDA: PARADOS a {final} cm de la pared del fondo, rumbo {hardware.mag.heading():.1f} "
          f"(calle 0 = {hardware.rumbo_calle[0]:.1f}), calle {hardware.calle_actual}, lineas {hardware.contadorLineas}")
    print("--- MISION 3 COMPLETADA CON EXITO ---")
    while True:
        hardware.ledR.value(1)
        hardware.ledV.value(1)
        time.sleep_ms(500)