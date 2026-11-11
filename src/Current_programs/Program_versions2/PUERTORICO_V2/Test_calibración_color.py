"""
TEST STANDALONE - Calibracion del sensor de color TCS34725 con resumen.

Medimos tres superficies, una a una. Para cada una:
  1) colocamos el sensor sobre ella (o lo pasamos a la velocidad real del robot),
  2) pulsamos el boton del escudo (si no pulsamos en 10 s, saltamos esa superficie),
  3) durante 3 s leemos el sensor lo mas rapido posible y guardamos minimos,
     maximos y medias.
Al final imprimimos un resumen con el margen y el filtro de luz que separan
mejor las tres clases, y cuantas lecturas de cada superficie clasificaria
bien la regla actual de clasificar_color() (margen 0.15, total < 400).

Superficies: BLANCO, NARANJA y AZUL. El sensor va pegado al suelo con una falda
de goma-eva que lo aisla de la luz ambiente, asi que no medimos sombras. Si
queremos medir otra zona dudosa (una junta o un bache), la añadimos a la lista
SUPERFICIES con el color que deberia salir.
"""
from machine import Pin, I2C
from tcs34725 import TCS34725
import time

MARGEN_ACTUAL = 0.15      # el de clasificar_color()
TOTAL_ACTUAL = 400        # el filtro de luz de clasificar_color()
DURACION_MS = 3000        # tiempo de medida de cada superficie
ESPERA_BOTON_MS = 10000   # tiempo para pulsar antes de saltar la superficie

SUPERFICIES = [
    ('BLANCO', 'BLANCO'),
    ('NARANJA', 'NARANJA'),
    ('AZUL', 'AZUL'),
]

pin_boton = Pin(2, Pin.IN, Pin.PULL_DOWN)
led_verde = Pin(10, Pin.OUT)
led_rojo = Pin(22, Pin.OUT)

i2c0 = I2C(0, sda=Pin(4), scl=Pin(5))
sensor_color = TCS34725(i2c0)
print("Sensor listo.")


def clasificar(r, g, b):
    """Misma regla que clasificar_color() de funciones_comunes.py."""
    total = r + g + b
    if total == 0:
        return 'BLANCO'
    pr = r / total
    pb = b / total
    if pb > pr + MARGEN_ACTUAL and total < TOTAL_ACTUAL:
        return 'AZUL'
    if pr > pb + MARGEN_ACTUAL and total < TOTAL_ACTUAL:
        return 'NARANJA'
    return 'BLANCO'


def esperar_boton(timeout_ms):
    """True si pulsan el boton antes del timeout. Espera a que lo suelten."""
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if pin_boton.value() == 1:
            while pin_boton.value() == 1:
                time.sleep_ms(10)
            time.sleep_ms(50)
            return True
        time.sleep_ms(10)
    return False


def medir():
    """Leemos durante DURACION_MS lo mas rapido posible. Devolvemos un
    diccionario con n, ms por lectura y min/max/media de total, r%, b%, r%-b%."""
    n = 0
    suma_total = suma_pr = suma_pb = 0
    mn = {'total': 99999, 'pr': 9, 'pb': 9, 'dif': 9}
    mx = {'total': -1, 'pr': -1, 'pb': -1, 'dif': -9}
    clases = {}
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < DURACION_MS:
        r, g, b, claro = sensor_color.read_rgbc()
        total = r + g + b
        if total == 0:
            continue
        pr = r / total
        pb = b / total
        dif = pr - pb
        n += 1
        suma_total += total
        suma_pr += pr
        suma_pb += pb
        for clave, valor in (('total', total), ('pr', pr), ('pb', pb), ('dif', dif)):
            if valor < mn[clave]:
                mn[clave] = valor
            if valor > mx[clave]:
                mx[clave] = valor
        clase = clasificar(r, g, b)
        clases[clase] = clases.get(clase, 0) + 1
    ms = DURACION_MS / n if n else 0
    return {'n': n, 'ms': ms, 'min': mn, 'max': mx,
            'media_total': suma_total / n if n else 0,
            'media_pr': suma_pr / n if n else 0,
            'media_pb': suma_pb / n if n else 0,
            'clases': clases}


resultados = {}
for nombre, esperado in SUPERFICIES:
    print("\n>>> Coloca el sensor sobre", nombre, "y pulsa el boton (10 s)...")
    led_verde.value(1)
    if not esperar_boton(ESPERA_BOTON_MS):
        led_verde.value(0)
        print("    (saltada)")
        continue
    led_verde.value(0)
    led_rojo.value(1)
    res = medir()
    led_rojo.value(0)
    resultados[nombre] = (esperado, res)
    clases = res['clases']
    bien = clases.get(esperado, 0)
    print(f"    {nombre}: {res['n']} lecturas ({res['ms']:.1f} ms/lectura)")
    print(f"      total  min {res['min']['total']:4d}  media {res['media_total']:6.1f}  max {res['max']['total']:4d}")
    print(f"      r%     min {res['min']['pr']:.2f}  media {res['media_pr']:.2f}  max {res['max']['pr']:.2f}")
    print(f"      b%     min {res['min']['pb']:.2f}  media {res['media_pb']:.2f}  max {res['max']['pb']:.2f}")
    print(f"      r%-b%  min {res['min']['dif']:+.2f}  max {res['max']['dif']:+.2f}")
    print(f"      regla actual: {bien}/{res['n']} bien clasificadas -> {clases}")

# --- Resumen ---
print("\n=========== RESUMEN ===========")
blancos = [r for (nom, (esp, r)) in resultados.items() if esp == 'BLANCO']
naranja = resultados.get('NARANJA', (None, None))[1]
azul = resultados.get('AZUL', (None, None))[1]

if blancos:
    max_dif_blanco = max(max(abs(r['min']['dif']), abs(r['max']['dif'])) for r in blancos)
    print(f"Blanco: |r%-b%| maximo = {max_dif_blanco:.2f}")
else:
    max_dif_blanco = None
if naranja:
    print(f"Naranja: r%-b% minimo = {naranja['min']['dif']:+.2f}, total max = {naranja['max']['total']}")
if azul:
    print(f"Azul: b%-r% minimo = {-azul['max']['dif']:+.2f}, total max = {azul['max']['total']}")

if max_dif_blanco is not None and naranja and azul:
    peor_color = min(naranja['min']['dif'], -azul['max']['dif'])
    if peor_color > max_dif_blanco:
        sugerido = (max_dif_blanco + peor_color) / 2
        print(f"MARGEN sugerido: {sugerido:.2f} (entre {max_dif_blanco:.2f} del blanco y {peor_color:.2f} del color mas flojo)")
    else:
        print("AVISO: el color mas flojo y el blanco se solapan: el margen no puede separarlos.")
        print("  Revisamos la altura/luz del sensor o añadimos otro criterio.")
if naranja and azul:
    total_colores = max(naranja['max']['total'], azul['max']['total'])
    print(f"Filtro de luz: el total de las lineas llega a {total_colores}; el codigo actual exige < {TOTAL_ACTUAL}.")
    if total_colores >= TOTAL_ACTUAL:
        print("  AVISO: con este filtro perderiamos lecturas de linea; hay que subirlo.")
print("Velocidad de lectura (ms/lectura):",
      ", ".join(f"{nom} {r['ms']:.1f}" for nom, (esp, r) in resultados.items()))
print("Fin.")