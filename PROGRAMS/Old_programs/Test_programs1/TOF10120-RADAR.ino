#include <Servo.h>

Servo miServo;
int angulo = 0;
int direccion = 1; // 1 = Derecha, -1 = Izquierda

void setup() {
  // Inicia la comunicación con la computadora (Monitor Serie)
  Serial.begin(115200); 
  
  // Inicia el puerto físico Serial1 (Pines 0 y 1) a la velocidad del sensor
Serial1.begin(9600); 
  
  miServo.attach(9); // Conectar servo al pin 9
}

void loop() {
  // Mover el servo al ángulo actual
  miServo.write(angulo);
  delay(30); // Esperar a que el motor se posicione

  // Leer la distancia desde el sensor TOF10120
  int distancia = leerDistanciaTOF();

  // Si la lectura es válida, enviar los datos formateados a la PC
  if (distancia > 0) {
    Serial.print(angulo);
    Serial.print(",");
    Serial.println(distancia);
  }

  // Incrementar o decrementar el ángulo para el barrido radar
  angulo += direccion;
  if (angulo >= 180 || angulo <= 0) {
    direccion = -direccion; // Cambiar el sentido del giro
  }
}

// Función para procesar los datos que llegan por Serial1
int leerDistanciaTOF() {
  String datosRecibidos = "";
  
  // El TOF10120 envía texto terminado en 'm' (ejemplo: "125mm\r\n")
  while (Serial1.available()) {
    char c = Serial1.read();
    if (c >= '0' && c <= '9') { // Guardar solo los números
      datosRecibidos += c;
    }
    if (c == 'm') { // Romper el ciclo al llegar a la unidad de medida
      break;
    }
  }
  
  if (datosRecibidos.length() > 0) {
    return datosRecibidos.toInt(); // Devuelve la distancia en milímetros
  }
  return -1; // Retorna -1 si no hubo lectura nueva
}
