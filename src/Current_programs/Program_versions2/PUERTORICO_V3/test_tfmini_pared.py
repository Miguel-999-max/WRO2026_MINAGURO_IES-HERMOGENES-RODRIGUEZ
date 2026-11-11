"""
Prueba del TFmini frontal (UART0, continuo) en las condiciones reales del
robot. Importamos hardware para que todo se inicialice igual que en las
misiones (mismo servo de camara, misma HuskyLens en el bus I2C1).

Hacemos la prueba con el robot alimentado como en pista (bateria de servicios
encendida) y con una pared a unos 15-20 cm de cada lado. Para cada posicion
de la camara imprimimos:
  - lo que devuelve el driver del frontal (cm o None),
  - la ultima medida sin filtrar del frontal (distancia, fuerza),
  - lo que mide el lateral derecho (I2C, a demanda), para comprobar que no
    se interfieren entre si cuando la camara mira a la derecha.
Asi distinguimos:
  - None y medida None  -> el frontal no emite (cable, alimentacion, config)
  - fuerza < 100        -> el sensor responde pero no ve la pared (apunta mal)
  - distancia correcta  -> el sensor esta bien
"""
import time
import hardware

print("Escaneo I2C1:", [hex(a) for a in hardware.i2c1.scan()], "(esperamos 0x10 y 0x50)")

posiciones = (
    ("derecha", hardware.RADAR_FIJO_DERECHA),
    ("izquierda", hardware.RADAR_FIJO_IZQUIERDA),
    ("centro", hardware.Cam_Centro),
)

for nombre, pulso in posiciones:
    hardware.SERVOcam.duty_u16(pulso)
    time.sleep_ms(800)  # esperamos a que el servo llegue
    print("--- Camara a la", nombre)
    validas = 0
    for _ in range(15):
        d = hardware.tfmini_frontal.leer()
        if d is not None:
            validas += 1
        print("frontal:", d, "| sin filtrar:", hardware.tfmini_frontal.ultima_medida,
              "| lateral derecho:", hardware.tfmini_derecho.leer())
        time.sleep_ms(100)
    print("lecturas validas del frontal {}/15".format(validas))

hardware.SERVOcam.duty_u16(hardware.Cam_Centro)
print("Ultimo error del bus del lateral derecho:", hardware.tfmini_derecho.ultimo_error)
