"""
TEST DE BANCO - Calibracion de la camara (Huskylens 2) sobre su servo.
El robot NO se mueve: solo gira el servo de la camara.

Colocamos el robot parado y UN pilar (rojo o verde) a unos 50 cm de frente,
bien centrado y a la altura de la camara. Sin nadie moviendo cosas delante.

Que hace:
  1. Espera a que la Huskylens 2 este lista (devuelve algun bloque).
  2. RUIDO: con la camara a 0 grados, hace 40 lecturas del x_center del pilar
     y calcula la dispersion. De ahi proponemos DEADBAND_PX.
  3. BARRIDO: gira la camara de -20 a +20 grados en pasos de 5 y mide el
     x_center del pilar en cada posicion. Ajustamos una recta x = a + b*grados.
     Como el servo gira a la derecha con angulo positivo, el pilar debe
     desplazarse hacia la izquierda de la imagen (b negativo). De b sale
     PX_A_GRADOS_CAMARA = 1 / |b|.
  4. Deja la camara otra vez en el centro.

Si en alguna posicion no se ve el pilar, la saltamos y lo indicamos.
"""
import time
import hardware

ANGULOS = (-20, -15, -10, -5, 0, 5, 10, 15, 20)
LECTURAS_RUIDO = 40
LECTURAS_POR_ANGULO = 10
ESPERA_SERVO_MS = 600


def pulso(angulo):
    return int(hardware.Cam_Centro - angulo * hardware.GRADOS_A_PULSO)


def x_pilar():
    """x_center del pilar aprendido mas cercano (mayor y_center), o None."""
    bloques = hardware.husky.get_blocks(solo_aprendidos=True)
    if not bloques:
        return None
    return max(bloques, key=lambda b: b.y_center).x_center


def media_desv(valores):
    n = len(valores)
    m = sum(valores) / n
    d = (sum((v - m) ** 2 for v in valores) / n) ** 0.5
    return m, d


def mediana(valores):
    v = sorted(valores)
    return v[len(v) // 2]


hardware.servoTraccion.duty_u16(hardware.Para)
hardware.SERVOcam.duty_u16(pulso(0))

print("Esperando a la Huskylens 2 ...")
t0 = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), t0) < 12000:
    if hardware.husky.get_blocks(solo_aprendidos=False):
        break
    time.sleep_ms(200)
time.sleep_ms(ESPERA_SERVO_MS)

print("\n=== 1. Ruido con la camara a 0 grados ===")
xs = []
for _ in range(LECTURAS_RUIDO):
    x = x_pilar()
    if x is not None:
        xs.append(x)
    time.sleep_ms(30)
if len(xs) < LECTURAS_RUIDO // 2:
    print("Pilar visto solo en {} de {} lecturas: comprobamos que esta centrado y a la vista.".format(len(xs), LECTURAS_RUIDO))
    ruido_desv = None
else:
    m, ruido_desv = media_desv(xs)
    print("Lecturas {} de {} | x_center medio {:.1f} | desviacion {:.2f} px | min {} max {} (rango {} px)".format(
        len(xs), LECTURAS_RUIDO, m, ruido_desv, min(xs), max(xs), max(xs) - min(xs)))
    print("Pilar respecto al centro de imagen ({}): {:+.1f} px".format(hardware.FRAME_CENTRO_X, m - hardware.FRAME_CENTRO_X))

print("\n=== 2. Barrido de la camara ===")
puntos = []
for ang in ANGULOS:
    hardware.SERVOcam.duty_u16(pulso(ang))
    time.sleep_ms(ESPERA_SERVO_MS)
    lec = []
    for _ in range(LECTURAS_POR_ANGULO):
        x = x_pilar()
        if x is not None:
            lec.append(x)
        time.sleep_ms(30)
    if len(lec) >= LECTURAS_POR_ANGULO // 2:
        x_med = mediana(lec)
        puntos.append((ang, x_med))
        print("{:+3d} grados -> x_center {} ({} lecturas)".format(ang, x_med, len(lec)))
    else:
        print("{:+3d} grados -> pilar no visible ({} lecturas)".format(ang, len(lec)))

hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

print("\n=== Resultado ===")
if len(puntos) >= 3:
    n = len(puntos)
    sa = sum(p[0] for p in puntos)
    sx = sum(p[1] for p in puntos)
    saa = sum(p[0] * p[0] for p in puntos)
    sax = sum(p[0] * p[1] for p in puntos)
    b = (n * sax - sa * sx) / (n * saa - sa * sa)
    a = (sx - b * sa) / n
    resid = max(abs(p[1] - (a + b * p[0])) for p in puntos)
    print("Recta: x = {:.1f} + {:.2f} * grados | peor desviacion de la recta {:.1f} px ({} puntos)".format(a, b, resid, n))
    if b >= 0:
        print("ATENCION: pendiente positiva. El pilar se mueve en el sentido contrario al esperado: avisamos antes de seguir.")
    else:
        print("Pixeles por grado: {:.2f}".format(-b))
        print("PX_A_GRADOS_CAMARA propuesto: {:.3f} (actual: {})".format(-1 / b, hardware.PX_A_GRADOS_CAMARA))
    if ruido_desv is not None:
        print("DEADBAND_PX: ruido (3 desviaciones) = {:.0f} px, rango visto = {} px (actual: {})".format(
            3 * ruido_desv, max(xs) - min(xs), hardware.DEADBAND_PX))
else:
    print("Menos de 3 posiciones con pilar visible: no podemos ajustar. Acercamos el pilar o lo centramos mejor.")
