"""
TEST DE BANCO - Latencia de la Huskylens 2 con la camara en movimiento.
El robot NO se mueve: solo gira el servo de la camara.

Colocamos UN pilar (rojo o verde) a unos 50 cm de frente. La camara da saltos
de -8 a +8 grados y al reves (16 grados, unos 200 px de desplazamiento en la
imagen). En cada salto pedimos bloques sin parar y apuntamos cuando cambia el
x_center del pilar. Medimos:
  - TIEMPO HASTA PRIMER CAMBIO: desde la orden al servo hasta que la
    Huskylens 2 informa de un x distinto (retraso de la imagen + arranque del servo).
  - TIEMPO HASTA ASENTARSE: hasta que el x ya no cambia mas (servo + retraso).
  - PERIODO ENTRE ACTUALIZACIONES: cada cuantos ms nos llega un x nuevo
    (si es mucho mayor que lo que tardamos en preguntar, leemos datos repetidos).
"""
import time
import hardware

ANGULOS = (-8, 8, -8, 8, -8, 8)
VENTANA_MS = 700
TOLERANCIA_PX = 10


def pulso(angulo):
    return int(hardware.Cam_Centro - angulo * hardware.GRADOS_A_PULSO)


def x_pilar():
    bloques = hardware.husky.get_blocks(solo_aprendidos=True)
    if not bloques:
        return None
    return max(bloques, key=lambda b: b.y_center).x_center


def mediana(v):
    v = sorted(v)
    return v[len(v) // 2]


hardware.servoTraccion.duty_u16(hardware.Para)
hardware.SERVOcam.duty_u16(pulso(0))

print("Esperando a la Huskylens 2 ...")
t0 = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), t0) < 12000:
    if hardware.husky.get_blocks(solo_aprendidos=False):
        break
    time.sleep_ms(200)
time.sleep_ms(2000)

res_primer = []
res_asentado = []
res_periodo = []

for i in range(len(ANGULOS)):
    ang = ANGULOS[i]
    # Posicion de partida: el angulo contrario, bien asentado
    hardware.SERVOcam.duty_u16(pulso(-ang))
    time.sleep_ms(1000)

    # Salto y registro de (t_ms, x)
    t_ini = time.ticks_ms()
    hardware.SERVOcam.duty_u16(pulso(ang))
    muestras = []
    while time.ticks_diff(time.ticks_ms(), t_ini) < VENTANA_MS:
        x = x_pilar()
        muestras.append((time.ticks_diff(time.ticks_ms(), t_ini), x))

    validas = [(t, x) for (t, x) in muestras if x is not None]
    if len(validas) < 10:
        print("Salto {} a {:+d} grados: pilar no visible (solo {} lecturas validas). Lo centramos.".format(i, ang, len(validas)))
        continue

    x_ini = mediana([x for (t, x) in validas[:2]])
    x_fin = mediana([x for (t, x) in validas[-5:]])
    if abs(x_fin - x_ini) < 5 * TOLERANCIA_PX:
        print("Salto {} a {:+d} grados: el pilar casi no se desplaza ({} -> {} px), descartado.".format(i, ang, x_ini, x_fin))
        continue

    t_primer = None
    for (t, x) in validas:
        if abs(x - x_ini) > TOLERANCIA_PX:
            t_primer = t
            break
    t_asent = 0
    for (t, x) in validas:
        if abs(x - x_fin) > TOLERANCIA_PX:
            t_asent = t
    # Periodo entre actualizaciones: tiempo medio entre cambios de x mientras se mueve
    cambios = []
    anterior = validas[0][1]
    for (t, x) in validas:
        if x != anterior:
            cambios.append(t)
            anterior = x
    periodo = None
    if len(cambios) >= 3:
        periodo = (cambios[-1] - cambios[0]) / (len(cambios) - 1)

    print("Salto {} a {:+d} grados: x {} -> {} px | primer cambio {} ms | asentado {} ms | periodo entre actualizaciones {}".format(
        i, ang, x_ini, x_fin, t_primer,
        t_asent, "{:.0f} ms".format(periodo) if periodo else "sin datos"))
    if t_primer is not None:
        res_primer.append(t_primer)
    res_asentado.append(t_asent)
    if periodo:
        res_periodo.append(periodo)

hardware.SERVOcam.duty_u16(hardware.Cam_Centro)

print("\n=== Resumen ===")
if res_primer:
    print("Tiempo hasta el primer cambio (mediana): {} ms".format(mediana(res_primer)))
    print("Tiempo hasta asentarse (mediana): {} ms".format(mediana(res_asentado)))
if res_periodo:
    print("Periodo entre actualizaciones de x (mediana): {:.0f} ms".format(mediana(res_periodo)))
if not res_primer:
    print("Ningun salto valido: comprobamos que el pilar esta centrado, a la vista y a ~50 cm.")